

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF


class DaisyServiceTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyServiceTest, cls).resource_setup()
        cls.host_meta = {'name': 'test_add_host',
                         'description': 'test_tempest'}
        cls.host_meta_interfaces = {'type': 'ether',
                                    'name': 'eth1',
                                    'mac': 'fe80::f816:3eff',
                                    'ip': '10.43.177.121',
                                    'netmask': '255.255.254.0',
                                    'is_deployment': 'True',
                                    'assigned_networks': ['MANAGEMENT', 'DEPLOYMENT'],
                                    'slaves': 'eth1'}

        cls.cluster_meta = {'description': 'desc',
                            'logic_networks': [{'name': 'external1',
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
        cls.service_meta = {'name': 'test_service', 'description': 'test'}

    def test_list_service(self):
        service_meta = {}
        service_flag = True
        list_service = self.list_service(**service_meta)
        query_service_list = [service_info for service_info in list_service]
        service_list = ["lb", "ha", "mariadb", "amqp",
                        "ceilometer-central", "ceilometer-alarm",
                        "ceilometer-notification", "ceilometer-collector",
                        "heat-engine", "ceilometer-api", "heat-api-cfn",
                        "heat-api", "horizon", "neutron-metadata",
                        "neutron-dhcp", "neutron-server", "neutron-l3",
                        "keystone", "cinder-volume", "cinder-api",
                        "cinder-scheduler", "glance", "ironic", "compute",
                        "nova-cert", "nova-sched", "nova-vncproxy",
                        "nova-conductor", "nova-api"]
        for service in service_list:
            for query_service in query_service_list:
                if service == query_service.name:
                    break
            else:
                service_flag = False
        self.assertTrue(service_flag, "test_list_service error")

    def test_add_service(self):
        service = self.add_service(**self.service_meta)
        self.assertEqual("test_service", service.name, "test_add_service failed")
        self.delete_service(service.id)

    def test_service_delete(self):
        service = self.add_service(**self.service_meta)
        self.delete_service(service.id)
        service_flag = True
        service_meta = {}
        list_service = self.list_service(**service_meta)
        query_service_list = [service_info for service_info in list_service]
        for query_service in query_service_list:
            if service.name == query_service.name:
                service_flag = False
        self.assertTrue(service_flag, "test_list_service error")

    def test_get_service_detail(self):
        add_service_info = self.add_service(**self.service_meta)
        get_service = self.get_service(add_service_info.id)
        self.assertEqual('test_service', get_service.name)
        self.delete_service(get_service.id)

    def test_update_service(self):
        add_service_info = self.add_service(**self.service_meta)
        update_service_meta = {'name': 'test_update_service',
                               'description': 'test_tempest'}
        update_service_info = self.update_service(add_service_info.id, **update_service_meta)
        self.assertEqual("test_update_service", update_service_info.name, "test_update_service_with_cluster failed")
        self.delete_service(add_service_info.id)
