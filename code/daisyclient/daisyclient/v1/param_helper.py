# Copyright 2012 OpenStack Foundation
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

# -*- coding:utf-8 -*-

import os


def _read_template_file(args):
    template_file = args.params_file_path
    if not os.path.exists(template_file):
        print("Params_file not exist or permission deiny.")
        return
    with open(template_file) as tfp:
        params = ''.join(
            tfp.read().replace("\\'", "").split(" ")).replace("\n", "")
        return dict(eval(params))

CLUSTER_ADD_PARAMS_FILE = {
    'description': 'desc',
    'name': "test",
    'routers': [{
            'description': 'router1',
            'external_logic_network': 'flat1',
            'name': 'router1',
            'subnets': ['subnet2', 'subnet10']}],
    'networks': [],
    'nodes': [],
    'logic_networks': [{
        'name': 'internal1',
        'physnet_name': 'PRIVATE1',
        'segmentation_id': 200,
        'segmentation_type': 'vlan',
        'shared': True,
        'subnets': [{'cidr': '192.168.1.0/24',
                     'dns_nameservers': ['8.8.4.4',
                                         '8.8.8.8'],
                     'floating_ranges': [['192.168.1.2',
                                          '192.168.1.200']],
                     'gateway': '192.168.1.1',
                     'name': 'subnet2'},
                    {'cidr': '172.16.1.0/24',
                     'dns_nameservers': ['8.8.4.4',
                                         '8.8.8.8'],
                     'floating_ranges': [['172.16.1.130',
                                          '172.16.1.150'],
                                         ['172.16.1.151',
                                          '172.16.1.254']],
                     'gateway': '172.16.1.1',
                     'name': 'subnet10'}],
        'type': 'internal'},
        {'name': 'flat1',
         'physnet_name': 'physnet1',
         'segmentation_type': 'flat',
         'segmentation_id': -1,
         'shared': True,
         'subnets': [{'cidr': '192.168.2.0/24',
                      'dns_nameservers': ['8.8.4.4',
                                          '8.8.8.8'],
                      'floating_ranges': [['192.168.2.130',
                                           '192.168.2.254']],
                      'gateway': '192.168.2.1',
                      'name': 'subnet123'}],
         'type': 'external'}
    ],
    'networking_parameters': {
        'base_mac': 'fa:16:3e:00:00:00',
        'gre_id_range': [2, 4094],
        'net_l23_provider': 'ovs',
        'public_vip': '172.16.0.3',
        'segmentation_type': 'vlan,flat,vxlan,gre',
        'vlan_range': [2, 4094],
        'vni_range': [2, 4094]}
}
