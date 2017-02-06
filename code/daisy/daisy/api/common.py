# Copyright 2012 OpenStack Foundation.
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

import ast
from oslo_log import log as logging

from webob import exc
from daisy.common import utils
from daisy import i18n
from daisy.api.configset import clush

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW


def get_pxe_mac(host_detail):
    pxe_macs = [interface['mac'] for interface in host_detail['interfaces']
                if interface['is_deployment']]
    return pxe_macs


def valid_network_range(req, network_meta):
    if (('vlan_start' in network_meta and
         'vlan_end' not in network_meta) or
        ('vlan_start' not in network_meta and
            'vlan_end' in network_meta)):
        msg = "vlan-start and vlan-end must be appeared "\
              "at the same time"
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg, request=req)
    if 'vlan_start' in network_meta:
        if not (int(network_meta['vlan_start']) >= 1 and
                int(network_meta['vlan_start']) <= 4094):
            msg = "vlan_start must be a integer in 1~4096"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)
    if 'vlan_end' in network_meta:
        if not (int(network_meta['vlan_end']) >= 1 and
                int(network_meta['vlan_end']) <= 4094):
            msg = "vlan_end must be a integer in 1~4096"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)
        if int(network_meta['vlan_start']) > int(network_meta['vlan_end']):
            msg = "vlan_start must be less than vlan_end"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)

    if (('vni_start' in network_meta and 'vni_end' not in
         network_meta) or (
            'vni_start' not in network_meta and
            'vni_end' in network_meta)):

        msg = "vni_start and vni_end must be appeared at the same time"
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg, request=req)
    if 'vni_start' in network_meta:
        if not (int(network_meta['vni_start']) >= 1 and
                int(network_meta['vni_start']) <= 16777216):
            msg = "vni_start must be a integer in 1~16777216"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)
    if 'vni_end' in network_meta:
        if not (int(network_meta['vni_end']) >= 1 and
                int(network_meta['vni_end']) <= 16777216):
            msg = "vni_end must be a integer in 1~16777216"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)
        if int(network_meta['vni_start']) > int(network_meta['vni_end']):
            msg = "vni_start must be less than vni_end"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)

    if (('gre_id_start' in network_meta and
         'gre_id_end' not in network_meta) or
        ('gre_id_start' not in network_meta and
            'gre_id_end' in network_meta)):
        msg = "gre_id_start and gre_id_end must"\
            "be appeared at the same time"
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg, request=req)
    if 'gre_id_start' in network_meta:
        if not (int(network_meta['gre_id_start']) >= 1 and
                int(network_meta['gre_id_start']) <= 4094):
            msg = "gre_id_start must be a integer in 1~4094"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)
    if 'gre_id_end' in network_meta:
        if not (int(network_meta['gre_id_end']) >= 1 and
                int(network_meta['gre_id_end']) <= 4094):
            msg = "gre_id_end must be a integer in 1~4094"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)
        if int(network_meta['gre_id_start']) >\
                int(network_meta['gre_id_end']):
            msg = "gre_id_start must be less than gre_id_end"
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg, request=req)


def valid_ip_ranges(ip_ranges, cidr=None):
    if not ip_ranges:
        msg = (_("IP ranges not given."))
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg)

    if not isinstance(ip_ranges, list):
        ip_ranges = ast.literal_eval(ip_ranges)

    last_ip_range_end = 0
    int_ip_ranges_list = list()
    sorted_int_ip_ranges_list = list()
    for ip_pair in ip_ranges:
        if ['start', 'end'] != ip_pair.keys():
            msg = (_("IP range was not start with 'start:' "
                     "or end with 'end:'."))
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg)
        ip_start = ip_pair['start']
        ip_end = ip_pair['end']
        utils.validate_ip_format(ip_start)  # check ip format
        utils.validate_ip_format(ip_end)
        # transform ip format to int when the string format is
        # valid
        int_ip_start = utils.ip_into_int(ip_start)
        int_ip_end = utils.ip_into_int(ip_end)
        if int_ip_start > int_ip_end:
            msg = (_("Start ip should be larger then end ip."))
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg)
        if cidr:
            if not utils.is_ip_in_cidr(ip_start, cidr):
                msg = (_("IP address %s is not in the range "
                         "of CIDR %s." % (ip_start, cidr)))
                LOG.error(msg)
                raise exc.HTTPBadRequest(explanation=msg)

            if not utils.is_ip_in_cidr(ip_end, cidr):
                msg = (_("IP address %s is not in the range "
                         "of CIDR %s." % (ip_end, cidr)))
                LOG.error(msg)
                raise exc.HTTPBadRequest(explanation=msg)
        int_ip_ranges_list.append([int_ip_start, int_ip_end])

    sorted_int_ip_ranges_list = \
        sorted(int_ip_ranges_list, key=lambda x: x[0])

    for int_ip_range in sorted_int_ip_ranges_list:
        if (last_ip_range_end and
                last_ip_range_end >= int_ip_range[0]):
            msg = (_("Ip ranges can not be overlap with each other."))
            # such as "[10, 15], [12, 16]", last_ip_range_end >=
            # int_ip_range[0], this ip ranges were overlap
            LOG.error(msg)
            raise exc.HTTPBadRequest(explanation=msg)
        else:
            last_ip_range_end = int_ip_range[1]


def valid_vlan_id(vlan_id):
    if not vlan_id:
        msg = (_("IP ranges not given."))
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg)

    if not isinstance(vlan_id, int):
        vlan_id = ast.literal_eval(vlan_id)

    if not (vlan_id >= 1 and vlan_id <= 4094):
        msg = "vlan id must be a integer between 1~4094"
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg)


def valid_cluster_networks(cluster_networks):
    for network1 in cluster_networks:
        for network2 in cluster_networks:
            if network1['id'] == network2['id']:
                continue
            if network1.get('cidr', None) == network2.get('cidr', None):
                if (not network1.get('cidr') and
                    not network2.get('cidr')):
                    continue
                if (str(network1.get('vlan_id', None)) !=
                        str(network2.get('vlan_id', None))):
                    msg = (_("When cidr equal for networks %s and %s, "
                             "vlan id must be equal for them."
                             % (network1['name'], network2['name'])))
                    LOG.error(msg)
                    raise exc.HTTPBadRequest(explanation=msg)
                if not utils.is_ip_ranges_equal(
                        network1.get('ip_ranges', None),
                        network2.get('ip_ranges', None)):
                    msg = (_("When cidr equal for networks %s and %s, "
                             "ip ranges must be equal for them."
                             % (network1['name'], network2['name'])))
                    LOG.error(msg)
                    raise exc.HTTPBadRequest(explanation=msg)

                if ((network1.get('gateway') or network2.get('gateway')) and
                        str(network1.get('gateway')) != str(
                            network2.get('gateway'))):
                    msg = (_("When cidr equal for networks %s and %s, "
                             "gateway must be equal for them."
                             % (network1['name'], network2['name'])))
                    LOG.error(msg)
                    raise exc.HTTPBadRequest(explanation=msg)
            else:
                 if (str(network1.get('vlan_id', None)) ==
                        str(network2.get('vlan_id', None))):
                    if (not network1.get('vlan_id') and
                        not network2.get('vlan_id')):
                        continue
                    msg = (_("When vlan id equal for networks '%s' and '%s',"
                             " cidr must be equal for them."
                             % (network1['name'], network2['name'])))
                    LOG.error(msg)
                    raise exc.HTTPBadRequest(explanation=msg)


def check_gateway_uniqueness(new_cluster_networks):
    used_gateways = set()
    for network in new_cluster_networks:
        if (network['network_type'] != 'DATAPLANE'
            and network.get('gateway')):
            used_gateways.add(network['gateway'])
    if len(used_gateways) > 1:
        msg = (_("Only one gateway is allowed."))
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg)


def remote_execute_script(ssh_host_info,
                          files=[], commands=[]):
    try:
        clush.copy_file_and_run_cmd(ssh_host_info,
                                    files,
                                    commands)
    except Exception as e:
        msg = e.message
        LOG.error(msg)
        raise exc.HTTPBadRequest(explanation=msg)


def config_network_new(ssh_host_info, backend, json_file=None):
    remote_dir = '/home/'
    daisy_script_name = 'daisy.py'
    linux_action_name = 'linux_action.sh'
    daisy_path = '/var/lib/daisy/%s/' % backend
    scp_files = [{'file': daisy_path + daisy_script_name,
                  'remote_dir': remote_dir},
                 {'file': daisy_path + linux_action_name,
                  'remote_dir': remote_dir}]
    cmd1 = 'cd %s; chmod +x %s' % (remote_dir, daisy_script_name)
    cmd2 = 'cd %s; chmod +x %s' % (remote_dir, linux_action_name)
    if json_file:
        cmd3 = 'cd %s; python %s %s' % (remote_dir, daisy_script_name,
                                        json_file)
    else:
        cmd3 = 'cd %s; python %s' % (remote_dir, daisy_script_name)
    remote_execute_script(ssh_host_info,
                          scp_files,
                          [cmd1, cmd2, cmd3])
    cmds = ['systemctl restart network']
    try:
        scp_files = []
        clush.copy_file_and_run_cmd(ssh_host_info, scp_files, cmds)
    except Exception:
        msg = "Wait network restart..."
        LOG.info(msg)


def config_network(ssh_host_info, json_file=None):
    config_network_new(ssh_host_info, 'tecs', json_file)
