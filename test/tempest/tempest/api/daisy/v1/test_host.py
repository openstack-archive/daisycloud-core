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

class DaisyHostTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyHostTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.host_meta = {'name': 'test_add_host',
                         'description': 'test_tempest'}
        cls.host_meta2 = {'name': 'test_other_host',
                         'description': 'test_tempest'}
        cls.host_meta_interfaces ={'type':'ether',
           'name': 'enp129s0f0',
           'mac': '00:07:e9:15:99:00',
           'ip': '99.99.1.121',
           'netmask': '255.255.255.0',
           'is_deployment': 'True',
           'assigned_networks': [{'name':'DEPLOYMENT','ip':'99.99.1.121'}],
           'slaves':'eth1',
           'pci': '1',
           'gateway': '99.99.1.1'}

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

        cls.daisy_data = {'description': 'default',
                            'name': '0007e9159900',
                            'ipmi_addr': '10.43.203.129',
                            'ipmi_user':'zteroot',
                            'ipmi_passwd':'superuser',
                            'interfaces': [{
                                        'name': 'enp129s0f0',
                                        "mac": '00:07:e9:15:99:00',
                                        "ip": '99.99.1.140',
                                        'is_deployment': 'True',
                                        'netmask': '255.255.255.0',
                                        'pci': '1'
                                        }],
                            'os_status': 'init',
                            'dmi_uuid': '03000200-0400-0500-0006-000700080009'}
        cls.ironic_data_all = {'uuid':'03000200-0400-0500-0006-000700080009',
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
        cls.ironic_data = {'uuid':'03000200-0400-0500-0006-000700080009',
                            'mac': '00:07:e9:15:99:00',
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

        cls.ironic_data2 = {'uuid':'03000200-0400-0500-0006-000700080009',
                            'mac': '00:07:e9:15:99:00',
                            'patch':[{'path': '/cpu/real',
                                      'value': 1,
                                      'op':  'add'},
                                    {'path': '/cpu/total',
                                     'value': 2,
                                     'op': 'add'},
                                    {'path': '/cpu/spec_1',
                                     'value':  {'model': ' Pentium(R) Dual-Core  CPU    E5700  @ 3.00GHz' ,                                                'frequency': 3003},
                                     'op': 'add'},
                                    {'path': '/cpu/spec_2',
                                     'value': {'model': ' Pentium(R) Dual-Core  CPU      E5700  @ 3.00GHz',                                               'frequency': 3003},
                                     'op': 'add'}
                                    ]}

        cls.ironic_data3 = {'uuid':'03000200-0400-0500-0006-000700080009',
                            'mac': '00:07:e9:15:99:00',
                            'patch':[{'path': '/memory/total',
                                      'value': '        1850020 kB',
                                      'op': 'add'},
                                     {'path': '/memory/phy_memory_1',
                                      'value': {'slots': ' 2',
                                                'devices_1': {'frequency': '',
                                                              'type': ' DIMM SDRAM',
                                                              'size': ' 4096 MB'},
                                                'maximum_capacity': ' 4 GB',
                                                'devices_2': {'frequency': ' 3 ns',
                                                              'type': ' DIMM SDRAM',
                                                              'size': ' 8192 MB'}},
                                      'op': 'add'},
                                    ]}

        cls.ironic_data4 = {'uuid':'03000200-0400-0500-0006-000700080009',
                            'mac': '00:07:e9:15:99:00',
                            'patch':[{'path': '/system/product',
                                      'value': 'QiTianM7150',
                                      'op': 'add'},
                                     {'path': '/system/uuid',
                                      'value': '006E0B2F-68B4-4F69-BF27-0136713BE582',
                                      'op': 'add'},
                                     {'path': '/system/family',
                                      'value': ' To Be Filled By O.E.M.',
                                      'op': 'add'},
                                     {'path': '/system/fqdn',
                                      'value': 'Hostname',
                                      'op': 'add'},
                                     {'path': '/system/version',
                                      'value': 'Lenovo',
                                      'op': 'add'},
                                     {'path': '/system/serial',
                                      'value': 'EA05336053',
                                      'op': 'add'},
                                     {'path': '/system/manufacturer',
                                      'value': 'LENOVO',
                                      'op': 'add'}
                                    ]}
        cls.ironic_data5 = {'uuid':'03000200-0400-0500-0006-000700080009',
                            'mac': 'fe:80:f8:16:3e:ff',
                            'patch':[{'path': '/system/product',
                                      'value': 'QiTianM7150',
                                      'op': 'add'},
                                     {'path': '/system/uuid',
                                      'value': '006E0B2F-68B4-4F69-BF27-0136713BE582',
                                      'op': 'add'},
                                     {'path': '/system/family',
                                      'value': ' To Be Filled By O.E.M.',
                                      'op': 'add'},
                                     {'path': '/system/fqdn',
                                      'value': 'Hostname',
                                      'op': 'add'},
                                     {'path': '/system/version',
                                      'value': 'Lenovo',
                                      'op': 'add'},
                                     {'path': '/system/serial',
                                      'value': 'EA05336053',
                                      'op': 'add'},
                                     {'path': '/system/manufacturer',
                                      'value': 'LENOVO',
                                      'op': 'add'}
                                    ]}

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

    def test_add_host(self):

        host=self.add_host(**self.host_meta)

        self.assertEqual("init", host.status,"add-host failed")

    def test_add_host_with_hwm_id(self):
        host_meta_hmw_id = {
            'name': 'test_add_host',
            'description': 'test_tempest',
            'hwm_id': "233444444444"
        }
        host = self.add_host(**host_meta_hmw_id)

        self.assertEqual("233444444444", host.hwm_id, "add-host failed")

    def test_add_host_with_cluster(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.host_meta['cluster']=cluster_info.id
        host_with_cluster=self.add_host(**self.host_meta)
        self.private_network_delete()

        self.assertEqual("in-cluster", host_with_cluster.status,"add-host use optional_parameters cluster failed")

    def test_add_host_with_cluster_and_role(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.host_meta['cluster']=cluster_info.id
        self.host_meta['role']=['CONTROLLER_HA']
        host_meta_with_cluster_and_role=self.add_host(**self.host_meta)

        self.assertEqual("with-role", host_meta_with_cluster_and_role.status,"add-host use optional_parameters cluster and role failed")
        self.private_network_delete()

    def test_add_host_with_interfaces(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.host_meta['cluster']=cluster_info.id
        self.host_meta['role']=['CONTROLLER_HA']
        self.host_meta['interfaces']=[self.host_meta_interfaces]
        host_with_interfaces=self.add_host(**self.host_meta)

        self.assertEqual("with-role", host_with_interfaces.status,"add-host use optional_parameters interfaces failed")
        self.private_network_delete()

    def test_add_host_with_other_optional_parameters(self):
        self.host_meta['dmi_uuid']='1750bcbc-e26a-42ea-aa04-773978005851'
        self.host_meta['ipmi_user']='root'
        self.host_meta['ipmi_passwd']='ossdbg1'
        self.host_meta['ipmi_addr']='10.43.177.123'
        self.host_meta['os_version']='/var/lib/daisy/tecs/ZXTECS_V02.01.10_dev_I252_installtecs_el7_noarch.bin'
        self.host_meta['os_status']='active'
        host_with_optional_parameters=self.add_host(**self.host_meta)

        self.assertEqual("active", host_with_optional_parameters.os_status,"test_add_host_other_optional_parameters failed")
        self.assertEqual("ossdbg1", host_with_optional_parameters.ipmi_passwd,"test_add_host_other_optional_parameters failed")

    def test_update_host(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        update_host_meta = {'name': 'test_update_host',
                            'description': 'test_tempest'}
        add_host=self.add_host(**self.daisy_data)
        #set_trace()
        update_host=self.update_host(add_host.id,**update_host_meta)

        self.assertEqual("test_update_host", update_host.name,"update-host interface failed")

    def test_update_host_with_hwm_id(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host = self.add_host(**self.daisy_data)
        update_host_meta = {"hwm_id": "233444444444"}
        update_host = self.update_host(add_host.id, **update_host_meta)
        self.assertEqual("233444444444", update_host.hwm_id,
                         "update-host hwm_id failed")

    def test_update_host_with_cluster(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        update_host_meta = {'name': 'test_update_host',
                            'description': 'test_tempest'}
        add_host=self.add_host(**self.daisy_data)
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        update_host_meta['cluster']=cluster_info.id
        update_host=self.update_host(add_host.id,**update_host_meta)

        self.assertEqual("in-cluster", update_host.status,"update-host use optional_parameters cluster failed")
        self.private_network_delete()

    def test_update_host_with_cluster_and_role(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        update_host_meta = {'name': 'test_update_host',
                            'description': 'test_tempest'}
        add_host=self.add_host(**self.daisy_data)
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        update_host_meta['cluster']=cluster_info.id
        update_host_meta['role']=['CONTROLLER_HA']
        update_host=self.update_host(add_host.id,**update_host_meta)

        self.assertEqual("with-role", update_host.status,"update-host use optional_parameters cluster and role failed")
        self.private_network_delete()


    def test_update_host_with_interfaces(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        update_host_meta = {'name': 'test_update_host',
                            'description': 'test_tempest'}
        add_host=self.add_host(**self.daisy_data)
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        update_host_meta['cluster']=cluster_info.id
        update_host_meta['role']=['CONTROLLER_HA']
        update_host_meta['interfaces']=[self.host_meta_interfaces]
        update_host=self.update_host(add_host.id,**update_host_meta)

        self.assertEqual("with-role", update_host.status,"update-host use optional_parameters cluster and role failed")
        self.private_network_delete()

    def test_update_host_with_root_disk_only(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'root_disk':'sdb'}
        update_host = self.update_host(add_host.id,**update_host_meta)

        self.assertEqual('sdb',update_host.root_disk,"update-host with root-disk only failed")
        self.assertEqual(102400,update_host.root_lv_size,"update-host with root-disk only failed")
        self.assertEqual(4096,update_host.swap_lv_size,"update-host with root-disk only failed")


    def test_update_host_with_root_lv_size_only(self):

        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'root_lv_size':102400}
        update_host = self.update_host(add_host.id,**update_host_meta)

        self.assertEqual('sda',update_host.root_disk,"update-host with root-disk only failed")
        self.assertEqual(102400,update_host.root_lv_size,"update-host with root-disk only failed")
        self.assertEqual(4096,update_host.swap_lv_size,"update-host with root-disk only failed")

    def test_update_host_with_swap_lv_size_only(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'swap_lv_size':5000}
        update_host = self.update_host(add_host.id,**update_host_meta)

        self.assertEqual('sda',update_host.root_disk,"update-host with root-disk only failed")
        self.assertEqual(102400,update_host.root_lv_size,"update-host with root-disk only failed")
        self.assertEqual(5000,update_host.swap_lv_size,"update-host with root-disk only failed")

    def test_update_host_with_swap_lv_size_and_root_lv_size_and_root_disk(self):

        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'swap_lv_size':5000,
                            'root_disk':'sdb',
                            'root_lv_size':102400}
        update_host = self.update_host(add_host.id,**update_host_meta)

        self.assertEqual('sdb',update_host.root_disk,"update-host with root-disk only failed")
        self.assertEqual(102400,update_host.root_lv_size,"update-host with root-disk only failed")
        self.assertEqual(5000,update_host.swap_lv_size,"update-host with root-disk only failed")

    def test_update_host_with_large_root_lv_size(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'root_lv_size': '300000',
                            'root_disk':'sdc'}
        self.assertRaisesMessage(
            client_exc.Forbidden,
            "403 Forbidden: root_lv_size of %s is larger than the free_root_disk_storage_size. (HTTP 403)" %add_host.id,
            self.update_host, add_host.id, **update_host_meta)

    def test_update_host_with_small_root_lv_size(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'root_lv_size': '3000',
                            'root_disk':'sdc'}
        self.assertRaisesMessage(
            client_exc.Forbidden,
            "403 Forbidden: root_lv_size of %s is too small, it must be larger than 102400M. (HTTP 403)" %add_host.id,
            self.update_host, add_host.id, **update_host_meta)

    def test_update_host_with_large_swap_lv_size(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'swap_lv_size': '300000'}
        self.assertRaisesMessage(
            client_exc.Forbidden,
            "403 Forbidden: the sum of swap_lv_size and glance_lv_size and nova_lv_size and db_lv_size of %s is larger than the free_disk_storage_size. (HTTP 403)" %add_host.id,
            self.update_host, add_host.id, **update_host_meta)

    def test_update_host_with_small_swap_lv_size(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'swap_lv_size': '1000'}
        self.assertRaisesMessage(
            client_exc.Forbidden,
            "403 Forbidden: swap_lv_size of %s is too small, it must be larger than 2000M. (HTTP 403)" %add_host.id,
            self.update_host, add_host.id, **update_host_meta)

    def test_update_host_with_root_pwd(self):

        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host =  self.add_host(**self.daisy_data)
        update_host_meta = {'root_pwd':'ossdbg2'}
        update_host = self.update_host(add_host.id,**update_host_meta)

        self.assertEqual('ossdbg2',update_host.root_pwd,"update-host with root-pwd failed")


    def test_update_host_with_isolcpus(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host = self.add_host(**self.daisy_data)
        update_host_meta = {'isolcpus':"0"}
        update_host = self.update_host(add_host.id,**update_host_meta)
        self.assertEqual('0',update_host.isolcpus,"update-host with isolcpus failed")


    def test_update_host_with_hugepages(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host = self.add_host(**self.daisy_data)
        update_host_meta = {'hugepages': '1'}
        update_host = self.update_host(add_host.id, **update_host_meta)
        self.assertEqual(1, update_host.hugepages, "update-host with hugepages failed")


    def test_update_host_with_bad_hugepages(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host = self.add_host(**self.daisy_data)
        update_host_meta = {'hugepages': -1}
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                 "400 Bad Request: The parameter hugepages "
                                 "must be zero or positive integer. (HTTP 400)",
                                 self.update_host, add_host.id, **update_host_meta)


    def test_update_host_with_hugepagesize(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host = self.add_host(**self.daisy_data)
        update_host_meta = {'hugepagesize': '1G'}
        update_host = self.update_host(add_host.id, **update_host_meta)
        self.assertEqual('1G', update_host.hugepagesize, "update-host with hugepagesize failed")

    def test_update_host_with_bad_hugepagesize(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host = self.add_host(**self.daisy_data)
        update_host_meta = {'hugepagesize': '2g'}
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                 "400 Bad Request: The value 0f parameter "
                                 "hugepagesize is not supported. (HTTP 400)",
                                 self.update_host, add_host.id, **update_host_meta)


    def test_update_host_with_hugepages_and_hugepagesize(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        add_host = self.add_host(**self.daisy_data)
        update_host_meta = {'hugepagesize': '1G',
                            'hugepages': 1}
        update_host = self.update_host(add_host.id, **update_host_meta)
        self.assertEqual('1G', update_host.hugepagesize, "update-host with hugepagesize failed")
        self.assertEqual(1, update_host.hugepages, "update-host with hugepages failed")


    def test_update_host_with_other_optional_parameters(self):
        self.ironic_client.physical_node.update(self.ironic_data_all['uuid'],
                                                self.ironic_data_all['mac'],
                                                self.ironic_data_all['patch'])
        update_host_meta = {'dmi_uuid':'1750bcbc-e26a-42ea-aa04-773978005851',
                            'ipmi_user':'root',
                            'ipmi_passwd':'ossdbg1',
                            'ipmi_addr':'10.43.177.123',
                            'os_version':'/var/lib/daisy/tecs/ZXTECS_V02.01.10_dev_I252_installtecs_el7_noarch.bin',
                            'os_status':'active'}
        add_host=self.add_host(**self.daisy_data)
        update_host=self.update_host(add_host.id,**update_host_meta)

        self.assertEqual("active", update_host.os_status,"test_update_host_with_other_optional_parameters failed")
        self.assertEqual("root", update_host.ipmi_user,"test_update_host_with_other_optional_parameters failed")


    def test_host_detail_info(self):
        self.ironic_client.physical_node.update(self.ironic_data5['uuid'],
                                                self.ironic_data5['mac'],
                                                self.ironic_data5['patch'])
        host_meta_interfaces ={'type': 'ether',
                               'name': 'eth1',
                               'mac': 'fe:80:f8:16:3e:ff',
                               'ip': '10.43.177.121',
                               'netmask': '255.255.255.0',
                               'is_deployment': 'True',
                               'slaves':'eth1',
                               'pci': '1'}

        self.host_meta['interfaces']=[host_meta_interfaces]
        add_host=self.add_host(**self.host_meta)
        host_detail=self.get_host_detail(add_host.id)

        for host_detail_interface in host_detail.interfaces:
            host_interface_test=host_detail_interface['name']

        self.assertEqual("eth1", host_interface_test,"test_host_detail_info failed")


    def test_host_list_with_filter_by_status(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.host_meta['cluster']=cluster_info.id
        host_with_cluster=self.add_host(**self.host_meta)
        host2=self.add_host(**self.host_meta2)
        filter_status_meta={'status':'in-cluster'}
        host_status_lists=self.list_host(**filter_status_meta)
        host_flag = False
        for host_list in host_status_lists:
            if host_list.name == "test_add_host":
                host_flag = True
        self.assertTrue(host_flag, "test_host_list_with_filter_by_status failed")
        self.private_network_delete()

    def test_host_list_with_discover_state(self):
        self.add_host(**self.host_meta)
        hosts_list = self.list_host()
        for host in hosts_list:
            self.assertEqual(None, host.discover_state)

    def test_host_list_with_filter_by_name(self):
        host=self.add_host(**self.host_meta)
        host2=self.add_host(**self.host_meta2)
        filter_name_meta={'name':'test_add_host'}
        host_cluster_lists=self.list_host(**filter_name_meta)
        host_flag = False
        for query_host in host_cluster_lists:
            if query_host.name == "test_add_host":
                host_flag = True
        self.assertTrue(host_flag, "test_host_list_with_filter_by_name error")

    def test_host_list_with_filter_by_cluster(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.host_meta['cluster']=cluster_info.id
        host_with_cluster=self.add_host(**self.host_meta)
        host2=self.add_host(**self.host_meta2)
        filter_cluster_meta={'cluster':cluster_info.id}
        host_cluster_lists=self.list_host(**filter_cluster_meta)
        host_flag = False
        for host_list in host_cluster_lists:
            if host_list.name == "test_add_host":
                host_flag = True
        self.assertTrue(host_flag, "test_host_list_with_filter_by_cluster failed")
        self.private_network_delete()

    def test_host_list_with_filter_by_cluster_and_status(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.host_meta['cluster']=cluster_info.id
        self.host_meta['role']=['COMPUTER']
        host_with_cluster=self.add_host(**self.host_meta)
        self.host_meta2['cluster']=cluster_info.id
        host2=self.add_host(**self.host_meta2)
        filter_cluster_meta={'cluster':cluster_info.id,'status':"with-role"}
        host_cluster_lists=self.list_host(**filter_cluster_meta)
        host_flag = False
        for host_list in host_cluster_lists:
            if host_list.name == "test_add_host":
                host_flag = True
        self.assertTrue(host_flag, "test_host_list_with_filter_by_cluster_and_status failed")
        self.private_network_delete()

    def test_host_delete(self):
        host=self.add_host(**self.host_meta)
        self.delete_host(host.id)

    def test_host_detail_with_ipmi(self):
        """STC-F-Daisy_Host-0017"""
        #set_trace()
        #subprocess.check_output('systemctl start openstack-ironic-discoverd.service', shell=True, stderr=subprocess.STDOUT)
        python_path = subprocess.check_output("pwd", shell=True, stderr=subprocess.STDOUT).split("\n")[0]
        node_info = "%s/getnodeinfo.sh" %python_path
        print(subprocess.check_output(node_info, shell=True, stderr=subprocess.STDOUT))
        filter_status_meta={}
        time.sleep(30)
        host_ipmi_lists=self.list_host(**filter_status_meta)
        host_flag = True
        host_ipmi_lists = [host_ipmi_info for host_ipmi_info in host_ipmi_lists]
        for query_host in host_ipmi_lists:
            if query_host.ipmi_addr != "127.0.0.1":
                host_flag = False

        self.assertTrue(host_flag, "test_host_detail_with_ipmi failed")

    # too many bug when test, gm 2016-02-05
    # def test_host_add_with_same_mac(self):
        # """STC-F-Daisy_Host-0016"""
        # self.private_network_add()
        # cluster_info = self.add_cluster(**self.cluster_meta)
        # self.host_meta['cluster']=cluster_info.id
        # self.host_meta['interfaces']=[self.host_meta_interfaces]
        # host_with_interfaces=self.add_host(**self.host_meta)
        # self.host_meta2['cluster']=cluster_info.id
        # self.host_meta2['interfaces']=[self.host_meta_interfaces]
        # host_with_interfaces2=self.add_host(**self.host_meta2)
        # host_flag=False
        # if host_with_interfaces.id == host_with_interfaces2.id:
            # host_flag=True
        # self.assertTrue(host_flag, "test_host_add_with_same_mac error")
        # self.private_network_delete()

    def test_host_detail_with_ironic_discover_disks(self):
        """STC-F-Daisy_Host-0015"""
        self.ironic_client.physical_node.update(self.ironic_data['uuid'],
                                                self.ironic_data['mac'],
                                                self.ironic_data['patch'])
        host_info = self.daisy_client.hosts.add(**self.daisy_data)
        host_detail = self.get_host_detail(host_info.id)
        host_detail_flag = True
        for i in range(len(self.ironic_data['patch'])):
            if self.ironic_data['patch'][i]['value'] != host_detail.disks.values()[i]:
                host_detail_flag = False
        self.assertTrue(host_detail_flag, "test_host_detail_with_ironic_discover_disks error")
        # self.daisy_client.hosts.delete(host_info.id)

    def test_host_detail_with_ironic_discover_cpu(self):
        """STC-F-Daisy_Host-0018"""
        self.ironic_client.physical_node.update(self.ironic_data2['uuid'],
                                                self.ironic_data2['mac'],
                                                self.ironic_data2['patch'])
        host_info = self.daisy_client.hosts.add(**self.daisy_data)
        host_detail = self.get_host_detail(host_info.id)
        host_detail_flag = True
        for i in range(len(self.ironic_data2['patch'])):
            if self.ironic_data2['patch'][i]['value'] != host_detail.cpu.values()[i]:
                host_detail_flag = False
        self.assertTrue(host_detail_flag, "test_host_detail_with_ironic_discover_cpu error")
        #  self.daisy_client.hosts.delete(host_info.id)

    def test_host_detail_with_ironic_discover_memory(self):
        """STC-F-Daisy_Host-0019"""
        self.ironic_client.physical_node.update(self.ironic_data3['uuid'],
                                                self.ironic_data3['mac'],
                                                self.ironic_data3['patch'])
        host_info = self.daisy_client.hosts.add(**self.daisy_data)
        host_detail = self.get_host_detail(host_info.id)
        host_detail_flag = True
        for i in range(len(self.ironic_data3['patch'])):
            if self.ironic_data3['patch'][i]['value'] != host_detail.memory.values()[i]:
                host_detail_flag = False
        self.assertTrue(host_detail_flag, "test_host_detail_with_ironic_discover_memory error")
      #  self.daisy_client.hosts.delete(host_info.id)

    def test_host_detail_with_ironic_discover_system(self):
        """STC-F-Daisy_Host-0020"""
        self.ironic_client.physical_node.update(self.ironic_data4['uuid'],
                                                self.ironic_data4['mac'],
                                                self.ironic_data4['patch'])
        host_info = self.daisy_client.hosts.add(**self.daisy_data)
        host_detail = self.get_host_detail(host_info.id)
        host_detail_flag = True
        for i in range(len(self.ironic_data4['patch'])):
            if self.ironic_data4['patch'][i]['value'] != host_detail.system.values()[i]:
                host_detail_flag = False
        self.assertTrue(host_detail_flag, "test_host_detail_with_ironic_discover_system error")
        #   self.daisy_client.hosts.delete(host_info.id)

    def tearDown(self):
        if self.host_meta.get('cluster',None):
           del self.host_meta['cluster']
        if self.host_meta.get('role',None):
           del self.host_meta['role']
        if self.host_meta.get('interfaces',None):
           del self.host_meta['interfaces']
        if self.host_meta.get('dmi_uuid',None):
           del self.host_meta['dmi_uuid']
        if self.host_meta.get('ipmi_user',None):
           del self.host_meta['ipmi_user']
        if self.host_meta.get('ipmi_passwd',None):
           del self.host_meta['ipmi_passwd']
        if self.host_meta.get('ipmi_addr',None):
           del self.host_meta['ipmi_addr']
        if self.host_meta.get('os_version',None):
           del self.host_meta['os_version']
        if self.host_meta.get('os_status',None):
           del self.host_meta['os_status']
        if self.host_meta2.get('cluster',None):
           del self.host_meta2['cluster']
        if self.host_meta2.get('interfaces',None):
           del self.host_meta2['interfaces']
        self._clean_all_host()
        self._clean_all_cluster()
        # self._clean_all_physical_node()
        super(DaisyHostTest, self).tearDown()

