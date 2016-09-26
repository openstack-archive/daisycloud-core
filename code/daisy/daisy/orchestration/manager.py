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

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class OrchestrationManager():

    def __init__(self, *args, **kwargs):
        """Load orchestration options and initialization."""
        pass

    def _os_install(self, cluster_id, daisy_client):
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
        for host in host_list:
            host_info = daisy_client.hosts.get(host.id)
            if hasattr(host_info, "role") and "COMPUTER" in host_info.role and\
               hasattr(host_info, "interfaces"):
                active_compute_list.append(host_info)
        return active_compute_list

    def set_scale_host_interface(self, cluster_id, host_info, daisy_client):
        compute_list = []
        active_compute_host = None
        compute_list = self.get_active_compute(cluster_id, daisy_client)
        if compute_list and hasattr(host_info, "interfaces"):
            active_compute_host = self.check_isomorphic_host(
                compute_list, host_info.interfaces)
            if not active_compute_host:
                LOG.info("%s not isomorphic host" % host_info.name)
                return None
            host_info.os_version_file = active_compute_host.os_version_file
            host_info.root_lv_size = active_compute_host.root_lv_size
            host_info.swap_lv_size = active_compute_host.swap_lv_size
            host_info.name = "computer-" + host_info.name[-12:]
            # add for autoscale computer host
            host_info.hugepagesize = active_compute_host.hugepagesize
            host_info.hugepages = active_compute_host.hugepages
            host_info.isolcpus = active_compute_host.isolcpus
        else:
            LOG.error("no active compute node in cluster")
            return None

        if active_compute_host:
            for interface in host_info.interfaces:
                for compute_interface in active_compute_host.interfaces:
                    if interface['pci'] == compute_interface['pci'] and \
                       "assigned_networks" in compute_interface:
                        for assigned_network in compute_interface[
                                'assigned_networks']:
                            assigned_network['ip'] = ''
                        interface['assigned_networks'] = compute_interface[
                            'assigned_networks']
                        interface['name'] = compute_interface['name']
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

    def check_isomorphic_host(self, compute_list, new_interfaces):
        for compute_host in compute_list:
            new_interface_count = len(
                [interface for interface in
                 new_interfaces if interface['type'] == "ether"])
            compute_interface_count = len(
                [interface for interface in
                 compute_host.interfaces if interface['type'] == "ether"])
            if new_interface_count != compute_interface_count:
                continue
            is_isomorphic = False
            for interface in new_interfaces:
                if interface['type'] != "ether":
                    continue
                for compute_interface in compute_host.interfaces:
                    if interface['pci'] == compute_interface['pci'] and\
                       interface['max_speed'] == \
                       compute_interface['max_speed']:
                        is_isomorphic = True
                    elif interface['pci'] == compute_interface['pci'] and \
                            interface['max_speed'] != \
                            compute_interface['max_speed']:
                        is_isomorphic = False
                        break
                if not is_isomorphic:
                    break
            if is_isomorphic:
                return compute_host
        return False
