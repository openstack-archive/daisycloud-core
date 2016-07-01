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
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn
from daisy.common import utils


def _write_role_configs_to_db(req, cluster_id, role_name, configs):
    config_meta = {'cluster': cluster_id,
                   'role': role_name,
                   'config': configs}
    registry.config_interface_metadata(req.context,
                                       config_meta)


def _write_host_configs_to_db(req, host_id, configs):
    config_meta = {'host_id': host_id,
                   'config': configs}
    registry.config_interface_metadata(req.context,
                                       config_meta)


def _get_config_item(file, section, key, value, description):
    return {'file-name': file,
            'section': section,
            'key': key,
            'value': value,
            'description': description}


def _add_configs_for_nova(req, host_detail):
    config_file = '/etc/nova/nova.conf'
    default_section = 'DEFAULT'

    key_name = 'vcpu_pin_set'
    key_value = host_detail.get(key_name)
    config_items = []
    if not key_value:
        key_value = host_detail.get('isolcpus')

    nova_key_name = key_name
    description = 'vcpu pin set for all vm'
    item = _get_config_item(config_file,
                            default_section,
                            nova_key_name,
                            key_value,
                            description)
    config_items.append(item)

    key_name = 'dvs_high_cpuset'
    key_value = host_detail.get(key_name)

    nova_key_name = 'dvs_high_cpu_set'
    description = 'vcpu pin set for high-performance dvs vm'
    item = _get_config_item(config_file,
                            default_section,
                            nova_key_name,
                            key_value,
                            description)
    config_items.append(item)

    numa_cpus = utils.get_numa_node_cpus(host_detail.get('cpu', {}))
    numa_nodes = utils.get_numa_node_from_cpus(numa_cpus, key_value)
    if numa_nodes:
        libvirt_section = 'libvirt'
        nova_key_name = 'reserved_huge_pages'
        # only support one NUMA node for DVS now
        key_value = 'node:%s,size:1048576,count:4' % numa_nodes[0]
        description = 'reserved huges for DVS service '\
                      'on high NUMA node'
        config_items.append({'file-name': config_file,
                             'key': nova_key_name,
                             'section': libvirt_section,
                             'value': key_value,
                             'description': description})

    key_name = 'pci_high_cpuset'
    pci_key_value = host_detail.get(key_name)

    nova_key_name = 'vsg_card_cpu_set'
    description = 'vcpu pin set for high-performance CLC card vm'
    item = _get_config_item(config_file,
                            default_section,
                            nova_key_name,
                            pci_key_value,
                            description)
    config_items.append(item)
    if pci_key_value:
        nova_key_name = 'default_ephemeral_format'
        description = 'config for CLC card'
        key_value = 'ext3'
        item = _get_config_item(config_file,
                                default_section,
                                nova_key_name,
                                key_value,
                                description)
        config_items.append(item)

        nova_key_name = 'pci_passthrough_whitelist'
        description = 'config for CLC card'
        key_value = '[{"vendor_id": "8086","product_id": "0435"}]'
        item = _get_config_item(config_file,
                                default_section,
                                nova_key_name,
                                key_value,
                                description)
        config_items.append(item)

    _write_host_configs_to_db(req,
                              host_detail['id'],
                              config_items)


def update_configset(req, cluster_id):
    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    for role in roles:
        # now only computer has configs
        if role['name'] != 'COMPUTER':
            continue
        role_meta = {'config_set_update_progress': 0}
        daisy_cmn.update_role(req, role['id'], role_meta)

        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
        for host in role_hosts:
            host_detail = daisy_cmn.get_host_detail(req, host['host_id'])
            _add_configs_for_nova(req, host_detail)
