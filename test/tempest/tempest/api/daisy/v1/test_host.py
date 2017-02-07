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

import copy
from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from fake.logical_network_fake import FakeLogicNetwork as logical_fake
from fake.logical_network_fake import FakeDiscoverHosts


class DaisyHostTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyHostTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.host_meta = copy.deepcopy(FakeDiscoverHosts().daisy_data[0])
        cls.host_meta_interfaces = {'type': 'ether',
                                    'name': 'enp129s0f0',
                                    'mac': '00:07:e9:15:99:00',
                                    'ip': '99.99.1.121',
                                    'netmask': '255.255.255.0',
                                    'is_deployment': 'True',
                                    'slaves': 'eth1',
                                    'pci': '1',
                                    'gateway': '99.99.1.1'}
        cls.cluster_meta = {
            'description': 'desc',
            'target_systems': "os+tecs",
            'logic_networks': [{'name': 'external1',
                                'physnet_name': 'phynet3',
                                'segmentation_id': 200,
                                'segmentation_type': 'vlan',
                                'shared': True,
                                'subnets': [{'cidr': '99.99.1.0/24',
                                             'dns_nameservers':
                                                 ['8.8.4.4', '8.8.8.8'],
                                             'floating_ranges': [
                                                 ['99.99.1.2', '99.99.1.200']],
                                             'gateway': '99.99.1.1',
                                             'name': 'subnet2'},
                                            {'cidr': '172.16.1.0/24',
                                             'dns_nameservers':
                                                 ['8.8.4.4', '8.8.8.8'],
                                             'floating_ranges': [
                                                 ['172.16.1.130',
                                                  '172.16.1.150'],
                                                 ['172.16.1.151',
                                                  '172.16.1.254']],
                                             'gateway': '172.16.1.1',
                                             'name': 'subnet10'}],
                                'type': 'external'},
                               {'name': 'internal2',
                                'physnet_name': 'phynet1',
                                'segmentation_id': 1023,
                                'segmentation_type': 'vxlan',
                                'shared': True,
                                'subnets': [{'cidr': '192.168.2.0/24',
                                             'dns_nameservers':
                                                 ['8.8.4.4', '8.8.8.8'],
                                             'floating_ranges': [
                                                 ['192.168.2.130',
                                                  '192.168.2.254']],
                                             'gateway': '192.168.2.1',
                                             'name': 'subnet123'}],
                                'type': 'internal'},
                               {'name': 'internal1',
                                'physnet_name': 'phynet2',
                                'segmentation_id': '777',
                                'segmentation_type': 'vlan',
                                'shared': False,
                                'subnets': [{'cidr': '192.168.31.0/24',
                                             'dns_nameservers':
                                                 ['8.8.4.4', '8.8.8.8'],
                                             'floating_ranges': [
                                                 ['192.168.31.130',
                                                  '192.168.31.254']],
                                             'gateway': '192.168.31.1',
                                             'name': 'subnet3'},
                                            {'cidr': '192.168.4.0/24',
                                             'dns_nameservers':
                                                 ['8.8.4.4', '8.8.8.8'],
                                             'floating_ranges': [
                                                 ['192.168.4.130',
                                                  '192.168.4.254']],
                                             'gateway': '192.168.4.1',
                                             'name': 'subnet4'}],
                                'type': 'internal'}],
            'name': 'test',
            'networking_parameters': {'base_mac': 'fa:16:3e:00:00:00',
                                      'gre_id_range': [2, 2000],
                                      'net_l23_provider': 'ovs',
                                      'public_vip': '172.16.0.3',
                                      'segmentation_type': 'vlan,vxlan',
                                      'vlan_range': [2, 4094],
                                      'vni_range': [1000, 1030]},
            'networks': [],
            'nodes': [],
            'routers': [{'description': 'router1',
                         'external_logic_network': 'external1',
                         'name': 'router1',
                         'subnets': ['subnet4', 'subnet3', 'subnet2']},
                        {'description': 'router2',
                         'external_logic_network': 'external1',
                         'name': 'router2',
                         'subnets': ['subnet10']}]}

        cls.version_data = {'description': 'default',
                            'name': 'rhel-server-whl-7.0-x86_64-dvd.iso',
                            'type': 'redhat 7.0',
                            }

    def private_network_add(self):
        # add network plane
        private_network_params = self.fake.fake_private_network_parameters()
        private_network_params1 = self.fake.fake_private_network_parameters1()
        private_network_params2 = self.fake.fake_private_network_parameters2()

        private_network_params = self.add_network(**private_network_params)
        private_network_params1 = self.add_network(**private_network_params1)
        private_network_params2 = self.add_network(**private_network_params2)

        self.private_network_id = private_network_params.id
        self.private_network_id1 = private_network_params1.id
        self.private_network_id2 = private_network_params2.id

        self.cluster_meta['networks'] = [self.private_network_id,
                                         self.private_network_id1,
                                         self.private_network_id2]

        return copy.deepcopy(private_network_params)

    def private_network_delete(self):
        self.delete_network(self.private_network_id)
        self.delete_network(self.private_network_id1)
        self.delete_network(self.private_network_id2)

    def test_host_check_with_error_ipmi_parameters(self):
        host_info = self.add_fake_node(0)
        check_meta = {'id': host_info.id,
                      'check_item': 'ipmi'}
        check_result = self.host_check(**check_meta)
        self.assertEqual("ipmi check failed",
                         check_result.ipmi_check_result,
                         "host_check_with_error_ipmi_parameters failed")

    def tearDown(self):
        if self.host_meta.get('cluster', None):
            del self.host_meta['cluster']
        if self.host_meta.get('role', None):
            del self.host_meta['role']
        if self.host_meta.get('os_version', None):
            del self.host_meta['os_version']
        if self.host_meta.get('os_status', None):
            del self.host_meta['os_status']
        self._clean_all_host()
        self._clean_all_cluster()
        # self._clean_all_physical_node()
        super(DaisyHostTest, self).tearDown()
