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
/install endpoint for daisy API
"""
import copy
import subprocess
import time
import re
import commands
from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from daisy.api import common
import threading
from daisy import i18n
import json

from daisy.common import exception
from daisy.common import utils
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

CONF = cfg.CONF
install_opts = [
    cfg.StrOpt('max_parallel_os_number', default=10,
               help='Maximum number of hosts install os at the same time.'),
]
CONF.register_opts(install_opts)
upgrade_opts = [
    cfg.StrOpt('max_parallel_os_upgrade_number', default=10,
               help='Maximum number of hosts upgrade os at the same time.'),
]
CONF.register_opts(upgrade_opts)

host_os_status = {
    'INIT': 'init',
    'PRE_INSTALL': 'pre-install',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed'
}

LINUX_BOND_MODE = {'balance-rr': '0', 'active-backup': '1',
                   'balance-xor': '2', 'broadcast': '3',
                   '802.3ad': '4', 'balance-tlb': '5',
                   'balance-alb': '6'}


def build_pxe_server(eth_name, ip_address, build_pxe, net_mask,
                     client_ip_begin, client_ip_end):
    """build pxe server."""
    pxe_dict = dict()
    pxe_dict['ethname_l'] = eth_name
    pxe_dict['ip_addr_l'] = ip_address
    pxe_dict['build_pxe'] = build_pxe
    pxe_dict['net_mask_l'] = net_mask
    pxe_dict['client_ip_begin'] = client_ip_begin
    pxe_dict['client_ip_end'] = client_ip_end
    LOG.info('pxe_dict=%s' % pxe_dict)
    with open('/var/log/ironic/pxe.json', 'w') as f:
        json.dump(pxe_dict, f, indent=2)
    f.close()
    _PIPE = subprocess.PIPE
    cmd = "/usr/bin/pxe_server_install /var/log/ironic/pxe.json && \
           chmod 755 /tftpboot -R"
    try:
        obj = subprocess.Popen(cmd, stdin=_PIPE, stdout=_PIPE,
                               stderr=_PIPE, shell=True)
        obj.communicate()
    except Exception as e:
        msg = "build_pxe_server error: %s" % e
        LOG.error(msg)
        raise exception.Invalid(msg)

    if obj.returncode:
        msg = "execute set pxe command failed."
        LOG.error(msg)
        raise exception.Invalid(msg)


def set_boot_or_power_state(user, passwd, addr, action):
    if action in ['on', 'off', 'reset']:
        device = 'power'
    elif action in ['pxe', 'disk']:
        device = 'bootdev'
    else:
        return

    cmd = ['ipmitool', '-I', 'lanplus', '-H', addr, '-U', user,
           '-P', passwd, 'chassis', device, action]

    if device == 'bootdev':
        cmd.append('options=persistent')
    _PIPE = subprocess.PIPE
    try:
        obj = subprocess.Popen(cmd, stdin=_PIPE, stdout=_PIPE,
                               stderr=_PIPE, shell=False)
        obj.communicate()
    except Exception as e:
        msg = "%s set_boot_or_power_state error: %s" % (addr, e)
        LOG.error(msg)
        return -1

    return obj.returncode


def install_os(**kwargs):
    json_file = "/var/log/ironic/%s.json" % kwargs['dhcp_mac']
    with open(json_file, 'w') as f:
        json.dump(kwargs, f, indent=2)
    f.close()
    _PIPE = subprocess.PIPE
    cmd = "/usr/bin/pxe_os_install /var/log/ironic/%s.json && \
           chmod 755 /tftpboot -R && \
           chmod 755 /home/install_share -R && \
           chmod 755 /linuxinstall -R" % kwargs['dhcp_mac']
    try:
        obj = subprocess.Popen(cmd, stdin=_PIPE, stdout=_PIPE,
                               stderr=_PIPE, shell=True, cwd=None, env=None)
        out, error = obj.communicate()
    except Exception as e:
        msg = "%s install_os error: %s" % (kwargs['dhcp_mac'], e)
        LOG.error(msg)
        return -1, msg

    return obj.returncode, error


def get_install_progress(dhcp_mac):
    _PIPE = subprocess.PIPE
    cmd = "/usr/bin/pxe_os_install_progress %s" % dhcp_mac

    try:
        obj = subprocess.Popen(cmd, stdin=_PIPE, stdout=_PIPE,
                               stderr=_PIPE, shell=True)
        out, error = obj.communicate()
        progress_list = out.split()
        progress = progress_list.pop(0)
        info = ' '.join(progress_list)
        rc = obj.returncode
    except Exception as e:
        info = '%s get install progress failed: %s' % (dhcp_mac, e)
        progress, rc = 0, -1
        LOG.error(info)

    ret = {'return_code': rc,
           'progress': progress,
           'info': info}
    return ret


def check_discover_state(req, host_meta, is_detail=False):
    if host_meta.get("hwm_id"):
        daisy_cmn.check_discover_state_with_hwm(req,
                                                host_meta,
                                                is_detail=is_detail)
    else:
        daisy_cmn.check_discover_state_with_no_hwm(req,
                                                   host_meta,
                                                   is_detail=is_detail)


def pxe_server_build(req, install_meta):
    params = {'filters': {'type': 'system'}}
    try:
        networks = registry.get_all_networks(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)

    try:
        ip_inter = lambda x: sum([256 ** j * int(i)
                                  for j, i in enumerate(x.split('.')[::-1])])
        inter_ip = lambda x: '.'.join(
            [str(x / (256**i) % 256) for i in range(3, -1, -1)])
        for network in networks:
            if 'system' in network['type']:
                network_cidr = network.get('cidr')
                if not network_cidr:
                    msg = "Error:The CIDR is blank of pxe server!"
                    LOG.error(msg)
                    raise exception.Forbidden(msg)
                cidr_end = network_cidr.split('/')[1]
                mask = ~(2**(32 - int(cidr_end)) - 1)
                net_mask = inter_ip(mask)
                pxe_server_ip = network.get('ip')
                ip_ranges = network.get('ip_ranges')
                for ip_range in ip_ranges:
                    client_ip_begin = ip_range.get('start')
                    client_ip_end = ip_range.get('end')
                    ip_addr = network_cidr.split('/')[0]
                    ip_addr_int = ip_inter(ip_addr)
                    ip_addr_min = inter_ip(ip_addr_int & (mask & 0xffffffff))
                    ip_addr_max = inter_ip(ip_addr_int | (~mask & 0xffffffff))
                    if not client_ip_begin and not client_ip_end:
                        client_ip_begin = inter_ip((ip_inter(ip_addr_min)) + 2)
                        client_ip_end = ip_addr_max
                    if pxe_server_ip:
                        ip_in_cidr = utils.is_ip_in_cidr(pxe_server_ip,
                                                         network_cidr)
                        if not ip_in_cidr:
                            msg = "Error:The ip '%s' is not in cidr '%s'" \
                                  " range." % (pxe_server_ip, network_cidr)
                            LOG.error(msg)
                            raise HTTPBadRequest(explanation=msg)
                    else:
                        pxe_server_ip = inter_ip((ip_inter(ip_addr_min)) + 1)

        eth_name = install_meta.get('deployment_interface')
        if not eth_name:
            msg = "Error:The nic name is blank of build pxe server!"
            LOG.error(msg)
            raise exception.Forbidden(msg)
        (status, output) = commands.getstatusoutput('ifconfig')
        netcard_pattern = re.compile('\S*: ')
        nic_list = []
        for netcard in re.finditer(netcard_pattern, str(output)):
            nic_name = netcard.group().split(': ')[0]
            nic_list.append(nic_name)
        if eth_name not in nic_list:
            msg = "Error:The nic name is not exist!"
            LOG.error(msg)
            raise exception.Forbidden(msg)
        args = {'build_pxe': 'yes',
                'eth_name': eth_name,
                'ip_address': pxe_server_ip,
                'net_mask': net_mask,
                'client_ip_begin': client_ip_begin,
                'client_ip_end': client_ip_end}
        build_pxe_server(**args)
    except exception.Invalid as e:
        msg = "build pxe server failed"
        LOG.error(msg)
        raise exception.InvalidNetworkConfig(msg)


def _get_network_plat(req, host_config, cluster_networks, dhcp_mac):
    host_config['dhcp_mac'] = dhcp_mac
    if host_config['interfaces']:
        count = 0
        host_config_orig = copy.deepcopy(host_config)
        for interface in host_config['interfaces']:
            count += 1
            # if (interface.has_key('assigned_networks') and
            if ('assigned_networks' in interface and
                    interface['assigned_networks']):
                assigned_networks = copy.deepcopy(
                    interface['assigned_networks'])
                host_config['interfaces'][count - 1]['assigned_networks'] = []
                alias = []
                for assigned_network in assigned_networks:
                    network_name = assigned_network['name']
                    cluster_network = [
                        network for network in cluster_networks
                        if network['name'] == network_name][0]
                    alias.append(cluster_network['alias'])
                    # convert cidr to netmask
                    cidr_to_ip = ""
                    assigned_networks_ip = daisy_cmn.get_host_network_ip(
                        req, host_config_orig, cluster_networks, network_name)
                    if cluster_network.get('cidr', None):
                        inter_ip = lambda x: '.'.join(
                            [str(x / (256**i) % 256) for i in
                             range(3, -1, -1)])
                        cidr_to_ip = inter_ip(
                            2**32 - 2**(32 - int(
                                cluster_network['cidr'].split('/')[1])))
                    if cluster_network['alias'] is None or len(alias) == 1:
                        network_type = cluster_network['network_type']
                        network_plat = dict(network_type=network_type,
                                            ml2_type=cluster_network[
                                                'ml2_type'],
                                            capability=cluster_network[
                                                'capability'],
                                            physnet_name=cluster_network[
                                                'physnet_name'],
                                            gateway=cluster_network.get(
                                                'gateway', ""),
                                            ip=assigned_networks_ip,
                                            # ip=cluster_network.get('ip', ""),
                                            netmask=cidr_to_ip,
                                            vlan_id=cluster_network.get(
                                                'vlan_id', ""))
                        host_config['interfaces'][
                            count - 1][
                            'assigned_networks'].append(network_plat)
            interface['ip'] = ""
            interface['netmask'] = ""
            interface['gateway'] = ""

    return host_config


def get_cluster_hosts_config(req, cluster_id):
    # params = dict(limit=1000000)
    try:
        cluster_data = registry.get_cluster_metadata(req.context, cluster_id)
        networks = registry.get_networks_detail(req.context, cluster_id)
        all_roles = registry.get_roles_detail(req.context)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)

    roles = [role for role in all_roles if role['cluster_id'] == cluster_id]
    all_hosts_ids = cluster_data['nodes']
    hosts_config = []
    for host_id in all_hosts_ids:
        host_detail = daisy_cmn.get_host_detail(req, host_id)
        role_host_db_lv_size_lists = list()
        # if host_detail.has_key('role') and host_detail['role']:
        if 'role' in host_detail and host_detail['role']:
            host_roles = host_detail['role']
            for role in roles:
                if role['name'] in host_detail['role'] and\
                        role['glance_lv_size']:
                    host_detail['glance_lv_size'] = role['glance_lv_size']
                if role.get('db_lv_size', None) and host_roles and\
                        role['name'] in host_roles:
                    role_host_db_lv_size_lists.append(role['db_lv_size'])
                if role['name'] == 'COMPUTER' and\
                        role['name'] in host_detail['role'] and\
                        role['nova_lv_size']:
                    host_detail['nova_lv_size'] = role['nova_lv_size']
                service_disks = daisy_cmn.get_service_disk_list(
                    req, {'role_id': role['id']})
                for service_disk in service_disks:
                    if service_disk['disk_location'] == 'local' \
                            and role['name'] in host_detail['role']:
                        if service_disk['service'] == 'mongodb':
                            host_detail['mongodb_lv_size'] = \
                                service_disk['size']
                        if service_disk['service'] == 'provider':
                            host_detail['provider_lv_size'] = \
                                service_disk['size']
            if role_host_db_lv_size_lists:
                host_detail['db_lv_size'] = max(role_host_db_lv_size_lists)
            else:
                host_detail['db_lv_size'] = 0

        for interface in host_detail['interfaces']:
            if interface['type'] == 'bond'and\
               interface['mode'] in LINUX_BOND_MODE.keys():
                interface['mode'] = LINUX_BOND_MODE[interface['mode']]

        if (host_detail['os_status'] == host_os_status['INIT'] or
                host_detail['os_status'] == host_os_status['PRE_INSTALL'] or
                host_detail['os_status'] == host_os_status['INSTALLING'] or
                host_detail['os_status'] == host_os_status['INSTALL_FAILED']):
            pxe_macs = common.get_pxe_mac(host_detail)
            if not pxe_macs:
                msg = "cann't find dhcp interface on host %s" % host_detail[
                    'id']
                raise exception.InvalidNetworkConfig(msg)
            if len(pxe_macs) > 1:
                msg = "dhcp interface should only has one on host %s"\
                    % host_detail['id']
                raise exception.InvalidNetworkConfig(msg)

            host_config_detail = copy.deepcopy(host_detail)
            host_config = _get_network_plat(req, host_config_detail,
                                            networks,
                                            pxe_macs[0])
            hosts_config.append(daisy_cmn.sort_interfaces_by_pci(networks,
                                                                 host_config))
    return hosts_config


def _rm_ipmi_failed_host(req, install_hosts):
    for install_host in install_hosts:
        host_info = daisy_cmn.get_host_detail(req, install_host['id'])
        if host_info["os_status"] == host_os_status["INSTALL_FAILED"]:
            install_host["os_status"] = host_os_status["INSTALL_FAILED"]
    install_hosts = [install_host for install_host in install_hosts if
                     install_host["os_status"] != host_os_status[
                         "INSTALL_FAILED"]]
    return install_hosts


def get_host_location_of_cisco(host_detail):
    LOG.info(_("Get location for host %s" % host_detail['id']))
    try:
        location_result = subprocess.check_output(
            'sshpass -p%s ssh -o StrictHostKeyChecking=no '
            '%s@10.10.100.254 "show identity ip-addr %s"' %
            (host_detail.get('ipmi_passwd'),
             host_detail.get('ipmi_user'),
             host_detail.get('ipmi_addr')), shell=True,
            stderr=subprocess.STDOUT)
        pattern = re.compile("chassis-(\d*)\/blade-(\d*)")
        res = pattern.search(location_result).groups()
        location = res[0] + '/' + res[1]
    except subprocess.CalledProcessError as e:
        LOG.info(_("Get location for %s failed!" % host_detail['id']))
        return None
    else:
        LOG.info(_("Get location for %s successfully!" % host_detail['id']))
        return location


def set_pxe_start_of_cisco(host_detail):
    LOG.info(_("Set pxe start for host %s" % (host_detail['id'])))
    try:
        exc_result = subprocess.check_output(
            'sshpass -p%s ssh -o StrictHostKeyChecking=no '
            '%s@10.10.100.254 "scope service-profile server %s;'
            'set boot-policy pxe;commit-buffer"' %
            (host_detail.get('ipmi_passwd'),
             host_detail.get('ipmi_user'),
             host_detail.get('location')), shell=True,
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        LOG.info(_("set pxe start for %s failed!" % host_detail['id']))
        return
    else:
        LOG.info(_("set pxe start for %s successfully!" %
                   host_detail['id']))


def set_reboot_of_cisco(host_detail):
    LOG.info(_("Set boot from disk for host %s" % (host_detail['id'])))
    try:
        exc_result = subprocess.check_output(
            'sshpass -p%s ssh -o StrictHostKeyChecking=no '
            '%s@10.10.100.254 "scope service-profile server %s;'
            'reboot;commit-buffer"' % (host_detail.get('ipmi_passwd'),
                                       host_detail.get('ipmi_user'),
                                       host_detail.get('location')),
            shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        LOG.info(_("restart for %s failed!" % host_detail['id']))
        return
    else:
        LOG.info(_("restart for %s successfully!" %
                   host_detail['id']))


def set_disk_start_of_cisco(host_detail):
    LOG.info(_("Set boot from disk for host %s" % (host_detail['id'])))
    try:
        exc_result = subprocess.check_output(
            'sshpass -p%s ssh -o StrictHostKeyChecking=no '
            '%s@10.10.100.254 "scope service-profile server %s;'
            'set boot-policy local-disk;commit-buffer"' %
            (host_detail.get('ipmi_passwd'), host_detail.get('ipmi_user'),
             host_detail.get('location')), shell=True,
            stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        LOG.info(_("set disk start for %s failed!" % host_detail['id']))
        return
    else:
        LOG.info(_("set disk start for %s successfully!" %
                   host_detail['id']))


def _get_host_interfaces(host_info):
    interfaces = host_info['interfaces']
    for interface in interfaces:
        no_dup_networks = {}
        for assigned_network in interface['assigned_networks']:
            if assigned_network['network_type'] == 'DATAPLANE':
                assigned_network['ip'] = None
                break

            # remove duplicates assigned networks
            if assigned_network.get('ip') not in no_dup_networks.keys() \
                    or assigned_network.get('network_type') == 'MANAGEMENT':
                no_dup_networks[assigned_network['ip']] = assigned_network
        if no_dup_networks:
            interface['assigned_networks'] = no_dup_networks.values()
    return interfaces


class OSInstall():

    """
    Class for install OS.
    """
    """ Definition for install states."""

    def __init__(self, req, cluster_id):
        self.req = req
        self.cluster_id = cluster_id
        # 5s
        self.time_step = 5
        # 30 min
        self.single_host_install_timeout = 30 * (12 * self.time_step)

        self.max_parallel_os_num = int(CONF.max_parallel_os_number)
        self.cluster_hosts_install_timeout = (
            self.max_parallel_os_num / 4 + 2) * 60 * (12 * self.time_step)

    def _set_boot_or_power_state(self, host_detail, action):
        user = host_detail['ipmi_user']
        passwd = host_detail['ipmi_passwd']
        addr = host_detail['ipmi_addr']
        count = 0
        repeat_times = 5
        ipmi_result_flag = True
        stop_flag = False
        while count < repeat_times:
            rc = set_boot_or_power_state(user, passwd, addr, action)
            if rc == 0:
                LOG.info(
                    _("Set %s to '%s' successfully for %s times by ironic" % (
                        addr, action, count + 1)))
                host_status = {'messages': "Set %s to '%s' successfully for "
                                           "%s times by ironic" % (
                                               addr, action, count + 1)}
                daisy_cmn.update_db_host_status(self.req, host_detail['id'],
                                                host_status)
                # make user know set successfull
                time.sleep(1)
                host_status = {
                    'messages': 'Preparing for OS installation',
                    'os_progress': 0}
                daisy_cmn.update_db_host_status(self.req, host_detail['id'],
                                                host_status)

                # One host set 'disk' return success, but it still 'pxe'
                # mode in German site. If we have a method to confirm,
                # this can be deleted.
                if action == 'pxe' or action == 'disk':
                    set_boot_or_power_state(user, passwd, addr,
                                            action)
                break
            else:
                count += 1
                LOG.info(
                    _("Try setting %s to '%s' failed for %s times by ironic"
                      % (addr, action, count)))
                host_status = {'messages': "Set %s to '%s' failed for "
                                           "%s times by ironic" % (
                                               addr, action, count + 1)}
                daisy_cmn.update_db_host_status(self.req, host_detail['id'],
                                                host_status)
                time.sleep(count * 2)
        if count >= repeat_times:
            ipmi_result_flag = False
            if host_detail.get('role', None):
                role_of_host = host_detail['role']
            else:
                role_of_host = []
            if "CONTROLLER_HA" in role_of_host or "CONTROLLER_LB" in \
                    role_of_host:
                stop_flag = True
            if stop_flag:
                host_status = {
                    'os_status': host_os_status['INSTALL_FAILED'],
                    'os_progress': 0,
                    'messages': "set %s to '%s' failed for 10 mins,is "
                                "controller host,can't go on playing" % (
                                    addr, action)}
                daisy_cmn.update_db_host_status(self.req, host_detail['id'],
                                                host_status)
                message = "set %s to '%s' failed for 10 mins,is controller" \
                          " host,can't go on playing" % (addr, action)
                raise exception.IMPIOprationFailed(message=message)
            else:
                LOG.info(
                    _("set %s to '%s' failed for 10 mins,not controller"
                      " host or no role ,go on playing" % (addr, action)))
                host_status = {
                    'os_status': host_os_status['INSTALL_FAILED'],
                    'os_progress': 0,
                    'messages': "set %s to '%s' failed for 10 mins,not "
                                "controller host or no role ,go on playing"
                                % (addr, action)}
                daisy_cmn.update_db_host_status(self.req, host_detail['id'],
                                                host_status)

        return ipmi_result_flag

    def _install_os_for_baremetal(self, host_detail):
        # os_version_file and os_version_id only exist one at
        # same time
        if host_detail.get('os_version_file', None):
            os_version_file = host_detail['os_version_file']
        if host_detail.get('os_version_id', None):
            version_info = registry.get_version_metadata(
                self.req.context,
                host_detail['os_version_id'])
            if version_info:
                os_version = version_info['name']
                os_version_file = "/var/lib/daisy/" + os_version
        if os_version_file:
            test_os_version_exist = 'test -f %s' % os_version_file
            daisy_cmn.subprocess_call(test_os_version_exist)
        else:
            self.message = "No OS version file configed for host %s" %\
                           host_detail['id']
            raise exception.NotFound(message=self.message)
        if host_detail.get('root_disk', None):
            root_disk = host_detail['root_disk']
        else:
            root_disk = 'sda'
        if host_detail.get('root_lv_size', None):
            root_lv_size_m = host_detail['root_lv_size']
        else:
            root_lv_size_m = 102400
        memory_size_b_str = str(host_detail['memory']['total'])
        memory_size_b_int = int(memory_size_b_str.strip().split()[0])
        memory_size_m = memory_size_b_int // 1024
        memory_size_g = memory_size_m // 1024
        swap_lv_size_m = host_detail['swap_lv_size']
        cinder_vg_size_m = 0
        disk_list = []
        disk_storage_size_b = 0
        for key in host_detail['disks']:
            if host_detail['disks'][key]['disk'].find("-fc-") != -1 \
                    or host_detail['disks'][key]['disk'].\
                    find("-iscsi-") != -1 \
                    or host_detail['disks'][key]['name'].\
                    find("mpath") != -1 \
                    or host_detail['disks'][key]['name'].\
                    find("spath") != -1 \
                    or host_detail['disks'][key]['removable'] == 'removable':
                continue
            disk_list.append(host_detail['disks'][key]['name'])
            stroage_size_str = host_detail['disks'][key]['size']
            stroage_size_b_int = int(stroage_size_str.strip().split()[0])
            disk_storage_size_b = disk_storage_size_b + stroage_size_b_int
        disk_list = ','.join(disk_list)
        disk_storage_size_m = disk_storage_size_b // (1024 * 1024)

        if 'root_pwd' in host_detail and host_detail['root_pwd']:
            root_pwd = host_detail['root_pwd']
        else:
            root_pwd = 'ossdbg1'

        isolcpus = None
        if host_detail.get('isolcpus', None):
            isolcpus = host_detail['isolcpus']
        elif host_detail.get('os_cpus', None):
            os_cpus = utils.cpu_str_to_list(host_detail['os_cpus'])
            host_cpu = host_detail.get('cpu', {})
            if 'total' in host_cpu:
                total_cpus = range(0, host_cpu['total'])
                isolcpus_list = list(set(total_cpus) - set(os_cpus))
                isolcpus_list.sort()
                isolcpus = utils.cpu_list_to_str(isolcpus_list)

        if host_detail.get('hugepages', None):
            hugepages = host_detail['hugepages']
        else:
            hugepages = 0

        if host_detail.get('hugepagesize', None):
            hugepagesize = host_detail['hugepagesize']
        else:
            hugepagesize = '1G'
        # tfg_patch_pkg_file = check_tfg_exist()

        host_manufacturer = host_detail['system'].get('manufacturer')
        if host_detail.get('hwm_id'):
            host_hwm_meta = {
                "hwm_ip": host_detail.get('hwm_ip'),
                "hwm_id": host_detail.get('hwm_id'),
                "boot_type": "pxe"
            }
            self.providerclient(host_hwm_meta['hwm_ip']).node.set_boot(
                **host_hwm_meta)
        elif host_manufacturer == 'Cisco Systems Inc':
            set_pxe_start_of_cisco(host_detail)
        else:
            if (not host_detail['ipmi_user'] or
                    not host_detail['ipmi_passwd'] or
                    not host_detail['ipmi_addr']):
                self.message = \
                    "Invalid ipmi information configed for host %s" \
                    % host_detail['id']
                raise exception.NotFound(message=self.message)

                ipmi_result_flag = self._set_boot_or_power_state(host_detail,
                                                                 'pxe')

        host_interfaces = _get_host_interfaces(host_detail)
        kwargs = {'hostname': host_detail['name'],
                  'iso_path': os_version_file,
                  'group_list': host_detail['group_list'],
                  # 'tfg_bin':tfg_patch_pkg_file,
                  'dhcp_mac': host_detail['dhcp_mac'],
                  'storage_size': disk_storage_size_m,
                  'memory_size': memory_size_g,
                  'interfaces': host_interfaces,
                  'root_lv_size': root_lv_size_m,
                  'swap_lv_size': swap_lv_size_m,
                  'cinder_vg_size': cinder_vg_size_m,
                  'disk_list': disk_list,
                  'root_disk': root_disk,
                  'root_pwd': root_pwd,
                  'isolcpus': isolcpus,
                  'hugepagesize': hugepagesize,
                  'hugepages': hugepages,
                  'reboot': 'no'}

        # if host_detail.has_key('glance_lv_size'):
        if 'glance_lv_size' in host_detail:
            kwargs['glance_lv_size'] = host_detail['glance_lv_size']
        else:
            kwargs['glance_lv_size'] = 0

        # if host_detail.has_key('db_lv_size') and host_detail['db_lv_size']:
        if 'db_lv_size' in host_detail and host_detail['db_lv_size']:
            kwargs['db_lv_size'] = host_detail['db_lv_size']
        else:
            kwargs['db_lv_size'] = 0

        # if host_detail.has_key('mongodb_lv_size') and
        # host_detail['mongodb_lv_size']:
        if 'mongodb_lv_size' in host_detail and host_detail['mongodb_lv_size']:
            kwargs['mongodb_lv_size'] = host_detail['mongodb_lv_size']
        else:
            kwargs['mongodb_lv_size'] = 0

        if host_detail.get('provider_lv_size', None):
            # provider_lv_size_m = int(host_detail['provider_lv_size']) * 1024
            kwargs['provider_lv_size'] = host_detail['provider_lv_size']
        else:
            kwargs['provider_lv_size'] = 0

        # if host_detail.has_key('nova_lv_size') and
        # host_detail['nova_lv_size']:
        if 'nova_lv_size' in host_detail and host_detail['nova_lv_size']:
            kwargs['nova_lv_size'] = host_detail['nova_lv_size']
        else:
            kwargs['nova_lv_size'] = 0
        if host_detail.get('hwm_id') or ipmi_result_flag:
            rc, error = install_os(**kwargs)
            if rc != 0:
                install_os_description = error
                LOG.info(
                    _("install os config failed because of '%s'" % error))
                host_status = {'os_status': host_os_status['INSTALL_FAILED'],
                               'os_progress': 0,
                               'messages': error}
                daisy_cmn.update_db_host_status(self.req, host_detail['id'],
                                                host_status)
                msg = "ironic install os return failed for host %s" % \
                      host_detail['id']
                raise exception.OSInstallFailed(message=msg)

        if host_detail.get('hwm_id'):
            host_hwm_meta = {
                "hwm_ip": host_detail.get('hwm_ip'),
                "hwm_id": host_detail.get('hwm_id')
            }
            self.providerclient(host_hwm_meta['hwm_ip']).node.restart(
                **host_hwm_meta)
        elif host_manufacturer == 'Cisco Systems Inc':
            set_reboot_of_cisco(host_detail)
        else:
            if ipmi_result_flag:
                self._set_boot_or_power_state(host_detail, 'reset')

    def _begin_install_os(self, hosts_detail):
        # all hosts status is set to 'pre-install' before os installing
        for host_detail in hosts_detail:
            host_status = {'os_status': host_os_status['PRE_INSTALL'],
                           'os_progress': 0,
                           'messages': 'Preparing for OS installation'}
            daisy_cmn.update_db_host_status(self.req, host_detail['id'],
                                            host_status)

        for host_detail in hosts_detail:
            self._install_os_for_baremetal(host_detail)

    def _set_disk_start_mode(self, host_detail):
        host_manufacturer = host_detail['system'].get('manufacturer')
        LOG.info(_("Set boot from disk for host %s" % (host_detail['id'])))
        if host_detail.get('hwm_id'):
            host_hwm_meta = {
                "hwm_ip": host_detail.get('hwm_ip'),
                "hwm_id": host_detail.get('hwm_id'),
                "boot_type": "disk"
            }
            self.providerclient(host_hwm_meta['hwm_ip']).node.set_boot(
                **host_hwm_meta)
            LOG.info(_("reboot host %s" % (host_detail['id'])))
            host_hwm_meta.pop('boot_type')
            self.providerclient(host_hwm_meta['hwm_ip']).node.restart(
                **host_hwm_meta)
        elif host_manufacturer == 'Cisco Systems Inc':
            set_disk_start_of_cisco(host_detail)
            set_reboot_of_cisco(host_detail)
        else:
            self._set_boot_or_power_state(host_detail, 'disk')
            LOG.info(_("reboot host %s" % (host_detail['id'])))
            self._set_boot_or_power_state(host_detail, 'reset')

    def _init_progress(self, host_detail, hosts_status):
        host_id = host_detail['id']

        host_status = hosts_status[host_id] = {}
        host_status['os_status'] = host_os_status['INSTALLING']
        host_status['os_progress'] = 0
        host_status['count'] = 0
        if host_detail['resource_type'] == 'docker':
            host_status['messages'] = "docker container is creating"
        else:
            host_status['messages'] = "OS installing"

        daisy_cmn.update_db_host_status(self.req, host_id, host_status)

    def _query_host_progress(self, host_detail, host_status, host_last_status):
        host_id = host_detail['id']
        install_result = get_install_progress(
            host_detail['dhcp_mac'])
        rc = int(install_result['return_code'])
        host_status['os_progress'] = int(install_result['progress'])
        if rc == 0:
            if host_status['os_progress'] == 100:
                time_cost = str(
                    round((time.time() -
                           daisy_cmn.os_install_start_time) / 60, 2))
                LOG.info(
                    _("It takes %s min for host %s to install os"
                        % (time_cost, host_id)))
                LOG.info(_("host %s install os completely." % host_id))
                host_status['os_status'] = host_os_status['ACTIVE']
                host_status['messages'] = "OS installed successfully"
                # wait for nicfix script complete
                time.sleep(10)
                self._set_disk_start_mode(host_detail)
            else:
                if host_status['os_progress'] ==\
                        host_last_status['os_progress']:
                    host_status['count'] = host_status['count'] + 1
                    LOG.debug(_("host %s has kept %ss when progress is %s."
                                % (host_id,
                                   host_status['count'] * self.time_step,
                                   host_status['os_progress'])))
        else:
            LOG.info(_("host %s install failed." % host_id))
            host_status['os_status'] = host_os_status['INSTALL_FAILED']
            host_status['messages'] = install_result['info']

    def _query_progress(self, hosts_last_status, hosts_detail):
        hosts_status = copy.deepcopy(hosts_last_status)
        for host_detail in hosts_detail:
            host_id = host_detail['id']
            # if not hosts_status.has_key(host_id):
            if host_id not in hosts_status:
                self._init_progress(host_detail, hosts_status)
                continue

            host_status = hosts_status[host_id]
            host_last_status = hosts_last_status[host_id]
            # only process installing hosts after init, other hosts info will
            # be kept in hosts_status
            if host_status['os_status'] != host_os_status['INSTALLING']:
                continue
            self._query_host_progress(
                host_detail, host_status, host_last_status)

            if host_status['count'] * self.time_step >=\
                    self.single_host_install_timeout:
                host_status['os_status'] = host_os_status['INSTALL_FAILED']
                if host_detail['resource_type'] == 'docker':
                    host_status[
                        'messages'] = "docker container created timeout"
                else:
                    host_status['messages'] = "os installed timeout"
                    if daisy_cmn.in_cluster_list(self.cluster_id):
                        LOG.info("os install clear install global variables")
                        daisy_cmn.cluster_list_delete(self.cluster_id)
            if (host_status['os_progress'] !=
                host_last_status['os_progress'] or
                    host_status['os_status'] != host_last_status['os_status']):
                host_status['count'] = 0
                daisy_cmn.update_db_host_status(self.req, host_id, host_status)
        return hosts_status

    def _get_install_status(self, hosts_detail):
        query_count = 0
        hosts_last_status = {}
        while True:
            hosts_install_status = self._query_progress(
                hosts_last_status, hosts_detail)
            # if all hosts install over, break
            installing_hosts = [id for id in hosts_install_status.keys()
                                if hosts_install_status[id]['os_status'] ==
                                host_os_status['INSTALLING']]
            if not installing_hosts:
                break
            # after 3h, if some hosts are not 'active', label them to 'failed'.
            elif query_count * self.time_step >=\
                    self.cluster_hosts_install_timeout:
                for host_id, host_status in hosts_install_status.iteritems():
                    if (host_status['os_status'] !=
                        host_os_status['ACTIVE'] and
                        host_status['os_status'] !=
                            host_os_status['INSTALL_FAILED']):
                        # label the host install failed because of time out for
                        # 3h
                        host_status['os_status'] = host_os_status[
                            'INSTALL_FAILED']
                        host_status[
                            'messages'] = "cluster os installed timeout"
                        daisy_cmn.update_db_host_status(self.req, host_id,
                                                        host_status)
                if daisy_cmn.in_cluster_list(self.cluster_id):
                    LOG.info("os install clear install global variables")
                    daisy_cmn.cluster_list_delete(self.cluster_id)
                break
            else:
                query_count += 1
                hosts_last_status = hosts_install_status
                time.sleep(self.time_step)
        return hosts_install_status

    def install_os(self, hosts_detail, role_hosts_ids):
        # 15 hosts ,install 10 firstly ,then 5 host
        # output :host_detail=5 ,role_hosts_ids is failed host among 10 hosts
        if len(hosts_detail) > self.max_parallel_os_num:
            install_hosts = hosts_detail[:self.max_parallel_os_num]
            hosts_detail = hosts_detail[self.max_parallel_os_num:]
        else:
            install_hosts = hosts_detail
            hosts_detail = []

        install_hosts_id = [host_detail['id'] for host_detail in install_hosts]
        LOG.info(
            _("Begin install os for hosts %s." % ','.join(install_hosts_id)))
        daisy_cmn.os_install_start_time = time.time()
        for host_detail in install_hosts:
            host_manufacturer = host_detail['system'].get('manufacturer')
            if host_manufacturer == 'Cisco Systems Inc':
                host_detail['location'] = \
                    get_host_location_of_cisco(host_detail)
        self._begin_install_os(install_hosts)
        install_hosts = _rm_ipmi_failed_host(self.req, install_hosts)
        LOG.info(_("Begin to query install progress..."))
        # wait to install completely
        cluster_install_status = self._get_install_status(install_hosts)
        total_time_cost = str(
            round((time.time() - daisy_cmn.os_install_start_time) / 60, 2))
        if daisy_cmn.in_cluster_list(self.cluster_id):
            daisy_cmn.cluster_list_delete(self.cluster_id)
            LOG.info("Clear install global variables")
        LOG.info(
            _("It totally takes %s min for all host to install os"
              % total_time_cost))
        LOG.info(_("OS install in cluster %s result is:" % self.cluster_id))
        LOG.info(_("%s                                %s        %s" %
                   ('host-id', 'os-status', 'description')))

        for host_id, host_status in cluster_install_status.iteritems():
            LOG.info(
                _("%s   %s   %s" % (host_id, host_status['os_status'],
                                    host_status['messages'])))
            if host_id in role_hosts_ids:
                if host_status['os_status'] == host_os_status['ACTIVE']:
                    role_hosts_ids.remove(host_id)
        return (hosts_detail, role_hosts_ids)


def _os_thread_bin(req, host_ip, host_id, update_file, update_script):
    host_meta = {}
    password = "ossdbg1"
    LOG.info(_("Begin update os for host %s." % (host_ip)))
    cmd = 'mkdir -p /var/log/daisy/daisy_update/'
    daisy_cmn.subprocess_call(cmd)

    var_log_path = "/var/log/daisy/daisy_update/%s_update_os.log" % host_ip
    with open(var_log_path, "w+") as fp:
        cmd = '/var/lib/daisy/tecs/trustme.sh %s %s' % (host_ip, password)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -w %s "mkdir -p /home/daisy_update/"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -b -w %s  "rm -rf /home/daisy_update/*"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -w %s -c /var/lib/daisy/tecs/%s\
                 /var/lib/daisy/os/%s \
                 --dest=/home/daisy_update' % (
            host_ip, update_file, update_script,)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -w %s "chmod 777 /home/daisy_update/*"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        host_meta['os_progress'] = 30
        host_meta['os_status'] = host_os_status['UPDATING']
        host_meta['messages'] = "OS upgrading,copy file successfully"
        daisy_cmn.update_db_host_status(req, host_id, host_meta)
        try:
            exc_result = subprocess.check_output(
                'clush -S -w %s "cd /home/daisy_update/ && ./%s"' % (
                    host_ip, update_script),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            if e.returncode == 255 and "reboot" in e.output.strip():
                host_meta['os_progress'] = 100
                host_meta['os_status'] = host_os_status['ACTIVE']
                host_meta['messages'] = "upgrade OS successfully,os reboot"
                daisy_cmn.update_db_host_status(req, host_id, host_meta)
                LOG.info(
                    _("Update os for %s successfully,os reboot!" % host_ip))
                daisy_cmn.check_reboot_ping(host_ip)
            else:
                host_meta['os_progress'] = 0
                host_meta['os_status'] = host_os_status['UPDATE_FAILED']
                host_meta[
                    'messages'] = \
                    e.output.strip()[-400:-30].replace('\n', ' ')
                LOG.error(_("Update OS for %s failed!" % host_ip))
                daisy_cmn.update_db_host_status(req, host_id, host_meta)
            fp.write(e.output.strip())
        else:
            host_meta['os_progress'] = 100
            host_meta['os_status'] = host_os_status['ACTIVE']
            host_meta['messages'] = "upgrade OS successfully"
            daisy_cmn.update_db_host_status(req, host_id, host_meta)
            LOG.info(_("Upgrade OS for %s successfully!" % host_ip))
            fp.write(exc_result)
            if "reboot" in exc_result:
                daisy_cmn.check_reboot_ping(host_ip)


# this will be raise raise all the exceptions of the thread to log file
def os_thread_bin(req, host_ip, host_id, update_file, update_script):
    try:
        _os_thread_bin(req, host_ip, host_id, update_file, update_script)
    except Exception as e:
        LOG.exception(e.message)
        raise exception.ThreadBinException(e.message)


def _get_host_os_version(host_ip, host_pwd='ossdbg1'):
    version = ""
    tfg_version_file = '/usr/sbin/tfg_showversion'
    try:
        subprocess.check_output("sshpass -p %s ssh -o StrictHostKeyChecking=no"
                                " %s test -f %s" % (host_pwd, host_ip,
                                                    tfg_version_file),
                                shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        LOG.info(_("Host %s os version is TFG" % host_ip))
        return version
    try:
        process =\
            subprocess.Popen(["sshpass", "-p", "%s" % host_pwd, "ssh",
                              "-o StrictHostKeyChecking=no", "%s" % host_ip,
                              'tfg_showversion'], shell=False,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        version = process.stdout.read().strip('\n')
    except subprocess.CalledProcessError:
        msg = _("Get host %s os version by subprocess failed!" % host_ip)
        raise exception.SubprocessCmdFailed(message=msg)

    if version:
        LOG.info(_("Host %s os version is %s" % (host_ip, version)))
        return version
    else:
        msg = _("Get host %s os version by tfg_showversion failed!" % host_ip)
        LOG.error(msg)
        raise exception.Invalid(message=msg)


def _cmp_os_version(new_os_file, old_os_version,
                    target_host_ip, password='ossdbg1'):
    shell_file = '/usr/sbin/tfg_showversion'
    if old_os_version:
        try:
            subprocess.check_output("test -f %s" % shell_file, shell=True,
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            scripts = ["sshpass -p %s scp -r -o\
                        StrictHostKeyChecking=no %s:%s "
                       "/usr/sbin/" % (password, target_host_ip, shell_file)]
            daisy_cmn.run_scrip(scripts)

        cmp_script = "tfg_showversion /var/lib/daisy/tecs/%s %s"\
                     % (new_os_file, old_os_version)
        try:
            result = subprocess.check_output(cmp_script, shell=True,
                                             stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            return -1
    else:
        if new_os_file.find("Mimosa") != -1:
            return 0
        else:
            msg = _("Please use Mimosa os to upgrade instead of TFG")
            LOG.error(msg)
            raise exception.Forbidden(message=msg)
    return result.find("yes")


def upgrade(self, req, cluster_id, version_id, version_patch_id,
            update_script, update_file, hosts_list, update_object):
    reached_hosts = []
    for host_id in hosts_list:
        cluster_networks = daisy_cmn.get_cluster_networks_detail(
            req, cluster_id)
        host_meta = daisy_cmn.get_host_detail(req, host_id)
        host_ip = daisy_cmn.get_host_network_ip(
            req, host_meta, cluster_networks, 'MANAGEMENT')
        if daisy_cmn.get_local_deployment_ip(host_ip):
            LOG.exception("%s host os upgrade by hand" % host_ip)
            continue
        if update_object == "vplat":
            target_host_os = _get_host_os_version(
                host_ip, host_meta['root_pwd'])
            if _cmp_os_version(update_file, target_host_os, host_ip) == -1:
                LOG.warn(
                    _("new os version is lower than or equal to "
                        "host %s, don't need to upgrade!" % host_ip))
                host_meta['messages'] = "New os version is lower than" \
                                        " or equal to host %s." % host_ip
                daisy_cmn.update_db_host_status(req, host_id, host_meta)
                continue
        host_set = set()
        host_set.add(host_ip)
        unreached_hosts = daisy_cmn.check_ping_hosts(host_set, 5)
        if unreached_hosts:
            host_meta['messages'] = "hosts %s ping failed" % host_ip
            host_meta['os_status'] = host_os_status['UPDATE_FAILED']
            daisy_cmn.update_db_host_status(req, host_id, host_meta)
            continue
        else:
            daisy_cmn.subprocess_call(
                'sed -i "/%s/d" /root/.ssh/known_hosts' % host_ip)
            host_meta['messages'] = "begin to update os"
            host_meta['os_progress'] = 0
            host_meta['os_status'] = host_os_status['UPDATING']
            daisy_cmn.update_db_host_status(req, host_id, host_meta)
        reached_hosts.append({host_id: host_ip})
    upgrade_os(req, version_id, version_patch_id, update_script,
               update_file, reached_hosts, update_object)


def upgrade_os(req, version_id, version_patch_id, update_script,
               update_file, hosts_list, update_object):
    upgrade_hosts = []
    max_parallel_os_upgrade_number = int(CONF.max_parallel_os_upgrade_number)
    while hosts_list:
        host_meta = {}
        threads = []
        if len(hosts_list) > max_parallel_os_upgrade_number:
            upgrade_hosts = hosts_list[:max_parallel_os_upgrade_number]
            hosts_list = hosts_list[max_parallel_os_upgrade_number:]
        else:
            upgrade_hosts = hosts_list
            hosts_list = []
        for host_info in upgrade_hosts:
            host_id = host_info.keys()[0]
            host_ip = host_info.values()[0]
            host_meta['os_progress'] = 10
            host_meta['os_status'] = host_os_status['UPDATING']
            host_meta['messages'] = "os updating,begin copy iso"
            daisy_cmn.update_db_host_status(req, host_id, host_meta)
            t = threading.Thread(target=os_thread_bin, args=(req, host_ip,
                                                             host_id,
                                                             update_file,
                                                             update_script))
            t.setDaemon(True)
            t.start()
            threads.append(t)

        try:
            for t in threads:
                t.join()
        except:
            LOG.warn(_("Join update thread %s failed!" % t))
        else:
            for host_info in upgrade_hosts:
                update_failed_flag = False
                host_id = host_info.keys()[0]
                host_ip = host_info.values()[0]
                host = registry.get_host_metadata(req.context, host_id)
                if host['os_status'] == host_os_status['UPDATE_FAILED'] or\
                        host['os_status'] == host_os_status['INIT']:
                    update_failed_flag = True
                    raise exception.ThreadBinException(
                        "%s update os failed! %s" % (
                            host_ip, host['messages']))
                if not update_failed_flag:
                    host_meta = {}
                    host_meta['os_progress'] = 100
                    host_meta['os_status'] = host_os_status['ACTIVE']
                    host_meta['messages'] = "upgrade OS successfully"
                    daisy_cmn.update_db_host_status(req, host_id, host_meta,
                                                    version_id,
                                                    version_patch_id)
