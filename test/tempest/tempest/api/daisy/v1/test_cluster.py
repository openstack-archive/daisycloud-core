# -*- coding: UTF-8 -*-
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


import logging
from tempest.api.daisy import base
from tempest import config
from fake.logical_network_fake import FakeLogicNetwork as logical_fake
import copy

CONF = config.CONF
LOG = logging.getLogger(__name__)


class TecsClusterTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(TecsClusterTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.host_meta = {'name': 'test_add_host',
                         'description': 'test_tempest'}
        cls.cluster_meta1 = {'description': 'desc',
                             'name': 'test'}

        cls.cluster_meta2 = \
            {'description': 'desc',
             'logic_networks':
                 [{'name': 'external1',
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
                                                     '172.16.1.150']],
                                'gateway': '172.16.1.1',
                                'name': 'subnet10'}],
                   'type': 'external'},
                  {'name': 'internal1',
                   'physnet_name': 'phynet1',
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
                          'subnets': ['subnet4']},
                         {'description': 'router2',
                          'external_logic_network': 'external1',
                          'name': 'router2',
                          'subnets': ['subnet10']}]}
        cls.cluster_meta3 = {'description': "This cluster's name is null",
                             'name': ""}
        cls.cluster_meta4 = {'description': "",
                             'name': "rwj_test_add_cluster_no_description"}
        cls.cluster_meta5 = {'description': "test_add_host5",
                             'name': "test_add_host5"}
        cls.cluster_meta6 = {'description': "test_add_host6",
                             'name': "test_add_host6"}
        cls.cluster_meta7 = {'description': "test_add_host7",
                             'name': "test_add_host7"}
        cls.cluster_meta8 = {'description': "test_add_host7",
                             'name': "test_add_host7",
                             'auto_scale': 1}
        cls.cluster_meta9 = {'description': "test_with_hwm",
                             'name': "test_with_hwm",
                             'hwm_ip': "10.43.211.63"}

    def private_network_add(self):
        private_network_params = self.fake.fake_private_network_parameters()
        private_network_params1 = self.fake.fake_private_network_parameters1()
        private_network_params2 = self.fake.fake_private_network_parameters2()

        private_network_params = self.add_network(**private_network_params)
        private_network_params1 = self.add_network(**private_network_params1)
        private_network_params2 = self.add_network(**private_network_params2)

        self.private_network_id = private_network_params.id
        self.private_network_id1 = private_network_params1.id
        self.private_network_id2 = private_network_params2.id

        self.cluster_meta2['networks'] = [self.private_network_id,
                                          self.private_network_id1,
                                          self.private_network_id2]

        return copy.deepcopy(private_network_params)

    def private_network_delete(self):
        self.delete_network(self.private_network_id)
        self.delete_network(self.private_network_id1)
        self.delete_network(self.private_network_id2)

    def test_add_cluster_with_networking_parameters(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta2)
        self.assertEqual(self.cluster_meta2['name'],
                         cluster_info.name,
                         "cluster name is not correct")
        self.assertEqual(self.cluster_meta2['description'],
                         cluster_info.description,
                         "cluster add  interface execute failed")
        self.assertEqual(
            self.cluster_meta2['networking_parameters']['base_mac'],
            cluster_info.base_mac,
            "cluster add  interface execute failed")
        self.assertEqual(
            self.cluster_meta2['networking_parameters']['net_l23_provider'],
            cluster_info.net_l23_provider,
            "cluster add  interface execute failed")
        self.assertEqual(
            self.cluster_meta2['networking_parameters']['public_vip'],
            cluster_info.public_vip,
            "cluster add  interface execute failed")
        self.assertEqual(
            self.cluster_meta2['networking_parameters']['segmentation_type'],
            cluster_info.segmentation_type,
            "cluster add  interface execute failed")
        self.delete_cluster(cluster_info.id)

    def test_add_cluster_no_networking_parameters(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta1)
        self.assertEqual(self.cluster_meta1['name'],
                         cluster_info.name,
                         "cluster add interface is not correct")
        self.assertEqual(self.cluster_meta1['description'],
                         cluster_info.description,
                         "cluster add  interface execute failed")
        self.delete_cluster(cluster_info.id)

    def test_add_cluster_with_networking_parameters_no_routers(self):
        if self.cluster_meta2.get('routers', None):
            self.private_network_add()
            cluster_temp = self.cluster_meta2.copy()
            del cluster_temp['routers']
            cluster_info = self.add_cluster(**cluster_temp)
            # cluster = self.get_cluster(cluster_info.id)
            self.assertEqual(cluster_temp['name'],
                             cluster_info.name,
                             "cluster add  interface execute failed")
            self.delete_cluster(cluster_info.id)

    def test_add_cluster_with_nodes(self):
        host_info = self.add_host(**self.host_meta)
        nodes = []
        nodes.append(host_info.id)
        self.cluster_meta1['nodes'] = nodes
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta1)
        cluster = self.get_cluster(cluster_info.id)
        self.assertEqual(self.cluster_meta1['name'],
                         cluster.name,
                         "add cluster with nodes  is not correct")
        self.assertEqual(self.cluster_meta1['description'],
                         cluster.description,
                         "add cluster with nodes execute failed")
        self.assertEqual(self.cluster_meta1['nodes'],
                         cluster.nodes,
                         "add cluster with nodes execute failed")
        self.delete_cluster(cluster_info.id)
        self.delete_host(host_info.id)

    def test_update_cluster_with_no_networking_parameters(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta1)
        self.cluster_meta1['name'] = "test_name"
        self.cluster_meta1['description'] = "test_desc"
        cluster_update_info = self.update_cluster(cluster_info.id,
                                                  **self.cluster_meta1)
        self.assertEqual(self.cluster_meta1['name'],
                         cluster_update_info.name,
                         "cluster update interface is not correct")
        self.assertEqual(self.cluster_meta1['description'],
                         cluster_update_info.description,
                         "cluster update  interface is not correct")
        self.delete_cluster(cluster_info.id)

    def test_update_cluster_with_nodes(self):
        host_info = self.add_host(**self.host_meta)
        nodes = []
        nodes.append(host_info.id)
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta1)
        self.cluster_meta1['nodes'] = nodes
        cluster_update_info = self.update_cluster(cluster_info.id,
                                                  **self.cluster_meta1)
        cluster = self.get_cluster(cluster_info.id)
        self.assertEqual(self.cluster_meta1['name'],
                         cluster_update_info.name,
                         "update cluster with nodes  is not correct")
        self.assertEqual(self.cluster_meta1['description'],
                         cluster_update_info.description,
                         "update cluster with nodes execute failed")
        self.assertEqual(self.cluster_meta1['nodes'],
                         cluster.nodes,
                         "update cluster with nodes execute failed")
        self.delete_cluster(cluster_info.id)
        self.delete_host(host_info.id)

    def test_update_cluster_with_networking_parameters(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta1)
        cluster_update_info = self.update_cluster(cluster_info.id,
                                                  **self.cluster_meta2)
        self.assertEqual(self.cluster_meta2['name'],
                         cluster_update_info.name,
                         "update cluster with networking parameters "
                         "is not correct")
        self.assertEqual(self.cluster_meta2['description'],
                         cluster_update_info.description,
                         "update cluster with networking parameters "
                         "execute failed")
        # cluster = self.get_cluster(cluster_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_cluster_with_hwm(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta1)
        hwm_meta = {"hwm_ip": "10.43.211.63"}
        cluster_update_info = self.update_cluster(cluster_info.id,
                                                  **hwm_meta)
        self.assertEqual("10.43.211.63",
                         cluster_update_info.hwm_ip,
                         "Update cluster with hwm_ip failed")
        self.delete_cluster(cluster_info.id)

    def test_update_cluster_with_networking_parameters_add_router(self):
        """ """
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta2)
        router = {'description': 'router3',
                  'external_logic_network': 'external1',
                  'name': 'router3',
                  'subnets': ['subnet3']}
        self.cluster_meta2['routers'].append(router)

        cluster_update_info = self.update_cluster(cluster_info.id,
                                                  **self.cluster_meta2)
        self.assertEqual(self.cluster_meta2['name'],
                         cluster_update_info.name,
                         "update cluster with networking parameters "
                         "is not correct")
        self.assertEqual(self.cluster_meta2['description'],
                         cluster_update_info.description,
                         "update cluster with networking parameters "
                         "execute failed")
        # cluster = self.get_cluster(cluster_info.id)
        self.delete_cluster(cluster_info.id)

    def test_list_cluster(self):
        # filter_cluster_meta = {}
        # self.list_clusters()
        pass

    def test_list_cluster_filter_by_name(self):
        self.add_cluster(**self.cluster_meta1)
        # cluster_info5 = self.add_cluster(**self.cluster_meta5)
        filter_cluster_meta = {'name': "test"}
        list_clusters = self.list_filter_clusters(**filter_cluster_meta)
        cluster_flag = False
        for query_cluster in list_clusters:
            if query_cluster.name == "test":
                cluster_flag = True
        self.assertTrue(cluster_flag,
                        "test_list_cluster_filter_by_name error")

    def test_delete_cluster(self):
        cluster_info1 = self.add_cluster(**self.cluster_meta1)
        cluster_info5 = self.add_cluster(**self.cluster_meta5)
        self.delete_cluster(cluster_info1.id)
        cluster_flag = True
        cluster_meta = {}
        list_cluster = self.list_clusters(**cluster_meta)
        for query_cluster in list_cluster:
            if query_cluster.id == cluster_info1.id:
                    cluster_flag = False
        self.assertTrue(cluster_flag, "test_delete_cluster error")
        self.delete_cluster(cluster_info5.id)

    def test_list_cluster_by_sort_key(self):
        cluster_info5 = self.add_cluster(**self.cluster_meta5)
        cluster_info6 = self.add_cluster(**self.cluster_meta6)
        cluster_info7 = self.add_cluster(**self.cluster_meta7)
        cluster_id_sort = sorted([cluster_info5.id,
                                  cluster_info6.id,
                                  cluster_info7.id],
                                 reverse=True)
        cluster_meta = {'sort_key': "id"}
        list_cluster = self.list_clusters(**cluster_meta)
        query_cluster_id_list = [cluster_info.id for cluster_info
                                 in list_cluster]
        self.assertEqual(query_cluster_id_list, cluster_id_sort,
                         "test_list_cluster_by_sort_key error")
        self.delete_cluster(cluster_info5.id)
        self.delete_cluster(cluster_info6.id)
        self.delete_cluster(cluster_info7.id)

    def test_list_cluster_by_sort_dir(self):
        cluster_info5 = self.add_cluster(**self.cluster_meta5)
        cluster_info6 = self.add_cluster(**self.cluster_meta6)
        cluster_info7 = self.add_cluster(**self.cluster_meta7)
        cluster_name_sort = ['test_add_host7',
                             'test_add_host6',
                             'test_add_host5']
        cluster_meta = {'sort_dir': "desc", 'sort_key': "name"}
        list_cluster = self.list_clusters(**cluster_meta)
        query_cluster_name_list = [cluster_info.name for cluster_info
                                   in list_cluster]
        self.assertEqual(query_cluster_name_list, cluster_name_sort,
                         "test_list_cluster_by_sort_dir error")
        self.delete_cluster(cluster_info5.id)
        self.delete_cluster(cluster_info6.id)
        self.delete_cluster(cluster_info7.id)

    def test_list_cluster_by_sort_limit(self):
        cluster_info5 = self.add_cluster(**self.cluster_meta5)
        cluster_info6 = self.add_cluster(**self.cluster_meta6)
        cluster_info7 = self.add_cluster(**self.cluster_meta7)
        cluster_meta = {'page_size': "1",
                        'sort_dir': "desc",
                        'sort_key': "name"}
        list_cluster = self.list_clusters(**cluster_meta)
        query_cluster_id_list = [cluster_info.id for cluster_info
                                 in list_cluster]
        self.assertEqual(query_cluster_id_list,
                         [cluster_info7.id],
                         "test_list_cluster_by_sort_key error")
        self.delete_cluster(cluster_info5.id)
        self.delete_cluster(cluster_info6.id)
        self.delete_cluster(cluster_info7.id)

    def test_add_cluster_with_neutron_parameters(self):
        self.private_network_add()
        add_host = self.add_cluster(**self.cluster_meta2)
        cluster_detail = self.get_cluster(add_host.id)
        self.assertEqual(
            self.cluster_meta2['networking_parameters']['base_mac'],
            cluster_detail.base_mac,
            "cluster add  networking_parameters failed")
        router_flag = False
        floating_ranges_flag = False
        dns_nameservers_flag = False
        if (cluster_detail.routers[0]['name'] == 'router1')
                or (cluster_detail.routers[0]['name'] == 'router2'):
            router_flag = True

        floating_ranges = cluster_detail.logic_networks[0]\
            ['subnets'][0]['floating_ranges']
        if (floating_ranges == [['192.168.4.130', '192.168.4.254']]) or \
                (floating_ranges == [['192.168.1.2', '192.168.1.200']]) or \
                (floating_ranges == [['172.16.1.130', '172.16.1.150']]) or \
                (floating_ranges == [['192.168.31.130', '192.168.31.254']]):
            floating_ranges_flag = True

        dns_nameservers = cluster_detail.logic_networks[0]\
            ['subnets'][0]['dns_nameservers']
        if dns_nameservers == ['8.8.8.8', '8.8.4.4'] or \
                dns_nameservers == ['8.8.4.4', '8.8.8.8']:
            dns_nameservers_flag = True

        self.assertTrue(router_flag, "cluster add floating_ranges failed")
        self.assertTrue(floating_ranges_flag,
                        "cluster add floating_ranges failed")
        self.assertTrue(dns_nameservers_flag,
                        "cluster add dns_nameservers failed")
        self.delete_cluster(add_host.id)

    def test_cluster_detail_info(self):
        self.private_network_add()
        add_cluster = self.add_cluster(**self.cluster_meta2)
        cluster_detail = self.get_cluster(add_cluster.id)
        self.assertEqual(
            self.cluster_meta2['networking_parameters']['base_mac'],
            cluster_detail.base_mac,
            "cluster base_mac detail failed")
        self.assertEqual(self.cluster_meta2['name'],
                         cluster_detail.name,
                         "cluster name detail failed")
        self.assertEqual(self.cluster_meta2['description'],
                         cluster_detail.description,
                         "cluster description detail failed")
        self.assertEqual(
            self.cluster_meta2['networking_parameters']['public_vip'],
            cluster_detail.public_vip,
            "cluster public_vip detail failed")
        self.private_network_delete()

    def test_add_cluster_no_description(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta4)
        if cluster_info.description is None:
            self.assertEqual(self.cluster_meta4['description'],
                             cluster_info.description,
                             "cluster add  interface execute failed")
            print("\n ===========cluster_description= %s ",
                  cluster_info.description)
        print("\n ===========STC-F-Daisy_Cluster-0013  run is over "
              " ===============")
        self.delete_cluster(cluster_info.id)

    def test_add_cluster_set_auto_scale(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta8)
        if cluster_info:
            self.assertEqual(self.cluster_meta8['auto_scale'],
                             cluster_info.auto_scale,
                             "cluster add set auto_scale=1 failed")
            print("\n ===========cluster auto_scale= %s ",
                  cluster_info.auto_scale)
        print("\n ===========STC-F-Daisy_Cluster-0020  run is over "
              "===============")
        self.delete_cluster(cluster_info.id)

    def test_add_cluster_with_hwm(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta9)
        if cluster_info:
            self.assertEqual(self.cluster_meta9['hwm_ip'],
                             cluster_info.hwm_ip,
                             "Add cluster with hwm_ip failed")
        self.delete_cluster(cluster_info.id)

    def tearDown(self):
        if self.cluster_meta1.get('nodes', None):
            del self.cluster_meta1['nodes']
        self._clean_all_cluster()
        super(TecsClusterTest, self).tearDown()
