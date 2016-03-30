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
import re
import copy
import subprocess
import time

import traceback
import webob.exc
from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from webob.exc import HTTPServerError

from threading import Thread

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1

from daisy.common import exception
import daisy.registry.client.v1.api as registry
from daisy.api.backends.tecs import config
from daisy.api.backends import driver
from daisy.api.network_api import network as neutron
from ironicclient import client as ironic_client
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.tecs.common as tecs_cmn
import daisy.api.backends.tecs.disk_array as disk_array
from daisy.api.configset import manager

try:
    import simplejson as json
except ImportError:
    import json

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE

CONF = cfg.CONF
install_opts = [
    cfg.StrOpt('max_parallel_os_number', default=10,
               help='Maximum number of hosts install os at the same time.'),
]
CONF.register_opts(install_opts)

CONF.import_opt('disk_formats', 'daisy.common.config', group='image_format')
CONF.import_opt('container_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('image_property_quota', 'daisy.common.config')


tecs_state = tecs_cmn.TECS_STATE
daisy_tecs_path = tecs_cmn.daisy_tecs_path


def _invalid_bond_type(network_type, vswitch_type, bond_mode):
    msg = "Invalid bond_mode(%s) for %s in %s network" % (
        bond_mode, vswitch_type, network_type)
    raise_exception = False
    if bond_mode in ['0', '1', '2', '3', '4']:
        return

    if bond_mode and (2 == len(bond_mode.split(';'))):
        bond_mode, lacp_mode = bond_mode.split(';')
        if network_type in ['vxlan'] and vswitch_type in ['dvs', 'DVS']:
            if bond_mode in ['active-backup', 'balance-slb']:
                if lacp_mode not in ['off']:
                    raise_exception = True
            else:
                    raise_exception = True

        elif network_type in ['vlan'] and vswitch_type in ['dvs', 'DVS',
                                                           'ovs', 'OVS']:
            if bond_mode in ['balance-tcp']:
                if lacp_mode not in ['active', 'passive', 'off']:
                    raise_exception = True
            elif bond_mode in ['active-backup', 'balance-slb']:
                if lacp_mode not in ['off']:
                    raise_exception = True
            else:
                    raise_exception = True
    else:
        raise_exception = True

    if raise_exception:
        raise exception.InstallException(msg)


def _get_host_private_networks(host_detail, cluster_private_networks_name):
    """
    User member nic pci segment replace the bond pci, we use it generate the mappings.json.
    :param host_detail: host infos
    :param cluster_private_networks_name: network info in cluster
    :return:
    """
    host_private_networks = [hi for pn in cluster_private_networks_name
                             for hi in host_detail['interfaces'] 
                             for assigned_network in hi['assigned_networks'] 
                             if assigned_network and pn == assigned_network['name']]
                             
    # If port type is bond,use pci segment of member port replace pci1 & pci2 segments of bond port
    for interface_outer in host_private_networks:
        if 0 != cmp(interface_outer.get('type', None), "bond"):
            continue
        slave1 = interface_outer.get('slave1', None)
        slave2 = interface_outer.get('slave2', None)
        if not slave1 or not slave2:
            continue
        interface_outer.pop('pci')

        for interface_inner in host_detail['interfaces']:
            if 0 == cmp(interface_inner.get('name', None), slave1):
                interface_outer['pci1'] = interface_inner['pci']
            elif 0 == cmp(interface_inner.get('name', None), slave2):
                interface_outer['pci2'] = interface_inner['pci']
    return host_private_networks

def _write_private_network_cfg_to_json(req, cluster_id, private_networks):
    """
    Generate cluster private network json. We use the json file after tecs is installed.
    :param private_networks: cluster private network params set.
    :return:
    """
    if not private_networks:
        LOG.error("private networks can't be empty!")
        return False

    cluster_hosts_network_cfg = {}
    hosts_network_cfg = {}
    for k in private_networks.keys():
        private_network_info = {}
        for private_network in private_networks[k]:
            # host_interface
            type = private_network.get('type', None)
            name = private_network.get('name', None)
            assign_networks = private_network.get('assigned_networks', None)
            slave1 =  private_network.get('slave1', None)
            slave2 =  private_network.get('slave2', None)
            pci = private_network.get('pci', None)
            pci1 = private_network.get('pci1', None)
            pci2 = private_network.get('pci2', None)
            mode = private_network.get('mode', None)
            if not type or not name or not assign_networks:
                LOG.error("host_interface params invalid in private networks!")
                continue

            for assign_network in assign_networks:
                # network
                #network_type = assign_network.get('network_type', None)
                vswitch_type_network = daisy_cmn.get_assigned_network(
                    req, private_network['id'], assign_network['id'])
                    
                vswitch_type = vswitch_type_network['vswitch_type']
                physnet_name = assign_network.get('name', None)
                mtu = assign_network.get('mtu', None)
                if not vswitch_type or not physnet_name:
                    LOG.error("private networks vswitch_type or physnet name is invalid!")
                    continue

                physnet_name_conf = {}
                physnet_name_conf['type'] = type
                physnet_name_conf['name'] = name
                physnet_name_conf['vswitch_type'] = vswitch_type
                if mtu:
                    physnet_name_conf['mtu'] = mtu
                # physnet_name_conf['ml2'] = ml2_type + "(direct)"
                if 0 == cmp("bond", type):
                    if not pci1 or not pci2 or not slave1 or not slave2 or not mode:
                        LOG.error("when type is 'bond',input params is invalid in private networks!")
                        continue
                    physnet_name_conf['slave1'] = slave1
                    physnet_name_conf['slave2'] = slave2
                    physnet_name_conf['pci1'] = pci1
                    physnet_name_conf['pci2'] = pci2
                    physnet_name_conf['mode'] = mode
                    _invalid_bond_type('vlan', 'OVS', mode)
                elif 0 == cmp("ether", type):
                    if not pci:
                        LOG.error("when type is 'ether',input params is invalid in private networks!")
                        continue
                    physnet_name_conf['pci'] = pci

                if not physnet_name_conf:
                    continue
                private_network_info[physnet_name] =  physnet_name_conf

        if not private_network_info:
            continue
        hosts_network_cfg[k] = private_network_info

    if not hosts_network_cfg:
        return False
    cluster_hosts_network_cfg['hosts'] = hosts_network_cfg
    mkdir_daisy_tecs_path = "mkdir -p " + daisy_tecs_path + cluster_id
    daisy_cmn.subprocess_call(mkdir_daisy_tecs_path)
    mapping_json = daisy_tecs_path + "/" + cluster_id + "/" + "mappings.json"
    with open(mapping_json, "w+") as fp:
        fp.write(json.dumps(cluster_hosts_network_cfg))
    return True

def _conf_private_network(req, cluster_id, host_private_networks_dict, cluster_private_network_dict):
    if not host_private_networks_dict:
        LOG.info(_("No private network need config"))
        return {}

    # different host(with ip) in host_private_networks_dict
    config_neutron_ml2_vlan_ranges = []
    for k in host_private_networks_dict.keys():
        host_private_networks = host_private_networks_dict[k]
        # different private network plane in host_interface
        for host_private_network in host_private_networks:
            assigned_networks = host_private_network.get('assigned_networks', None)
            if not assigned_networks:
                break
            private_network_info = \
                [network for assigned_network in assigned_networks
                 for network in cluster_private_network_dict
                     if assigned_network and assigned_network['name'] == network['name']]
           
            host_private_network['assigned_networks'] = private_network_info
            config_neutron_ml2_vlan_ranges += \
                ["%(name)s:%(vlan_start)s:%(vlan_end)s" %
                {'name':network['name'], 'vlan_start':network['vlan_start'], 'vlan_end':network['vlan_end']}
                 for network in private_network_info
                 if network['name'] and network['vlan_start'] and network['vlan_end']]

    physic_network_cfg = {}
    if _write_private_network_cfg_to_json(req, cluster_id, host_private_networks_dict):
        physic_network_cfg['json_path'] = daisy_tecs_path + "/" + cluster_id + "/" + "mappings.json"
    if config_neutron_ml2_vlan_ranges:
        host_private_networks_vlan_range = ",".join(list(set(config_neutron_ml2_vlan_ranges)))
        physic_network_cfg['vlan_ranges'] = host_private_networks_vlan_range
    return physic_network_cfg


def _enable_network(host_networks_dict):
    for network in host_networks_dict:
        if network != []:
            return True
    return False


def _get_dvs_network_type(vxlan, vlan):
    if _enable_network(vxlan):
        return 'vxlan', vxlan
    elif _enable_network(vlan):
        return 'vlan', vlan
    else:
        return None, None


def _get_vtep_ip_ranges(ip_ranges):
    vtep_ip_ranges = []
    for ip_range in ip_ranges:
        ip_range_start = ip_range.get('start')
        ip_range_end = ip_range.get('end')
        if ip_range_start and ip_range_end:
            vtep_ip_ranges.append(
                [ip_range_start.encode('utf8'),
                 ip_range_end.encode('utf8')])
    return vtep_ip_ranges


def _get_dvs_vxlan_info(interfaces, mode_str):
    vxlan_nic_info = ''
    for interface in interfaces:
        if interface['type'] == 'ether':
            vxlan_nic_info = interface['name']
        elif interface['type'] == 'bond':
            _invalid_bond_type('vxlan', 'DVS', interface.get('mode'))
            name = interface.get('name', 'bond1')
            if interface.get('mode') in ['0', '1', '2', '3', '4']:
                try:
                    bond_mode = mode_str[
                        'vxlan'].get(interface.get('mode'))
                except:
                    bond_mode = mode_str['vxlan']['0']
                vxlan_nic_info = name + bond_mode % (
                    interface['slave1'], interface['slave2'])
            else:
                vxlan_nic_info = "%s(%s;%s-%s)" % (
                    name, interface.get('mode'),
                    interface['slave1'], interface['slave2'])
    return vxlan_nic_info


def _get_dvs_domain_id(assign_network, dvs_domain_id, host_ip):
    domain_id = assign_network.get('dvs_domain_id')
    if not domain_id:
        domain_id = '0'

    domain_ip = dvs_domain_id.get(domain_id, [])
    domain_ip.append(host_ip)
    domain_ip = {domain_id.encode('utf8'): domain_ip}
    return domain_ip


def _get_bridge_mappings(interface):
    try:
        interface = interface['assigned_networks'][0]
    except:
        return {}

    bridge_mappings = {}
    if interface.get('network_type') in ['PRIVATE']:
        phynet_name, nic = interface.get(
            'physnet_name').split('_')
        phynet_name = interface.get('name')
        if phynet_name and nic:
            bridge_mappings.update({nic: phynet_name})
    return bridge_mappings


def _convert_bridge_mappings2list(bridge_mappings):
    bridge_maps = []
    for nic, phynet in bridge_mappings.items():
        bridge_maps.append('%s:br_%s' % (phynet, nic))
    return set(bridge_maps)


def _convert_physical_mappings2list(physical_mappings):
    physical_maps = []
    for phynet, nic_info in physical_mappings.items():
        physical_maps.append('%s:%s' % (phynet, nic_info))
    return set(physical_maps)


def _get_physical_mappings(interface, mode_str, bridge_mappings):
    # bridge_mappings = {'eth0':'phynet1': 'bond0':'phynet2'}
    vlan_nic_map_info = {}
    phynic_name = interface.get('name')
    physnet_name = bridge_mappings.get(phynic_name)
    if interface['type'] == 'bond':
        _invalid_bond_type('vlan', 'DVS', interface.get('mode'))
        if interface.get('mode') in ['0', '1', '2', '3', '4']:
            try:
                bond_mode = mode_str['vlan'].get(interface.get('mode'))
            except:
                bond_mode = mode_str['vlan']['0']
            vlan_nic_map_info[physnet_name] = phynic_name + bond_mode % (
                interface['slave1'], interface['slave2'])
        else:
            # interface.get('mode') = active-backup;off
            vlan_nic_map_info[physnet_name] = "%s(%s;%s-%s)" % (
                phynic_name, interface.get('mode'),
                interface['slave1'], interface['slave2'])
    else:
        vlan_nic_map_info[physnet_name] = phynic_name

    return vlan_nic_map_info


def get_network_config_for_dvs(host_private_networks_dict,
                               cluster_private_network_dict):
    # different private network plane in host_interface
    host_private_networks_dict_for_dvs = copy.deepcopy(
        host_private_networks_dict)

    for host_private_network in host_private_networks_dict_for_dvs:
        private_networks = host_private_network.get(
            'assigned_networks', None)
        if not private_networks:
            break
        private_network_info = \
            [network for private_network in private_networks
             for network in cluster_private_network_dict
                if private_network and private_network['name'] == network['name']]
        host_private_network['assigned_networks'] = private_network_info
    return host_private_networks_dict_for_dvs


def conf_dvs(req, host_vxlan_networks_dict, host_private_networks_dict):
    mode_str = {
        'vxlan':
        {
            '0': '(active-backup;off;%s-%s)',
            '1': '(balance-slb;off;%s-%s)',
        },
        'vlan': {
            '0': '(active-backup;off;%s-%s)',
            '1': '(balance-slb;off;%s-%s)',
            '2': '(balance-tcp;active;%s-%s)'
        }
    }

    network_type, networks_dict = _get_dvs_network_type(
        host_vxlan_networks_dict, host_private_networks_dict)

    if not network_type:
        return {}

    dvs_config = {}

    network_config = {}
    vswitch_type = {}
    physnics_config = {}
    installed_dvs = []
    installed_ovs = []
    network_config['network_type'] = network_type

    # for vxlan
    network_config['vtep_ip_ranges'] = []
    dvs_domain_id = {}

    # for vlan
    bridge_mappings = {}
    physical_mappings = {}

    for host_ip, interfaces in networks_dict.items():
        host_ip = host_ip.encode('utf8')
        assign_network = daisy_cmn.get_assigned_network(
            req, interfaces[0]['id'],
            interfaces[0]['assigned_networks'][0].get('id'))

        if assign_network['vswitch_type'] in ['dvs', 'DVS']:
            installed_dvs.append(host_ip)
        elif assign_network['vswitch_type'] in ['ovs', 'OVS']:
            installed_ovs.append(host_ip)

        if network_type == 'vxlan':
            network_config['vtep_ip_ranges'].extend(
                _get_vtep_ip_ranges(
                    interfaces[0]['assigned_networks'][0].get('ip_ranges')))

            dvs_domain_id.update(
                _get_dvs_domain_id(assign_network, dvs_domain_id, host_ip))

            if not physnics_config.get('vxlan_info'):
                physnics_config['vxlan_info'] = _get_dvs_vxlan_info(
                    interfaces, mode_str)

        if network_type == 'vlan':
            for interface in interfaces:
                bridge_mapping = _get_bridge_mappings(interface)
                physical_mapping = _get_physical_mappings(
                    interface, mode_str, bridge_mapping)
                bridge_mappings.update(bridge_mapping)
                physical_mappings.update(physical_mapping)

    vswitch_type['ovdk'] = installed_dvs
    vswitch_type['ovs_agent_patch'] = installed_ovs
    physnics_config['dvs_domain_id'] = dvs_domain_id
    physnics_config['physical_mappings'] = ",".join(
        _convert_physical_mappings2list(physical_mappings))
    physnics_config['bridge_mappings'] = ",".join(
        _convert_bridge_mappings2list(bridge_mappings))

    dvs_config['vswitch_type'] = vswitch_type
    dvs_config['network_config'] = network_config
    dvs_config['physnics_config'] = physnics_config

    return dvs_config


def _get_interfaces_network(req, host_detail, cluster_networks):
    has_interfaces = {}
    host_mngt_network = tecs_cmn.get_host_interface_by_network(host_detail, 'MANAGEMENT')
    host_mgnt_ip = tecs_cmn.get_host_network_ip(req, host_detail, cluster_networks, 'MANAGEMENT')
    host_mgnt_netmask = tecs_cmn.get_network_netmask(cluster_networks, 'MANAGEMENT')
    host_mngt_network['ip'] = host_mgnt_ip
    host_mngt_network['netmask'] = host_mgnt_netmask
    has_interfaces['management'] = host_mngt_network

    host_deploy_network = tecs_cmn.get_host_interface_by_network(host_detail, 'DEPLOYMENT')
    host_deploy_network_info = tecs_cmn.get_host_interface_by_network(host_detail, 'DEPLOYMENT')   
    #note:"is_deployment" can't label delpoyment network, it only used to label dhcp mac
    if host_deploy_network_info:
        host_deploy_ip = tecs_cmn.get_host_network_ip(req, host_detail, cluster_networks, 'DEPLOYMENT')
        host_deploy_netmask = tecs_cmn.get_network_netmask(cluster_networks, 'DEPLOYMENT')
        host_deploy_network_info['ip'] = host_deploy_ip
        host_deploy_network_info['netmask'] = host_deploy_netmask
        has_interfaces['deployment'] = host_deploy_network_info
        

    host_storage_network_info = tecs_cmn.get_host_interface_by_network(host_detail, 'STORAGE')
    if host_storage_network_info:
        host_storage_ip = tecs_cmn.get_host_network_ip(req, host_detail, cluster_networks, 'STORAGE')
        host_storage_netmask = tecs_cmn.get_network_netmask(cluster_networks, 'STORAGE')
        host_storage_network_info['ip'] = host_storage_ip
        host_storage_network_info['netmask'] = host_storage_netmask
        has_interfaces['storage'] = host_storage_network_info
        
    host_public_network_info = tecs_cmn.get_host_interface_by_network(host_detail, 'PUBLIC')
    
    if host_public_network_info:
        public_vlan_id = tecs_cmn.get_network_vlan_id(cluster_networks, 'PUBLIC')
        
        if public_vlan_id:
            public_nic_name = host_public_network_info['name'] + '.' + public_vlan_id
        else:
            public_nic_name = host_public_network_info['name']

        host_public_ip = tecs_cmn.get_host_network_ip(req, host_detail, cluster_networks, 'PUBLIC')
        host_public_netmask = tecs_cmn.get_network_netmask(cluster_networks, 'PUBLIC')
        host_public_network_info['ip'] = host_public_ip
        host_public_network_info['name'] = public_nic_name
        host_public_network_info['netmask'] = host_public_netmask
        has_interfaces['public'] = host_public_network_info
    return has_interfaces

def _get_host_nic_name(cluster_network, host_detail):
    """
    Different networking will generate different ha port name, the rule of generation
    is describe in comment.
    :param cluster_network: Network info in cluster.
    :param host_detail:
    :return:
    """
    copy_host_detail = copy.deepcopy(host_detail)

    mgr_interface_info = tecs_cmn.get_host_interface_by_network(copy_host_detail, 'MANAGEMENT')
    nic_info = [network
                for network in cluster_network
                for netname in mgr_interface_info.get('assigned_networks', None)
                if network.get('name', None) == netname]

    nic_capability = [info['capability'] for info in nic_info if info['network_type'] != "PRIVATE"]
    if not nic_capability or nic_capability == [None]:
        return mgr_interface_info['name']

    mgr_nic_info = [mgr_net for mgr_net in nic_info if mgr_net['network_type'] == "MANAGEMENT"][0]
    # if private and management plane is unifier
    if set(["PRIVATE", "MANAGEMENT"]).issubset(set([info['network_type'] for info in nic_info])):
        # if type = 'ether' and  'ovs' not in ml2  and management is 'high'
        if "ether" == mgr_interface_info.get('type', None) and \
           "ovs" not in [mgr_interface_info.get('vswitch_type', None)] and \
           "high" == mgr_nic_info['capability']:
            return mgr_interface_info['name']

        # if ip at outer
        if mgr_interface_info.get('ip', None) and mgr_interface_info.get('name', None):
            return "v_" + mgr_interface_info['name']
        # ip at inner
        elif mgr_nic_info.get('ip', None):
            return "managent"

    if "low" not in nic_capability:
        return mgr_interface_info['name']

    # if ip at outer
    if mgr_interface_info.get('ip', None) and mgr_interface_info.get('name', None):
         return "v_" + mgr_interface_info['name']

    # ip at inner
    elif mgr_nic_info.get('ip', None):
        return "managent"

def get_share_disk_services(req, role_id):
    service_disks = tecs_cmn.get_service_disk_list(req, {'role_id':role_id})
    share_disk_services = []
    
    for service_disk in service_disks:
        if service_disk['disk_location'] == 'share':
            share_disk_services.append(service_disk['service'])
    return share_disk_services

def get_cluster_tecs_config(req, cluster_id):
    LOG.info(_("Get tecs config from database..."))
    params = dict(limit=1000000)
    roles = daisy_cmn.get_cluster_roles_detail(req,cluster_id)
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    try:
        all_services = registry.get_services_detail(req.context, **params)
        all_components = registry.get_components_detail(req.context, **params)
        cluster_data = registry.get_cluster_metadata(req.context, cluster_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    
    cluster_private_network_dict = [network for network in cluster_networks if network['network_type'] == 'PRIVATE']
    cluster_private_networks_name = [network['name'] for network in cluster_private_network_dict]

    cluster_vxlan_network_dict = [network for network in cluster_networks if network['network_type'] == 'VXLAN']

    tecs_config = {}
    tecs_config.update({'OTHER':{}})
    other_config = tecs_config['OTHER']
    other_config.update({'cluster_data':cluster_data})
    tecs_installed_hosts = set()
    host_private_networks_dict = {}
    host_vxlan_network_dict = {}
    mgnt_ip_list = set()
    host_private_networks_dict_for_dvs = {}
    zenic_cfg = {}

    for role in roles:
        if role['name'] == 'ZENIC_NFM':
            zenic_cfg['vip'] = role['vip']
        if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
            continue
        try:
            role_service_ids = registry.get_role_services(req.context, role['id'])
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)

        role_services_detail = [asc for rsci in role_service_ids for asc in all_services if asc['id'] == rsci['service_id']]
        component_id_to_name = dict([(ac['id'], ac['name'])  for ac in all_components])
        service_components = dict([(scd['name'], component_id_to_name[scd['component_id']]) for scd in role_services_detail])

        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])

        host_interfaces = []
        for role_host in role_hosts:
            host_detail = daisy_cmn.get_host_detail(req, role_host['host_id'])

            sorted_host_detail = tecs_cmn.sort_interfaces_by_pci(host_detail)
            host_private_networks_list = _get_host_private_networks(sorted_host_detail,
                                                                    cluster_private_networks_name)
            # get ha nic port name
            if not other_config.has_key('ha_nic_name') and role['name'] == "CONTROLLER_HA":
                mgr_nic_name = _get_host_nic_name(cluster_networks, sorted_host_detail)
                mgr_vlan_id = tecs_cmn.get_mngt_network_vlan_id(cluster_networks)
                if mgr_vlan_id:
                    mgr_nic_name = mgr_nic_name + '.' + mgr_vlan_id
                other_config.update({'ha_nic_name':mgr_nic_name})

            has_interfaces = _get_interfaces_network(req, host_detail, cluster_networks)
            has_interfaces.update({'name':host_detail['name']})
            host_interfaces.append(has_interfaces)
            # mangement network must be configed
            host_mgnt_ip = has_interfaces['management']['ip']

            # host_mgnt_ip used to label who the private networks is
            host_private_networks_dict[host_mgnt_ip] = host_private_networks_list
            if role['name'] == 'COMPUTER':
                host_vxlan_network_list = _get_host_private_networks(sorted_host_detail, ['VXLAN'])
                if host_vxlan_network_list:
                    host_private_networks_dict_for_dvs = {}
                    host_vxlan_network_dict[host_mgnt_ip] = get_network_config_for_dvs(
                        host_vxlan_network_list, cluster_vxlan_network_dict)
                elif host_private_networks_list:
                    host_vxlan_network_dict = {}
                    host_private_networks_dict_for_dvs[host_mgnt_ip] = get_network_config_for_dvs(
                        host_private_networks_list, cluster_private_network_dict)

            #get host ip of tecs is active
            if (role_host['status'] == tecs_state['ACTIVE'] or
                role_host['status'] == tecs_state['UPDATING'] or
                role_host['status'] == tecs_state['UPDATE_FAILED']):
                tecs_installed_hosts.add(host_mgnt_ip)
            else:
                mgnt_ip_list.add(host_mgnt_ip)

        share_disk_services = get_share_disk_services(req, role['id'])
        is_ha = re.match(".*_HA$", role['name']) is not None
        if host_interfaces:
            if role['public_vip'] and not host_interfaces[0].has_key('public'):
                msg = "no public networkplane found while role has public vip"
                LOG.error(msg)
                raise exception.NotFound(message=msg)

            tecs_config.update({role['name']: {'services': service_components,
                                               'vip': role['vip'],
                                               'host_interfaces': host_interfaces,
                                               'share_disk_services': share_disk_services
                                               }})
        if is_ha:
            tecs_config[role['name']]['ntp_server'] = role['ntp_server']
            tecs_config[role['name']]['public_vip'] = role['public_vip']
            tecs_config[role['name']]['glance_vip'] = role['glance_vip']
            tecs_config[role['name']]['db_vip'] = role['db_vip']

    other_config.update({'tecs_installed_hosts':tecs_installed_hosts})
    # replace private network
    physic_network_cfg = _conf_private_network(req, cluster_id, host_private_networks_dict, cluster_private_network_dict)
    dvs_cfg = conf_dvs(req, host_vxlan_network_dict, host_private_networks_dict_for_dvs)
    other_config.update({'physic_network_config':physic_network_cfg})
    other_config.update({'dvs_config':dvs_cfg})
    other_config.update({'zenic_config':zenic_cfg})
    return (tecs_config, mgnt_ip_list)


def get_host_name_and_mgnt_ip(tecs_config):
    name_ip_list = []
    ip_list = []
    nodes_ips = {'ha': [], 'lb': [], 'computer': []}

    for role_name, role_configs in tecs_config.items():
        if role_name == "OTHER":
                continue
        for host in role_configs['host_interfaces']:
            ip_domain_dict = {}
            host_mgt = host['management']
            if host_mgt['ip'] not in ip_list:
                ip_list.append(host_mgt['ip'])
                ip_domain_dict.update({host['name']: host_mgt['ip']})
                name_ip_list.append(ip_domain_dict)

            if role_name == 'CONTROLLER_HA':
                nodes_ips['ha'].append(host_mgt['ip'])
            if role_name == 'CONTROLLER_LB':
                nodes_ips['lb'].append(host_mgt['ip'])
            if role_name == 'COMPUTER':
                nodes_ips['computer'].append(host_mgt['ip'])
    return name_ip_list, nodes_ips


def replace_ip_with_domain_name(req, tecs_config):
    domain_ip_list = []
    ip_list = []
    lb_float_ip = tecs_config['CONTROLLER_LB']['vip']
    for role_name, role_configs in tecs_config.items():
        if role_name == "OTHER":
                continue
        is_ha = re.match(".*_HA$", role_name) is not None
        is_lb = re.match(".*_LB$", role_name) is not None

        for host in role_configs['host_interfaces']:
            ip_domain_dict = {}
            host_mgt = host['management']
            if host_mgt['ip'] not in ip_list:
                ip_list.append(host_mgt['ip'])
                ip_domain_dict.update({host['name']: host_mgt['ip']})
                domain_ip_list.append(ip_domain_dict)
            host_mgt['ip'] = host['name']

        if is_ha and role_configs.get('vip'):
            domain_ip_list.append({'ha-vip': role_configs['vip']})
            if role_configs['ntp_server'] == role_configs['vip']:
                role_configs['ntp_server'] = 'ha-vip'
            elif role_configs['ntp_server'] == lb_float_ip:
                role_configs['ntp_server'] = 'lb-vip'
            role_configs['vip'] = 'ha-vip'

        if role_configs.get('public_vip'):
            domain_ip_list.append({'public-vip': role_configs['public_vip']})
            role_configs['public_vip'] = 'public-vip'
        if role_configs.get('glance_vip'):
            domain_ip_list.append({'glance-vip': role_configs['glance_vip']})
            role_configs['glance_vip'] = 'glance-vip'
        if role_configs.get('db_vip'):
            domain_ip_list.append({'db-vip': role_configs['db_vip']})
            role_configs['db_vip'] = 'db-vip'

        if is_lb and role_configs.get('vip'):
            domain_ip_list.append({'lb-vip': role_configs['vip']})
            role_configs['vip'] = 'lb-vip'
    return domain_ip_list


def config_dnsmasq_server(host_ip_list, domain_ip_list, password='ossdbg1'):
    dns_conf = "/etc/dnsmasq.conf"
    for host_ip in host_ip_list:
        try:
            result = subprocess.check_output(
                "sshpass -p %s ssh -o StrictHostKeyChecking=no %s "
                "test -f %s" % (password, host_ip, dns_conf),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            msg = '%s does not exist in %s' % (dns_conf, host_ip)
            LOG.error(msg)
            raise exception.NotFound(message=msg)

        config_scripts = [
            "sed -i '/^[^#]/s/no-resolv[[:space:]]*/\#no-resolv/' %s" % dns_conf,
            "sed -i '/^[^#]/s/no-poll[[:space:]]*/\#no-poll/' %s" % dns_conf,
            "cache_size_linenumber=`grep -n 'cache-size=' %s| awk -F ':' "
            "'{print $1}'` && [ ! -z $cache_size_linenumber ] && sed -i "
            "${cache_size_linenumber}d %s" % (dns_conf, dns_conf),
            "echo 'cache-size=3000' >> %s" % dns_conf]

        tecs_cmn.run_scrip(config_scripts, host_ip, password)

        config_ip_scripts = []
        for domain_name_ip in domain_ip_list:
            domain_name = domain_name_ip.keys()[0]
            domain_ip = domain_name_ip.values()[0]
            config_ip_scripts.append(
                "controller1_linenumber=`grep -n 'address=/%s' %s| awk -F ':' "
                "'{print $1}'` && [ ! -z ${controller1_linenumber} ] && "
                "sed -i ${controller1_linenumber}d %s" %
                (domain_name, dns_conf, dns_conf))
            config_ip_scripts.append("echo 'address=/%s/%s' >> %s" %
                                     (domain_name, domain_ip, dns_conf))
        tecs_cmn.run_scrip(config_ip_scripts, host_ip, password)

        service_start_scripts = [
            "dns_linenumber=`grep -n \"^[[:space:]]*ExecStart=/usr/sbin/dnsmasq -k\" "
            "/usr/lib/systemd/system/dnsmasq.service|cut -d \":\" -f 1` && "
            "sed -i \"${dns_linenumber}c ExecStart=/usr/sbin/dnsmasq -k "
            "--dns-forward-max=50000\" /usr/lib/systemd/system/dnsmasq.service",
            "for i in `ps -elf | grep dnsmasq |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $i;done ",
            "systemctl daemon-reload && systemctl enable dnsmasq.service && "
            "systemctl restart dnsmasq.service"]
        tecs_cmn.run_scrip(service_start_scripts, host_ip, password)


def config_dnsmasq_client(host_ip_list, ha_ip_list, password='ossdbg1'):
    dns_client_file = "/etc/resolv.conf"
    config_scripts = ["rm -rf %s" % dns_client_file]
    for ha_ip in ha_ip_list:
        config_scripts.append("echo 'nameserver %s' >> %s" %
                              (ha_ip, dns_client_file))
    for host_ip in host_ip_list:
        tecs_cmn.run_scrip(config_scripts, host_ip, password)
    tecs_cmn.run_scrip(config_scripts)


def config_nodes_hosts(host_ip_list, domain_ip, password='ossdbg1'):
    hosts_file = "/etc/hosts"
    config_scripts = []
    for name_ip in domain_ip:
        config_scripts.append("linenumber=`grep -n '%s' /etc/hosts | "
                              "awk -F '' '{print $1}'` && "
                              "[ ! -z $linenumber ] && "
                              "sed -i ${linenumber}d %s" %
                              (name_ip.keys()[0], hosts_file))
        config_scripts.append("echo '%s %s' >> %s" % (name_ip.values()[0],
                                                      name_ip.keys()[0],
                                                      hosts_file))

    for host_ip in host_ip_list:
        tecs_cmn.run_scrip(config_scripts, host_ip, password)
    tecs_cmn.run_scrip(config_scripts)


def revise_nova_config(computer_nodes, ha_vip, public_vip, compute_ip_domain,
                       password='ossdbg1'):
    nova_file = "/etc/nova/nova.conf"
    for host_ip in computer_nodes:
        scripts = []
        if public_vip:
            scripts.extend(["linenumber=`grep -n '^novncproxy_base_url' %s | "
                            "awk -F ':' '{print $1}'`" % nova_file,
                           'sed -i "${linenumber}s/public-vip/%s/" %s' %
                           (public_vip, nova_file)])
        else:
            scripts.extend(["linenumber=`grep -n '^novncproxy_base_url' %s | "
                            "awk -F ':' '{print $1}'`" % nova_file,
                            'sed -i "${linenumber}s/ha-vip/%s/" %s' %
                            (ha_vip, nova_file)])
        scripts.extend(["linenumber=`grep -n '^vncserver_proxyclient_address' "
                        "%s | awk -F ':' '{print $1}'`" % nova_file,
                        'sed -i "${linenumber}s/127.0.0.1/%s/" %s' %
                        (compute_ip_domain[host_ip], nova_file),
                        "systemctl restart openstack-nova-compute.service "])
        tecs_cmn.run_scrip(scripts, host_ip, password)


def revise_horizon_config(ha_nodes, ha_vip, public_vip, password='ossdbg1'):
    dashboard_file = "/etc/httpd/conf.d/15-horizon_vhost.conf"
    for host_ip in ha_nodes:
        config_scripts = ["linenumber1=`grep -n 'ServerAlias %s' "
                          "%s| awk -F ':' '{print $1}'` && "
                          "[ ! -z ${linenumber1} ] && sed -i "
                          "${linenumber1}d %s" % (host_ip,
                                                  dashboard_file,
                                                  dashboard_file),
        "linenumber2=`grep -n 'ServerAlias %s' %s| awk -F ':' '"
        "{print $1}'` && [ ! -z ${linenumber2} ] && sed -i "
        "${linenumber2}d %s" % (ha_vip, dashboard_file,
                                dashboard_file),
        "linenumber3=`grep -n 'ServerAlias %s' %s| awk -F ':' '"
        "{print $1}'` && [ ! -z ${linenumber3} ] && sed -i "
        "${linenumber3}d %s" % (public_vip, dashboard_file,
                                dashboard_file),
        'dasboard_linenumber1=`grep -n "ServerAlias localhost" '
        '%s|cut -d ":" -f 1` && sed -i "${dasboard_linenumber1}a '
        'ServerAlias %s" %s' % (dashboard_file, host_ip,
                                dashboard_file),
        'dasboard_linenumber1=`grep -n "ServerAlias localhost" %s'
        '|cut -d ":" -f 1` && sed -i "${dasboard_linenumber1}a '
        'ServerAlias %s" %s' % (dashboard_file, ha_vip,
                                dashboard_file)]
        if public_vip:
            config_scripts.append('dasboard_linenumber2=`grep -n '
                                  '"ServerAlias localhost" %s|cut '
                                  '-d ":" -f 1` && sed -i '
                                  '"${dasboard_linenumber2}a '
                                  'ServerAlias %s" %s' %
                                  (dashboard_file, public_vip,
                                   dashboard_file))

        tecs_cmn.run_scrip(config_scripts, host_ip, password)

    restart_http_scripts = ['systemctl daemon-reload &&'
                            'systemctl restart httpd.service']
    tecs_cmn.run_scrip(restart_http_scripts, ha_vip, password)


class TECSInstallTask(Thread):
    """
    Class for install tecs bin.
    """
    """ Definition for install states."""

    def __init__(self, req, cluster_id):
        super(TECSInstallTask, self).__init__()
        self.req = req
        self.cluster_id = cluster_id
        self.progress = 0
        self.state = tecs_state['INIT']
        self.message = ""
        self.tecs_config_file = ''
        self.mgnt_ip_list = ''
        self.install_log_fp = None
        self.last_line_num = 0
        self.need_install = False
        self.ping_times = 36
        self.log_file = "/var/log/daisy/tecs_%s_install.log" % self.cluster_id
        self.dns_name_ip = []
        self.password = 'ossdbg1'
        self.nodes_ips = {}

    def _check_install_log(self, tell_pos):
        with open(self.log_file, "r") as tmp_fp:
            tmp_fp.seek(tell_pos, os.SEEK_SET)
            line_num = self.last_line_num
            for lnum, lcontent in enumerate(tmp_fp, 1):
                tell_pos = tmp_fp.tell()
                line_num += 1
                LOG.debug("<<<Line,%s:Content,%s>>>", line_num, lcontent)
                if -1 != lcontent.find("Preparing servers"):
                    self.progress = 3

                if -1 != lcontent.find("successfully"):
                    self.progress = 100
                elif -1 != lcontent.find("Error") \
                    or -1 != lcontent.find("ERROR") \
                    or -1 != lcontent.find("error") \
                    or -1 != lcontent.find("not found"):
                    self.state = tecs_state['INSTALL_FAILED']
                    self.message = "Tecs install error, see line %s in '%s'" % (line_num,self.log_file)
                    raise exception.InstallException(self.message)
        self.last_line_num = line_num
        return tell_pos

    def _calc_progress(self, path):
        """
        Calculate the progress of installing bin.
        :param path: directory contain ".pp" and ".log" files
        :return: installing progress(between 1~100)
        """
        ppcount = logcount = 0
        for file in os.listdir(path):
            if file.endswith(".log"):
                logcount += 1
            elif file.endswith(".pp"):
                ppcount += 1

        progress = 0
        if 0 != ppcount:
            progress = (logcount * 100.00)/ ppcount
        return progress

    def _update_install_progress_to_db(self):
        """
        Update progress of intallation to db.
        :return:
        """
        roles = daisy_cmn.get_cluster_roles_detail(self.req,self.cluster_id)
        for role in roles:
            if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
                continue
            role_hosts = daisy_cmn.get_hosts_of_role(self.req, role['id'])
            for role_host in role_hosts:
                if role_host['status'] != tecs_state['ACTIVE']:
                    self.need_install = True
                    role_host['status'] = self.state
                    role_host['progress'] = self.progress
                    role_host['messages'] = self.message
                    daisy_cmn.update_role_host(self.req, role_host['id'], role_host)
                    role['progress'] = self.progress
                    role['status'] = self.state
                    role['messages'] = self.message
                    daisy_cmn.update_role(self.req, role['id'], role)
                
    def _generate_tecs_config_file(self, cluster_id, tecs_config):
        tecs_config_file = ''
        if tecs_config:
            cluster_conf_path = daisy_tecs_path + cluster_id
            LOG.info(_("Generate tecs config..."))
            config.update_tecs_config(tecs_config, cluster_conf_path)
            tecs_config_file = cluster_conf_path + "/tecs.conf"
            ha_config_file = cluster_conf_path + "/HA_1.conf"
            mkdir_tecs_install = "mkdir -p /home/tecs_install/"
            daisy_cmn.subprocess_call(mkdir_tecs_install)
            cp_ha_conf = "\cp %s /home/tecs_install/" % ha_config_file
            tecs_conf = "\cp %s /home/tecs_install/" % ha_config_file
            daisy_cmn.subprocess_call(cp_ha_conf)
        return tecs_config_file

    def run(self):
        try:
            start_time = time.time()
            self._run()
        except Exception as e:
            self.state = tecs_state['INSTALL_FAILED']
            self.message = e.message
            self._update_install_progress_to_db()
            LOG.exception(e.message)
        else:
            if not self.need_install:
                return
            self.progress = 100
            self.state = tecs_state['ACTIVE']
            self.message = "Tecs installed successfully"
            LOG.info(_("Install TECS for cluster %s successfully."
                        % self.cluster_id))
            time_cost = str(round((time.time() - start_time)/60, 2))
            LOG.info(_("It totally takes %s min for installing tecs" % time_cost))

            if self.dns_name_ip:
                ha_vip = ""
                public_vip = ""
                compute_ip_domain = {}
                for dns_dict in self.dns_name_ip:
                    domain_name = dns_dict.keys()[0]
                    domain_ip = dns_dict.values()[0]
                    if domain_name == "ha-vip":
                        ha_vip = domain_ip
                    if domain_name == "public-vip":
                        public_vip = domain_ip
                    if domain_ip in self.nodes_ips['computer']:
                        compute_ip_domain.update({domain_ip: domain_name})

                revise_nova_config(self.nodes_ips['computer'], ha_vip,
                                   public_vip, compute_ip_domain)
                revise_horizon_config(self.nodes_ips['ha'], ha_vip, public_vip)

            # load neutron conf after installation
            roles = registry.get_roles_detail(self.req.context)
            for role in roles:
                if role['cluster_id'] == self.cluster_id:
                    backend=manager.configBackend('clushshell', self.req, role['id'])
                    backend.push_config()   
            result = config.get_conf(self.tecs_config_file,
                            neutron_float_ip="CONFIG_NEUTRON_SERVER_HOST",
                            keystone_float_ip="CONFIG_KEYSTONE_HOST",
                            neutron_install_mode="CONFIG_NEUTRON_SERVER_INSTALL_MODE",
                            keystone_install_mode="CONFIG_KEYSTONE_INSTALL_MODE",
                            lb_float_ip="CONFIG_LB_HOST")
            if (result.get('keystone_install_mode', None) == "LB" and
                    result.get('neutron_install_mode', None) == "LB"):
                LOG.info(_("<<<Begin config lb neutron.>>>"))
                time.sleep(20)
                neutron(self.req,
                        result.get('lb_float_ip', None),
                        result.get('lb_float_ip', None),
                        self.cluster_id)
            else:
                LOG.info(_("<<<Begin config neutron.>>>"))
                time.sleep(20)
                neutron(self.req,
                        result.get('neutron_float_ip', None),
                        result.get('keystone_float_ip', None),
                        self.cluster_id)
        finally:
            self._update_install_progress_to_db()
            if self.install_log_fp:
                self.install_log_fp.close()

    def _run(self):
        """
        Exectue install file(.bin) with sync mode.
        :return:
        """

        def executor(**params):
            # if subprocsee is failed, we need break
            if os.path.exists(self.log_file):
                params['tell_pos'] =  self._check_install_log(params.get('tell_pos', 0))
                LOG.debug(_("<<<Check install bin is OK.>>>"))
                if 100 == self.progress:
                    return params
                if 3 == self.progress:
                    self._update_install_progress_to_db()
            # waiting for 'progress_log_location' file exist
            if not params.get("if_progress_file_read", None):
                if not os.path.exists(self.progress_log_location):
                    params['if_progress_file_read'] = False
                    return params
                else:
                    with open(self.progress_log_location, "r") as fp:
                        line = fp.readline()
                        self.progress_logs_path = line.split('\n')[0] + "/manifests"
                        LOG.info(_("TECS installation log path: %s."
                                    % self.progress_logs_path))
                        params['if_progress_file_read'] = True

            # waiting for 'self.progress_logs_path' file exist
            if not os.path.exists(self.progress_logs_path):
                return params

            LOG.debug(_("<<<Calc install progress.>>>"))

            # cacl progress & sync to db
            progress = self._calc_progress(self.progress_logs_path)

            if self.progress != progress and progress >= 3:
                self.progress = progress
                self.state = tecs_state['INSTALLING']
                self._update_install_progress_to_db()
            elif progress == 100:
                self.progress = 100
                self.state = tecs_state['ACTIVE']
                self.message = "Tecs installed successfully"
            return params

        if not self.cluster_id or \
            not self.req:
            raise exception.InstallException("invalid params.")

        self.progress = 0
        self.message = "Preparing for TECS installation"
        self._update_install_progress_to_db()
        if not self.need_install:
            LOG.info(_("No host in cluster %s need to install tecs."
                    % self.cluster_id))
            return

        (tecs_config, self.mgnt_ip_list) = get_cluster_tecs_config(self.req, self.cluster_id)
        # after os is installed successfully, if ping all role hosts
        # management ip successfully, begin to install TECS
        unreached_hosts = daisy_cmn.check_ping_hosts(self.mgnt_ip_list, self.ping_times)
        if unreached_hosts:
            self.message = "ping hosts %s failed" % ','.join(unreached_hosts)
            raise exception.InstallException(self.message)
        else:
            # os maybe not reboot completely, wait for 20s to ensure ssh successfully.
            # ssh test until sucess should better here
            time.sleep(20)

        name_ip_list, self.nodes_ips = get_host_name_and_mgnt_ip(tecs_config)
        all_nodes = list(set(self.nodes_ips['ha'] + self.nodes_ips['lb'] +
                             self.nodes_ips['computer']))
        # delete daisy server known_hosts file to avoid
        # ssh command failed because of incorrect host key.
        daisy_cmn.subprocess_call('rm -rf /root/.ssh/known_hosts')
        if tecs_config['OTHER']['cluster_data']['use_dns']:
            self.dns_name_ip = replace_ip_with_domain_name(self.req, tecs_config)
            storage_ip_list = tecs_cmn.get_storage_name_ip_dict(
                self.req, self.cluster_id, 'STORAGE')

            self.dns_name_ip.extend(storage_ip_list)
            tecs_config['OTHER'].update({'dns_config': self.dns_name_ip})

            config_dnsmasq_server(self.nodes_ips['ha'], self.dns_name_ip)
            config_dnsmasq_client(all_nodes, self.nodes_ips['ha'])
            config_nodes_hosts(all_nodes, self.dns_name_ip)
            host_domain = [name_ip.keys()[0] for name_ip in self.dns_name_ip
                           if name_ip.keys()[0] .find('vip') == -1]
            unreached_hosts = daisy_cmn.check_ping_hosts(host_domain,
                                                         self.ping_times)
            if unreached_hosts:
                self.message = "ping hosts %s failed after DNS configuration" %\
                               ','.join(unreached_hosts)
                raise exception.InstallException(self.message)
        else:
            config_nodes_hosts(all_nodes, name_ip_list)
        # generate tecs config must be after ping check
        self.tecs_config_file = self._generate_tecs_config_file(self.cluster_id,
                                                                tecs_config)

        # install network-configuration-1.1.1-15.x86_64.rpm
        if self.mgnt_ip_list:
            for mgnt_ip in self.mgnt_ip_list:
                LOG.info(_("begin to install network-configuration on %s"% mgnt_ip))
                tecs_cmn.TecsShellExector(mgnt_ip, 'install_rpm')
        # network-configuration will restart network, wait until ping test successfully
        time.sleep(10)
        unreached_hosts = daisy_cmn.check_ping_hosts(self.mgnt_ip_list, self.ping_times)
        if unreached_hosts:
            self.message = "ping hosts %s failed after network configuration" % ','.join(unreached_hosts)
            raise exception.InstallException(self.message)

        (share_disk_info, volume_disk_info) =\
             disk_array.get_disk_array_info(self.req, self.cluster_id)
        if share_disk_info or volume_disk_info:
            (controller_ha_nodes, computer_ips) =\
                 disk_array.get_ha_and_compute_ips(self.req, self.cluster_id)
        else:
            controller_ha_nodes = {}
            computer_ips = []

        all_nodes_ip = computer_ips + controller_ha_nodes.keys()
        if all_nodes_ip:
            LOG.info(_("begin to config multipth  ..."))
            compute_error_msg = disk_array.config_compute_multipath(all_nodes_ip)
            if compute_error_msg:
                self.message = compute_error_msg
                raise exception.InstallException(self.message)
            else:
                LOG.info(_("config Disk Array multipath successfully"))

        if share_disk_info:
            LOG.info(_("begin to config Disk Array ..."))
            ha_error_msg = disk_array.config_ha_share_disk(share_disk_info,
                                                           controller_ha_nodes)
            if ha_error_msg:
                self.message = ha_error_msg
                raise exception.InstallException(message=self.message)
            else:
                LOG.info(_("config Disk Array for HA nodes successfully"))

        # check and get TECS version
        tecs_version_pkg_file = tecs_cmn.check_and_get_tecs_version(daisy_tecs_path)
        if not tecs_version_pkg_file:
            self.state = tecs_state['INSTALL_FAILED']
            self.message = "TECS version file not found in %s" % daisy_tecs_path
            raise exception.NotFound(message=self.message)

        # use pattern 'tecs_%s_install' to distinguish multi clusters installation
        LOG.info(_("Open log file for TECS installation."))
        self.install_log_fp = open(self.log_file, "w+")

        # delete cluster_id file before installing, in case getting old log path
        self.progress_log_location = "/var/tmp/packstack/%s" % self.cluster_id
        if os.path.exists(self.progress_log_location):
            os.remove(self.progress_log_location)

        install_cmd = "sudo %s conf_file %s" % (tecs_version_pkg_file, self.tecs_config_file)
        LOG.info(_("Begin to install TECS in cluster %s." % self.cluster_id))
        clush_bin = subprocess.Popen(
            install_cmd, shell=True, stdout=self.install_log_fp, stderr=self.install_log_fp)

        self.progress = 1
        self.state = tecs_state['INSTALLING']
        self.message = "TECS installing"
        self._update_install_progress_to_db()
        # if clush_bin is not terminate
        # while not clush_bin.returncode:
        params = {}  # executor params
        execute_times = 0 # executor run times
        while True:
            time.sleep(5)
            if self.progress == 100:
                if volume_disk_info:
                    LOG.info(_("Begin to config cinder volume ..."))
                    ha_error_msg = disk_array.config_ha_cinder_volume(
                                               volume_disk_info, 
                                               controller_ha_nodes.keys())
                    if ha_error_msg:
                        self.message = ha_error_msg
                        raise exception.InstallException(self.message)
                    else:
                        LOG.info(_("Config cinder volume for HA nodes successfully"))
                break
            elif execute_times >= 1440:
                self.state = tecs_state['INSTALL_FAILED']
                self.message = "TECS install timeout for 2 hours"
                raise exception.InstallTimeoutException(cluster_id=self.cluster_id)
            params = executor(
                # just read cluster_id file once in 'while'
                if_progress_file_read=params.get("if_progress_file_read", False),
                # current fp location of tecs_install.log
                tell_pos=params.get("tell_pos", 0))

            # get clush_bin.returncode
            # clush_bin.poll()
            execute_times += 1


