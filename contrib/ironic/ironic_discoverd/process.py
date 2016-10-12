# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Handling introspection data from the ramdisk."""

import logging
import time

import eventlet


from logging import handlers
from ironic_discoverd import conf
from ironic_discoverd import firewall
from ironic_discoverd.plugins import base as plugins_base
from ironic_discoverd import utils


LOG = logging.getLogger("ironic_discoverd.process")
fh = handlers.RotatingFileHandler(
    '/var/log/ironic/parse.log',
    'a', maxBytes=2 * 1024 * 1024, backupCount=5)
formatter = logging.Formatter(
    '%(asctime)-12s:%(name)s:%(levelname)s:%(message)s')
fh.setFormatter(formatter)
LOG.addHandler(fh)

_POWER_CHECK_PERIOD = 5
_POWER_OFF_CHECK_PERIOD = 5


def write_data_to_daisy(node_info, ipmi_addr, os_status=None, hostname=None):
    daisy_client = utils.get_daisy_client()
    daisy_data = format_node_info_for_daisy_client(node_info, ipmi_addr,
                                                   os_status, hostname)
    daisy_client.hosts.add(**daisy_data)


def format_node_info_for_daisy_client(node_info, ipmi_addr,
                                      os_status, hostname):
    interface_list = []
    interfaces = node_info.get('interfaces', {})
    for value in interfaces.values():
        slaves = []
        if value.get("slaves"):
            slaves = value.get("slaves").split()

        interface = {
            'name': value['name'],
            'pci': value['pci'],
            "mac": value['mac'],
            "ip": value['ip'],
            'state': value['state'],
            'max_speed': value['max_speed'],
            'current_speed': value['current_speed'],
            'netmask': value['netmask'],
            'type': value['type'],
            'slaves': slaves,
        }
        interface_list.append(interface)

    min_mac = find_min_mac_in_node_info(node_info)
    unique_mac = ''.join(min_mac.split(":"))
    daisy_data = {'description': 'default',
                  'name': unique_mac,
                  'ipmi_addr': ipmi_addr,
                  'interfaces': interface_list,
                  'os_status': 'init',
                  'dmi_uuid': node_info.get('system').get('uuid', None),
                  'system': node_info.get('system'),
                  'cpu': node_info.get('cpu'),
                  'memory': node_info.get('memory'),
                  'disks': node_info.get('disk'),
                  'devices': node_info.get('devices'),
                  'pci': node_info.get('pci')}

    if os_status:
        daisy_data['os_status'] = 'active'
        daisy_data['name'] = hostname
    return daisy_data


def find_min_mac_in_node_info(node_info):
    interfaces_dict = node_info['interfaces']
    mac_list = []
    for value in interfaces_dict.values():
        if value['mac'] != '' and value['type'] == 'ether':
            mac_list.append(value['mac'])
    min_mac = min(mac_list)
    LOG.debug('min mac=%s', min_mac)
    return min_mac


def format_node_info_for_ironic(node_info):
    patch = []

    for property in node_info.keys():
        property_dict = node_info[property]

        for key, value in property_dict.items():
            data_dict = {'op': 'add'}
            key = key.replace(':', '-').replace('.', '-')
            if property == 'disk':
                data_dict['path'] = '/' + property + 's' + '/' + key
            else:
                data_dict['path'] = '/' + property + '/' + key
            data_dict['value'] = value
            patch.append(data_dict)

    LOG.debug('patch:%s', patch)
    return patch


def _run_post_hooks(node, ports, node_info):
    hooks = plugins_base.processing_hooks_manager()
    port_instances = list(ports.values())

    node_patches = []
    port_patches = {}
    for hook_ext in hooks:
        hook_patch = hook_ext.obj.before_update(node, port_instances,
                                                node_info)
        if not hook_patch:
            continue

        node_patches.extend(hook_patch[0])
        port_patches.update(hook_patch[1])

    node_patches = [p for p in node_patches if p]
    port_patches = {mac: patch for (mac, patch) in port_patches.items()
                    if mac in ports and patch}
    return node_patches, port_patches
