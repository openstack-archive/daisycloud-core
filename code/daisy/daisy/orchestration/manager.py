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
/orchestration for tecs API
"""

from oslo_config import cfg
from oslo_log import log as logging

from daisy.common import exception
from daisy.common import utils

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class OrchestrationManager():

    def __init__(self, *args, **kwargs):
        """Load orchestration options and initialization."""
        pass

    def _os_tecs_install(self, cluster_id, daisy_client):
        try:
            install_meta = {'cluster_id': cluster_id}
            daisy_client.install.install(**install_meta)
            LOG.info("install cluster %s" % cluster_id)
        except exception.Invalid as e:
            LOG.error("install error:%s" % e.message)

    def get_active_compute(self, cluster_id, daisy_client):
        host_meta = {'cluster_id': cluster_id}
        host_meta['filters'] = host_meta
        host_list_generator = daisy_client.hosts.list(**host_meta)
        active_compute_list = []
        host_list = [host for host in host_list_generator if hasattr(
            host, "role_status") and host.role_status == "active"]
        if not host_list:
            LOG.warn("No installed active node in cluster")
        host_list = [host for host in host_list
                     if host.discover_mode == "PXE"]
        if not host_list:
            LOG.warn("No pxe discover successful node in cluster")
        for host in host_list:
            host_info = daisy_client.hosts.get(host.id)
            if hasattr(host_info, "role") and ["COMPUTER"] == host_info.role \
                    and hasattr(host_info, "interfaces"):
                active_compute_list.append(host_info)
        return active_compute_list

    def set_scale_host_interface(self, cluster_id, host_info, daisy_client):
        compute_list = []
        active_compute_host = None
        compute_list = self.get_active_compute(cluster_id, daisy_client)
        if compute_list and hasattr(host_info, "interfaces"):
            active_compute_host = self.check_isomorphic_host(
                compute_list, host_info)
            if not active_compute_host:
                LOG.info("%s not isomorphic host" % host_info.name)
                return None
            host_info.os_version_file = active_compute_host.os_version_file
            host_info.os_version_id = active_compute_host.os_version_id
            host_info.root_lv_size = active_compute_host.root_lv_size
            host_info.swap_lv_size = active_compute_host.swap_lv_size
            host_info.hwm_ip = active_compute_host.hwm_ip
            host_info.hugepagesize = active_compute_host.hugepagesize
            host_info.hugepages = active_compute_host.hugepages
            host_info.isolcpus = active_compute_host.isolcpus
            host_info.ipmi_user = active_compute_host.ipmi_user
            host_info.ipmi_passwd = active_compute_host.ipmi_passwd
            host_info.vcpu_pin_set = active_compute_host.vcpu_pin_set
            host_info.dvs_high_cpuset = active_compute_host.dvs_high_cpuset
            host_info.pci_high_cpuset = active_compute_host.pci_high_cpuset
            host_info.os_cpus = active_compute_host.os_cpus
            host_info.dvs_cpus = active_compute_host.dvs_cpus
            host_info.root_disk = active_compute_host.root_disk
            host_info.config_set_id = active_compute_host.config_set_id
            host_info.group_list = active_compute_host.group_list
            host_info.dvsc_cpus = active_compute_host.dvsc_cpus
            host_info.dvsp_cpus = active_compute_host.dvsp_cpus
            host_info.dvsv_cpus = active_compute_host.dvsv_cpus
            host_info.dvsblank_cpus = active_compute_host.dvsblank_cpus
            host_info.flow_mode = active_compute_host.flow_mode
            host_info.virtio_queue_size = active_compute_host.virtio_queue_size
            host_info.dvs_config_type = active_compute_host.dvs_config_type
            host_info.tecs_patch_id= active_compute_host.tecs_patch_id
        else:
            LOG.warn("No installed active computer node in cluster")
            return None

        if active_compute_host:
            host_info.interfaces = [x for x in host_info.interfaces if
                                    x['type'] == "ether"]
            for interface in host_info.interfaces:
                for compute_interface in active_compute_host.interfaces:
                    if interface['name'] == compute_interface['name'] and \
                       "assigned_networks" in compute_interface:
                        for assigned_network in compute_interface[
                                'assigned_networks']:
                            assigned_network['ip'] = ''
                        interface['assigned_networks'] = compute_interface[
                            'assigned_networks']
                        interface['netmask'] = compute_interface['netmask']
                        interface['gateway'] = compute_interface['gateway']
                        interface['mode'] = compute_interface['mode']
                        interface['vswitch_type'] = \
                            compute_interface['vswitch_type']
            for compute_interface in active_compute_host.interfaces:
                for assigned_network in compute_interface['assigned_networks']:
                    assigned_network['ip'] = ''
                compute_interface['host_id'] = host_info.id
                if compute_interface['type'] == "bond":
                    interfaces = [interface for interface in
                                  host_info.interfaces if interface[
                                      'name'] == compute_interface['name']]
                    if not interfaces:
                        host_info.interfaces.append(compute_interface)
        return host_info

    def check_isomorphic_host(self, compute_list, host_info):
        new_interfaces = host_info.interfaces
        host_numa_cpus = utils.get_numa_node_cpus((host_info.cpu or {}))
        memory_size_b_str = str(host_info.memory['total'])
        memory_size_b_int = int(memory_size_b_str.strip().split()[0])
        for compute_host in compute_list:
            new_interface_count = len(
                [interface for interface in
                 new_interfaces if interface['type'] == "ether"])
            compute_interface_count = len(
                [interface for interface in
                 compute_host.interfaces if interface['type'] == "ether"])
            if new_interface_count != compute_interface_count:
                msg = "%s and new host interface number are different" %\
                      (compute_host.name)
                LOG.warn(msg)
                continue
            if host_info.cpu['total'] != compute_host.cpu['total']:
                msg = "%s and new host cpu total numbers are different" %\
                      (compute_host.name)
                LOG.warn(msg)
                continue
            compute_numa_cpus = utils.get_numa_node_cpus(
                (compute_host.cpu or {}))
            if compute_numa_cpus != host_numa_cpus:
                msg = "%s and new host numa cpus are different" %\
                      compute_host.name
                LOG.warn(msg)
                continue
            active_compu_memory_str = str(compute_host.memory['total'])
            active_compu_memory_size =\
                int(active_compu_memory_str.strip().split()[0])
            # host memory can't be lower than the installed host memory size-1G
            if memory_size_b_int < active_compu_memory_size - 1024 * 1024:
                msg = "new host memory is lower than %s" % compute_host.name
                LOG.warn(msg)
                continue
            is_isomorphic = self._check_interface_isomorphic(
                new_interfaces, compute_host)
            if is_isomorphic:
                return compute_host
        return False

    def _check_interface_isomorphic(self, new_interfaces, active_host):
        is_isomorphic = False
        for interface in new_interfaces:
            if interface['type'] != "ether":
                continue
            is_isomorphic = False
            for compute_interface in active_host.interfaces:
                if compute_interface['type'] != "ether":
                    continue
                if interface['name'] == compute_interface['name'] and \
                        interface['pci'] == compute_interface['pci'] and\
                        interface['max_speed'] == compute_interface['max_speed']:
                    is_isomorphic = True
                elif interface['name'] == compute_interface['name']\
                        and interface['max_speed'] != compute_interface['max_speed']:
                    msg = "%s and new host %s max speed are different" \
                          % (active_host.name, interface['name'])
                    LOG.warn(msg)
                    return False
                elif interface['name'] == compute_interface['name'] and\
                                interface['pci'] != compute_interface['pci']:
                    msg = "%s and new host %s pci are different" \
                          % (active_host.name, interface['name'])
                    LOG.warn(msg)
                    return False
            if not is_isomorphic:
                return False
        return is_isomorphic