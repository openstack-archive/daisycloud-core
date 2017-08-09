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
import subprocess
import os
import time
from oslo_log import log as logging
from webob.exc import HTTPForbidden
from threading import Thread
import threading
from daisy import i18n
import daisy.api.v1
from daisy.common import exception
from daisy.api.backends.kolla import config
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.kolla.common as kolla_cmn
import daisy.api.common as api_cmn
import daisy.registry.client.v1.api as registry

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE


host_os_status = {
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'FAILED': 'install-failed'
}

kolla_state = kolla_cmn.KOLLA_STATE
daisy_kolla_path = kolla_cmn.daisy_kolla_path
install_kolla_progress = 0.0
install_mutex = threading.Lock()
kolla_file = "/home/kolla_install"
kolla_config_file = "/etc/kolla/globals.yml"
daisy_kolla_ver_path = kolla_cmn.daisy_kolla_ver_path
thread_flag = {}


def update_progress_to_db(req, role_id_list,
                          status, progress=0.0):
    """
    Write install progress and status to db, we use global lock object
    'install_mutex' to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: install status.
    :return:
    """

    global install_mutex
    install_mutex.acquire(True)
    role = {}
    for role_id in role_id_list:
        role['status'] = status
        role['progress'] = progress
        daisy_cmn.update_role(req, role_id, role)
    install_mutex.release()


def update_host_progress_to_db(req, role_id_list, host,
                               status, message, progress=0.0):
    for role_id in role_id_list:
        role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
        for role_host in role_hosts:
            if role_host['host_id'] == host['id']:
                role_host['status'] = status
                role_host['progress'] = progress
                role_host['messages'] = message
                daisy_cmn.update_role_host(req, role_host['id'], role_host)


def update_all_host_progress_to_db(req, role_id_list, host_id_list,
                                   status, message, progress=0.0):
    for host_id in host_id_list:
        for role_id in role_id_list:
            role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
            for role_host in role_hosts:
                if role_host['host_id'] == host_id:
                    role_host['status'] = status
                    role_host['progress'] = progress
                    role_host['messages'] = message
                    daisy_cmn.update_role_host(req, role_host['id'], role_host)


def _ping_hosts_test(ips):
    ping_cmd = 'fping'
    for ip in set(ips):
        ping_cmd = ping_cmd + ' ' + ip
    obj = subprocess.Popen(ping_cmd, shell=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    _returncode = obj.returncode
    if _returncode == 0 or _returncode == 1:
        ping_result = stdoutput.split('\n')
        unreachable_hosts = [result.split()[0] for
                             result in ping_result if
                             result and result.split()[2] != 'alive']
    else:
        msg = "ping failed beaceuse there is invlid ip in %s", ips
        raise exception.InvalidIP(msg)
    return unreachable_hosts


def _check_ping_hosts(ping_ips, max_ping_times):
    if not ping_ips:
        LOG.info(_("no ip got for ping test"))
        return ping_ips
    ping_count = 0
    time_step = 5
    LOG.info(_("begin ping test for %s", ','.join(ping_ips)))
    while True:
        if ping_count == 0:
            ips = _ping_hosts_test(ping_ips)
        else:
            ips = _ping_hosts_test(ips)
        ping_count += 1
        if ips:
            LOG.debug(_("ping host %s for %s times"
                        % (','.join(ips), ping_count)))
            if ping_count >= max_ping_times:
                LOG.info(_("ping host %s timeout for %ss"
                           % (','.join(ips), ping_count*time_step)))
                return ips
            time.sleep(time_step)
        else:
            LOG.info(_("ping host %s success", ','.join(ping_ips)))
            time.sleep(120)
            LOG.info(_("120s after ping host %s success", ','.join(ping_ips)))
            return ips


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
    version_path = kolla_cmn.daisy_kolla_ver_path
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
    docker_registry_ip = kolla_cmn._get_local_ip()
    docker_registry = docker_registry_ip + ':4000'
    LOG.info(_("get cluster network detail..."))
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    for network in cluster_networks:
        vlans_id.update({network.get('network_type'): network.get('vlan_id')})
    all_roles = kolla_cmn.get_roles_detail(req)
    roles = [role for role in all_roles if
             (role['cluster_id'] == cluster_id and
              role['deployment_backend'] == daisy_cmn.kolla_backend_name)]
    for role in roles:
        if role['name'] == 'CONTROLLER_LB':
            kolla_vip = role['vip']
            role_hosts = kolla_cmn.get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                host_detail = kolla_cmn.get_host_detail(
                    req, role_host['host_id'])
                deploy_host_cfg = kolla_cmn.get_controller_node_cfg(
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
            kolla_config.update({'Odl_ips': controller_ip_list[0]})
            #kolla_config.update({'Storage_ips': controller_ip_list})
            kolla_config.update({'vlans_id': vlans_id})
        if role['name'] == 'COMPUTER':
            role_hosts = kolla_cmn.get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                host_detail = kolla_cmn.get_host_detail(
                    req, role_host['host_id'])
                deploy_host_cfg = kolla_cmn.get_computer_node_cfg(
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
        config.update_globals_yml(kolla_config, multicast_flag)
        config.update_password_yml()
        config.add_role_to_inventory(kolla_file, kolla_config)
        config.enable_cinder_backend(req,
                                     cluster_id,
                                     kolla_config)
        config.enable_neutron_backend(req, cluster_id, kolla_config)


def config_nodes_hosts(host_name_ip_list, host_ip):
    config_scripts = []
    hosts_file = "/etc/hosts"
    for name_ip in host_name_ip_list:
        config_scripts.append("linenumber=`grep -n '%s$' %s | "
                              "awk -F ':' '{print $1}'` && "
                              "[ ! -z $linenumber ] && "
                              "sed -i ${linenumber}d %s" %
                              (name_ip.keys()[0],
                               hosts_file, hosts_file))
        config_scripts.append("echo '%s %s' >> %s" % (name_ip.values()[0],
                                                      name_ip.keys()[0],
                                                      hosts_file))
    kolla_cmn.run_scrip(config_scripts, host_ip, "ossdbg1",
                        msg='Failed to config /etc/hosts on %s' % host_ip)


def _calc_progress(log_file):
    progress = 30
    mariadb_result = subprocess.call(
        'cat %s |grep "Running MariaDB"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if mariadb_result == 0:
        progress = 35
    rabbitmq_result = subprocess.call(
        'cat %s |grep "Running RabbitMQ"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if rabbitmq_result == 0:
        progress = 40
    keystone_result = subprocess.call(
        'cat %s |grep "Running Keystone"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if keystone_result == 0:
        progress = 45
    glance_result = subprocess.call(
        'cat %s |grep "Running Glance"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if glance_result == 0:
        progress = 50
    cinder_result = subprocess.call(
        'cat %s |grep "Running Cinder"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cinder_result == 0:
        progress = 55
    nova_bootstrap_result = subprocess.call(
        'cat %s |grep "Running Nova bootstrap"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if nova_bootstrap_result == 0:
        progress = 60
    nova_simple_result = subprocess.call(
        'cat %s |grep "Running nova simple"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if nova_simple_result == 0:
        progress = 65
    netron_bootstrap_result = subprocess.call(
        'cat %s |grep "Running Neutron bootstrap"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if netron_bootstrap_result == 0:
        progress = 70
    neutron_lbaas_result = subprocess.call(
        'cat %s |grep "Running Neutron lbaas"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if neutron_lbaas_result == 0:
        progress = 75
    neutron_vpnaas_result = subprocess.call(
        'cat %s |grep "Running Neutron vpnaas"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if neutron_vpnaas_result == 0:
        progress = 80
    heat_result = subprocess.call(
        'cat %s |grep "Running Heat"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if heat_result == 0:
        progress = 85
    horizon_result = subprocess.call(
        'cat %s |grep "Restart horizon"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if horizon_result == 0:
        progress = 90
    return progress


def _get_hosts_id_by_mgnt_ips(req, cluster_id, ips):
    params = {'cluster_id': cluster_id}
    hosts = registry.get_hosts_detail(req.context, **params)
    hosts_needed = []
    for host in hosts:
        host_info = registry.get_host_metadata(req.context,
                                               host['id'])
        for interface in host_info['interfaces']:
            if interface.get('assigned_networks', None):
                assigned_networks = interface['assigned_networks']
                for assigned_network in assigned_networks:
                    if assigned_network['type'] == 'MANAGEMENT' and\
                            assigned_network['ip'] in ips:
                        hosts_needed.append(host)
    hosts_id_needed = [host_needed['id'] for host_needed in hosts_needed]
    return hosts_id_needed


def configure_external_interface_vlan(req, cluster_id, host_ip):
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    for network in cluster_networks:
        if 'EXTERNAL' in network.get('network_type') and \
                network.get('vlan_id') != None:
            ext_interface = network.get('physnet_name').split("_")[1]
            cmd1 = 'ssh -o StrictHostKeyChecking=no %s \
                    "touch /etc/sysconfig/network-scripts/ifcfg-%s.%s"' \
                    % (host_ip, ext_interface, network.get('vlan_id'))
            cmd2 = 'echo -e "BOOTPROTO=static\nONBOOT=yes\nDEVICE=%s.%s\n'\
                   'VLAN=yes" > /etc/sysconfig/network-scripts/ifcfg-%s.%s' \
                   % (ext_interface, network.get('vlan_id'),
                      ext_interface, network.get('vlan_id'))
            cmd3 = "ssh -o StrictHostKeyChecking=no %s '%s'" % (host_ip, cmd2)

            try:
                exc_cmd1 = subprocess.check_output(cmd1,
                                                   shell=True,
                                                   stderr=subprocess.STDOUT)
                exc_cmd2 = subprocess.check_output(cmd3,
                                                   shell=True,
                                                   stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                message = "config external interface vlan on %s failed!"\
                          % host_ip
                LOG.error(message + e)
                raise exception.InstallException(message)
            else:
                LOG.info(_("config external interface vlan on %s successfully!"
                           % host_ip))


def _thread_bin(req, cluster_id, host, root_passwd, fp, host_name_ip_list,
                host_prepare_file, docker_registry_ip, role_id_list):
    host_ip = host['mgtip']

    config_nodes_hosts(host_name_ip_list, host_ip)
    cmd = 'ssh -o StrictHostKeyChecking=no %s \
          "if [ ! -d %s ];then mkdir %s;fi" ' % \
          (host_ip, host_prepare_file, host_prepare_file)
    daisy_cmn.subprocess_call(cmd, fp)

    # scp daisy4nfv-jasmine.rpm to the same dir of prepare.sh at target host
    cmd = "scp -o ConnectTimeout=10 \
           /var/lib/daisy/tools/daisy4nfv-jasmine*.rpm \
           root@%s:%s" % (host_ip, host_prepare_file)
    daisy_cmn.subprocess_call(cmd, fp)

    # scp registry-server.tar to the same dir of prepare.sh at target host
    cmd = "scp -o ConnectTimeout=10 \
           /var/lib/daisy/tools/registry-server.tar \
           root@%s:%s" % (host_ip, host_prepare_file)
    daisy_cmn.subprocess_call(cmd, fp)

    cmd = "scp -o ConnectTimeout=10 \
           /var/lib/daisy/kolla/prepare.sh \
           root@%s:%s" % (host_ip, host_prepare_file)
    daisy_cmn.subprocess_call(cmd, fp)

    cmd = 'ssh -o StrictHostKeyChecking=no %s \
          chmod u+x %s/prepare.sh' % \
          (host_ip, host_prepare_file)
    daisy_cmn.subprocess_call(cmd, fp)

    try:
        exc_result = subprocess.check_output(
            'ssh -o StrictHostKeyChecking='
            'no %s %s/prepare.sh %s' %
            (host_ip, host_prepare_file, docker_registry_ip),
            shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        message = "exec prepare.sh  in %s failed!", host_ip
        LOG.error(message + e)
        fp.write(e.output.strip())
        raise exception.InstallException(message)
    else:
        LOG.info(_("prepare for %s successfully!", host_ip))
        fp.write(exc_result)
        message = "Preparing for installation successful!"
        update_host_progress_to_db(req, role_id_list, host,
                                   kolla_state['INSTALLING'],
                                   message, 10)


def thread_bin(req, cluster_id, host, root_passwd, fp, host_name_ip_list,
               host_prepare_file, docker_registry_ip, role_id_list):
    try:
        _thread_bin(req, cluster_id, host, root_passwd, fp, host_name_ip_list,
                    host_prepare_file, docker_registry_ip, role_id_list)
    except Exception as e:
        message = "Prepare for installation failed!"
        LOG.error(message, e)
        update_host_progress_to_db(req, role_id_list, host,
                                   kolla_state['INSTALL_FAILED'],
                                   message)
        thread_flag['flag'] = False


class KOLLAInstallTask(Thread):
    """
    Class for kolla install openstack.
    """
    """ Definition for install states."""
    INSTALL_STATES = {
        'INIT': 'init',
        'INSTALLING': 'installing',
        'ACTIVE': 'active',
        'FAILED': 'install-failed'
    }

    def __init__(self, req, cluster_id):
        super(KOLLAInstallTask, self).__init__()
        self.req = req
        self.cluster_id = cluster_id
        self.progress = 0
        self.state = KOLLAInstallTask.INSTALL_STATES['INIT']
        self.message = ""
        self.kolla_config_file = ''
        self.mgt_ip_list = ''
        self.install_log_fp = None
        self.last_line_num = 0
        self.ping_times = 36
        self.precheck_file = "/var/log/daisy/kolla_%s_precheck.log" %\
                             self.cluster_id
        self.log_file = "/var/log/daisy/kolla_%s_deploy.log" % self.cluster_id
        self.host_prepare_file = "/home/kolla"
        self.kolla_file = "/home/kolla_install"

    def run(self):
        try:
            self._run()
        except (exception.InstallException,
                exception.NotFound,
                exception.InstallTimeoutException,
                exception.SubprocessCmdFailed) as e:
            (role_id_list, host_id_list, hosts_list) = \
                kolla_cmn.get_roles_and_hosts_list(self.req, self.cluster_id)
            update_all_host_progress_to_db(self.req, role_id_list,
                                           host_id_list,
                                           kolla_state['INSTALL_FAILED'],
                                           self.message)
            LOG.error(("kolla deploy openstack failed!"))
        else:
            LOG.info(_("install Kolla for cluster %s successfully."
                       % self.cluster_id))
        finally:
            if daisy_cmn.in_cluster_list(self.cluster_id):
                LOG.info("KOLLA install clear install global variables")
                daisy_cmn.cluster_list_delete(self.cluster_id)

    def _run(self):
        cluster_data = registry.get_cluster_metadata(self.req.context,
                                                     self.cluster_id)

        (kolla_config, self.mgt_ip_list, host_name_ip_list) = \
            get_cluster_kolla_config(self.req, self.cluster_id)
        if not self.mgt_ip_list:
            msg = _("there is no host in cluster %s") % self.cluster_id
            raise exception.ThreadBinException(msg)
        unreached_hosts = _check_ping_hosts(self.mgt_ip_list, self.ping_times)
        if unreached_hosts:
            self.message = "hosts %s ping failed" % unreached_hosts
            LOG.error(self.message)
            raise exception.InstallException(self.message)

        root_passwd = 'ossdbg1'
        threads_net = []
        for mgnt_ip in self.mgt_ip_list:
            check_hosts_id = _get_hosts_id_by_mgnt_ips(self.req,
                                                       self.cluster_id,
                                                       mgnt_ip.split(","))
            is_ssh_host = daisy_cmn._judge_ssh_host(self.req,
                                                    check_hosts_id[0])
            if not is_ssh_host:
                cmd = '/var/lib/daisy/trustme.sh %s %s' % \
                      (mgnt_ip, root_passwd)
                daisy_cmn.subprocess_call(cmd)
                LOG.info(_("Begin to config network on %s" % mgnt_ip))
                ssh_host_info = {'ip': mgnt_ip, 'root_pwd': root_passwd}
                configure_external_interface_vlan(self.req,
                                                  self.cluster_id,
                                                  mgnt_ip)

                t_net = threading.Thread(target=api_cmn.config_network,
                                         args=(ssh_host_info, 'kolla'))
                t_net.setDaemon(True)
                t_net.start()
                threads_net.append(t_net)
        try:
            LOG.info(_("config network threads"
                       " have started, please waiting...."))
            for t_net in threads_net:
                t_net.join()
        except:
            LOG.error("join config network "
                      "thread %s failed!", t_net)

        time.sleep(20)

        (role_id_list, host_id_list, hosts_list) = \
            kolla_cmn.get_roles_and_hosts_list(self.req, self.cluster_id)
        self.message = "Begin install"
        update_all_host_progress_to_db(self.req, role_id_list,
                                       host_id_list, kolla_state['INSTALLING'],
                                       self.message, 5)

        docker_registry_ip = kolla_cmn._get_local_ip()
        with open(self.precheck_file, "w+") as fp:
            threads = []
            for host in hosts_list:
                t = threading.Thread(target=thread_bin,
                                     args=(self.req, self.cluster_id, host,
                                           root_passwd, fp, host_name_ip_list,
                                           self.host_prepare_file,
                                           docker_registry_ip, role_id_list))
                t.setDaemon(True)
                t.start()
                threads.append(t)
            try:
                LOG.info(_("prepare kolla installation threads have started, "
                           "please waiting...."))
                for t in threads:
                    t.join()
            except:
                LOG.error("join kolla prepare installation "
                          "thread %s failed!", t)

            # check, load and multicast version
            if cluster_data.get('tecs_version_id', None):
                vid = cluster_data['tecs_version_id']
                version_info = registry.get_version_metadata(self.req.context,
                                                             vid)
                kolla_version_pkg_file = \
                    kolla_cmn.check_and_get_kolla_version(daisy_kolla_ver_path,
                                                          version_info['name'])
            else:
                kolla_version_pkg_file =\
                    kolla_cmn.check_and_get_kolla_version(daisy_kolla_ver_path)
            if not kolla_version_pkg_file:
                self.state = kolla_state['INSTALL_FAILED']
                self.message =\
                    "kolla version file not found in %s" % daisy_kolla_ver_path
                raise exception.NotFound(message=self.message)

            try:
                LOG.info(_("load kolla registry..."))
                kolla_cmn.version_load(kolla_version_pkg_file, hosts_list)
            except exception.SubprocessCmdFailed as e:
                self.message = "load kolla registry failed!"
                LOG.error(self.message)
                raise exception.InstallException(self.message)

            res = kolla_cmn.version_load_mcast(kolla_version_pkg_file,
                                               hosts_list)
            # Multicast done
            update_all_host_progress_to_db(self.req, role_id_list,
                                           host_id_list,
                                           kolla_state['INSTALLING'],
                                           self.message, 15)

            # always call generate_kolla_config_file after version_load()
            # TODO: re-config docker registry server based upon return value of
            # kolla_cmn.version_load_mcast
            LOG.info(_("begin to generate kolla config file ..."))
            (kolla_config, self.mgt_ip_list, host_name_ip_list) = \
                get_cluster_kolla_config(self.req, self.cluster_id)
            generate_kolla_config_file(self.req, self.cluster_id,
                                       kolla_config, res)
            LOG.info(_("generate kolla config file in /etc/kolla/ dir..."))

            if thread_flag.get('flag', None) and thread_flag['flag'] == False:
                self.message = "prepare deploy nodes failed!"
                LOG.error(self.message)
                raise exception.InstallException(self.message)

            LOG.info(_("kolla-ansible precheck..."))
            cmd = subprocess.Popen(
                'cd %s/kolla-ansible && ./tools/kolla-ansible prechecks '
                ' -i %s/kolla-ansible/ansible/inventory/multinode -vvv' %
                (self.kolla_file, self.kolla_file),
                shell=True, stdout=fp, stderr=fp)
            execute_times = 0
            while True:
                time.sleep(5)
                return_code = cmd.poll()
                if return_code == 0:
                    break
                elif return_code == 1:
                    self.message = "kolla-ansible preckecks failed!"
                    LOG.error(self.message)
                    raise exception.InstallException(self.message)
                else:
                    if execute_times >= 1440:
                        self.message = "kolla-ansible preckecks timeout"
                        LOG.error(self.message)
                        raise exception.InstallTimeoutException(
                            cluster_id=self.cluster_id)
                execute_times += 1

            self.message = "kolla-ansible preckecks successfully(%d)!" % \
                (return_code)
            self.progress = 20
            update_all_host_progress_to_db(self.req, role_id_list,
                                           host_id_list,
                                           kolla_state['INSTALLING'],
                                           self.message, self.progress)
        with open(self.log_file, "w+") as fp:
            LOG.info(_("kolla-ansible begin to deploy openstack ..."))
            cmd = subprocess.Popen(
                'cd %s/kolla-ansible && ./tools/kolla-ansible deploy -i '
                '%s/kolla-ansible/ansible/inventory/multinode' %
                (self.kolla_file, self.kolla_file),
                shell=True, stdout=fp, stderr=fp)
            self.message = "begin deploy openstack"
            self.progress = 25
            execute_times = 0
            while True:
                time.sleep(5)
                return_code = cmd.poll()
                if self.progress == 95:
                    break
                elif return_code == 0:
                    self.progress = 95
                elif return_code == 1:
                    self.message = "KOLLA deploy openstack failed"
                    LOG.error(self.message)
                    raise exception.InstallException(self.message)
                else:
                    self.progress = _calc_progress(self.log_file)
                if execute_times >= 1440:
                    self.message = "KOLLA deploy openstack timeout"
                    LOG.error(self.message)
                    raise exception.InstallTimeoutException(
                        cluster_id=self.cluster_id)
                else:
                    update_all_host_progress_to_db(self.req, role_id_list,
                                                   host_id_list,
                                                   kolla_state['INSTALLING'],
                                                   self.message, self.progress)
                execute_times += 1

            try:
                LOG.info(_("kolla-ansible post-deploy for each node..."))
                exc_result = subprocess.check_output(
                    'cd %s/kolla-ansible && ./tools/kolla-ansible post-deploy '
                    ' -i %s/kolla-ansible/ansible/inventory/multinode' %
                    (self.kolla_file, self.kolla_file),
                    shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                self.message = "kolla-ansible post-deploy failed!"
                LOG.error(self.message)
                fp.write(e.output.strip())
                raise exception.InstallException(self.message)
            else:
                LOG.info(_("kolla-ansible post-deploy successfully!"))
                fp.write(exc_result)
                self.message = "post-deploy successfully!"
                update_all_host_progress_to_db(self.req, role_id_list,
                                               host_id_list,
                                               kolla_state['ACTIVE'],
                                               self.message, 100)
                update_progress_to_db(self.req, role_id_list,
                                      kolla_state['ACTIVE'], 100)
                for host_id in host_id_list:
                    daisy_cmn.update_db_host_status(
                        self.req, host_id,
                        {'tecs_version_id': cluster_data['tecs_version_id'],
                         'tecs_patch_id': ''})
