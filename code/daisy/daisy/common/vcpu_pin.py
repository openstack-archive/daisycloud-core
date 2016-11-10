# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2014 SoftLayer Technologies, Inc.
# Copyright 2015 Mirantis, Inc
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
System-level utilities and helper functions.
"""
from oslo_config import cfg
from oslo_log import log as logging

from daisy.common import utils
from daisy import i18n

CONF = cfg.CONF

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE


def get_total_cpus_for_numa(numa_cpus):
    all_cpus = []
    for value in numa_cpus.values():
        all_cpus.extend(value)
    return all_cpus


def get_default_os_num(host_roles_name):
    if (('CONTROLLER_LB' in host_roles_name or
         'CONTROLLER_HA' in host_roles_name) and
            'COMPUTER' in host_roles_name):
        # host with role of CONTOLLER and COMPUTER,
        # isolate 4 cpu cores default for OS and TECS
        os_cpu_num = 4
    elif 'COMPUTER' in host_roles_name:
        # host with role of COMPUTER only,
        # isolate 2 cpu cores default for OS and TECS
        os_cpu_num = 2
    elif ('CONTROLLER_LB' in host_roles_name or
          'CONTROLLER_HA' in host_roles_name):
        # host with role of CONTOLLER only,
        # don't isolate cpu for OS and TECS
        os_cpu_num = 0
    else:
        os_cpu_num = 0

    return os_cpu_num


def pci_get_cpu_sets(numa_cpus, device_numa_node, clc_pci_list):
    high_pci_cpu_set = {}
    msg = ''
    return_code = 0
    status = {'rc': 0, 'msg': ''}

    if not numa_cpus or not numa_cpus['numa_node0']:
        msg = "The architecture of CPU isn't supported for CLC"
        LOG.error(msg)
        LOG.info("numa_cpus=%s" % numa_cpus)
        return_code = 4
        status['rc'] = return_code
        status['msg'] = msg
        high_pci_cpu_set = {'high': [-4], 'low': [-4]}
        return (status, high_pci_cpu_set)

    high_pci_cpusets = []
    for clc_pci in clc_pci_list:
        numa_node = device_numa_node['0000:' + clc_pci]
        if numa_node < 0:
            msg = "Invalid numa_node '%s' for CLC, maybe you "\
                  "need to upgrade BIOS version" % numa_node
            LOG.error(msg)
            return_code = 1
        status['rc'] = return_code
        status['msg'] = msg
        high_pci_cpu_set = {'high': [-1], 'low': [-1]}
        return (status, high_pci_cpu_set)

        numa_key = 'numa_node' + str(numa_node)
        if numa_key not in numa_cpus:
            msg = "Unknown numa node '%s' for CLC, NUMA CPU is  '%s'"\
                % (numa_key, numa_cpus)
            LOG.error(msg)
            return_code = 5
            status['rc'] = return_code
            status['msg'] = msg
            high_pci_cpu_set = {'high': [-5], 'low': [-5]}
            return (status, high_pci_cpu_set)
        high_pci_cpusets += numa_cpus[numa_key]

    high_pci_cpu_set['high'] = list(set(high_pci_cpusets))
    total_cpus = get_total_cpus_for_numa(numa_cpus)
    high_pci_cpu_set['low'] =\
        list(set(total_cpus) - set(high_pci_cpu_set['high']))
    LOG.debug("high_pci_cpu_set:%s" % high_pci_cpu_set)

    return (status, high_pci_cpu_set)


# if numa nodes are not same, return -2
def get_numa_by_nic(nics_info, device_numa_node):
    numa = []
    try:
        for nic in nics_info:
            numa.append(device_numa_node[nic['bus']])

        numa = list(set(numa))
        numa_info = (-100 if len(numa) > 1 else numa[0])
    except Exception as e:
        LOG.error("Error, exception message: %s" % e.message)
        numa_info = -200

    return numa_info


def dvs_get_cpu_sets(dic_numas, nics_info, device_numa_node, cpu_num=6):
    dvs_cpu_set = {}
    dvsc_cpus = []
    dvsp_cpus = []
    dvsv_cpus = []
    total_cpus = []
    high_cpu_set = []
    low_cpu_set = []
    cpu_set = {}
    msg = ''
    return_code = 0
    status = {}

    if not dic_numas or not dic_numas['numa_node0']:
        msg = "The architecture of CPU isn't supported for DVS"
        LOG.error(msg)
        LOG.info("numa_cpus=%s" % dic_numas)
        return_code = 4
        status['rc'] = return_code
        status['msg'] = msg
        cpu_set = {'high': [-4],
                   'low': [-4],
                   'dvs': {'dvsc': [-4],
                           'dvsp': [-4],
                           'dvsv': [-4]},
                   'numa_node': -4}
        return (status, cpu_set)

    numa_node = get_numa_by_nic(nics_info, device_numa_node)
    if numa_node < 0:
        if numa_node == -100:
            msg = "Get more than one numa nodes for DVS, it's not "\
                  "supported, maybe you config DVS on bond, but "\
                  "numa nodes of bond are not same"
            return_code = 2
            cpu_set = {'high': [-2],
                       'low': [-2],
                       'dvs': {'dvsc': [-2],
                               'dvsp': [-2],
                               'dvsv': [-2]},
                       'numa_node': -2}
        elif numa_node == -200:
            msg = "Get numa node failed for DVS"
            return_code = 3
            cpu_set = {'high': [-3],
                       'low': [-3],
                       'dvs': {'dvsc': [-3],
                               'dvsp': [-3],
                               'dvsv': [-3]},
                       'numa_node': -3}
        else:
            msg = "Invalid numa node '%s' for DVS, maybe you "\
                "need to upgrade BIOS version" % numa_node
            return_code = 1
            cpu_set = {'high': [-1],
                       'low': [-1],
                       'dvs': {'dvsc': [-1],
                               'dvsp': [-1],
                               'dvsv': [-1]},
                       'numa_node': -1}
        LOG.error(msg)
        status['rc'] = return_code
        status['msg'] = msg
        return (status, cpu_set)

    numa_key = "numa_node%s" % numa_node
    if numa_key not in dic_numas:
        msg = "Unknown numa node '%s'for DVS, NUMA CPU is '%s' "\
            % (numa_key, dic_numas)
        LOG.error(msg)
        return_code = 5
        status['rc'] = return_code
        status['msg'] = msg
        cpu_set = {'high': [-5],
                   'low': [-5],
                   'dvs': {'dvsc': [-5],
                           'dvsp': [-5],
                           'dvsv': [-5]},
                   'numa_node': -5}
        return (status, cpu_set)

    if len(dic_numas[numa_key]) < (cpu_num + 1):
        msg = "CPU on numa node '%s' is not enough for DVS" % numa_key
        LOG.error(msg)
        return_code = 6
        status['rc'] = return_code
        status['msg'] = msg
        cpu_set = {'high': [-6],
                   'low': [-6],
                   'dvs': {'dvsc': [-6],
                           'dvsp': [-6],
                           'dvsv': [-6]},
                   'numa_node': -6}
        return (status, cpu_set)

    total_cpus = get_total_cpus_for_numa(dic_numas)
    LOG.debug("total_cpu:%s" % total_cpus)
    cpu_total_num = len(dic_numas[numa_key])
    half_total_num = divmod(cpu_total_num, 2)[0]
    half_cpu_num = divmod(cpu_num, 2)[0]

    # sort
    dic_numas[numa_key] = sorted(dic_numas[numa_key])
    dvsc_cpus.append(dic_numas[numa_key][1])
    dvsc_cpus.append(dic_numas[numa_key][half_total_num + 1])
    dvsp_cpus = dic_numas[numa_key][(half_total_num + 2):
                                    (half_total_num + half_cpu_num + 1)]
    dvsv_cpus = dic_numas[numa_key][2:(half_cpu_num + 1)]
    dvs_cpu_set['dvsc'] = dvsc_cpus
    dvs_cpu_set['dvsp'] = dvsp_cpus
    dvs_cpu_set['dvsv'] = dvsv_cpus

    high_cpu_set =\
        list(set(dic_numas[numa_key]).difference(set(list(
             set(dvsc_cpus) | set(dvsp_cpus) | set(dvsv_cpus)))))
    low_cpu_set =\
        list(set(total_cpus).difference(set(dic_numas[numa_key])))
    LOG.debug("cpu used by dvs:%s" % dvs_cpu_set)
    LOG.debug("low_cpu_set:%s" % low_cpu_set)
    LOG.debug("high_cpu_set:%s" % high_cpu_set)

    cpu_set['numa_node'] = numa_node
    cpu_set['dvs'] = dvs_cpu_set
    cpu_set['high'] = high_cpu_set
    cpu_set['low'] = low_cpu_set
    LOG.debug("cpu_set:%s" % cpu_set)

    msg = 'Success'
    status['rc'] = return_code
    status['msg'] = msg
    LOG.debug("status:%s" % status)

    return (status, cpu_set)


def get_dvs_cpusets(numa_cpus, host_detail, host_hw_info):
    dvs_nics_name = []
    dvs_interfaces = utils.get_dvs_interfaces(host_detail['interfaces'])
    for dvs_interface in dvs_interfaces:
        if dvs_interface['type'] == 'ether':
            dvs_nics_name.append(dvs_interface['name'])
        if dvs_interface['type'] == 'bond':
            if dvs_interface.get('slaves', None):
                dvs_nics_name.extend(dvs_interface['slaves'])
            elif dvs_interface.get('slave1', None) and \
                    dvs_interface.get('slave2', None):
                slave_list = []
                slave_list.append(dvs_interface['slave1'])
                slave_list.append(dvs_interface['slave2'])
                dvs_nics_name.extend(slave_list)

    dvs_cpusets = {}
    if dvs_nics_name:
        nics_info = [{'name': nic_name, 'bus': interface['pci']}
                     for nic_name in dvs_nics_name
                     for interface in host_hw_info['interfaces']
                     if nic_name == interface['name']]
        dvs_cpu_num = 6
        device_numa = {}
        for device in host_hw_info['devices'].values():
            device_numa.update(device)
        LOG.info("DVS netcard info: '%s'" % nics_info)
        (status, dvs_cpusets) = \
            dvs_get_cpu_sets(numa_cpus,
                             nics_info,
                             device_numa,
                             dvs_cpu_num)
        if status['rc'] != 0:
            msg = "Get dvs cpu sets for host '%s' failed,\
                    detail error is '%s'"\
                    % (host_detail['id'], status['msg'])
            LOG.error(msg)
    else:
        dvs_cpusets = {'high': [-7],
                       'low': [-7],
                       'dvs': {'dvsc': [-7],
                               'dvsp': [-7],
                               'dvsv': [-7]},
                       'numa_node': -7}
        msg = "Can't get DVS nics for host %s" % host_detail['id']
        LOG.error(msg)

    return dvs_cpusets


def allocate_os_cpus(roles_name, pci_cpusets, dvs_cpusets):
    os_cpus = []
    if not dvs_cpusets and not pci_cpusets:
        return os_cpus
    if dvs_cpusets and dvs_cpusets['high'][0] < 0:
        LOG.info("Invalid DVS isolate CPUs configuration,"
                 " so can't allot cpus for OS")
        return os_cpus

    if pci_cpusets and pci_cpusets['high'][0] < 0:
        LOG.info("Invalid CLC isolate CPUs configuration,"
                 " so can't allot cpus for OS")
        return os_cpus
    os_cpu_num = get_default_os_num(roles_name)
    if os_cpu_num == 0:
        return os_cpus
    # cpu core 0 must give OS
    dvs_cpu_num = 6
    if dvs_cpusets:
        if dvs_cpusets['low']:
            numa_cpu_num = len(dvs_cpusets['high']) + dvs_cpu_num
        else:
            numa_cpu_num = divmod(len(dvs_cpusets['high']) + dvs_cpu_num, 2)[0]
        if numa_cpu_num < os_cpu_num + dvs_cpu_num:
            return os_cpus
    elif pci_cpusets:
        numa_cpu_num = len(pci_cpusets['high'])
    half_total_num = divmod(numa_cpu_num, 2)[0]
    cpu0 = 0
    if os_cpu_num == 2:
        os_cpus = [cpu0] + [cpu0 + numa_cpu_num]
    if os_cpu_num == 4:
        os_cpus = [cpu0] + [cpu0 + numa_cpu_num] +\
            [cpu0 + half_total_num] +\
            [cpu0 + half_total_num + numa_cpu_num]
    return os_cpus


# when config role 'COMPUTER', allocate cpus for CLC
def allocate_clc_cpus(host_detail):
    pci_cpu_sets = {}
    if 'COMPUTER' not in host_detail.get('role', []):
        return pci_cpu_sets

    host_interfaces = host_detail.get('interfaces')
    host_hw_info = {'system': '', 'memory': '',
                    'cpu': '', 'disks': '', 'interfaces': '',
                    'pci': '', 'devices': ''}
    host_obj = host_detail
    for f in host_hw_info:
        host_hw_info[f] = host_obj.get(f)

    host_id = host_detail.get('id')
    clc_pci_list = utils.get_clc_pci_info(host_hw_info.get('pci', {}))
    if not clc_pci_list:
        return pci_cpu_sets
    else:
        LOG.info("CLC card pci number: '%s'" % clc_pci_list)
        numa_cpus = utils.get_numa_node_cpus(host_hw_info.get('cpu', {}))
        LOG.info("Get CLC cpusets of host '%s'" % host_id)
        device_numa = {}
        for device in host_hw_info['devices'].values():
            device_numa.update(device)
        (status, pci_cpu_sets) = pci_get_cpu_sets(numa_cpus,
                                                  device_numa,
                                                  clc_pci_list)
        if status['rc'] != 0:
            msg = "Get CLC cpu sets for host '%s' failed,\
                    detail error is '%s'"\
                    % (host_id, status['msg'])
            LOG.error(msg)
    return pci_cpu_sets


# when config DVS on network plane mapping, allocate cpus for dvs
def allocate_dvs_cpus(host_detail):
    dvs_cpu_sets = {}
    host_interfaces = host_detail.get('interfaces')
    if not host_interfaces:
        return dvs_cpu_sets

    dvs_interfaces = utils.get_dvs_interfaces(host_interfaces)
    if not dvs_interfaces:
        return dvs_cpu_sets

    host_id = host_detail.get('id')
    host_hw_info = {'system': '', 'memory': '',
                    'cpu': '', 'disks': '', 'interfaces': '',
                    'pci': '', 'devices': ''}
    host_obj = host_detail
    for f in host_hw_info:
        host_hw_info[f] = host_obj.get(f)
    numa_cpus = utils.get_numa_node_cpus(host_hw_info.get('cpu', {}))

    LOG.info("Get DVS cpusets of host '%s'" % host_id)
    dvs_cpu_sets = get_dvs_cpusets(numa_cpus,
                                   host_detail,
                                   host_hw_info)

    return dvs_cpu_sets


def allocate_cpus(host_detail):
    host_cpu_sets = {'suggest_dvs_high_cpuset': '',
                     'pci_high_cpuset': '',
                     'suggest_dvs_cpus': '',
                     'suggest_os_cpus': ''}
    dvs_cpusets = allocate_dvs_cpus(host_detail)
    pci_cpusets = allocate_clc_cpus(host_detail)

    # no CLC and no DVS
    if (not pci_cpusets and not dvs_cpusets):
        return host_cpu_sets

    host_roles_name = host_detail.get('role', [])
    os_cpus = allocate_os_cpus(host_roles_name,
                               pci_cpusets,
                               dvs_cpusets)

    host_cpu_sets['suggest_dvs_high_cpuset'] =\
        utils.cpu_list_to_str(dvs_cpusets.get('high', []))
    host_cpu_sets['pci_high_cpuset'] =\
        utils.cpu_list_to_str(pci_cpusets.get('high', []))
    host_cpu_sets['numa_node'] = dvs_cpusets.get('numa_node', [])
    if dvs_cpusets.get('dvs', {}):
        if dvs_cpusets['dvs'].get('dvsc', []):
            host_cpu_sets['suggest_dvsc_cpus'] =\
                utils.cpu_list_to_str(dvs_cpusets['dvs']['dvsc'])
        if dvs_cpusets['dvs'].get('dvsp', []):
            host_cpu_sets['suggest_dvsp_cpus'] =\
                utils.cpu_list_to_str(dvs_cpusets['dvs']['dvsp'])
        if dvs_cpusets['dvs'].get('dvsv', []):
            host_cpu_sets['suggest_dvsv_cpus'] =\
                utils.cpu_list_to_str(dvs_cpusets['dvs']['dvsv'])
    host_cpu_sets['suggest_dvs_cpus'] =\
        utils.cpu_list_to_str(dvs_cpusets['dvs'].get(
            'dvsv', []) + dvs_cpusets['dvs'].get('dvsc', []) +
        dvs_cpusets['dvs'].get('dvsp', []))
    host_cpu_sets['suggest_os_cpus'] = utils.cpu_list_to_str(os_cpus)

    LOG.info("NUMA CPU usage for host %s: %s"
             % (host_detail['id'], host_cpu_sets))

    return host_cpu_sets
