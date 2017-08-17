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

from daisy.api.v1 import networks
from daisy.common import exception
from daisy.context import RequestContext
#import daisy.registry.client.v1.api as registry
from daisy import test
import mock
from oslo_serialization import jsonutils
import webob
from webob import exc

network_list = [{u'alias': None,
                 u'capability': u'high',
                 u'cidr': u'192.168.1.1/24',
                 u'cluster_id': u'63d26456-9975-4d7c-a400-45a1ae64b9f3',
                 u'created_at': u'2016-08-31T02:40:17.000000',
                 u'deleted': False,
                 u'deleted_at': None,
                 u'description': u'',
                 u'gateway': u'',
                 u'gre_id_end': None,
                 u'gre_id_start': None,
                 u'id': u'8f7cc123-08d6-4424-9352-383bc5890bb6',
                 u'ip': None,
                 u'ip_ranges': [],
                 u'ml2_type': None,
                 u'mtu': 1500,
                 u'name': u'PUBLICAPI',
                 u'network_type': u'PUBLICAPI',
                 u'physnet_name': u'physnet_enp132s0f1',
                 u'segmentation_type': None,
                 u'type': u'default',
                 u'updated_at': u'2016-08-31T02:41:16.000000',
                 u'vlan_end': 4094,
                 u'vlan_id': None,
                 u'vlan_start': 1,
                 u'vni_end': None,
                 u'vni_start': None},
                {u'alias': None,
                 u'capability': u'high',
                 u'cidr': u'192.168.1.1/24',
                 u'cluster_id': u'63d26456-9975-4d7c-a400-45a1ae64b9f3',
                 u'created_at': u'2016-08-31T02:40:17.000000',
                 u'deleted': False,
                 u'deleted_at': None,
                 u'description': u'',
                 u'gateway': None,
                 u'gre_id_end': None,
                 u'gre_id_start': None,
                 u'id': u'79052a8a-b51f-461a-bdbc-c36bc69d6126',
                 u'ip': None,
                 u'ip_ranges': [],
                 u'ml2_type': u'ovs',
                 u'mtu': 1500,
                 u'name': u'physnet1',
                 u'network_type': u'DATAPLANE',
                 u'physnet_name': u'physnet_enp132s0f2',
                 u'segmentation_type': u'vlan',
                 u'type': u'default',
                 u'updated_at': u'2016-08-31T02:41:38.000000',
                 u'vlan_end': 4094,
                 u'vlan_id': None,
                 u'vlan_start': 1,
                 u'vni_end': None,
                 u'vni_start': None},
                {u'alias': None,
                 u'capability': u'high',
                 u'cidr': u'199.168.1.1/24',
                 u'cluster_id': u'63d26456-9975-4d7c-a400-45a1ae64b9f3',
                 u'created_at': u'2016-08-31T02:40:17.000000',
                 u'deleted': False,
                 u'deleted_at': None,
                 u'description': u'',
                 u'gateway': u'',
                 u'gre_id_end': None,
                 u'gre_id_start': None,
                 u'id': u'1fafc035-d945-4cf1-807a-86d2a6c2a65c',
                 u'ip': None,
                 u'ip_ranges': [],
                 u'ml2_type': None,
                 u'mtu': 1500,
                 u'name': u'MANAGEMENT',
                 u'network_type': u'MANAGEMENT',
                 u'physnet_name': u'physnet_enp132s0f0',
                 u'segmentation_type': None,
                 u'type': u'default',
                 u'updated_at': u'2016-08-31T02:41:38.000000',
                 u'vlan_end': 4094,
                 u'vlan_id': None,
                 u'vlan_start': 1,
                 u'vni_end': None,
                 u'vni_start': None}]


class TestNetworkApi(test.TestCase):

    def setUp(self):
        super(TestNetworkApi, self).setUp()
        self.controller = networks.Controller()

    @mock.patch("daisy.registry.client.v1.api.get_networks_detail")
    @mock.patch("daisy.registry.client.v1.api.update_network_metadata")
    @mock.patch("daisy.api.v1.networks.Controller.get_network_meta_or_404")
    @mock.patch('daisy.registry.client.v1.api.'
                'get_assigned_networks_data_by_network_id')
    def test_update_network(
            self, get_assigned_networks_data_by_network_id,
            mock_get_network_meta_or_404, mock_update_network_metadata,
            mock_get_networks_detail):
        mock_get_network_meta_or_404.return_value = network_list[0]
        #self.controller.get_network_meta_or_404 = \
        #    mock.Mock(return_value=network_list[0])
        mock_get_networks_detail.return_value = network_list
        #registry.get_networks_detail = mock.Mock(return_value=network_list)
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_id = "123"
        network_meta = {'network_type': 'DATAPLANE',
                        'cluster_id': 'test', 'gateway': '192.168.1.1'}
        mock_update_network_metadata.return_value = network_meta
        get_assigned_networks_data_by_network_id.return_value = []
        update_network = self.controller.update_network(
            req, network_id, network_meta)
        self.assertEqual(network_meta['network_type'],
                         update_network['network_meta']['network_type'])

    @mock.patch("daisy.registry.client.v1.api.add_network_metadata")
    def test_add_network(self, mock_add_network_metadata):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_meta = {'network_type': 'DATAPLANE',
                        'gateway': '192.168.1.1', 'name': 'pysnet1'}
        mock_add_network_metadata.return_value = network_meta
        #registry.add_network_metadata = mock.Mock(return_value=network_meta)
        add_network = self.controller.add_network(req, network_meta)
        self.assertEqual(network_meta['network_type'],
                         add_network['network_meta']['network_type'])

    def test_verify_uniqueness_of_network_custom_name(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        networks = {u'networks': [
                    {u'name': u'PUBLICAPI',
                     u'network_type': u'PUBLICAPI',
                     u'custom_name': u'publicapi'},
                    {u'name': u'physnet1',
                     u'network_type': u'DATAPLANE',
                     u'custom_name': u'physneta'},
                    {u'name': u'MANAGEMENT',
                     u'network_type': u'MANAGEMENT',
                     u'custom_name': u'management'}]}
        network_meta = {u'custom_name': u'management'}
        self.assertRaises(
            webob.exc.HTTPConflict,
            self.controller._verify_uniqueness_of_network_custom_name,
            req, networks, network_meta)

    @mock.patch('daisy.registry.client.v1.api.add_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    def test_add_network_with_no_exist_custom_name(self,
                                                   get_cluster,
                                                   get_networks,
                                                   add_network):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_meta = {'cluster_id': '1',
                        'network_type': 'MANAGEMENT',
                        'custom_name': 'management1',
                        'name': 'MANAGEMENT1'}
        cluster = {'id': '1',
                   'deleted': 0}
        networks = [{'name': 'PUBLICAPI',
                     'network_type': 'PUBLICAPI',
                     'custom_name': None},
                    {'name': 'physnet1',
                     'network_type': 'DATAPLANE',
                     'custom_name': 'physnet2'}]
        return_network = {'name': 'MANAGEMENT1',
                          'network_type': 'MANAGEMENT',
                          'custom_name': 'management1'}
        get_cluster.return_value = cluster
        get_networks.return_value = networks
        add_network.return_value = return_network
        network = self.controller.add_network(req, network_meta)
        self.assertEqual('management1',
                         network['network_meta']['custom_name'])

    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    def test_add_network_with_exist_custom_name(self,
                                                get_cluster,
                                                get_networks):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_meta = {'cluster_id': '1',
                        'network_type': 'MANAGEMENT',
                        'custom_name': 'management1',
                        'name': 'MANAGEMENT1'}
        cluster = {'id': '1',
                   'deleted': 0}
        networks_with_same_custom_name = [{'name': 'PUBLICAPI',
                                           'network_type': 'PUBLICAPI',
                                           'custom_name': None},
                                          {'name': 'physnet1',
                                           'network_type': 'DATAPLANE'},
                                          {'name': 'STORAGE',
                                           'network_type': 'STORAGE',
                                           'custom_name': 'management1'}]
        get_cluster.return_value = cluster
        get_networks.return_value = networks_with_same_custom_name
        self.assertRaises(webob.exc.HTTPConflict, self.controller.add_network,
                          req, network_meta)

    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_with_no_exist_custom_name(self,
                                                      get_network_meta,
                                                      get_cluster_meta,
                                                      get_networks_detail,
                                                      update_network):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_id = '1'
        network_meta = {'custom_name': 'publicapi1'}
        orig_network_meta = {'deleted': False,
                             'cluster_id': '1',
                             'id': '1',
                             'network_type': 'PUBLICAPI',
                             'cidr': '192.168.1.1/24',
                             'vlan_id': None,
                             'custom_name': 'publicapi',
                             'gateway': None}
        cluster_meta = {'id': '1',
                        'deleted': False}
        networks_detail = [{'deleted': False,
                            'cluster_id': '1',
                            'id': '1',
                            'network_type': 'PUBLICAPI',
                            'cidr': '192.168.1.1/24',
                            'vlan_id': None,
                            'custom_name': 'publicapi'},
                           {'deleted': False,
                            'cluster_id': '1',
                            'id': '2',
                            'network_type': 'MANAGEMENT',
                            'cidr': '192.168.1.1/24',
                            'vlan_id': None,
                            'custom_name': 'management'},
                           {'deleted': False,
                            'cluster_id': '1',
                            'id': '3',
                            'network_type': 'DATAPLANE',
                            'cidr': None,
                            'vlan_id': None,
                            'custom_name': 'physnet'}]
        update_network_meta = {'deleted': False,
                               'cluster_id': '1',
                               'id': '1',
                               'network_type': 'PUBLICAPI',
                               'cidr': '192.168.1.1/24',
                               'vlan_id': None,
                               'custom_name': 'publicapi1'}
        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        update_network.return_value = update_network_meta
        network_meta = self.controller.update_network(req, network_id,
                                                      network_meta)
        self.assertEqual('publicapi1',
                         network_meta['network_meta']['custom_name'])

    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_with_original_custom_name(self,
                                                      get_network_meta,
                                                      get_cluster_meta,
                                                      get_networks_detail,
                                                      update_network):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_id = '1'
        network_meta = {'custom_name': 'publicapi'}
        orig_network_meta = {'deleted': False,
                             'cluster_id': '1',
                             'id': '1',
                             'network_type': 'PUBLICAPI',
                             'cidr': '192.168.1.1/24',
                             'vlan_id': None,
                             'custom_name': 'publicapi',
                             'gateway': None}
        cluster_meta = {'id': '1',
                        'deleted': False}
        networks_detail = [{'deleted': False,
                            'cluster_id': '1',
                            'id': '1',
                            'network_type': 'PUBLICAPI',
                            'cidr': '192.168.1.1/24',
                            'vlan_id': None,
                            'custom_name': 'publicapi'}]
        update_network_meta = {'deleted': False,
                               'cluster_id': '1',
                               'id': '1',
                               'network_type': 'PUBLICAPI',
                               'cidr': '192.168.1.1/24',
                               'vlan_id': None,
                               'custom_name': 'publicapi'}
        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        update_network.return_value = update_network_meta
        network_meta = self.controller.update_network(req, network_id,
                                                      network_meta)
        self.assertEqual('publicapi',
                         network_meta['network_meta']['custom_name'])

    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_another_network_with_same_custom_name(self,
                                                          get_network_meta,
                                                          get_cluster_meta,
                                                          get_networks_detail):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_id = '2'
        network_meta = {'custom_name': 'publicapi'}
        orig_network_meta = {'deleted': False,
                             'cluster_id': '1',
                             'id': '1',
                             'network_type': 'PUBLICAPI',
                             'cidr': '192.168.1.1/24',
                             'vlan_id': None,
                             'custom_name': 'publicapi',
                             'gateway': None}
        cluster_meta = {'id': '1',
                        'deleted': False}
        networks_detail = [{'deleted': False,
                            'cluster_id': '1',
                            'id': '1',
                            'network_type': 'PUBLICAPI',
                            'cidr': '192.168.1.1/24',
                            'vlan_id': None,
                            'custom_name': 'publicapi'},
                           {'deleted': False,
                            'cluster_id': '1',
                            'id': '2',
                            'network_type': 'MANAGEMENT',
                            'cidr': '192.168.1.1/24',
                            'vlan_id': None,
                            'custom_name': 'management'}]
        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        self.assertRaises(webob.exc.HTTPConflict,
                          self.controller.update_network,
                          req, network_id, network_meta)

    @mock.patch('daisy.registry.client.v1.api.'
                'get_assigned_networks_data_by_network_id')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_with_forbidden_change_segment_type(
            self, get_network_meta, get_cluster_meta,
            get_networks_detail,
            get_assigned_networks_data_by_network_id):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_id = 'cf531581-a283-41dd-9e4e-4b98454d54e7'
        network_meta = {
            'cluster_id': '1',
            'custom_name': '',
            'description': '',
            'name': 'physnet1',
            'network_type': 'DATAPLANE',
            'segmentation_type': 'vlan',
            'vlan_end': '4090',
            'vlan_start': '1'}
        orig_network_meta = {'cidr': '1.2.3.4/24',
                             'vlan_id': None,
                             'cluster_id': '1',
                             'deleted': False,
                             'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                             'network_type': 'DATAPLANE',
                             'segmentation_type': 'vxlan',
                             'type': 'default'}
        cluster_meta = {'id': '1',
                        'deleted': False}
        networks_detail = [
            {
                'alias': None,
                'capability': 'high',
                'cidr': '1.2.3.4/24',
                'cluster_id': '1',
                'custom_name': '',
                'deleted': False,
                'gateway': '1.2.3.4',
                'gre_id_end': None,
                'gre_id_start': None,
                'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                'ip': None,
                'ip_ranges': [
                    {
                        'end': '1.2.3.6',
                        'start': '1.2.3.4'}],
                'ml2_type': 'ovs',
                'mt': 1500,
                'name': 'physnet1',
                'network_type': 'DATAPLANE',
                'physnet_name': 'physnet_eth1',
                'segmentation_type': 'vxlan',
                'type': 'default',
                'updated_at': '2015-05-07T04:26:28.000000',
                'vlan_end': 4090,
                'vlan_id': None,
                'vlan_start': 1,
                'vni_end': 20,
                'vni_start': 1}]
        assigned_network = [
            {
                'deleted': False,
                'id': '658333cf-93d4-499b-8bff-e8bd6bcbb5f1',
                'interface_id': '4de86a45-af28-4362-b5f0-afeee235786f',
                'ip': '1.2.3.4',
                'mac': 'fa:16:3e:7b:1a:95',
                'network_id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                'updated_at': '2015-05-07T04:01:59.000000',
                'vswitch_type': 'dvs'}]

        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        get_assigned_networks_data_by_network_id.return_value = \
            assigned_network
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller.update_network,
                          req, network_id, network_meta)

    @mock.patch('daisy.registry.client.v1.api.'
                'get_assigned_networks_data_by_network_id')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_with_assigned_network_not_found(
            self, get_network_meta, get_cluster_meta,
            get_networks_detail,
            get_assigned_networks_data_by_network_id):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_id = 'cf531581-a283-41dd-9e4e-4b98454d54e7'
        network_meta = {'cluster_id': '1',
                        'custom_name': '',
                        'description': '',
                        'name': 'physnet1',
                        'network_type': 'DATAPLANE',
                        'segmentation_type': 'vlan',
                        'vlan_end': '4090',
                        'vlan_start': '1'}
        orig_network_meta = {'cidr': '1.2.3.4/24',
                             'vlan_id': None,
                             'cluster_id': '1',
                             'deleted': False,
                             'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                             'network_type': 'DATAPLANE',
                             'segmentation_type': 'vxlan',
                             'type': 'default'}
        cluster_meta = {'id': '1',
                        'deleted': False}
        networks_detail = [{'alias': None,
                            'capability': 'high',
                            'cidr': '1.2.3.4/24',
                            'cluster_id': '1',
                            'custom_name': '',
                            'deleted': False,
                            'gateway': '1.2.3.4',
                            'gre_id_end': None,
                            'gre_id_start': None,
                            'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                            'ip': None,
                            'ip_ranges': [
                                {
                                    'end': '1.2.3.6',
                                    'start': '1.2.3.4'}],
                            'ml2_type': 'ovs',
                            'mt': 1500,
                            'name': 'physnet1',
                            'network_type': 'DATAPLANE',
                            'physnet_name': 'physnet_eth1',
                            'segmentation_type': 'vxlan',
                            'type': 'default',
                            'updated_at': '2015-05-07T04:26:28.000000',
                            'vlan_end': 4090,
                            'vlan_id': None,
                            'vlan_start': 1,
                            'vni_end': 20,
                            'vni_start': 1}]
        assigned_network = [
            {'deleted': False,
             'id': '658333cf-93d4-499b-8bff-e8bd6bcbb5f1',
             'interface_id': '4de86a45-af28-4362-b5f0-afeee235786f',
             'ip': '1.2.3.4',
             'mac': 'fa:16:3e:7b:1a:95',
             'network_id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
             'updated_at': '2015-05-07T04:01:59.000000',
             'vswitch_type': 'dvs'}]

        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        get_assigned_networks_data_by_network_id.side_effect = \
            exception.NotFound
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.update_network,
                          req, network_id, network_meta)

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_with_custom_name(
            self, get_network_meta, get_cluster_meta,
            get_networks_detail,
            update_network_metadata,
            mock_do_request):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        network_id = 'cf531581-a283-41dd-9e4e-4b98454d54e7'

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            if method == "GET":
                if path == "/assigned_networks/%s" % network_id:
                    get_result = {'network': []}
                    res.read.return_value = jsonutils.dumps(get_result)
                    return res

        network_meta = {
            'cluster_id': '1',
            'custom_name': 'phy1',
            'network_type': 'DATAPLANE',
            'segmentation_type': 'vlan'}

        orig_network_meta = {
            'cluster_id': '1',
            'custom_name': '',
            'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
            'name': 'physnet1',
            'network_type': 'DATAPLANE',
                            'physnet_name': 'physnet_eth1',
                            'segmentation_type': 'vlan',
                            'type': 'default',
                            'cidr': '',
                            'gateway': '',
                            'deleted': False,
                            'vlan_end': 4090,
                            'vlan_id': None,
                            'vlan_start': 1,
                            'vni_end': 20,
                            'vni_start': 1}

        cluster_meta = {'id': '1',
                        'deleted': False}
        networks_detail = [
            {
                'cluster_id': '1',
                'custom_name': '',
                'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                'name': 'physnet1',
                'network_type': 'DATAPLANE',
                'physnet_name': 'physnet_eth1',
                'segmentation_type': 'vlan',
                'type': 'default',
                'vlan_end': 4090,
                'vlan_id': None,
                'vlan_start': 1,
                'vni_end': 20,
                'vni_start': 1
            }]

        update_network_meta = {'deleted': False,
                               'cluster_id': '1',
                               'network_type': 'DATAPLANE',
                               'custom_name': 'phy1'}

        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        mock_do_request.side_effect = fake_do_request
        update_network_metadata.return_value = update_network_meta
        update_network = self.controller.update_network(
            req, network_id, network_meta)
        self.assertEqual(network_meta['custom_name'],
                         update_network['network_meta']['custom_name'])

    @mock.patch('daisy.api.common.valid_network_range')
    @mock.patch('daisy.registry.client.v1.api.add_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    def test_add_network_invalid_ip_ranges(self, get_cluster, get_networks,
                                           add_network,
                                           fake_valid_network_range):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'start': '12.18.1.5',
                'cidr': '12.18.1.1/24',
                'end': '12.18.1.5',
                'gateway': '12.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.5'
            },
        ]
        network_meta = {'name': 'PUBLICAPI',
                        'network_type': 'PUBLICAPI',
                        'ip_ranges': str(ip_ranges)
                        }
        return_network = {'name': 'MANAGEMENT1',
                          'network_type': 'MANAGEMENT',
                          'custom_name': 'management1'}
        fake_valid_network_range.return_value = True
        self.assertRaises(
            exc.HTTPForbidden, self.controller.add_network, req, network_meta)

    @mock.patch('daisy.api.common.valid_ip_ranges')
    @mock.patch('daisy.api.common.valid_network_range')
    @mock.patch('daisy.registry.client.v1.api.add_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    def test_add_network_publicapi_net(self, get_cluster, get_networks,
                                       add_network, fake_valid_network_range,
                                       fake_valid_ip_ranges):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'start': '112.18.1.5',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.5',
                'gateway': '112.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.1'
            },
        ]
        network_meta = {'name': 'PUBLICAPI',
                        'network_type': 'PUBLICAPI',
                        'ip_ranges': str(ip_ranges),
                        'cidr': '112.18.1.1/24'
                        }
        return_network = {'name': 'PUBLICAPI',
                          'network_type': 'PUBLICAPI'}
        get_cluster.return_value = []
        get_networks.return_value = []
        add_network.return_value = return_network
        fake_valid_network_range.return_value = True
        network = self.controller.add_network(req, network_meta)
        self.assertEqual('PUBLICAPI',
                         network['network_meta']['name'])

    @mock.patch('daisy.api.common.valid_ip_ranges')
    @mock.patch('daisy.api.v1.networks.Controller.get_network_meta_or_404')
    @mock.patch('daisy.api.common.valid_network_range')
    @mock.patch('daisy.registry.client.v1.api.add_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    def test_add_network_with_invalid_ip_ranges(self,
                                                get_cluster,
                                                get_networks,
                                                add_network,
                                                fake_valid_network_range,
                                                fake_get_network_meta_or_404,
                                                fake_valid_ip_ranges):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'start': '112.18.1.5',
                'cidr': '112.18.1.1/24',
                'gateway': '112.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.1'
            },
        ]
        network_meta = {'name': 'PUBLICAPI',
                        'network_type': 'PUBLICAPI',
                        'ip_ranges': str(ip_ranges),
                        'cidr': '112.18.1.1/24'
                        }
        return_network = {'name': 'PUBLICAPI',
                          'network_type': 'PUBLICAPI'}
        # get_cluster.return_value = []
        # get_networks.return_value = []
        # add_network.return_value = return_network
        fake_valid_network_range.return_value = True
        fake_get_network_meta_or_404.return_value = True
        self.assertRaises(
            exc.HTTPForbidden, self.controller.add_network, req, network_meta)

    @mock.patch('daisy.api.common.valid_ip_ranges')
    @mock.patch('daisy.api.common.valid_network_range')
    @mock.patch('daisy.registry.client.v1.api.add_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    def test_add_network_dataplane_net(self, get_cluster, get_networks,
                                       add_network, fake_valid_network_range,
                                       fake_valid_ip_ranges):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'start': '112.18.1.5',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.5',
                'gateway': '112.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.1'
            },
        ]
        network_meta = {'name': 'DATAPLANE',
                        'network_type': 'DATAPLANE',
                        'ip_ranges': str(ip_ranges),
                        'cidr': '112.18.1.1/24',
                        'gateway': '112.18.1.1'
                        }
        return_network = {'name': 'DATAPLANE',
                          'network_type': 'DATAPLANE'}
        get_cluster.return_value = []
        get_networks.return_value = []
        add_network.return_value = return_network
        fake_valid_network_range.return_value = True
        network = self.controller.add_network(req, network_meta)
        self.assertEqual('DATAPLANE',
                         network['network_meta']['name'])

    @mock.patch('daisy.api.common.valid_ip_ranges')
    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.api.v1.networks.Controller._is_dataplane_in_use')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_dataplane_net(self, get_network_meta,
                                          get_cluster_meta,
                                          get_networks_detail,
                                          fake_is_dataplane_in_use,
                                          fake_update_network,
                                          fake_valid_ip_ranges):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'start': '112.18.1.5',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.5',
                'gateway': '112.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.1'
            },
        ]
        network_id = 'cf531581-a283-41dd-9e4e-4b98454d54e7'
        network_meta = {'cluster_id': '1',
                        'name': 'physnet1',
                        'network_type': 'DATAPLANE',
                        'segmentation_type': 'vxlan',
                        'ip_ranges': str(ip_ranges),
                        'cidr': '112.18.1.1/24', }
        orig_network_meta = {'cidr': '112.18.1.1/24',
                             'gateway': '112.18.1.1',
                             'cluster_id': '1',
                             'vlan_id': None,
                             'deleted': False,
                             'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                             'network_type': 'DATAPLANE',
                             'segmentation_type': 'vxlan',
                             'type': 'default'}
        cluster_meta = {'id': '1', 'deleted': False, }
        networks_detail = [{'cluster_id': '1',
                            'gateway': '112.18.1.1',
                            'vlan_id': None,
                            'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                            'ip_ranges': [
                                {
                                    'end': '112.18.1.16',
                                    'start': '112.18.1.17'}],
                            'name': 'physnet1',
                            'network_type': 'DATAPLANE',
                            'physnet_name': 'physnet_eth1',
                            'segmentation_type': 'vxlan',
                            'type': 'default'}]

        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        fake_update_network.return_value = network_meta
        fake_is_dataplane_in_use.return_value = False
        updated_network = self.controller.update_network(
            req, network_id, network_meta)
        self.assertEqual('physnet1', updated_network['network_meta']['name'])

    @mock.patch('daisy.api.common.valid_ip_ranges')
    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.api.v1.networks.Controller._is_dataplane_in_use')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_publicapi_net(self, get_network_meta,
                                          get_cluster_meta,
                                          get_networks_detail,
                                          fake_is_dataplane_in_use,
                                          fake_update_network,
                                          fake_valid_ip_ranges):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'start': '112.18.1.5',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.5',
                'gateway': '112.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.1'
            },
        ]
        network_id = 'cf531581-a283-41dd-9e4e-4b98454d54e7'
        network_meta = {'cluster_id': '1',
                        'name': 'PUBLICAPI',
                        'network_type': 'PUBLICAPI',
                        'segmentation_type': 'vxlan',
                        'ip_ranges': str(ip_ranges),
                        'cidr': '112.18.1.1/24', }
        orig_network_meta = {'cidr': '112.18.1.1/24',
                             'gateway': '112.18.1.1',
                             'cluster_id': '1',
                             'vlan_id': None,
                             'deleted': False,
                             'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                             'network_type': 'PUBLICAPI',
                             'type': 'default'}
        cluster_meta = {'id': '1', 'deleted': False, }
        networks_detail = [{'cluster_id': '1',
                            'gateway': '112.18.1.1',
                            'vlan_id': None,
                            'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                            'ip_ranges': [
                                {
                                    'end': '112.18.1.16',
                                    'start': '112.18.1.17'}],
                            'name': 'physnet1',
                            'network_type': 'PUBLICAPI',
                            'physnet_name': 'PUBLICAPI',
                            'type': 'default'}]

        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        fake_update_network.return_value = network_meta
        fake_is_dataplane_in_use.return_value = False
        updated_network = self.controller.update_network(
            req, network_id, network_meta)
        self.assertEqual('PUBLICAPI', updated_network['network_meta']['name'])

    @mock.patch('daisy.api.common.valid_ip_ranges')
    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.api.v1.networks.Controller._is_dataplane_in_use')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_invalid_cidr(self, get_network_meta,
                                         get_cluster_meta,
                                         get_networks_detail,
                                         fake_is_dataplane_in_use,
                                         fake_update_network,
                                         fake_valid_ip_ranges):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'start': '112.18.1.5',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.5',
                'gateway': '112.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.1'
            },
        ]
        network_id = 'cf531581-a283-41dd-9e4e-4b98454d54e7'
        network_meta = {'cluster_id': '1',
                        'name': 'PUBLICAPI',
                        'network_type': 'PUBLICAPI',
                        'ip_ranges': str(ip_ranges),
                        'cidr': None}
        orig_network_meta = {'cidr': None,
                             'gateway': '112.18.1.1',
                             'cluster_id': '1',
                             'vlan_id': None,
                             'deleted': False,
                             'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                             'network_type': 'PUBLICAPI',
                             'type': 'default'}
        cluster_meta = {'id': '1', 'deleted': False, }
        networks_detail = [{'cluster_id': '1',
                            'gateway': '112.18.1.1',
                            'vlan_id': None,
                            'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                            'ip_ranges': [
                                {
                                    'end': '112.18.1.16',
                                    'start': '112.18.1.17'}],
                            'name': 'physnet1',
                            'network_type': 'PUBLICAPI',
                            'type': 'default'}]

        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        fake_update_network.return_value = network_meta
        fake_is_dataplane_in_use.return_value = False
        self.assertRaises(exc.HTTPForbidden, self.controller.update_network,
                          req, network_id, network_meta)

    @mock.patch('daisy.api.common.valid_ip_ranges')
    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.api.v1.networks.Controller._is_dataplane_in_use')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_network_metadata')
    def test_update_network_invalid_ipranges(self, get_network_meta,
                                             get_cluster_meta,
                                             get_networks_detail,
                                             fake_is_dataplane_in_use,
                                             fake_update_network,
                                             fake_valid_ip_ranges):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        ip_ranges = [
            {
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.5',
                'gateway': '112.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.1'
            },
        ]
        network_id = 'cf531581-a283-41dd-9e4e-4b98454d54e7'
        network_meta = {'cluster_id': '1',
                        'name': 'PUBLICAPI',
                        'network_type': 'PUBLICAPI',
                        'ip_ranges': str(ip_ranges),
                        'cidr': '112.18.1.1/24'}
        orig_network_meta = {'cidr': '112.18.1.1/24',
                             'gateway': '112.18.1.1',
                             'cluster_id': '1',
                             'vlan_id': None,
                             'deleted': False,
                             'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                             'network_type': 'PUBLICAPI',
                             'type': 'default'}
        cluster_meta = {'id': '1', 'deleted': False, }
        networks_detail = [{'cluster_id': '1',
                            'gateway': '112.18.1.1',
                            'vlan_id': None,
                            'id': 'cf531581-a283-41dd-9e4e-4b98454d54e7',
                            'ip_ranges': [
                                {
                                    'end': '112.18.1.16',
                                    'start': '112.18.1.17'}],
                            'name': 'physnet1',
                            'network_type': 'PUBLICAPI',
                            'type': 'default'}]

        get_network_meta.return_value = orig_network_meta
        get_cluster_meta.return_value = cluster_meta
        get_networks_detail.return_value = networks_detail
        fake_update_network.return_value = network_meta
        fake_is_dataplane_in_use.return_value = False
        self.assertRaises(exc.HTTPForbidden, self.controller.update_network,
                          req, network_id, network_meta)
