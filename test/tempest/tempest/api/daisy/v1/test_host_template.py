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
#    under the License.from six import moves

from six import moves
import copy
from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception
import subprocess
import time
from daisyclient import exc as client_exc
from fake.logical_network_fake import FakeLogicNetwork as logical_fake
import json

class DaisyHostTemplateTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyHostTemplateTest, cls).resource_setup()
        cls.fake = logical_fake()
        cls.host_meta = {'name': 'add_host',
                         'description': 'test_tempest'}
        cls.host_meta1 = {'name': 'add_host1',
                          'description': 'test_tempest'}
        cls.host_to_template_meta = {'host_template_name': 'host_to_template'}

        cls.host_meta_interfaces = {'type': 'ether',
                                    'name': 'enp129s0f0',
                                    'mac': '00:07:e9:15:99:00',
                                    'ip': '99.99.1.121',
                                    'netmask': '255.255.255.0',
                                    'is_deployment': 'True',
                                    'slaves': 'eth1',
                                    'pci': '1',
                                    'gateway': '99.99.1.1'}
        cls.host_meta_interfaces1 = {'type': 'ether',
                                    'name': 'enp129s0f1',
                                    'mac': '00:07:e9:15:99:01',
                                    'ip': '99.99.1.120',
                                    'netmask': '255.255.255.0',
                                    'is_deployment': 'True',
                                    'slaves': 'eth1',
                                    'pci': '2',
                                    'gateway': '99.99.1.1'}
        cls.ironic_data_1 = {'uuid':'03000200-0400-0500-0006-000700080002',
                             'mac': '00:07:e9:15:99:00',
                             'patch':[{'op': 'add',
                                       'path': '/disks/sda',
                                       'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                       'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                       'model': '',
                                       'name': 'sda',
                                       'removable': '',
                                       'size': ' 200127266818 bytes'}},
                                      {'op': 'add',
                                       'path': '/disks/sdb',
                                       'value': {'disk': 'ip-192.163.1.236:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-0',
                                       'extra': ['', ''],
                                       'model': '',
                                       'name': 'sdb',
                                       'removable': '',
                                       'size': ' 136870912008 bytes'}},
                                      {'op': 'add',
                                       'path': '/cpu/total',
                                       'value': 2
                                      },
                                      {'path': '/memory/total',
                                       'value': '1918888 kB',
                                       'op': 'add'},
                                      {'op': 'add',
                                       'path': '/disks/sdc',
                                       'value': {'disk': 'ip-192.163.1.236:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-1',
                                       'extra': ['', ''],
                                       'model': '',
                                       'name': 'sdc',
                                       'removable': '',
                                       'size': '122122547208 bytes'}}
                                      ]}
        cls.ironic_data = {'uuid':'03000200-0400-0500-0006-000700080003',
                           'mac': '00:07:e9:15:99:01',
                            'patch':[{'op': 'add',
                                    'path': '/disks/sda',
                                    'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                                'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                                'model': '',
                                                'name': 'sda',
                                                'removable': '',
                                                'size': ' 200127266816 bytes'}},
                                    {'op': 'add',
                                    'path': '/disks/sdb',
                                    'value': {'disk': 'ip-192.163.1.237:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-0',
                                                'extra': ['', ''],
                                                'model': '',
                                                'name': 'sdb',
                                                'removable': '',
                                                'size': ' 136870912000 bytes'}},
                                    ]}
        cls.cluster_meta = {'description': 'desc',
                            'logic_networks': [{'name': 'external1',
                            'physnet_name': 'phynet3',
                            'segmentation_id': 200,
                            'segmentation_type': 'vlan',
                            'shared': True,
                            'subnets': [{'cidr': '99.99.1.0/24',
                                         'dns_nameservers': ['8.8.4.4',
                                                             '8.8.8.8'],
                                         'floating_ranges': [['99.99.1.2',
                                                              '99.99.1.200']],
                                         'gateway': '99.99.1.1',
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
                            'physnet_name': 'phynet2',
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

    def test_host_to_template(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        host_info = self.add_host(**self.host_meta)
        self.host_to_template_meta['cluster_name'] = cluster_info.name
        self.host_to_template_meta['host_id'] = host_info.id
        host_template = self.host_to_template(**self.host_to_template_meta)
        self.assertEqual("test", host_template.cluster_name,
                         "host to template failed")
        self.private_network_delete()
        self.delete_host(host_info.id)
        self.delete_cluster(cluster_info.id)
        self.delete_host_template(cluster_name='test',
                                  host_template_name='host_to_template')

    def test_host_template_list(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        host_info = self.add_host(**self.host_meta)
        self.host_to_template_meta['cluster_name'] = cluster_info.name
        self.host_to_template_meta['host_id'] = host_info.id
        host_template = self.host_to_template(**self.host_to_template_meta)
        host_template_list_meta = {'cluster_name': cluster_info.name}
        host_templates = self.host_template_list(**host_template_list_meta)
        self.private_network_delete()
        self.delete_host(host_info.id)
        self.delete_cluster(cluster_info.id)
        self.delete_host_template(cluster_name='test',
                                  host_template_name='host_to_template')

    def test_template_to_host(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        host_info = self.add_host(**self.host_meta)
        self.host_to_template_meta['cluster_name'] = cluster_info.name
        self.host_to_template_meta['host_id'] = host_info.id
        host_template = self.host_to_template(**self.host_to_template_meta)
        host_info1 = self.add_host(**self.host_meta1)
        template_to_host_meta = {'cluster_name': cluster_info.name,
                                 'host_template_name': 'host_to_template',
                                 'host_id': host_info1.id}
        self.template_to_host(**template_to_host_meta)
        self.private_network_delete()
        self.delete_host(host_info.id)
        self.delete_host(host_info1.id)
        self.delete_cluster(cluster_info.id)
        self.delete_host_template(cluster_name='test',
                                  host_template_name='host_to_template')

    def test_template_to_host_with_no_exist_template(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        host_info = self.add_host(**self.host_meta)
        self.host_to_template_meta['cluster_name'] = cluster_info.name
        self.host_to_template_meta['host_id'] = host_info.id
        host_template = self.host_to_template(**self.host_to_template_meta)
        host_info1 = self.add_host(**self.host_meta1)
        template_to_host_meta = {'cluster_name': cluster_info.name,
                                 'host_template_name': 'template',
                                 'host_id': host_info1.id}
        self.assertRaisesMessage(client_exc.HTTPNotFound,
                                 "404 Not Found: not host_template "
                                 "template (HTTP 404)",
                                 self.template_to_host, **template_to_host_meta)
        self.private_network_delete()
        self.delete_host(host_info.id)
        self.delete_host(host_info1.id)
        self.delete_cluster(cluster_info.id)
        self.delete_host_template(cluster_name='test',
                                  host_template_name='host_to_template')

    #def test_template_to_host_with_no_match_interfaces(self):
    #    self.ironic_client.physical_node.update(self.ironic_data_1['uuid'],
    #                                            self.ironic_data_1['mac'],
    #                                            self.ironic_data_1['patch'])
    #    self.private_network_add()
    #    cluster_info = self.add_cluster(**self.cluster_meta)
    #    self.host_meta['interfaces'] = [self.host_meta_interfaces]
    #    host_info = self.add_host(**self.host_meta)
    #    self.host_to_template_meta['cluster_name'] = cluster_info.name
    #    self.host_to_template_meta['host_id'] = host_info.id
    #    host_template = self.host_to_template(**self.host_to_template_meta)
    #    self.host_meta1['interfaces'] = [self.host_meta_interfaces1]
    #    host_info1 = self.add_host(**self.host_meta1)
    #    template_to_host_meta = {'cluster_name': cluster_info.name,
    #                             'host_template_name': 'host_to_template',
    #                             'host_id': host_info1.id}
    #    self.assertRaisesMessage(client_exc.HTTPBadRequest,
    #                             '400 Bad Request: host_id %s does not match '
    #                             'the host host_template host_to_template. '
    #                             '(HTTP 400)' % host_info1.id,
    #                             self.template_to_host, **template_to_host_meta)
    #    self.private_network_delete()
    #    self.delete_host_template(cluster_name='test',
    #                              host_template_name='host_to_template')

    def tearDown(self):
        if self.host_meta.get('interfaces', None):
            del self.host_meta['interfaces']
        if self.host_meta1.get('interfaces', None):
            del self.host_meta1['interfaces']
        if self.host_to_template_meta.get('cluster', None):
            del self.host_to_template_meta['cluster']
        if self.host_to_template_meta.get('host', None):
            del self.host_to_template_meta['host']
        self._clean_all_host()
        self._clean_all_cluster()
        super(DaisyHostTemplateTest, self).tearDown()


