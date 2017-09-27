# Copyright 2017 OpenStack Foundation
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
DPDK CPU set helper functions.
"""
from oslo_config import cfg
from oslo_log import log as logging

from daisy.common import utils
from daisy import i18n

CONF = cfg.CONF

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE


# if numa nodes are not same, return -2
def get_numa_by_nic(nics_info, device_numa):
    numa = []
    try:
        for nic in nics_info:
            numa.append(device_numa[nic['bus']])

        # Remove duplicated numa ids
        numa = list(set(numa))

        numa_info = (-100 if len(numa) > 1 else numa[0])
    except Exception as e:
        LOG.error("Error, exception message: %s" % e.message)
        numa_info = -200

    return numa_info


def dvs_get_cpu_sets(numa_cpus, nics_info, device_numa, num):
    dvs_cpu_set = {}
    dvsc_cpus = []
    cpu_set = {}
    msg = ''
    return_code = 0
    status = {}

    if not numa_cpus or not numa_cpus['numa_node0']:
        msg = "No NUMA info found for CPUs"
        LOG.error(msg)
        LOG.info("numa_cpus=%s" % numa_cpus)
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

    # All DPDK nics should be located in a single NUMA region
    numa_node = get_numa_by_nic(nics_info, device_numa)
    if numa_node < 0:
        if numa_node == -100:
            msg = "Get more than one numa nodes for DVS, not supported"
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
    if numa_key not in numa_cpus:
        msg = "Unknown numa node '%s'for DVS nic, NUMA CPU is '%s' "\
            % (numa_key, numa_cpus)
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

    if len(numa_cpus[numa_key]) < 1 + num:
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

    # Allocate num CPUs from each NUMA region for DPDK's pmd thread
    for key in numa_cpus.keys():
        # sort
        numa_cpus[key] = sorted(numa_cpus[key])
        dvsc_cpus += numa_cpus[key][1:1+num]

    dvs_cpu_set['dvsc'] = dvsc_cpus # for pmd thread
    dvs_cpu_set['dvsp'] = [-1] # Not used
    dvs_cpu_set['dvsv'] = [-1] # Not used
    cpu_set['numa_node'] = numa_node # Not used currently
    cpu_set['dvs'] = dvs_cpu_set
    cpu_set['high'] = [-1] # Not used
    cpu_set['low'] = [-1] # Not used
    LOG.info("cpu_set:%s" % cpu_set)
    msg = 'Success'
    status['rc'] = return_code
    status['msg'] = msg
    return (status, cpu_set)


def get_dvs_cpusets(numa_cpus, dvs_interfaces, host_hw_info, num):
    nics_info = []

    # For simplity, do not support bond interface currently
    for dvs_interface in dvs_interfaces:
        if dvs_interface['type'] == 'ether':
            nics_info.append({'name': dvs_interface['name'],
                              'bus': dvs_interface['pci']})

    dvs_cpusets = {}

    if nics_info:
        LOG.info("DVS netcard info: '%s'" % nics_info)
        device_numa = {}
        for device in host_hw_info['devices'].values():
            device_numa.update(device)

        (status, dvs_cpusets) = \
            dvs_get_cpu_sets(numa_cpus,
                             nics_info,
                             device_numa)
        if status['rc'] != 0:
            msg = "Get dvs cpu sets for host '%s' failed,\
                    detail error is '%s'"\
                    % (host_hw_info['id'], status['msg'])
            LOG.error(msg)
    else:
        dvs_cpusets = {'high': [-7],
                       'low': [-7],
                       'dvs': {'dvsc': [-7],
                               'dvsp': [-7],
                               'dvsv': [-7]},
                       'numa_node': -7}
        msg = "Can't get DVS nics for host %s" % host_hw_info['id']
        LOG.error(msg)

    return dvs_cpusets


# If any interface is selected for dvs(dpdk), then allocate cpus for pmd thread
def allocate_dvs_cpus(host_detail, num):
    dvs_cpu_sets = {}
    host_interfaces = host_detail.get('interfaces')
    if not host_interfaces:
        return dvs_cpu_sets

    # 'vswitch_type' in interface and
    # interface['vswitch_type'] == 'dvs'
    dvs_interfaces = utils.get_dvs_interfaces(host_interfaces)
    if not dvs_interfaces:
        return dvs_cpu_sets

    # extract host_hw_info out from host_detail
    host_hw_info = {'id': '', 'system': '', 'memory': '',
                    'cpu': '', 'disks': '', 'interfaces': '',
                    'pci': '', 'devices': ''}
    host_obj = host_detail
    for f in host_hw_info:
        host_hw_info[f] = host_obj.get(f)

    # Given host_hw_info.get('cpu', {}) =
    # host_cpu = {"numa_node0": "0-7,16-23",
    #             "numa_node1": "8-15,24-31"}
    # then get_numa_node_cpus will return cpu id list as follows:
    # {'numa_node0': [0,1,2,3,4,5,6,7, 16,17,18,19,20,21,22,23],
    #  'numa_node1': [8,9,10,11,12,13,14,15, 24,25,26,27,28,29,30,31]}
    numa_cpus = utils.get_numa_node_cpus(host_hw_info.get('cpu', {}))

    LOG.info("Get DVS cpusets of host '%s'" % host_hw_info.get('id'))
    dvs_cpu_sets = get_dvs_cpusets(numa_cpus,
                                   dvs_interfaces,
                                   host_hw_info, num)

    return dvs_cpu_sets


def allocate_cpus_for_dpdk(host_detail, num=1):
    host_cpu_sets = {'suggest_dvs_high_cpuset': '',
                     'pci_high_cpuset': '',
                     'suggest_dvs_cpus': '',
                     'suggest_dvsc_cpus': '', # CPU Ids for pmd threads.
                     'suggest_dvsp_cpus': '',
                     'suggest_dvsv_cpus': '',
                     'suggest_os_cpus': '',
                     'numa_node': ''}
    dvs_cpusets = allocate_dvs_cpus(host_detail, num)
    if (not dvs_cpusets):
        return host_cpu_sets

    host_cpu_sets['numa_node'] = dvs_cpusets.get('numa_node', []) # Not used
    if dvs_cpusets.get('dvs', {}):
        if dvs_cpusets['dvs'].get('dvsc', []):
            host_cpu_sets['suggest_dvsc_cpus'] =\
                utils.cpu_list_to_str(dvs_cpusets['dvs'].get('dvsc', []))
            host_cpu_sets['suggest_dvs_cpus'] =\
                utils.cpu_list_to_str(dvs_cpusets['dvs'].get('dvsc', []))

    host_cpu_sets['suggest_dvsp_cpus'] = [-1] # Not used
    host_cpu_sets['suggest_dvsv_cpus'] = [-1] # Not used
    host_cpu_sets['suggest_os_cpus'] = [-1] # Not used
    host_cpu_sets['suggest_dvs_high_cpuset'] = [-1] # Not used
    host_cpu_sets['pci_high_cpuset'] = [-1] # Not used

    LOG.info("NUMA CPU usage for host %s: %s"
             % (host_detail['id'], host_cpu_sets))

    return host_cpu_sets
