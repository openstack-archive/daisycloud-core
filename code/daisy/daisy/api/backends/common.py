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
/install endpoint for tecs API
"""
import os
import subprocess
import time
import re
import commands
import socket
import netaddr
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPNotFound
from webob.exc import HTTPForbidden
from daisy import i18n

from daisy.common import utils
from daisy.common import exception
import daisy.registry.client.v1.api as registry
from daisy.api.backends.osinstall import osdriver
import ConfigParser
import copy
import fcntl

STR_MASK = '*' * 8
LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

daisy_conf_file = '/home/daisy_install/daisy.conf'
daisy_path = '/var/lib/daisy/'
tecs_backend_name = "tecs"
zenic_backend_name = "zenic"
proton_backend_name = "proton"
kolla_backend_name = "kolla"
os_install_start_time = 0.0
cluster_list_file = "/var/lib/daisy/cluster-list"
BACKEND_STATE = {
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UNINSTALLING': 'uninstalling',
    'UNINSTALL_FAILED': 'uninstall-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed',
}


# This is used for mapping daisy service id to systemctl service name
# Only used by non containerized deploy tools such as clush/puppet.

service_map = {
    'lb': 'haproxy',
    'mongodb': 'mongod',
    'ha': '',
    'mariadb': 'mariadb',
    'amqp': 'rabbitmq-server',
    'ceilometer-api': 'openstack-ceilometer-api',
    'ceilometer-collector': 'openstack-ceilometer-collector,\
                                openstack-ceilometer-mend',
    'ceilometer-central': 'openstack-ceilometer-central',
    'ceilometer-notification': 'openstack-ceilometer-notification',
    'ceilometer-alarm': 'openstack-ceilometer-alarm-evaluator,\
                        openstack-ceilometer-alarm-notifier',
    'heat-api': 'openstack-heat-api',
    'heat-api-cfn': 'openstack-heat-api-cfn',
    'heat-engine': 'openstack-heat-engine',
    'ironic': 'openstack-ironic-api,openstack-ironic-conductor',
    'horizon': 'httpd,opencos-alarmmanager',
    'keystone': 'openstack-keystone',
    'glance': 'openstack-glance-api,openstack-glance-registry',
    'cinder-volume': 'openstack-cinder-volume',
    'cinder-scheduler': 'openstack-cinder-scheduler',
    'cinder-api': 'openstack-cinder-api',
    'neutron-metadata': 'neutron-metadata-agent',
    'neutron-lbaas': 'neutron-lbaas-agent',
    'neutron-dhcp': 'neutron-dhcp-agent',
    'neutron-server': 'neutron-server',
    'neutron-l3': 'neutron-l3-agent',
    'compute': 'openstack-nova-compute',
    'nova-cert': 'openstack-nova-cert',
    'nova-sched': 'openstack-nova-scheduler',
    'nova-vncproxy': 'openstack-nova-novncproxy,openstack-nova-consoleauth',
    'nova-conductor': 'openstack-nova-conductor',
    'nova-api': 'openstack-nova-api',
    'nova-cells': 'openstack-nova-cells',
    'camellia-api': 'camellia-api'
}
config = ConfigParser.ConfigParser()
config.read(daisy_conf_file)
try:
    OS_INSTALL_TYPE = config.get("OS", "os_install_type")
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    OS_INSTALL_TYPE = 'pxe'

_OS_HANDLE = None


def get_os_handle():
    global _OS_HANDLE
    if _OS_HANDLE is not None:
        return _OS_HANDLE

    _OS_HANDLE = osdriver.load_install_os_driver(OS_INSTALL_TYPE)
    return _OS_HANDLE


def list_2_file(f, cluster_list):
    f.seek(0)
    for cluster_id in cluster_list:
        f.write(cluster_id+"\n")


def file_2_list(f, cluster_list):
    f.seek(0)
    cluster_ids = f.readlines()
    for cluster_id in cluster_ids:
        cluster_list.append(cluster_id.strip("\n"))


def cluster_list_add(cluster_id):
    cluster_list = []
    with open(cluster_list_file, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        file_2_list(f, cluster_list)
        cluster_list.append(cluster_id)
        f.seek(0)
        f.truncate()
        list_2_file(f, cluster_list)
        fcntl.flock(f, fcntl.LOCK_UN)


def cluster_list_delete(cluster_id):
    cluster_list = []
    with open(cluster_list_file, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        file_2_list(f, cluster_list)
        cluster_list.remove(cluster_id)
        f.seek(0)
        f.truncate()
        list_2_file(f, cluster_list)
        fcntl.flock(f, fcntl.LOCK_UN)


def in_cluster_list(cluster_id):
    cluster_list = []
    with open(cluster_list_file, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        file_2_list(f, cluster_list)
        fcntl.flock(f, fcntl.LOCK_UN)
    return cluster_id in cluster_list


def cluster_list_get():
    cluster_list = []
    with open(cluster_list_file, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        file_2_list(f, cluster_list)
        fcntl.flock(f, fcntl.LOCK_UN)
    return cluster_list


def subprocess_call(command, file=None):
    try:
        subprocess.check_output(command,
                                shell=True,
                                stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        if file:
            file.write(e.output.strip())
        msg = "execute '%s' failed by subprocess call, "\
              "error message: %s." % (command, e.output.strip())
        raise exception.SubprocessCmdFailed(message=msg)


def check_file_whether_exist(file_name):
    try:
        subprocess.check_output("test -f %s" % file_name, shell=True,
                                stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            msg = "%s does not exist" % file_name
            LOG.info(msg)
            return False
        else:
            msg = "command execute failed"
            LOG.error(msg)
            exception.SubprocessCmdFailed(message=msg)
    else:
        return True


def get_host_detail(req, host_id):
    try:
        host_detail = registry.get_host_metadata(req.context, host_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    except exception.NotFound:
        msg = "Host with identifier %s not found" % host_id
        LOG.debug(msg)
        raise HTTPNotFound(msg)
    return host_detail


def get_roles_detail(req):
    try:
        roles = registry.get_roles_detail(req.context)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return roles


def get_cluster_roles_detail(req, cluster_id):
    try:
        params = {'cluster_id': cluster_id}
        roles = registry.get_roles_detail(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return roles


def get_cluster_hosts_list(req, cluster_id):
    try:
        params = {'cluster_id': cluster_id}
        hosts = registry.get_cluster_hosts(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return hosts


def get_hosts_of_role(req, role_id):
    try:
        hosts = registry.get_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return hosts


def get_roles_of_host(req, host_id):
    try:
        roles = registry.get_host_roles_by_host_id(req.context, host_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return roles


def get_role_detail(req, role_id):
    try:
        role = registry.get_role_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return role


def get_cluster_configs_list(req, cluster_id):
    roles = get_cluster_roles_detail(req, cluster_id)
    config_set_list = [role['config_set_id'] for role in roles]
    cluster_configs_list = []
    for config_set_id in config_set_list:
        config_set_metadata = registry.get_config_set_metadata(req.context,
                                                               config_set_id)
        if config_set_metadata.get('config', None):
            cluster_configs_list.extend(config_set_metadata['config'])
    return cluster_configs_list


def update_role(req, role_id, role_meta):
    try:
        registry.update_role_metadata(req.context, role_id, role_meta)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def update_role_host(req, host_role_id, role_host):
    try:
        registry.update_role_host_metadata(
            req.context, host_role_id, role_host)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def get_role_hosts(req, role_id):
    try:
        role_hosts = registry.get_role_host_metadata(
            req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return role_hosts


def delete_role_hosts(req, role_id):
    try:
        registry.delete_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def set_role_status_and_progress(req, cluster_id, opera, status,
                                 backend_name='tecs'):
    """
    set information in role of some backend.
    :status:key in host_role tables, such as:
        {'messages':'Waiting','progress': '0'}
    """
    roles = get_cluster_roles_detail(req, cluster_id)
    for role in roles:
        if role.get('deployment_backend') == backend_name:
            role_hosts = get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                if (opera == 'upgrade' and role_host['status'] in ['active']) \
                        or (opera == 'install' and role_host['status'] not in
                            ['active', 'updating', 'update-failed']):
                    update_role_host(req, role_host['id'], status)


def get_cluster_networks_detail(req, cluster_id):
    try:
        networks = registry.get_networks_detail(req.context, cluster_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return networks


def get_assigned_network(req, host_interface_id, network_id):
    try:
        assigned_network = registry.get_assigned_network(
            req.context, host_interface_id, network_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return assigned_network


def _ping_hosts_test(ips):
    ping_cmd = 'fping'
    for ip in set(ips):
        ping_cmd = ping_cmd + ' ' + ip
    obj = subprocess.Popen(
        ping_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    _returncode = obj.returncode
    if _returncode == 0 or _returncode == 1:
        ping_result = stdoutput.split('\n')
        unreachable_hosts = [result.split(
        )[0] for result in ping_result if result and
            result.split()[2] != 'alive']
    else:
        msg = "ping failed beaceuse there is invlid ip in %s" % ips
        raise exception.InvalidIP(msg)
    return unreachable_hosts


def check_ping_hosts(ping_ips, max_ping_times):
    if not ping_ips:
        LOG.info(_("no ip got for ping test"))
        return ping_ips
    ping_count = 0
    time_step = 5
    LOG.info(_("begin ping test for %s" % ','.join(ping_ips)))
    while True:
        if ping_count == 0:
            ips = _ping_hosts_test(ping_ips)
        else:
            ips = _ping_hosts_test(ips)

        ping_count += 1
        if ips:
            LOG.debug(
                _("ping host %s for %s times" % (','.join(ips), ping_count)))
            if ping_count >= max_ping_times:
                LOG.info(_("ping host %s timeout for %ss" %
                           (','.join(ips), ping_count * time_step)))
                return ips
            time.sleep(time_step)
        else:
            LOG.info(_("ping %s successfully" % ','.join(ping_ips)))
            return ips


def _ping_reachable_to_unreachable_host_test(ip, max_ping_times):
    ping_cmd = 'fping'
    ping_cmd = ping_cmd + ' ' + ip
    ping_count = 0
    time_step = 5
    while True:
        obj = subprocess.Popen(
            ping_cmd, shell=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        (stdoutput, erroutput) = obj.communicate()
        _returncode = obj.returncode
        if _returncode != 0:
            return True
        ping_count += 1
        if ping_count >= max_ping_times:
            LOG.info(
                _("ping host %s timeout for %ss"
                    % (ip, ping_count * time_step)))
            return False
        time.sleep(time_step)
    return False


def _ping_unreachable_to_reachable_host_test(ip, max_ping_times):
    ping_count = 0
    time_step = 5
    ping_cmd = 'fping'
    ping_cmd = ping_cmd + ' ' + ip
    while True:
        obj = subprocess.Popen(
            ping_cmd, shell=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        (stdoutput, erroutput) = obj.communicate()
        _returncode = obj.returncode
        if _returncode == 0:
            return True
        ping_count += 1
        if ping_count >= max_ping_times:
            LOG.info(
                _("ping host %s timeout for %ss"
                    % (ip, ping_count * time_step)))
            return False
        time.sleep(time_step)
    return False


def check_reboot_ping(ip):
    # ha host reboot may spend 20 min,so timeout time is 30min
    stop_max_ping_times = 360
    start_max_ping_times = 60
    _ping_reachable_to_unreachable_host_test(ip, stop_max_ping_times)
    _ping_unreachable_to_reachable_host_test(ip, start_max_ping_times)
    time.sleep(5)


def cidr_to_netmask(cidr):
    ip_netmask = cidr.split('/')
    if len(ip_netmask) != 2 or not ip_netmask[1]:
        raise exception.InvalidNetworkConfig("cidr is not valid")

    cidr_end = ip_netmask[1]
    mask = ~(2 ** (32 - int(cidr_end)) - 1)
    inter_ip = lambda x: '.'.join(
        [str(x / (256 ** i) % 256) for i in range(3, -1, -1)])
    netmask = inter_ip(mask)
    return netmask


def get_rpm_package_by_name(path, rpm_name):
    cmd = "ls %s | grep ^%s.*\.rpm" % (path, rpm_name)
    try:
        rpm_name = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT).split('\n')[0]
    except subprocess.CalledProcessError:
        msg = _("Get rpm %s failed in %s!" % (rpm_name, path))
        raise exception.SubprocessCmdFailed(message=msg)
    return rpm_name


def remote_remove_rpm(rpm_name, dest_ip):
    remove_cmd = 'clush -S -w %s "rpm -q %s && rpm -e %s"' % (dest_ip,
                                                              rpm_name,
                                                              rpm_name)
    subprocess.call(remove_cmd,
                    shell=True,
                    stdout=open('/dev/null', 'w'),
                    stderr=subprocess.STDOUT)


def remote_install_rpm(rpm_name, rpm_src_path, rpm_dest_path, dest_ips):
    rpm_package = get_rpm_package_by_name(rpm_src_path, rpm_name)
    for dest_ip in dest_ips:
        scp_rpm = "scp -o ConnectTimeout=10 %s/%s root@%s:%s" \
                  % (rpm_src_path, rpm_package, dest_ip, rpm_dest_path)
        subprocess_call(scp_rpm)

        remote_remove_rpm(rpm_name, dest_ip)

        install_cmd = 'clush -S -w %s "rpm -i %s/%s"' % (dest_ip,
                                                         rpm_dest_path,
                                                         rpm_package)
        subprocess_call(install_cmd)


def remote_upgrade_rpm(rpm_name, rpm_src_path, rpm_dest_path, dest_ip):
    rpm_package = get_rpm_package_by_name(rpm_src_path, rpm_name)
    scp_rpm = "scp -o ConnectTimeout=10 %s/%s root@%s:%s" \
              % (rpm_src_path, rpm_package, dest_ip, rpm_dest_path)
    subprocess_call(scp_rpm)

    upgrade_cmd = 'clush -S -w %s "rpm -U %s/%s"' % (dest_ip,
                                                     rpm_dest_path,
                                                     rpm_package)
    subprocess.call(upgrade_cmd,
                    shell=True,
                    stdout=open('/dev/null', 'w'),
                    stderr=subprocess.STDOUT)


def trust_me(host_ips, root_passwd):
    for host_ip in host_ips:
        count = 0
        try_times = 10
        while count < try_times:
            try:
                trust_me_cmd = "/var/lib/daisy/tecs/trustme.sh\
                        %s %s" % (host_ip, root_passwd)
                subprocess_call(trust_me_cmd)
            except:
                count += 1
                LOG.info("Trying to trust '%s' for %s times" %
                         (host_ip, count))
                time.sleep(2)
                if count >= try_times:
                    message = "Setup trust for '%s' failed,"\
                        "see '/var/log/trustme.log' please" % (host_ip)
                    raise exception.TrustMeFailed(message=message)
            else:
                message = "Setup trust to '%s' successfully" % (host_ip)
                LOG.info(message)
                break


def calc_host_iqn(min_mac):
    cmd = "echo -n %s |openssl md5" % min_mac
    obj = subprocess.Popen(cmd,
                           shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    iqn = ""
    if stdoutput:
        get_uuid = stdoutput.split('=')[1]
        iqn = "iqn.opencos.rh:" + get_uuid.strip()
    return iqn


def _get_cluster_network(cluster_networks, network_name):
    network = [cn for cn in cluster_networks if cn['name'] == network_name]
    if not network or not network[0]:
        msg = "network %s is not exist" % (network_name)
        raise exception.InvalidNetworkConfig(msg)
    else:
        return network[0]


def get_host_interface_by_network(host_detail, network_name):
    host_detail_info = copy.deepcopy(host_detail)
    interface_list = [hi for hi in host_detail_info['interfaces']
                      for assigned_network in hi['assigned_networks']
                      if assigned_network and
                      network_name == assigned_network['name']]
    interface = {}
    if interface_list:
        interface = interface_list[0]

    if not interface and 'MANAGEMENT' == network_name:
        msg = "network %s of host %s is not exist" % (
            network_name, host_detail_info['id'])
        raise exception.InvalidNetworkConfig(msg)

    return interface


def get_host_network_ip(req, host_detail, cluster_networks, network_name):
    interface_network_ip = ''
    for host_interface in host_detail.get('interfaces', []):
        for assigned_network in host_interface.get('assigned_networks', []):
            if assigned_network.get('name') == network_name:
                return assigned_network.get('ip')

    if not interface_network_ip and 'MANAGEMENT' == network_name:
        msg = "%s network ip of host %s can't be empty" % (
            network_name, host_detail['id'])
        raise exception.InvalidNetworkConfig(msg)
    return interface_network_ip


def get_service_disk_list(req, params):
    try:
        service_disks = registry.list_service_disk_metadata(
            req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return service_disks


def sort_interfaces_by_pci(networks, host_detail):
    """
    Sort interfaces by pci segment, if interface type is bond,
    user the pci of first memeber nic.This function is fix bug for
    the name length of ovs virtual port, because if the name length large than
    15 characters, the port will create failed.
    :param interfaces: interfaces info of the host
    :return:
    """
    interfaces = eval(host_detail.get('interfaces', None)) \
        if isinstance(host_detail, unicode) else \
        host_detail.get('interfaces', None)
    if not interfaces:
        LOG.info("This host has no interfaces info.")
        return host_detail

    tmp_interfaces = copy.deepcopy(interfaces)

    slaves_name_list = []
    for interface in tmp_interfaces:
        if interface.get('type', None) == "bond" and\
                interface.get('slave1', None) and\
                interface.get('slave2', None):
            slaves_name_list.append(interface['slave1'])
            slaves_name_list.append(interface['slave2'])

    for interface in interfaces:
        if interface.get('name') not in slaves_name_list:
            vlan_id_len_list = [len(str(network['vlan_id']))
                                for assigned_network in interface.get(
                                    'assigned_networks', [])
                                for network in networks
                                if assigned_network.get('name') ==
                                network.get('name') and network.get('vlan_id')]
            max_vlan_id_len = max(vlan_id_len_list) if vlan_id_len_list else 0
            interface_name_len = len(interface['name'])
            redundant_bit = interface_name_len + max_vlan_id_len - 14
            interface['name'] = interface['name'][
                redundant_bit:] if redundant_bit > 0 else interface['name']
    return host_detail


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


def run_scrip(script, ip=None, password=None, msg=None):
    try:
        _run_scrip(script, ip, password)
    except:
        msg1 = 'Error occurred during running scripts.'
        message = msg1 + msg if msg else msg1
        LOG.error(message)
        raise HTTPForbidden(explanation=message)


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


def get_ctl_ha_nodes_min_mac(req, cluster_id):
    '''
    ctl_ha_nodes_min_mac = {'host_name1':'min_mac1', ...}
    '''
    ctl_ha_nodes_min_mac = {}
    roles = get_cluster_roles_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] != tecs_backend_name:
            continue
        if role['name'] == "CONTROLLER_HA":
            role_hosts = get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                host_detail = get_host_detail(req,
                                              role_host['host_id'])
                host_name = host_detail['name']
                min_mac = utils.get_host_min_mac(host_detail['interfaces'])
                ctl_ha_nodes_min_mac[host_name] = min_mac
    return ctl_ha_nodes_min_mac


def update_db_host_status(req, host_id, host_status, version_id=None,
                          version_patch_id=None):
    """
    Update host status and intallation progress to db.
    :return:
    """
    try:
        host_meta = {}
        if host_status.get('os_progress', None) is not None:
            host_meta['os_progress'] = host_status['os_progress']
        if host_status.get('os_status', None):
            host_meta['os_status'] = host_status['os_status']
        if host_status.get('messages', None):
            host_meta['messages'] = host_status['messages']
        if host_status.get('tecs_version_id', None):
            host_meta['tecs_version_id'] = host_status['tecs_version_id']
        if version_id:
            host_meta['os_version_id'] = version_id
        if version_patch_id:
            host_meta['version_patch_id'] = version_patch_id
        hostinfo = registry.update_host_metadata(req.context,
                                                 host_id,
                                                 host_meta)
        return hostinfo
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def get_local_deployment_ip(tecs_deployment_ips):
    (status, output) = commands.getstatusoutput('ifconfig')
    netcard_pattern = re.compile('\S*: ')
    ip_str = '([0-9]{1,3}\.){3}[0-9]{1,3}'
    pattern = re.compile(ip_str)
    nic_ip = {}
    for netcard in re.finditer(netcard_pattern, str(output)):
        nic_name = netcard.group().split(': ')[0]
        if nic_name == "lo":
            continue
        ifconfig_nic_cmd = "ifconfig %s" % nic_name
        (status, output) = commands.getstatusoutput(ifconfig_nic_cmd)
        if status:
            continue
        ip = pattern.search(str(output))
        if ip and ip.group() != "127.0.0.1":
            nic_ip[nic_name] = ip.group()

    deployment_ip = ''
    for nic in nic_ip.keys():
        if nic_ip[nic] in tecs_deployment_ips:
            deployment_ip = nic_ip[nic]
            break
    return deployment_ip


def whether_insl_backends(req, host_ids_failed):
    # after os installed, host_ids_failed are ids of host installed failed
    # if host installed failed is CONTROLLER_LB host or CONTROLLER_HA host
    # continue_installing_backends is false ,stop installing backends
    continue_installing_backends = True
    if not host_ids_failed:
        return continue_installing_backends
    for host_id_failed in host_ids_failed:
        host_failed_info = get_host_detail(req, host_id_failed)
        roles_of_host = host_failed_info['role']
        if "CONTROLLER_HA" in roles_of_host or "CONTROLLER_LB" \
                in roles_of_host:
            continue_installing_backends = False
            return continue_installing_backends
    return continue_installing_backends


def whether_insl_tecs_aft_ping(unreached_hosts, ha_ip_set,
                               lb_ip_set):
    continue_installing_tecs = True
    ha_ip_set = set(ha_ip_set)
    lb_ip_set = set(lb_ip_set)
    controller_ips = (ha_ip_set | lb_ip_set)
    if not unreached_hosts:
        return continue_installing_tecs
    for unreached_host in unreached_hosts:
        if unreached_host in controller_ips:
            continue_installing_tecs = False
            return continue_installing_tecs
    return continue_installing_tecs


def get_management_ip(host_detail, is_throw_exception=True):
    host_management_ip = ''
    for interface in host_detail['interfaces']:
        if ('assigned_networks' in interface and
                interface['assigned_networks']):
            for as_network in interface['assigned_networks']:
                if ((as_network.get('name', '') == 'MANAGEMENT' or
                    as_network.get('network_type', '') == 'MANAGEMENT') and
                        'ip' in as_network):
                    host_management_ip = as_network['ip']

    if not host_management_ip and is_throw_exception:
        msg = "Can't find management ip for host %s"\
            % host_detail['id']
        LOG.error(msg)
        raise HTTPBadRequest(explanation=msg)
    return host_management_ip


def _judge_ssh_host(req, host_id):
    ssh_host_flag = False
    kwargs = {}
    nodes = registry.get_hosts_detail(req.context, **kwargs)
    for node in nodes:
        os_handle = get_os_handle()
        os_handle.check_discover_state(req,
                                       node)
        if node['discover_state'] and \
                'SSH:DISCOVERY_SUCCESSFUL' in node['discover_state']:
            if host_id == node['id']:
                ssh_host_flag = True
                break
    return ssh_host_flag


def check_discover_state_with_hwm(req, node, is_detail=False):
    node['discover_state'] = None
    if node.get("discover_mode"):
        node['discover_state'] = node['discover_mode'] + \
            ":DISCOVERY_SUCCESSFUL"
        return node
    if is_detail:
        host_interfaces = node.get('interfaces')
    else:
        host_interfaces = registry.get_host_interface_by_host_id(
            req.context, node.get('id'))
    if host_interfaces:
        mac_list = [interface['mac'] for interface in host_interfaces if
                    interface.get('mac')]
        if mac_list:
            min_mac = min(mac_list)
            pxe_discover_host = _get_discover_host_by_mac(req, min_mac)
            if pxe_discover_host:
                if pxe_discover_host.get('ip'):
                    node['discover_state'] = \
                        "SSH:" + pxe_discover_host.get('status')
                else:
                    node['discover_state'] = \
                        "PXE:" + pxe_discover_host.get('status')

    return node


def check_discover_state_with_no_hwm(req, node, is_detail=False):
    node['discover_state'] = None
    if node.get("discover_mode"):
        node['discover_state'] = node['discover_mode'] + \
            ":DISCOVERY_SUCCESSFUL"
        return node
    if is_detail:
        host_interfaces = node.get('interfaces')
    else:
        host_interfaces = registry.get_host_interface_by_host_id(
            req.context, node.get('id'))
    if host_interfaces:
        ip_list = [interface['ip'] for interface in host_interfaces if
                   interface['ip']]
        for ip in ip_list:
            ssh_discover_host = _get_discover_host_filter_by_ip(
                req, ip)
            if ssh_discover_host:
                node['discover_state'] = \
                    "SSH:" + ssh_discover_host.get('status')

    return node


def _get_discover_host_by_mac(req, host_mac):
    params = dict()
    discover_hosts = \
        registry.get_discover_hosts_detail(req.context, **params)
    LOG.info("%s" % discover_hosts)
    for host in discover_hosts:
        if host.get('mac') == host_mac:
            return host
    return


def _get_discover_host_filter_by_ip(req, host_ip):
    params = {}
    discover_hosts = \
        registry.get_discover_hosts_detail(req.context, **params)
    LOG.debug("%s" % discover_hosts)
    for host in discover_hosts:
        if host.get('ip') == host_ip:
            return host
    return


def add_ssh_host_to_cluster_and_assigned_network(req, cluster_id, host_id):
    if cluster_id:
        host_list = []
        father_vlan_list = []
        discover_successful = 0
        host_info = get_host_detail(req, host_id)
        host_status = host_info.get('status', None)
        if host_status != 'init':
            interfac_meta_list = host_info.get('interfaces', None)
            for interface_info in interfac_meta_list:
                assigned_networks = \
                    interface_info.get('assigned_networks', None)
                if assigned_networks:
                    discover_successful = 1
        if not discover_successful:
            host_list.append(host_id)

        if host_list:
            params = {'filters': {'cluster_id': cluster_id}}
            networks = registry.get_networks_detail(req.context,
                                                    cluster_id, **params)
            father_vlan_list = check_vlan_nic_and_join_vlan_network(req,
                                                                    cluster_id,
                                                                    host_list,
                                                                    networks)
            check_bond_or_ether_nic_and_join_network(req,
                                                     cluster_id,
                                                     host_list,
                                                     networks,
                                                     father_vlan_list)


def check_vlan_nic_and_join_vlan_network(req, cluster_id,
                                         host_list, networks):
    father_vlan_list = []
    for host_id in host_list:
        host_meta_detail = get_host_detail(req, host_id)
        if host_meta_detail.get('interfaces', None):
            interfac_list = host_meta_detail.get('interfaces', None)
            for interface_info in interfac_list:
                host_ip = interface_info.get('ip', None)
                if interface_info['type'] == 'vlan' and host_ip:
                    check_ip_if_valid = \
                        _checker_the_ip_or_hostname_valid(host_ip)
                    if not check_ip_if_valid:
                        msg = "Error:The %s is not the right ip!" % host_ip
                        LOG.error(msg)
                        raise HTTPForbidden(explanation=msg)
                    nic_name_list = interface_info['name'].split('.')
                    if len(nic_name_list) < 2:
                        msg = "No vlan id can be got from the nic '%s' of "\
                              "host '%s', but the nic type is 'vlan'."\
                              % (interface_info['name'],
                                 host_meta_detail['name'])
                        LOG.error(msg)
                        raise HTTPForbidden(explanation=msg)
                    # we think the last section of nic name splited
                    # by '.' is vlan number, and remaining part is
                    # physical nic name.
                    vlan_id = nic_name_list[len(nic_name_list) - 1]
                    nic_name = interface_info['name'][: -len(vlan_id) - 1]
                    exclude_networks = ['DATAPLANE', 'EXTERNAL']
                    use_share_disk = if_used_shared_storage(req, cluster_id)
                    if not use_share_disk:
                        exclude_networks.append('STORAGE')

                    for network in networks:
                        if network['network_type'] in exclude_networks:
                            continue
                        network_cidr = network.get('cidr', None)
                        if network_cidr:
                            ip_in_cidr = \
                                utils.is_ip_in_cidr(host_ip,
                                                    network['cidr'])
                            if vlan_id == network['vlan_id']\
                                    and ip_in_cidr:
                                father_vlan_list.append(
                                    {nic_name: {'name': network['name'],
                                                'ip': host_ip}})
                                interface_info['assigned_networks'].\
                                    append({'name': network['name'],
                                            'ip': host_ip})
                                LOG.info("add the nic %s of the host "
                                         "%s to assigned_network %s" %
                                         (interface_info['name'],
                                          host_id,
                                          interface_info
                                          ['assigned_networks']))
                            elif vlan_id == network['vlan_id'] \
                                    and not ip_in_cidr:
                                msg = "The vlan of nic %s is the same " \
                                      "as network %s, but the ip of nic " \
                                      "is not in the cidr range." % \
                                      (nic_name, network['name'])
                                LOG.error(msg)
                                raise HTTPForbidden(explanation=msg)
                        else:
                            msg = "There is no cidr in network " \
                                  "%s" % network['name']
                            LOG.error(msg)
                            raise HTTPForbidden(explanation=msg)
    return father_vlan_list


def _checker_the_ip_or_hostname_valid(ip_str):
    try:
        ip_lists = socket.gethostbyname_ex(ip_str)
        return True
    except Exception:
        if netaddr.IPAddress(ip_str).version == 6:
            return True
        else:
            return False


def check_bond_or_ether_nic_and_join_network(req,
                                             cluster_id,
                                             host_list,
                                             networks,
                                             father_vlan_list):
    for host_id in host_list:
        host_info = get_host_detail(req, host_id)
        if host_info.get('interfaces', None):
            update_host_interface = 0
            interfac_meta_list = host_info.get('interfaces', None)
            for interface_info in interfac_meta_list:
                update_flag = 0
                host_info_ip = interface_info.get('ip', None)
                if interface_info['type'] != 'vlan':
                    nic_name = interface_info['name']
                    for nic in father_vlan_list:
                        if nic.keys()[0] == nic_name:
                            update_flag = 1
                            update_host_interface = 1
                            interface_info['assigned_networks']\
                                .append(nic.values()[0])
                    if update_flag:
                        continue
                    if host_info_ip:
                        check_ip_if_valid = \
                            _checker_the_ip_or_hostname_valid(host_info_ip)
                        if not check_ip_if_valid:
                            msg = "Error:The %s is not the right ip!"\
                                  % host_info_ip
                            LOG.error(msg)
                            raise exception.Forbidden(msg)
                        exclude_networks = ['DATAPLANE', 'EXTERNAL']
                        use_share_disk = if_used_shared_storage(req,
                                                                cluster_id)
                        if not use_share_disk:
                            exclude_networks.append('STORAGE')
                        for network in networks:
                            if network['network_type'] in exclude_networks:
                                continue
                            if network.get('cidr', None):
                                ip_in_cidr = utils.is_ip_in_cidr(
                                    host_info_ip,
                                    network['cidr'])
                                if ip_in_cidr:
                                    vlan_id = network['vlan_id']
                                    if not vlan_id:
                                        update_host_interface = 1
                                        interface_info['assigned_networks'].\
                                            append({'name': network['name'],
                                                    'ip': host_info_ip})
                                        LOG.info("add the nic %s of the "
                                                 "host %s to "
                                                 "assigned_network %s" %
                                                 (nic_name,
                                                  host_id,
                                                  interface_info
                                                  ['assigned_networks']))
                                    else:
                                        msg = ("the nic %s of ip %s is in "
                                               "the %s cidr range,but the "
                                               "network vlan id is %s " %
                                               (nic_name,
                                                host_info_ip,
                                                network['name'], vlan_id))
                                        LOG.error(msg)
                                        raise HTTPForbidden(explanation=msg)
                            else:
                                msg = "There is no cidr in network " \
                                      "%s" % network['name']
                                LOG.error(msg)
                                raise HTTPForbidden(explanation=msg)

            if update_host_interface:
                host_meta = {}
                host_meta['cluster'] = cluster_id
                host_meta['interfaces'] = str(interfac_meta_list)
                host_meta = registry.update_host_metadata(req.context,
                                                          host_id,
                                                          host_meta)
                LOG.info("add the host %s join the cluster %s and"
                         " assigned_network successful" %
                         (host_id, cluster_id))


def if_used_shared_storage(req, cluster_id):
    cluster_roles = get_cluster_roles_detail(req, cluster_id)
    cluster_backends = set([role['deployment_backend']
                            for role in cluster_roles])
    for backend in cluster_backends:
        try:
            backend_disk = importutils.import_module(
                'daisy.api.backends.%s.disk_array' % backend)
        except Exception:
            return False
        else:
            if hasattr(backend_disk, 'get_disk_array_info'):
                disks_info = backend_disk.get_disk_array_info(req, cluster_id)
                for info in disks_info:
                    if info:
                        return True
    return False
