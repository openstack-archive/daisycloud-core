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
import subprocess
import time
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPNotFound
from daisy import i18n

from daisy.common import exception
import daisy.registry.client.v1.api as registry
import copy

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


def subprocess_call(command, file=None):
    if file:
        return_code = subprocess.call(command,
                                      shell=True,
                                      stdout=file,
                                      stderr=file)
    else:
        return_code = subprocess.call(command,
                                      shell=True,
                                      stdout=open('/dev/null', 'w'),
                                      stderr=subprocess.STDOUT)
    if return_code != 0:
        msg = "execute '%s' failed by subprocess call." % command
        raise exception.SubprocessCmdFailed(msg)


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


def update_role_host(req, role_id, role_host):
    try:
        registry.update_role_host_metadata(req.context, role_id, role_host)
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


def delete_role_hosts(req, role_id):
    try:
        registry.delete_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


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


def get_host_network_ip(req, host_detail, cluster_networks, network_name):
    interface_network_ip = ''
    host_interface = get_host_interface_by_network(host_detail, network_name)
    if host_interface:
        network = _get_cluster_network(cluster_networks, network_name)
        assigned_network = get_assigned_network(req,
                                                host_interface['id'],
                                                network['id'])
        interface_network_ip = assigned_network['ip']

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
            vlan_id_len_list = [len(network['vlan_id'])
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


def get_ctl_ha_nodes_min_mac(req, cluster_id):
    '''
    ctl_ha_nodes_min_mac = {'host_name1':'min_mac1', ...}
    '''
    ctl_ha_nodes_min_mac = {}
    roles = get_cluster_roles_detail(req, cluster_id)
    cluster_networks =\
        get_cluster_networks_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] != tecs_backend_name:
            continue
        role_hosts = get_hosts_of_role(req, role['id'])
        for role_host in role_hosts:
            # host has installed tecs are exclusive
            if (role_host['status'] == TECS_STATE['ACTIVE'] or
                    role_host['status'] == TECS_STATE['UPDATING'] or
                    role_host['status'] == TECS_STATE['UPDATE_FAILED']):
                continue
            host_detail = get_host_detail(req,
                                          role_host['host_id'])
            host_name = host_detail['name']
            if role['name'] == "CONTROLLER_HA":
                min_mac = utils.get_host_min_mac(host_detail['interfaces'])
                ctl_ha_nodes_min_mac[host_name] = min_mac
    return ctl_ha_nodes_min_mac
