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
from ironicclient import exceptions


from logging import handlers
from ironic_discoverd import conf
from ironic_discoverd import firewall
from ironic_discoverd import node_cache
from ironic_discoverd.plugins import base as plugins_base
from ironic_discoverd import utils


LOG = logging.getLogger("ironic_discoverd.process")
fh = handlers.RotatingFileHandler(
    '/var/log/ironic/parse.log',
    'a', maxBytes=2*1024*1024, backupCount=5)
formatter = logging.Formatter(
    '%(asctime)-12s:%(name)s:%(levelname)s:%(message)s')
fh.setFormatter(formatter)
LOG.addHandler(fh)

_POWER_CHECK_PERIOD = 5
_POWER_OFF_CHECK_PERIOD = 5


def process(node_info):
    """Process data from the discovery ramdisk.

    This function heavily relies on the hooks to do the actual data processing.
    """
    hooks = plugins_base.processing_hooks_manager()
    for hook_ext in hooks:
        hook_ext.obj.before_processing(node_info)

    cached_node = node_cache.find_node(
        bmc_address=node_info.get('ipmi_address'),
        mac=node_info.get('macs'))

    ironic = utils.get_client()
    try:
        node = ironic.node.get(cached_node.uuid)
    except exceptions.NotFound:
        msg = ('Node UUID %s was found in cache, but is not found in Ironic'
               % cached_node.uuid)
        cached_node.finished(error=msg)
        raise utils.Error(msg, code=404)

    try:
        return _process_node(ironic, node, node_info, cached_node)
    except utils.Error as exc:
        cached_node.finished(error=str(exc))
        raise
    except Exception as exc:
        msg = 'Unexpected exception during processing'
        LOG.exception(msg)
        cached_node.finished(error=msg)
        raise utils.Error(msg)


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
            'slaves': slaves
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
                  'disk': node_info.get('disk'),
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
                data_dict['path'] = '/'+property+'s'+'/'+key
            else:
                data_dict['path'] = '/'+property+'/'+key
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


def _process_node(ironic, node, node_info, cached_node):
    ports = {}
    for mac in (node_info.get('macs') or ()):
        try:
            port = ironic.port.create(node_uuid=node.uuid, address=mac)
            ports[mac] = port
        except exceptions.Conflict:
            LOG.warning('MAC %(mac)s appeared in introspection data for '
                        'node %(node)s, but already exists in '
                        'database - skipping',
                        {'mac': mac, 'node': node.uuid})

    node_patches, port_patches = _run_post_hooks(node, ports, node_info)
    node = utils.retry_on_conflict(ironic.node.update, node.uuid, node_patches)
    for mac, patches in port_patches.items():
        utils.retry_on_conflict(ironic.port.update, ports[mac].uuid, patches)

    LOG.debug('Node %s was updated with data from introspection process, '
              'patches %s, port patches %s',
              node.uuid, node_patches, port_patches)

    firewall.update_filters(ironic)

    if cached_node.options.get('setup_ipmi_credentials'):
        eventlet.greenthread.spawn_n(_wait_for_power_management,
                                     ironic, cached_node)
        return {'ipmi_setup_credentials': True,
                'ipmi_username': node.driver_info.get('ipmi_username'),
                'ipmi_password': node.driver_info.get('ipmi_password')}
    else:
        eventlet.greenthread.spawn_n(_finish, ironic, cached_node)
        return {}


def _wait_for_power_management(ironic, cached_node):
    deadline = cached_node.started_at + conf.getint('discoverd', 'timeout')
    while time.time() < deadline:
        eventlet.greenthread.sleep(_POWER_CHECK_PERIOD)
        validation = utils.retry_on_conflict(ironic.node.validate,
                                             cached_node.uuid)
        if validation.power['result']:
            _finish(ironic, cached_node)
            return
        LOG.debug('Waiting for management credentials on node %s '
                  'to be updated, current error: %s',
                  cached_node.uuid, validation.power['reason'])

    msg = ('Timeout waiting for power credentials update of node %s '
           'after introspection' % cached_node.uuid)
    LOG.error(msg)
    cached_node.finished(error=msg)


def _force_power_off(ironic, cached_node):
    LOG.debug('Forcing power off of node %s', cached_node.uuid)
    try:
        utils.retry_on_conflict(ironic.node.set_power_state,
                                cached_node.uuid, 'off')
    except Exception as exc:
        msg = ('Failed to power off node %s, check it\'s power '
               'management configuration: %s' % (cached_node.uuid, exc))
        cached_node.finished(error=msg)
        raise utils.Error(msg)

    deadline = cached_node.started_at + conf.getint('discoverd', 'timeout')
    while time.time() < deadline:
        node = ironic.node.get(cached_node.uuid)
        if (node.power_state or '').lower() == 'power off':
            return
        LOG.info('Waiting for node %s to power off, current state is %s',
                 cached_node.uuid, node.power_state)
        eventlet.greenthread.sleep(_POWER_OFF_CHECK_PERIOD)

    msg = ('Timeout waiting for node %s to power off after introspection' %
           cached_node.uuid)
    cached_node.finished(error=msg)
    raise utils.Error(msg)


def _finish(ironic, cached_node):
    _force_power_off(ironic, cached_node)

    patch = [{'op': 'add', 'path': '/extra/newly_discovered', 'value': 'true'},
             {'op': 'remove', 'path': '/extra/on_discovery'}]
    utils.retry_on_conflict(ironic.node.update, cached_node.uuid, patch)

    cached_node.finished()
    LOG.info('Introspection finished successfully for node %s',
             cached_node.uuid)
