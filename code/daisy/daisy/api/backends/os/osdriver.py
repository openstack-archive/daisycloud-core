# Copyright 2011 Justin Santa Barbara
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
OS_Driver base-classes:

    (Beginning of) the contract that os installation drivers must follow,
    and shared types that support that contract
"""
import copy
import json
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
import subprocess
from daisy import i18n
from daisy.common import utils
from daisy.common import exception
from daisy.api import common
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn
from oslo_utils import importutils

_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
LOG = logging.getLogger(__name__)

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


def get_daisy_conf():
    """get daisy_conf file
    """
    daisy_conf_file = "/home/daisy_install/daisy.conf"
    return daisy_conf_file


def pxe_server_build(req, install_meta):
    params = {'filters': {'type': 'system'}}
    try:
        networks = registry.get_all_networks(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)

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
    args = {'build_pxe': 'yes',
            'ethname_l': eth_name,
            'ip_addr_l': pxe_server_ip,
            'net_mask_l': net_mask,
            'client_ip_begin': client_ip_begin,
            'client_ip_end': client_ip_end}
    with open('/var/log/ironic/pxe.json', 'w') as f:
        json.dump(args, f, indent=2)
    f.close()
    try:
        _PIPE = subprocess.PIPE
        cmd = "/usr/bin/pxe_server_install /var/log/ironic/pxe.json && \
               chmod 755 /tftpboot -R"
        obj = subprocess.Popen(cmd,
                               shell=True,
                               stdout=_PIPE,
                               stderr=_PIPE)
        out, error = obj.communicate()
    except Exception as ex:
        LOG.error("%s: execute set pxe command failed.", ex)
        msg = "build pxe server failed"
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
                        if network['name'] in network_name][0]
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
                    if service_disk['disk_location'] == 'local' and\
                       service_disk['service'] == 'mongodb':
                        host_detail['mongodb_lv_size'] = service_disk['size']
                        break
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


def load_install_os_driver(os_install_type):
    """	Load a operating system installation driver.
    """
    os_installation_driver = "%s.install.OSInstall" % os_install_type

    LOG.info(_("Loading os driver '%s'") % os_installation_driver)
    try:
        driver = importutils.import_object_ns(
            'daisy.api.backends.os', os_installation_driver)
        return driver
    except ImportError:
        LOG.exception(
            _("Error, unable to load the os driver '%s'"
                % os_installation_driver))
        return None
