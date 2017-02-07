import copy
from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
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
        cls.host_meta_interfaces = {'type': 'ether',
                                    'name': 'enp129s0f0',
                                    'mac': '00:07:e9:15:99:00',
                                    'ip': '99.99.1.121',
                                    'netmask': '255.255.255.0',
                                    'is_deployment': 'True',
                                    'slaves': 'eth1',
                                    'pci': '1',
                                    'gateway': '99.99.1.1'}

        cls.host_meta_interfaces_with_vf = {'type': 'ether',
                                            'name': 'enp129s0f0',
                                            'mac': '00:07:e9:15:99:00',
                                            'ip': '99.99.1.121',
                                            'netmask': '255.255.255.0',
                                            'is_deployment': 'True',
                                            'slaves': 'eth1',
                                            'pci': '1',
                                            'gateway': '99.99.1.1',
                                            'vf': [
                                                {'name': 'enp1',
                                                 'mac': '00:07:e9:15:99:10',
                                                 'ip': '192.168.1.6',
                                                 'netmask': '255.255.255.0',
                                                 'pci': '0000:03:00:10'}
                                            ]}

        cls.host_meta_interface_with_bond = {'type': 'bond',
                                             'name': 'bond0',
                                             'mode': 'active-backup',
                                             'slaves': ['enp132s0f2292',
                                                        'enp132s0f3292'],
                                             'assigned_networks': [
                                                 {'ip': '',
                                                  'name': 'phynet1'}]
                                             }

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

        cls.daisy_data = {'description': 'default',
                          'name': '0007e9159900',
                          'ipmi_addr': '10.4.2.4',
                          'ipmi_user': 'zteroot',
                          'ipmi_passwd': 'superuser',
                          'interfaces': [{
                              'name': 'enp129s0f0',
                              "mac": '00:07:e9:15:99:00',
                              "ip": '99.99.1.140',
                              'is_deployment': 'True',
                              'netmask': '255.255.255.0',
                              'pci': '1'
                          }],
                          'os_status': 'init',
                          'dmi_uuid':
                              '03000200-0400-0500-0006-000700080009',
                          'discover_mode': 'PXE'}
        cls.ironic_data_all = {
            'uuid': '03000200-0400-0500-0006-000700080009',
            'mac': '00:07:e9:15:99:00',
            'patch': [{'op': 'add',
                       'path': '/disks/sda',
                       'value': {'disk': 'pci-0000:01:00.0-sas-'
                                         '0x500003956831a6da-lun-0',
                                 'extra': ['scsi-3500003956831a6d8',
                                           'wwn-0x500003956831a6d8'],
                                 'model': '',
                                 'name': 'sda',
                                 'removable': '',
                                 'size': ' 2001127266818 bytes'}},
                      {'op': 'add',
                       'path': '/disks/sdb',
                       'value': {'disk': 'ip-192.163.1.236:3260-iscsi-'
                                         'iqn.2099-01.cn.com.zte:usp.spr-'
                                         '4c:09:b4:b0:01:31-lun-0',
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
                       'value': {'disk': 'ip-192.163.1.236:3260-iscsi-'
                                         'iqn.2099-01.cn.com.zte:usp.spr-'
                                         '4c:09:b4:b0:01:31-lun-1',
                                 'extra': ['', ''],
                                 'model': '',
                                 'name': 'sdc',
                                 'removable': '',
                                 'size': '122122547208 bytes'}}
                      ]}
        cls.ironic_data = {
            'uuid': '03000200-0400-0500-0006-000700080009',
            'mac': '00:07:e9:15:99:00',
            'patch': [{'op': 'add',
                       'path': '/disks/sda',
                       'value': {'disk': 'pci-0000:01:00.0-sas-'
                                         '0x500003956831a6da-lun-0',
                                 'extra': ['scsi-3500003956831a6d8',
                                           'wwn-0x500003956831a6d8'],
                                 'model': '',
                                 'name': 'sda',
                                 'removable': '',
                                 'size': ' 2001127266816 bytes'}},
                      {'op': 'add',
                       'path': '/disks/sdb',
                       'value': {'disk': 'ip-192.163.1.237:3260-iscsi-'
                                         'iqn.2099-01.cn.com.zte:usp.spr-'
                                         '4c:09:b4:b0:01:31-lun-0',
                                 'extra': ['', ''],
                                 'model': '',
                                 'name': 'sdb',
                                 'removable': '',
                                 'size': ' 136870912000 bytes'}},
                      ]}

        cls.ironic_data2 = {
            'uuid': '03000200-0400-0500-0006-000700080009',
            'mac': '00:07:e9:15:99:00',
            'patch': [{'path': '/cpu/real',
                       'value': 1,
                       'op': 'add'},
                      {'path': '/cpu/total',
                       'value': 2,
                       'op': 'add'},
                      {'path': '/cpu/spec_1',
                       'value':
                           {'model': ' Pentium(R) Dual-Core  CPU    '
                                     'E5700  @ 3.00GHz',
                            'frequency': 3003},
                       'op': 'add'},
                      {'path': '/cpu/spec_2',
                       'value':
                           {'model': ' Pentium(R) Dual-Core  CPU      '
                                     'E5700  @ 3.00GHz',
                            'frequency': 3003},
                       'op': 'add'}
                      ]}

        cls.ironic_data3 = {
            'uuid': '03000200-0400-0500-0006-000700080009',
            'mac': '00:07:e9:15:99:00',
            'patch': [{'path': '/memory/total',
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

        cls.ironic_data4 = {
            'uuid': '03000200-0400-0500-0006-000700080009',
            'mac': '00:07:e9:15:99:00',
            'patch': [{'path': '/system/product',
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
        cls.ironic_data5 = {
            'uuid': '03000200-0400-0500-0006-000700080009',
            'mac': 'fe:80:f8:16:3e:ff',
            'patch': [{'path': '/system/product',
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
        self.assertEqual("host discovered by hwm do not need ipmi check",
                         check_result.ipmi_check_result,
                         "host_check_with_error_ipmi_parameters failed")

    def tearDown(self):
        if self.host_meta.get('cluster', None):
            del self.host_meta['cluster']
        if self.host_meta.get('role', None):
            del self.host_meta['role']
        if self.host_meta.get('interfaces', None):
            del self.host_meta['interfaces']
        if self.host_meta.get('dmi_uuid', None):
            del self.host_meta['dmi_uuid']
        if self.host_meta.get('ipmi_user', None):
            del self.host_meta['ipmi_user']
        if self.host_meta.get('ipmi_passwd', None):
            del self.host_meta['ipmi_passwd']
        if self.host_meta.get('ipmi_addr', None):
            del self.host_meta['ipmi_addr']
        if self.host_meta.get('os_version', None):
            del self.host_meta['os_version']
        if self.host_meta.get('os_status', None):
            del self.host_meta['os_status']
        if self.host_meta2.get('cluster', None):
            del self.host_meta2['cluster']
        if self.host_meta2.get('interfaces', None):
            del self.host_meta2['interfaces']
        self._clean_all_host()
        self._clean_all_cluster()
        # self._clean_all_physical_node()
        super(DaisyHostTest, self).tearDown()
