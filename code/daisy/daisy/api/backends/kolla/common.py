# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
/install endpoint for kolla API
"""
import os
import time
import subprocess
import copy
import ConfigParser
import threading
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from daisy import i18n
from daisy.common import exception
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn
from daisy.api.backends.kolla import config as kconfig

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

daisy_conf_mcast_enabled = False
daisy_kolla_path = '/var/lib/daisy/kolla/'
daisy_kolla_ver_path = '/var/lib/daisy/versionfile/kolla/'
KOLLA_STATE = {
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UNINSTALLING': 'uninstalling',
    'UNINSTALL_FAILED': 'uninstall-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed',
}
kolla_file = "/home/kolla_install"


def get_cluster_hosts(req, cluster_id):
    try:
        cluster_hosts = registry.get_cluster_hosts(req.context, cluster_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return cluster_hosts


def get_host_detail(req, host_id):
    try:
        host_detail = registry.get_host_metadata(req.context, host_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return host_detail


def get_roles_detail(req):
    try:
        roles = registry.get_roles_detail(req.context)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return roles


def get_hosts_of_role(req, role_id):
    try:
        hosts = registry.get_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return hosts


def get_role_detail(req, role_id):
    try:
        role = registry.get_role_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return role


def update_role(req, role_id, role_meta):
    try:
        registry.update_role_metadata(req.context, role_id, role_meta)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def update_role_host(req, role_id, role_host):
    try:
        registry.update_role_host_metadata(req.context, role_id, role_host)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def delete_role_hosts(req, role_id):
    try:
        registry.delete_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def _get_cluster_network(cluster_networks, network_type):
    network = [cn for cn in cluster_networks if cn['name'] in network_type]
    if not network or not network[0]:
        msg = "network %s is not exist" % (network_type)
        raise exception.InvalidNetworkConfig(msg)
    else:
        return network[0]


def get_host_interface_by_network(host_detail, network_type):
    host_detail_info = copy.deepcopy(host_detail)
    interface_list = [hi for hi in host_detail_info['interfaces']
                      for assigned_network in hi['assigned_networks']
                      if assigned_network and
                      network_type == assigned_network['name']]
    interface = {}
    if interface_list:
        interface = interface_list[0]
    if not interface:
        msg = "network %s of host %s is not exist" % (
            network_type, host_detail_info['id'])
        raise exception.InvalidNetworkConfig(msg)
    return interface


def get_host_network_ip(req, host_detail, cluster_networks, network_type):
    interface_network_ip = ''
    host_interface = get_host_interface_by_network(host_detail, network_type)
    if host_interface:
        network = _get_cluster_network(cluster_networks, network_type)
        assigned_network = daisy_cmn.get_assigned_network(req,
                                                          host_interface['id'],
                                                          network['id'])
        interface_network_ip = assigned_network['ip']

    if not interface_network_ip:
        msg = "%s network ip of host %s can't be empty" % (
            network_type, host_detail['id'])
        raise exception.InvalidNetworkConfig(msg)
    return interface_network_ip


def get_controller_node_cfg(req, host_detail, cluster_networks):
    deploy_node_cfg = {}
    host_name = host_detail['name'].split('.')[0]
    host_mgt_network = get_host_interface_by_network(host_detail, 'MANAGEMENT')
    host_mgt_macname = host_mgt_network['name']
    host_mgt_ip = get_host_network_ip(req, host_detail,
                                      cluster_networks, 'MANAGEMENT')
    host_pub_network = get_host_interface_by_network(host_detail, 'PUBLICAPI')
    host_pub_macname = host_pub_network['name']
    host_sto_network = get_host_interface_by_network(host_detail, 'STORAGE')
    host_sto_macname = host_sto_network['name']
    try:
        host_hbt_network = get_host_interface_by_network(host_detail,
                                                         'HEARTBEAT')
        host_hbt_macname = host_hbt_network['name']
        deploy_node_cfg.update({'hbt_macname': host_hbt_macname})
    except:
        pass
    if not host_mgt_ip:
        msg = "management ip of host %s can't be empty" % host_detail['id']
        raise exception.InvalidNetworkConfig(msg)
    deploy_node_cfg.update({'mgtip': host_mgt_ip})
    deploy_node_cfg.update({'mgt_macname': host_mgt_macname})
    deploy_node_cfg.update({'pub_macname': host_pub_macname})
    deploy_node_cfg.update({'sto_macname': host_sto_macname})
    deploy_node_cfg.update({'host_name': host_name})
    return deploy_node_cfg


def get_computer_node_cfg(req, host_detail, cluster_networks):
    host_name = host_detail['name'].split('.')[0]
    host_mgt_network = get_host_interface_by_network(host_detail, 'MANAGEMENT')
    host_mgt_ip = get_host_network_ip(req, host_detail,
                                      cluster_networks, 'MANAGEMENT')
    host_dat_network = get_host_interface_by_network(host_detail, 'physnet1')
    host_dat_macname = host_dat_network['name']
    host_ext_network = get_host_interface_by_network(host_detail, 'EXTERNAL')
    host_ext_macname = host_ext_network['name']
    if not host_mgt_ip:
        msg = "management ip of host %s can't be empty" % host_detail['id']
        raise exception.InvalidNetworkConfig(msg)
    deploy_node_cfg = {}
    deploy_node_cfg.update({'mgtip': host_mgt_ip})
    deploy_node_cfg.update({'dat_macname': host_dat_macname})
    deploy_node_cfg.update({'ext_macname': host_ext_macname})
    deploy_node_cfg.update({'host_name': host_name})
    return deploy_node_cfg


def get_roles_and_hosts_list(req, cluster_id):
    roles_id_list = set()
    hosts_id_list = set()
    hosts_list = []
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] != daisy_cmn.kolla_backend_name:
            continue
        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
        if role_hosts:
            for role_host in role_hosts:
                if role_host['host_id'] not in hosts_id_list:
                    host = daisy_cmn.get_host_detail(req, role_host['host_id'])
                    host_ip = get_host_network_ip(
                        req, host, cluster_networks, 'MANAGEMENT')
                    hosts_id_list.add(host['id'])
                    host_cfg = {}
                    host_cfg['id'] = host['id']
                    host_cfg['mgtip'] = host_ip
                    host_cfg['rootpwd'] = host['root_pwd']
                    hosts_list.append(host_cfg)
            roles_id_list.add(role['id'])
    return (roles_id_list, hosts_id_list, hosts_list)


def run_scrip(script, ip=None, password=None, msg=None):
    try:
        _run_scrip(script, ip, password)
    except:
        msg1 = 'Error occurred during running scripts.'
        message = msg1 + msg if msg else msg1
        LOG.error(message)
        raise HTTPForbidden(explanation=message)
    else:
        LOG.info('Running scripts successfully!')


def _run_scrip(script, ip=None, password=None):
    mask_list = []
    repl_list = [("'", "'\\''")]
    script = "\n".join(script)
    _PIPE = subprocess.PIPE
    if ip:
        cmd = ["sshpass", "-p", "%s" % password,
               "ssh", "-o StrictHostKeyChecking=no",
               "%s" % ip, "bash -x"]
    else:
        cmd = ["bash", "-x"]
    environ = os.environ
    environ['LANG'] = 'en_US.UTF8'
    obj = subprocess.Popen(cmd, stdin=_PIPE, stdout=_PIPE, stderr=_PIPE,
                           close_fds=True, shell=False, env=environ)

    script = "function t(){ exit $? ; } \n trap t ERR \n" + script
    out, err = obj.communicate(script)
    masked_out = mask_string(out, mask_list, repl_list)
    masked_err = mask_string(err, mask_list, repl_list)
    if obj.returncode:
        pattern = (r'^ssh\:')
        if re.search(pattern, err):
            LOG.error(_("Network error occured when run script."))
            raise exception.NetworkError(masked_err, stdout=out, stderr=err)
        else:
            msg = ('Failed to run remote script, stdout: %s\nstderr: %s' %
                   (masked_out, masked_err))
            LOG.error(msg)
            raise exception.ScriptRuntimeError(msg, stdout=out, stderr=err)
    return obj.returncode, out


def mask_string(unmasked, mask_list=None, replace_list=None):
    """
    Replaces words from mask_list with MASK in unmasked string.
    If words are needed to be transformed before masking, transformation
    could be describe in replace list. For example [("'","'\\''")]
    replaces all ' characters with '\\''.
    """
    mask_list = mask_list or []
    replace_list = replace_list or []

    masked = unmasked
    for word in sorted(mask_list, lambda x, y: len(y) - len(x)):
        if not word:
            continue
        for before, after in replace_list:
            word = word.replace(before, after)
        masked = masked.replace(word, STR_MASK)
    return masked


def check_and_get_kolla_version(daisy_kolla_pkg_path, file_name=None):
    kolla_version_pkg_file = ""
    if file_name:
        get_kolla_version_pkg = "ls %s| grep %s$" % (daisy_kolla_pkg_path,
                                                     file_name)
    else:
        get_kolla_version_pkg = "ls %s| grep ^kolla.*\.tgz$"\
                                % daisy_kolla_pkg_path
    obj = subprocess.Popen(get_kolla_version_pkg,
                           shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    if stdoutput:
        kolla_version_pkg_name = stdoutput.split('\n')[0]
        kolla_version_pkg_file = daisy_kolla_pkg_path + kolla_version_pkg_name
        chmod_for_kolla_version = 'chmod +x %s' % kolla_version_pkg_file
        daisy_cmn.subprocess_call(chmod_for_kolla_version)
    return kolla_version_pkg_file


def _get_local_ip():
    config = ConfigParser.ConfigParser()
    config.read(daisy_cmn.daisy_conf_file)
    local_ip = config.get("DEFAULT", "daisy_management_ip")
    return local_ip


def _daisy_conf_mcast_flag():
    config = ConfigParser.ConfigParser()
    config.read(daisy_cmn.daisy_conf_file)
    try:
        daisy_conf_mcast_enabled = config.get(
            "multicast", "daisy_conf_mcast_enabled")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        daisy_conf_mcast_enabled = False
    return daisy_conf_mcast_enabled


class MulticastServerTask(object):

    """
    Class for server side multicast.
    """

    def __init__(self, kolla_version_pkg_file, host_list):
        self.kolla_version_pkg_file = kolla_version_pkg_file
        self.hosts_list = host_list

    def run(self):
        try:
            self._run()
            self.res = 0  # successful
        except Exception as e:
            self.res = -1  # failed

    def _run(self):
        cmd = 'jasmines %s %d < %s' % (_get_local_ip(),  # mgt interface
                                       len(self.hosts_list),
                                       # number of clients
                                       self.kolla_version_pkg_file)
        subprocess.check_output(cmd,
                                shell=True,
                                stderr=subprocess.STDOUT)


class MulticastClientTask(object):

    """
    Class for client side multicast.
    """

    def __init__(self, kolla_version_pkg_file, host):
        self.kolla_version_pkg_file = kolla_version_pkg_file
        self.host = host

    def run(self):
        try:
            self._run()
            self.res = 0  # successful
        except Exception as e:
            self.res = -1  # failed

    def _run(self):
        host_ip = self.host['mgtip']

        cmd = 'ssh -o StrictHostKeyChecking=no %s \
              "docker ps"' % host_ip
        docker_result = subprocess.check_output(cmd,
                                                shell=True,
                                                stderr=subprocess.STDOUT)
        if 'registry' in docker_result:

            # stop registry server
            cmd = 'ssh -o StrictHostKeyChecking=no %s \
                  "docker stop registry"' % host_ip
            subprocess.check_output(cmd,
                                    shell=True,
                                    stderr=subprocess.STDOUT)

            cmd = 'ssh -o StrictHostKeyChecking=no %s \
                  "docker rm -f registry"' % host_ip
            subprocess.check_output(cmd,
                                    shell=True,
                                    stderr=subprocess.STDOUT)

        cmd = 'ssh -o StrictHostKeyChecking=no %s \
              "if [ ! -d %s ];then mkdir -p %s;fi" ' % \
              (host_ip, daisy_kolla_ver_path, daisy_kolla_ver_path)
        subprocess.check_output(cmd,
                                shell=True,
                                stderr=subprocess.STDOUT)

        # receive image from daisy server
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
               "jasminec %s %s > %s"' % (host_ip,
                                         host_ip,
                                         _get_local_ip(),
                                         self.kolla_version_pkg_file)
        subprocess.check_output(cmd,
                                shell=True,
                                stderr=subprocess.STDOUT)

        # clean up the old version files
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
               "rm -rf %s/tmp"' % (host_ip,
                                   daisy_kolla_ver_path)

        daisy_cmn.subprocess_call(cmd)

        # install the new version files
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
               "cd %s && tar mzxf %s"' % (host_ip,
                                          daisy_kolla_ver_path,
                                          self.kolla_version_pkg_file)

        subprocess.call(cmd, shell=True)

        registry_file = daisy_kolla_ver_path + "/tmp/registry"

        # start registry server again
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
               "docker run -d -p 4000:5000 --restart=always \
               -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/tmp/registry \
               -v %s:/tmp/registry  --name registry registry:2"'\
                % (host_ip, registry_file)

        subprocess.call(cmd, shell=True)


def version_load_mcast(kolla_version_pkg_file, hosts_list):

    # TODO: impl. daisy_conf_mcast_enabled
    daisy_conf_mcast_enabled = _daisy_conf_mcast_flag()
    if daisy_conf_mcast_enabled != 'True':
        return -1
    mcobjset = []
    mcobj = MulticastServerTask(kolla_version_pkg_file, hosts_list)
    mcobj.t = threading.Thread(target=mcobj.run)
    mcobj.t.start()
    mcobjset.append(mcobj)

    time.sleep(5)  # Wait multicast server ready before start clients

    for host in hosts_list:
        mcobj = MulticastClientTask(kolla_version_pkg_file, host)
        mcobj.t = threading.Thread(target=mcobj.run)
        mcobj.t.start()
        mcobjset.append(mcobj)

    try:
        LOG.info(_("jasmine server as well as all jasmine clients started"))
        for mcobj in mcobjset:
            mcobj.t.join()  # wait server as well as all clients end.
    except:
        LOG.error("jasmine client thread %s failed!" % mcobj.t)

    for mcobj in mcobjset:
        if mcobj.res != 0:
            return -1
    return 0


def version_load(kolla_version_pkg_file, hosts_list):
    get_container_id = "docker ps -a |grep registry |awk -F ' ' '{printf $1}' "
    container_id = subprocess.check_output(get_container_id, shell=True)
    if container_id:
        stop_container = 'docker stop %s' % container_id
        daisy_cmn.subprocess_call(stop_container)
        remove_container = 'docker rm %s' % container_id
        daisy_cmn.subprocess_call(remove_container)

    remove_tmp_registry = 'rm -rf %s/tmp' % daisy_kolla_ver_path
    daisy_cmn.subprocess_call(remove_tmp_registry)

    LOG.info(_('begin to unzip kolla image,please wait.'))
    tar_for_kolla_version = 'cd %s && tar -mzxf %s ' % (daisy_kolla_ver_path,
                                                        kolla_version_pkg_file)
    subprocess.call(tar_for_kolla_version, shell=True)
    LOG.info(_('unzip kolla image successfully!'))

    registry_file = daisy_kolla_ver_path + "/tmp/registry"
    daisy_cmn.subprocess_call(
        'docker run -d -p 4000:5000 --restart=always \
        -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/tmp/registry \
        -v %s:/tmp/registry  --name registry registry:2' % registry_file)
    LOG.info(_('docker server loaded finished.'))


def get_cluster_kolla_config(req, cluster_id):
    LOG.info(_("get kolla config from database..."))
    mgt_ip_list = set()
    kolla_config = {}
    controller_ip_list = []
    computer_ip_list = []
    storage_ip_list = []
    mgt_macname_list = []
    pub_macname_list = []
    dat_macname_list = []
    ext_macname_list = []
    sto_macname_list = []
    hbt_macname_list = []
    vlans_id = {}
    openstack_version = '3.0.0'
    docker_namespace = 'kolla'
    host_name_ip = {}
    host_name_ip_list = []
    version_flag = False
    version_path = daisy_kolla_ver_path
    for parent, dirnames, filenames in os.walk(version_path):
        for filename in filenames:
            if filename.endswith('.version'):
                filename = version_path + filename
                for line in open(filename):
                    if 'tag' in line:
                        version_flag = True
                        kolla_openstack_version = line.strip()
                        openstack_version = kolla_openstack_version.split(
                            "= ")[1]
    if version_flag == False:
        version_path = kolla_file + '/kolla-ansible/ansible/group_vars/'
        for parent, dirnames, filenames in os.walk(version_path):
            for filename in filenames:
                if filename == 'all.yml':
                    filename = version_path + filename
                    for line in open(filename):
                        if 'openstack_release:' in line:
                            version_flag = True
                            kolla_openstack_version = line.strip()
                            openstack_version = kolla_openstack_version.split(
                                ": ")[1].strip('\"')
    LOG.info(_("openstack version is %s"), openstack_version)
    docker_registry_ip = _get_local_ip()
    docker_registry = docker_registry_ip + ':4000'
    LOG.info(_("get cluster network detail..."))
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    for network in cluster_networks:
        vlans_id.update({network.get('network_type'): network.get('vlan_id')})

    all_roles = get_roles_detail(req)
    roles = [role for role in all_roles if
             (role['cluster_id'] == cluster_id and
              role['deployment_backend'] == daisy_cmn.kolla_backend_name)]

    for role in roles:
        if role['name'] == 'CONTROLLER_LB':
            kolla_vip = role['vip']
            role_hosts = get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                host_detail = get_host_detail(
                    req, role_host['host_id'])
                deploy_host_cfg = get_controller_node_cfg(
                    req, host_detail, cluster_networks)
                mgt_ip = deploy_host_cfg['mgtip']
                host_name_ip = {
                    deploy_host_cfg['host_name']: deploy_host_cfg['mgtip']}
                controller_ip_list.append(mgt_ip)
                mgt_macname = deploy_host_cfg['mgt_macname']
                pub_macname = deploy_host_cfg['pub_macname']
                sto_macname = deploy_host_cfg['sto_macname']
                hbt_macname = deploy_host_cfg.get('hbt_macname')
                mgt_macname_list.append(mgt_macname)
                pub_macname_list.append(pub_macname)
                sto_macname_list.append(sto_macname)
                hbt_macname_list.append(hbt_macname)
                if host_name_ip not in host_name_ip_list:
                    host_name_ip_list.append(host_name_ip)
            if len(set(mgt_macname_list)) != 1 or \
                    len(set(pub_macname_list)) != 1 or \
                    len(set(sto_macname_list)) != 1 or \
                    len(set(hbt_macname_list)) > 1:
                msg = (_("hosts interface name of public and \
                         management and storage and heartbeat \
                         must be same!"))
                LOG.error(msg)
                raise HTTPForbidden(msg)
            kolla_config.update({'Version': openstack_version})
            kolla_config.update({'Namespace': docker_namespace})
            kolla_config.update({'VIP': kolla_vip})
            kolla_config.update({'IntIfMac': mgt_macname})
            kolla_config.update({'PubIfMac': pub_macname})
            kolla_config.update({'StoIfMac': sto_macname})
            kolla_config.update({'HbtIfMac': hbt_macname})
            kolla_config.update({'LocalIP': docker_registry})
            kolla_config.update({'Controller_ips': controller_ip_list})
            kolla_config.update({'Network_ips': controller_ip_list})
            #kolla_config.update({'Storage_ips': controller_ip_list})
            kolla_config.update({'vlans_id': vlans_id})
        if role['name'] == 'COMPUTER':
            role_hosts = get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                host_detail = get_host_detail(
                    req, role_host['host_id'])
                deploy_host_cfg = get_computer_node_cfg(
                    req, host_detail, cluster_networks)
                mgt_ip = deploy_host_cfg['mgtip']
                host_name_ip = {
                    deploy_host_cfg['host_name']: deploy_host_cfg['mgtip']}
                computer_ip_list.append(mgt_ip)
                if host_name_ip not in host_name_ip_list:
                    host_name_ip_list.append(host_name_ip)
                dat_macname = deploy_host_cfg['dat_macname']
                dat_macname_list.append(dat_macname)
                ext_macname = deploy_host_cfg['ext_macname']
                ext_macname_list.append(ext_macname)
            if len(set(dat_macname_list)) != 1 or \
                    len(set(ext_macname_list)) != 1:
                msg = (_("computer hosts interface name of dataplane \
                         and external must be same!"))
                LOG.error(msg)
                raise HTTPForbidden(msg)
            kolla_config.update({'Computer_ips': computer_ip_list})
            kolla_config.update({'TulIfMac': dat_macname})
            kolla_config.update({'ExtIfMac': ext_macname})
    mgt_ip_list = set(controller_ip_list + computer_ip_list)
    for ctl_host_ip in controller_ip_list:
        if len(storage_ip_list) > 2:
            break
        storage_ip_list.append(ctl_host_ip)
    for com_host_ip in computer_ip_list:
        if com_host_ip not in controller_ip_list:
            if len(storage_ip_list) > 2:
                break
            storage_ip_list.append(com_host_ip)
    kolla_config.update({'Storage_ips': storage_ip_list})
    return (kolla_config, mgt_ip_list, host_name_ip_list)


def generate_kolla_config_file(req, cluster_id, kolla_config, multicast_flag):
    LOG.info(_("generate kolla config..."))
    if kolla_config:
        kconfig.update_globals_yml(kolla_config, multicast_flag)
        kconfig.update_password_yml()
        kconfig.add_role_to_inventory(kolla_file, kolla_config)
        kconfig.enable_cinder_backend(req,
                                      cluster_id,
                                      kolla_config)
        kconfig.enable_neutron_backend(req, cluster_id, kolla_config)
        kconfig.enable_ceilometer()
