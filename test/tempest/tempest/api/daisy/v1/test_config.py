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

from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
import copy
from nose.tools import set_trace
from daisy.common import exception
from daisyclient import exc as client_exc
from fake.logical_network_fake import FakeLogicNetwork as logical_fake

class DaisyConfigTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyConfigTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.cluster_meta = {'description': 'desc',
                            'logic_networks': [{'name': 'external1',
                            'physnet_name': 'phynet2',
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
                            'type': 'external'},
                           {'name': 'internal2',
                            'physnet_name': 'phynet1',
                            'segmentation_id': 1023,
                            'segmentation_type': 'vxlan',
                            'shared': True,
                            'subnets': [{'cidr': '192.168.2.0/24',
                                         'dns_nameservers': ['8.8.4.4',
                                                             '8.8.8.8'],
                                         'floating_ranges': [['192.168.2.130',
                                                              '192.168.2.254']],
                                         'gateway': '192.168.2.1',
                                         'name': 'subnet123'}],
                            'type': 'internal'},
                           {'name': 'internal1',
                            'physnet_name': 'phynet3',
                            'segmentation_id': '777',
                            'segmentation_type': 'vlan',
                            'shared': False,
                            'subnets': [{'cidr': '192.168.31.0/24',
                                         'dns_nameservers': ['8.8.4.4',
                                                             '8.8.8.8'],
                                         'floating_ranges': [['192.168.31.130',
                                                              '192.168.31.254']],
                                         'gateway': '192.168.31.1',
                                         'name': 'subnet3'},
                                        {'cidr': '192.168.4.0/24',
                                         'dns_nameservers': ['8.8.4.4',
                                                             '8.8.8.8'],
                                         'floating_ranges': [['192.168.4.130',
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
        cls.config_meta={'file-name':'/home/config-test/test.conf',
                         'section':'default',
                         'key':'test',
                         'value':'1'}
        cls.config_meta1={'file-name':'/home/config-test/test1.conf',
                         'section':'default',
                         'key':'test1',
                         'value':'2'}

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

    def test_add_config_with_cluster_role_and_a_configuration_item(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='CONTROLLER_HA'
        config_para['config']=[self.config_meta]
        config_info=self.add_config(**config_para)
        for config in config_info.config:
            config_config_version=config['config_version']
            config_running_version=config['running_version']
            self.assertNotEqual(config_config_version, config_running_version)
            self.assertEqual(1, config_config_version)
        self.private_network_delete()

    def test_config_get(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='CONTROLLER_HA'
        config_para['config']=[self.config_meta]
        config_info=self.add_config(**config_para)
        for config_info_id in config_info.config:
            config_id=config_info_id['id']
            get_config_info=self.get_config(config_id)
            self.assertNotEqual(get_config_info.config_version, get_config_info.running_version)
            self.assertEqual(1, get_config_info.config_version)
        self.private_network_delete()

    def test_add_config_with_cluster_role_and_multiple_configuration_items(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='CONTROLLER_HA'
        config_para['config']=[self.config_meta,self.config_meta1]
        config_info=self.add_config(**config_para)
        for config in config_info.config:
            config_config_version=config['config_version']
            config_running_version=config['running_version']
            self.assertNotEqual(config_config_version, config_running_version)
            self.assertEqual(1, config_config_version)
        self.private_network_delete()

    def test_add_config_with_config_set_id_and_a_configuration_item(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        roles=self.list_roles()
        for role in roles:
            if role.cluster_id == cluster_info.id and role.name == "CONTROLLER_HA":
                config_set_id=role.config_set_id
        config_para={}
        config_para['config_set']=config_set_id
        config_para['config']=[self.config_meta]
        config_info=self.add_config(**config_para)

        for config in config_info.config:
            config_config_version=config['config_version']
            config_running_version=config['running_version']
            self.assertNotEqual(config_config_version, config_running_version)
            self.assertEqual(1, config_config_version)
        self.private_network_delete()

    def test_update_config_with_cluster_role_and_a_configuration_item(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='CONTROLLER_HA'
        config_para['config']=[self.config_meta]
        config_info=self.add_config(**config_para)

        update_config_meta={'file-name':'/home/config-test/test.conf',
                         'section':'default',
                         'key':'test',
                         'value':'2'}
        config_para['config']=[update_config_meta]
        config_info=self.add_config(**config_para)
        for config in config_info.config:
            config_config_version=config['config_version']
            config_running_version=config['running_version']
            self.assertNotEqual(config_config_version, config_running_version)
            self.assertEqual(2, config_config_version)
        self.private_network_delete()

    def test_delete_config(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='CONTROLLER_HA'
        config_para['config']=[self.config_meta]
        config_info=self.add_config(**config_para)
        for config_info_id in config_info.config:
            config_id=config_info_id['id']
        self.delete_config(config_id)
        self.private_network_delete()

    def test_update_config_with_cluster_role_and_multiple_configuration_items(self):
        self.private_network_add()
        # set_trace()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='CONTROLLER_HA'
        config_para['config']=[self.config_meta,self.config_meta1]
        config_info=self.add_config(**config_para)

        update_config_meta={'file-name':'/home/config-test/test.conf',
                         'section':'default',
                         'key':'test',
                         'value':'2'}
        update_config_meta1={'file-name':'/home/config-test/test1.conf',
                 'section':'default',
                 'key':'test1',
                 'value':'3'}
        config_para['config']=[update_config_meta,update_config_meta1]
        config_info=self.add_config(**config_para)
        for config in config_info.config:
            config_config_version=config['config_version']
            config_running_version=config['running_version']
            self.assertNotEqual(config_config_version, config_running_version)
            self.assertEqual(2, config_config_version)
        self.private_network_delete()

    def test_config_list(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='CONTROLLER_HA'
        config_para['config']=[self.config_meta,self.config_meta1]
        config_info=self.add_config(**config_para)
        config_list=self.list_config()
        for config_info in config_list:
            config_id=config_info.id
            get_config_info=self.get_config(config_id)
            self.assertNotEqual(get_config_info.config_version, get_config_info.running_version)
        self.private_network_delete()

    def test_add_config_with_cluster_and_error_role_name(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        config_para={}
        config_para['cluster']=cluster_info.id
        config_para['role']='error_role_name'
        config_para['config']=[self.config_meta]
        self.assertRaisesMessage(client_exc.HTTPNotFound,
            "404 Not Found: The resource could not be found.: the role name is not exist (HTTP 404)",
            self.add_config, **config_para)
        self.private_network_delete()

    def test_add_config_with_error_cluster_and_role(self):
        config_para={}
        config_para['role']='CONTROLLER_HA'
        config_para['cluster']="c79e1d0d-a889-4b11-b77d-9dbbed455bb"
        config_para['config']=[self.config_meta]
        self.assertRaisesMessage(client_exc.HTTPNotFound,
            "404 Not Found: The resource could not be found.: Cluster with identifier %s not found (HTTP 404)" % config_para['cluster'],
             self.add_config, **config_para)


    def tearDown(self):
        self._clean_all_cluster()
        self._clean_all_config()
        super(DaisyConfigTest, self).tearDown()

