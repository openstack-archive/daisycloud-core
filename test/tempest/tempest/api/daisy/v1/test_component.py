

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF


class DaisyComponentTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyComponentTest, cls).resource_setup()
        cls.host_meta = {'name': 'test_add_host',
                         'description': 'test_tempest'}
        cls.host_meta_interfaces = \
            {'type': 'ether',
             'name': 'eth1',
             'mac': 'fe80::f816:3eff',
             'ip': '10.43.177.121',
             'netmask': '255.255.254.0',
             'is_deployment': 'True',
             'assigned_networks': ['MANAGEMENT', 'DEPLOYMENT'],
             'slaves': 'eth1'}

        cls.cluster_meta = \
            {'description': 'desc',
             'logic_networks':
             [{'name': 'external1',
               'physnet_name': 'PRIVATE',
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
              {'name': 'external2',
               'physnet_name': 'PUBLIC',
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
               'type': 'external'},
              {'name': 'internal1',
               'physnet_name': 'PRIVATE',
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
                          'subnets': ['subnet4', 'subnet3']},
                         {'description': 'router2',
                          'external_logic_network': 'external2',
                          'name': 'router2',
                          'subnets': ['subnet2', 'subnet10']}]}
        cls.component_meta = {'name': 'test_component',
                              'description': 'test'}

    def test_list_component(self):
        component_meta = {}
        component_flag = True
        list_component = self.list_component(**component_meta)
        query_component_list = [component_info for component_info
                                in list_component]
        component_list = ["camellia", "ha", "loadbalance", "amqp", "database",
                          "keystone", "ironic", "neutron",
                          "horizon", "ceilometer", "glance", "heat", "nova",
                          "cinder"]
        for query_component in query_component_list:
            if query_component.name not in component_list:
                component_flag = False
        self.assertTrue(component_flag, "test_list_component error")

    def test_add_component(self):
        component = self.add_component(**self.component_meta)
        self.assertEqual("test_component",
                         component.name,
                         "test_add_component failed")
        self.delete_component(component.id)

    def test_component_delete(self):
        component = self.add_component(**self.component_meta)
        self.delete_component(component.id)
        component_flag = True
        component_meta = {}
        list_component = self.list_component(**component_meta)
        query_component_list = [component_info for component_info
                                in list_component]
        for query_component in query_component_list:
            if component.name == query_component.name:
                component_flag = False
        self.assertTrue(component_flag, "test_list_component error")

    def test_get_component_detail(self):
        add_component_info = self.add_component(**self.component_meta)
        get_component = self.get_component(add_component_info.id)
        self.assertEqual('test_component', get_component.name)
        self.delete_component(get_component.id)

    def test_update_component(self):
        add_component_info = self.add_component(**self.component_meta)
        update_component_meta = {'name': 'test_update_component',
                                 'description': 'test_tempest'}
        update_component_info = self.update_component(add_component_info.id,
                                                      **update_component_meta)
        self.assertEqual("test_update_component",
                         update_component_info.name,
                         "test_update_component_with_cluster failed")
        self.delete_component(add_component_info.id)
