
import uuid


class FakeLogicNetwork():
    # 1----------------------------------------------------------
    def fake_network_parameters(self):
        return {
                    'base_mac': 'fa:16:3e:00:00:00',
                    'gre_id_range': [2, 4094],
                    'net_l23_provider': 'ovs',
                    'public_vip': '172.16.0.3',
                    'segmentation_type': 'vlan,flat,vxlan,gre',
                    'vni_range': [2, 4094],
                    'vlan_range': [2, 4094],
        }

    def fake_logical_parameters(self, private_network):
        return [{
                     'name': 'internal1',
                     'physnet_name': private_network.name,
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
               ]

    def fake_router_parameters(self):
        return [{
                    'description': 'router1',
                    'external_logic_network': 'flat1',
                    'name': 'router1',
                    'subnets': ['subnet2', 'subnet10']}
        ]

    def fake_cluster_parameters(self, private_network=None):
        networks = []
        if private_network:
            networks.append(private_network.id)

        return {
            'description': 'desc',
            'name': str(uuid.uuid1()).split('-')[0],
            'networks': networks
        }

    # 2----------------------------------------------------------
    def fake_logical_parameters2(self):
        return [{
                     'name': 'internal1',
                     'physnet_name': 'phynet2',
                     'segmentation_id': 200,
                     'segmentation_type': 'vlan',
                     'shared': True,
                     'subnets': [],
                     'type': 'internal'}]

    def fake_subnet_parameters2(self):
        return [{'cidr': '192.168.1.0/24',
                  'dns_nameservers': ['8.8.4.4',
                                      '8.8.8.8'],
                  'floating_ranges': [['192.168.1.2',
                                       '192.168.1.200']],
                  'gateway': '192.168.1.1',
                  'name': 'subnet10'},
                 {'cidr': '172.16.1.0/24',
                  'dns_nameservers': ['8.8.4.4',
                                      '8.8.8.8'],
                  'floating_ranges': [['172.16.1.130',
                                       '172.16.1.152'],
                                      ['172.16.1.151',
                                       '172.16.1.254']],
                  'gateway': '172.16.1.1',
                  'name': 'subnet10'}]

    def fake_router_parameters2(self):
        return [{
                    'description': 'router1',
                    'external_logic_network': 'flat1',
                    'name': 'router1',
                    'subnets': ['subnet2', 'subnet10']},
                {
                    'description': 'test',
                    'external_logic_network': 'flat1',
                    'name': 'router1',
                    'subnets': ['subnet123']}
        ]

    # 3-------------------------------------------------------------
    def fake_private_network_parameters(self):
        return {
            'name' : 'phynet2',
            'description' : 'phynet2',
            'network_type': 'DATAPLANE',
            'type': 'custom',
            'vlan_start': '101',
            'vlan_end': '1001',
            'ml2_type': 'ovs'
        }

    def fake_private_network_parameters1(self):
        return {
            'name' : 'phynet3',
            'description' : 'phynet3',
            'network_type': 'DATAPLANE',
            'type': 'custom',
            'vlan_start': '101',
            'vlan_end': '2000',
            'ml2_type': 'ovs'
        }

    def fake_private_network_parameters2(self):
        return {
            'name' : 'phynet1',
            'description' : 'phynet1',
            'network_type': 'DATAPLANE',
            'type': 'custom',
            'vlan_start': '101',
            'vlan_end': '2000',
            'ml2_type': 'ovs'
        }

class FakeDiscoverHosts():
    # 1----------------------------------------------------------
    daisy_data = [{'description': 'default',
                    'name': '4c09b4b2788a',
                    'ipmi_addr': '10.43.203.230',
                    'ipmi_user': 'albert',
                    'ipmi_passwd': 'superuser',
                    'interfaces': [{'name': 'enp132s0f0',
                                    "mac": '4c:09:b4:b2:78:8a',
                                    "ip": '99.99.1.60',
                                    'is_deployment': 'True',
                                    'pci': '0000:84:00.0',
                                    'netmask': '255.255.255.0'}],
                    'os_status': 'init',
                    'dmi_uuid': '03000200-0400-0500-0006-000700080009'},
                    {'description': 'default',
                    'name': '4c09b4b2798a',
                    'ipmi_addr': '10.43.203.231',
                    'ipmi_user': 'albert',
                    'ipmi_passwd': 'superuser',
                    'interfaces': [{'name': 'enp132s0f0',
                                    "mac": '4c:09:b4:b2:79:8a',
                                    "ip": '99.99.1.61',
                                    'is_deployment': 'True',
                                    'pci': '0000:84:00.0',
                                    'netmask': '255.255.255.0'}],
                    'os_status': 'init',
                    'dmi_uuid': '03000200-0400-0500-0006-000700080009'},
                    {'description': 'default',
                    'name': '4c09b4b2808a',
                    'ipmi_addr': '10.43.203.232',
                    'ipmi_user': 'albert',
                    'ipmi_passwd': 'superuser',
                    'interfaces': [{'name': 'enp132s0f0',
                                    "mac": '4c:09:b4:b2:80:8a',
                                    "ip": '99.99.1.62',
                                    'is_deployment': 'True',
                                    'pci': '0000:84:00.0',
                                    'netmask': '255.255.255.0'}],
                'os_status': 'init',
                'dmi_uuid': '03000200-0400-0500-0006-000700080009'}]

    ironic_disk_data = [{'uuid': '03000200-0400-0500-0006-000700080009',
                    'mac': '4c:09:b4:b2:78:8a',
                    'patch':[{'op': 'add',
                            'path': '/disks/sda',
                            'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                        'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                        'model': '',
                                        'name': 'sda',
                                        'removable': '',
                                        'size': ' 200127266816 bytes'}}]},
                    {'uuid': '03000200-0400-0500-0006-000700080009',
                    'mac': '4c:09:b4:b2:79:8a',
                    'patch':[{'op': 'add',
                            'path': '/disks/sda',
                            'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                        'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                        'model': '',
                                        'name': 'sda',
                                        'removable': '',
                                        'size': ' 200127266816 bytes'}}]},
                    {'uuid': '03000200-0400-0500-0006-000700080009',
                    'mac': '4c:09:b4:b2:80:8a',
                    'patch':[{'op': 'add',
                            'path': '/disks/sda',
                            'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                        'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                        'model': '',
                                        'name': 'sda',
                                        'removable': '',
                                        'size': ' 200127266816 bytes'}}]}]
                            
    ironic_memory_data = [{'uuid': '03000200-0400-0500-0006-000700080009',
                           'mac': '4c:09:b4:b2:78:8a',
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
                                   ]},
                         {'uuid': '03000200-0400-0500-0006-000700080009',
                          'mac': '4c:09:b4:b2:79:8a',
                          'patch':[{'path': '/memory/total',
                                    'value': '        1850020 kB',
                                    'op': 'add'},
                                   {'path': '/memory/phy_memory_1',
                                    'value': {'slots': ' 3',
                                              'devices_1': {'frequency': '',
                                                            'type': ' DIMM SDRAM',
                                                            'size': ' 4096 MB'},
                                              'maximum_capacity': ' 4 GB',
                                              'devices_2': {'frequency': ' 3 ns',
                                                            'type': ' DIMM SDRAM',
                                                            'size': ' 8192 MB'}},
                                    'op': 'add'},
                                  ]},
                         {'uuid': '03000200-0400-0500-0006-000700080009',
                          'mac': '4c:09:b4:b2:80:8a',
                          'patch':[{'path': '/memory/total',
                                    'value': '        1850020 kB',
                                    'op': 'add'},
                                   {'path': '/memory/phy_memory_1',
                                    'value': {'slots': ' 3',
                                              'devices_1': {'frequency': '',
                                                            'type': ' DIMM SDRAM',
                                                            'size': ' 4096 MB'},
                                              'maximum_capacity': ' 4 GB',
                                              'devices_2': {'frequency': ' 3 ns',
                                                            'type': ' DIMM SDRAM',
                                                            'size': ' 8192 MB'}},
                                    'op': 'add'},
                                  ]}]
                                  
    ironic_cpu_data = [{'uuid': '03000200-0400-0500-0006-000700080009',
                                'mac': '4c:09:b4:b2:78:8a',
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
                                        ]},
                       {'uuid': '03000200-0400-0500-0006-000700080009',
                                'mac': '4c:09:b4:b2:79:8a',
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
                                        ]},
                       {'uuid': '03000200-0400-0500-0006-000700080009',
                                'mac': '4c:09:b4:b2:80:8a',
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
                                        ]}]
