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
from webob import exc

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


def pci_get_cpu_sets(numa_cpus, pci_info, device_numa_node):
    high_pci_cpu_set = {}
    msg = ''
    return_code = 0
    status = {'rc': 0, 'msg': ''}

    if not numa_cpus:
        msg = "The architecture of CPU does not supported"
        LOG.info(msg)
        return_code = 0
        status['rc'] = return_code
        status['msg'] = msg
        return (status, high_pci_cpu_set)

    # get Intel Corporation Coleto Creek PCIe Endpoint
    clc_pci_lines = utils.get_clc_pci_info(pci_info)
    if not clc_pci_lines:
        msg = "No CLC card in system"
        LOG.info(msg)
        return_code = 0
        status['rc'] = return_code
        status['msg'] = msg
        return (status, high_pci_cpu_set)

    high_pci_cpusets = []
    for clc_pci_line in clc_pci_lines:
        numa_node = device_numa_node['0000:' + clc_pci_line]
        numa_key = 'numa_node' + str(numa_node)
        if numa_key not in numa_cpus:
            msg = "Can't find numa_node '%s' for CLC" % numa_node
            return_code = 1
            status['rc'] = return_code
            status['msg'] = msg
            return (status, high_pci_cpu_set)
        high_pci_cpusets += numa_cpus[numa_key]

    high_pci_cpu_set['high'] = list(set(high_pci_cpusets))
    total_cpus = get_total_cpus_for_numa(numa_cpus)
    high_pci_cpu_set['low'] =\
        list(set(total_cpus) - set(high_pci_cpu_set['high']))
    LOG.debug("high_pci_cpu_set:%s" % high_pci_cpu_set)

    return (status, high_pci_cpu_set)


# if numa codes are not same, return -1
def get_numa_by_nic(nic_info, device_numa_node):
    numa = []
    try:
        for nic in nic_info:
            numa.append(device_numa_node[nic['bus']])

        numa = list(set(numa))
        numa_info = (-1 if len(numa) > 1 else numa[0])
    except Exception:
        numa_info = -1

    return numa_info


def dvs_get_cpu_sets(dic_numas, nic_info, device_numa_node, cpu_num=4):
    dvs_cpu_set = []
    total_cpus = []
    high_cpu_set = []
    low_cpu_set = []
    cpu_set = {}
    msg = ''
    return_code = 0
    status = {}

    if not dic_numas:
        msg = "The architecture of CPU not supported"
        LOG.info(msg)
        return_code = 1
        status['rc'] = return_code
        status['msg'] = msg
        return (status, cpu_set)

    numa_node = get_numa_by_nic(nic_info, device_numa_node)
    if numa_node < 0:
        msg = 'Invalid numa node:%s' % numa_node
        LOG.info(msg)
        return_code = 3
        status['rc'] = return_code
        status['msg'] = msg
        return (status, cpu_set)

    numa_key = "numa_node%s" % numa_node
    if numa_key not in dic_numas:
        msg = "Can't find numa node '%s' for DVS" % numa_node
        return_code = 4
        status['rc'] = return_code
        status['msg'] = msg
        return (status, cpu_set)

    if len(dic_numas[numa_key]) < (cpu_num + 1):
        msg = "CPU on %s is not enough" % numa_key
        LOG.info(msg)
        return_code = 5
        status['rc'] = return_code
        status['msg'] = msg
        return (status, cpu_set)

    total_cpus = get_total_cpus_for_numa(dic_numas)
    LOG.debug("total_cpu:%s" % total_cpus)

    # sort
    dic_numas[numa_key] = sorted(dic_numas[numa_key], reverse=True)
    for i in dic_numas[numa_key][0:cpu_num]:
        dvs_cpu_set.append(i)

    high_cpu_set = dic_numas[numa_key]
    low_cpu_set =\
        list(set(total_cpus).difference(set(dic_numas[numa_key])))
    LOG.debug("cpu used by dvs:%s" % dvs_cpu_set)
    LOG.debug("low_cpu_set:%s" % low_cpu_set)
    LOG.debug("high_cpu_set:%s" % high_cpu_set)

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
                     for interface in host_hw_info['interfaces'].values()
                     if nic_name == interface['name']]
        dvs_cpu_num = 4
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
                    % (host_detail['name'], status['msg'])
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg)

    return dvs_cpusets


def get_pci_cpusets(numa_cpus, host_hw_info):
    device_numa = {}
    for device in host_hw_info['devices'].values():
        device_numa.update(device)

    (status, pci_cpusets) = pci_get_cpu_sets(numa_cpus,
                                             host_hw_info['pci'].values(),
                                             device_numa)
    if status['rc'] != 0:
        LOG.error(status['msg'])
        raise exc.HTTPBadRequest(explanation=status['msg'])

    return pci_cpusets


def allocate_os_cpus(roles_name, pci_cpusets, dvs_cpusets):
    os_cpus = []
    if not dvs_cpusets and not pci_cpusets:
        return os_cpus

    os_cpu_num = get_default_os_num(roles_name)
    if os_cpu_num == 0:
        return os_cpus

    os_available_cpuset = []
    if ((pci_cpusets and pci_cpusets.get('high')) and
            (not dvs_cpusets or not dvs_cpusets.get('high'))):
        # if only pci exist, get OS cores from pci lowset
        cpus_low = pci_cpusets.get('low', [])
        cpus_high = pci_cpusets.get('high', [])

    if dvs_cpusets and dvs_cpusets.get('high'):
        # if only dvs exist, get OS cores from dvs lowset.
        # if pci and dvs exist at the same time,
        # get OS cores from lowset from dvs lowset.
        cpus_low = list(set(dvs_cpusets.get('low', [])) -
                        set(dvs_cpusets.get('dvs', [])))

        cpus_high = list(set(dvs_cpusets.get('high', [])) -
                         set(dvs_cpusets.get('dvs', [])))

    cpus_low.sort()
    cpus_high.sort()
    os_available_cpuset = cpus_low + cpus_high
    if not os_available_cpuset:
        return os_cpus

    if (len(os_available_cpuset) < os_cpu_num):
        msg = 'cpus are not enough'
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg)

    # cpu core 0 must give OS
    cpu0 = 0
    if cpu0 in os_available_cpuset:
        os_available_cpuset.remove(cpu0)
        os_available_cpuset = [cpu0] + os_available_cpuset

    os_cpus = os_available_cpuset[:os_cpu_num]
    return os_cpus


# when config role 'COMPUTER', allocate cpus for CLC
def allocate_clc_cpus(host_detail):
    pci_cpu_sets = {}
    if 'COMPUTER' not in host_detail.get('role', []):
        return pci_cpu_sets

    host_interfaces = host_detail.get('interfaces')
    host_hw_info = {'system': '', 'memory': '',
                    'cpu': '', 'disk': '', 'interfaces': '',
                    'pci': '', 'devices': ''}
    host_obj = host_detail
    for f in ['system', 'memory', 'cpu',
              'disk', 'interfaces',
              'pci', 'devices']:
        host_hw_info[f] = host_obj.get(f)

    host_id = host_detail.get('id')
    clc_pci = utils.get_clc_pci_info(host_hw_info['pci'].values())
    if not clc_pci:
        return pci_cpu_sets
    else:
        LOG.info("CLC card pci number: '%s'" % clc_pci)
        numa_cpus = utils.get_numa_node_cpus(host_hw_info.get('cpu', {}))
        if not numa_cpus or not numa_cpus['numa_node0']:
            msg = "No NUMA CPU found from of host '%s'" % host_id
            LOG.info(msg)
            return pci_cpu_sets
        LOG.info("Get CLC cpusets of host '%s'" % host_id)
        pci_cpu_sets = get_pci_cpusets(numa_cpus, host_hw_info)
        if not pci_cpu_sets or not pci_cpu_sets.get('high'):
            msg = "Can't get CLC cpusets of host '%s'" % host_id
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg)

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
                    'cpu': '', 'disk': '', 'interfaces': '',
                    'pci': '', 'devices': ''}
    host_obj = host_detail
    for f in host_hw_info:
        host_hw_info[f] = host_obj.get(f)
    numa_cpus = utils.get_numa_node_cpus(host_hw_info.get('cpu', {}))
    if not numa_cpus or not numa_cpus['numa_node0']:
        msg = "No NUMA CPU found from of host '%s'" % host_id
        LOG.info(msg)
        return dvs_cpu_sets

    LOG.info("Get dvs cpusets of host '%s'" % host_id)
    dvs_cpu_sets = get_dvs_cpusets(numa_cpus,
                                   host_detail,
                                   host_hw_info)
    if not dvs_cpu_sets or not dvs_cpu_sets.get('high'):
        msg = "Can't get dvs high cpusets of host '%s'" % host_id
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg)
    return dvs_cpu_sets


def allocate_cpus(host_detail):
    host_cpu_sets = {'dvs_high_cpuset': '',
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

    host_cpu_sets['dvs_high_cpuset'] =\
        utils.cpu_list_to_str(dvs_cpusets.get('high', []))
    host_cpu_sets['pci_high_cpuset'] =\
        utils.cpu_list_to_str(pci_cpusets.get('high', []))
    host_cpu_sets['suggest_dvs_cpus'] =\
        utils.cpu_list_to_str(dvs_cpusets.get('dvs', []))
    host_cpu_sets['suggest_os_cpus'] = utils.cpu_list_to_str(os_cpus)

    LOG.info("NUMA CPU usage for host %s: %s"
             % (host_detail['id'], host_cpu_sets))

    return host_cpu_sets
