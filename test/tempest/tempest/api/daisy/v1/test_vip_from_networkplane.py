
from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception
from daisyclient import exc as client_exc
from fake.logical_network_fake import FakeLogicNetwork as logical_fake
from fake.logical_network_fake import FakeDiscoverHosts

class DaisyVIPfromNetworkTest(base.BaseDaisyTest):
    @classmethod
    def resource_setup(cls):
        super(DaisyVIPfromNetworkTest, cls).resource_setup()
        cls.fake = logical_fake()
        cls.fake_hosts = FakeDiscoverHosts()
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
                            'physnet_name': 'phynet2',
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
        private_network_params = self.add_network(**private_network_params)
        self.private_network_id = private_network_params.id
        self.cluster_meta['networks'] = [self.private_network_id]

    def private_network_delete(self):
        self.delete_network(self.private_network_id)

    def discover_hosts(self):
        # discover 2 hosts
        for disk in self.fake_hosts.ironic_disk_data:
            self.ironic_client.physical_node.update(disk['uuid'], disk['mac'], disk['patch'])

        for memory in self.fake_hosts.ironic_memory_data:
            self.ironic_client.physical_node.update(memory['uuid'], memory['mac'], memory['patch'])

        for cpu in self.fake_hosts.ironic_cpu_data:
            self.ironic_client.physical_node.update(cpu['uuid'], cpu['mac'], cpu['patch'])
            
        self.node1 = self.daisy_client.hosts.add(**self.fake_hosts.daisy_data[0]).id
        self.node2 = self.daisy_client.hosts.add(**self.fake_hosts.daisy_data[1]).id
        self.node3 = self.daisy_client.hosts.add(**self.fake_hosts.daisy_data[2]).id

    def delete_discover_host(self):
        self.delete_host(self.node1)
        self.delete_host(self.node2)
        self.delete_host(self.node3)

    #STC-F-Daisy_VIPfromNetwork_001
    def test_assign_network_to_interface(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        networks = self.list_network(**{'cluster_id': cluster_info.id})
        management_network_id = [network.id for network in networks if network.name == 'MANAGEMENT'][0]

        update_network_meta = {'cidr': '192.168.1.0/24'}
        update_network_meta.update({'ip_ranges': [{'start': '192.168.1.10', 'end': '192.168.1.15'}]})
        self.update_network(management_network_id, **update_network_meta)
        
        self.discover_hosts()

        roles = self.list_roles(**{'cluster_id': cluster_info.id})
        update_role_meta = {'nodes': [self.node1, self.node2], 'cluster_id': cluster_info.id}
        for role in roles:
            if role.name in ['CONTROLLER_HA', 'CONTROLLER_LB', 'COMPUTER'] and role.cluster_id == cluster_info.id:
                self.update_role(role.id, **update_role_meta)

        update_host_meta1 = {'cluster': cluster_info.id,
                             'interfaces': [{u'name': u'enp132s0f0',
                                            u'is_deployment': False,
                                            u'deleted': False,
                                            u'vswitch_type': u'',
                                            u'mac': u'4c:09:b4:b2:78:8a',
                                            u'pci': u'0000:84:00.0',
                                            u'assigned_networks': [{u'name': u'MANAGEMENT'}],
                                            u'host_id': self.node1,
                                            u'type': u'ether'}]}
        update_host_meta2 = {'cluster': cluster_info.id,
                             'interfaces': [{u'name': u'enp132s0f0',
                                            u'is_deployment': False,
                                            u'deleted': False,
                                            u'vswitch_type': u'',
                                            u'mac': u'4c:09:b4:b2:79:8a',
                                            u'pci': u'0000:84:00.0',
                                            u'assigned_networks': [{u'name': u'MANAGEMENT'}],
                                            u'host_id': self.node2,
                                            u'type': u'ether'}]}
        
        update_host_meta3 = {'cluster': cluster_info.id,
                             'interfaces': [{u'name': u'enp132s0f0',
                                            u'is_deployment': False,
                                            u'deleted': False,
                                            u'vswitch_type': u'',
                                            u'mac': u'4c:09:b4:b2:80:8a',
                                            u'pci': u'0000:84:00.0',
                                            u'assigned_networks': [{u'name': u'MANAGEMENT'}],
                                            u'host_id': self.node3,
                                            u'type': u'ether'}]}
        self.update_host(self.node1, **update_host_meta1)
        self.update_host(self.node2, **update_host_meta2)
        self.assertRaisesMessage(client_exc.HTTPForbidden,
                    "403 Forbidden: Forbidden to update host: 403 Forbidden: Access was denied to this resource.: Error:The IP address assigned by ip ranges is already insufficient.   (HTTP 403)",
                    self.update_host, self.node3, **update_host_meta3)
        self.delete_discover_host()
        self.private_network_delete()
        self.delete_cluster(cluster_info.id)

    def tearDown(self):
        super(DaisyVIPfromNetworkTest, self).tearDown()
    