from daisy import test
from daisy.api import common
from webob import exc
from daisy.tests import fakes


class TestApiCommon(test.TestCase):

    def setUp(self):
        super(TestApiCommon, self).setUp()
        self.req = fakes.HTTPRequest.blank('/')

    def test_valid_cluster_networks(self):
        nets = [{'id': '123',
                 'cidr': None,
                 'vlan_id': None,
                 'ip_ranges': [],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'},
                {'id': '456',
                 'cidr': None,
                 'vlan_id': None,
                 'ip_ranges': [],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'}]
        common.valid_cluster_networks(nets)

        nets = [{'id': '123',
                 'cidr': '192.167.1.1/24',
                 'vlan_id': None,
                 'ip_ranges': [],
                 'gateway': '192.167.1.1',
                 'name': 'PUBLICAPI'},
                {'id': '456',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': None,
                 'ip_ranges': [],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'}]
        common.valid_cluster_networks(nets)

        nets = [{'id': '123',
                 'cidr': '192.167.1.1/24',
                 'vlan_id': 2,
                 'ip_ranges': [],
                 'gateway': '192.167.1.1',
                 'name': 'PUBLICAPI'},
                {'id': '456',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': 2,
                 'ip_ranges': [],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'}]
        self.assertRaises(exc.HTTPBadRequest,
                          common.valid_cluster_networks, nets)

        nets = [{'id': '123',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': 2,
                 'ip_ranges': [],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'},
                {'id': '456',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': 22,
                 'ip_ranges': [],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'}]
        self.assertRaises(exc.HTTPBadRequest,
                          common.valid_cluster_networks, nets)

        nets = [{'id': '123',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': 2,
                 'ip_ranges': [],
                 'gateway': '192.168.1.2',
                 'name': 'PUBLICAPI'},
                {'id': '456',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': 2,
                 'ip_ranges': [],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'}]
        self.assertRaises(exc.HTTPBadRequest,
                          common.valid_cluster_networks, nets)

        nets = [{'id': '123',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': 2,
                 'ip_ranges': [{'start': '192.168.1.10',
                                'end': '192.168.1.100'}],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'},
                {'id': '456',
                 'cidr': '192.168.1.1/24',
                 'vlan_id': 2,
                 'ip_ranges': [{'start': '192.168.1.10',
                                'end': '192.168.1.120'}],
                 'gateway': '192.168.1.1',
                 'name': 'PUBLICAPI'}]
        self.assertRaises(exc.HTTPBadRequest,
                          common.valid_cluster_networks, nets)

    def test_check_gateway_uniqueness(self):
        nets = [{'deleted': False,
                 'cluster_id': '1',
                 'id': '1',
                 'network_type': 'PUBLICAPI',
                 'cidr': '192.168.1.1/24',
                 'custom_name': 'publicapi',
                 'vlan_id': None,
                 'gateway': '192.168.1.1',
                 'ip_ranges': [],
                 'name': 'PUBLICAPI'},
                {'deleted': False,
                 'cluster_id': '1',
                 'id': '2',
                 'network_type': 'MANAGEMENT',
                 'cidr': '192.168.1.1/24',
                 'custom_name': 'management',
                 'vlan_id': None,
                 'gateway': '192.168.1.1',
                 'ip_ranges': [],
                 'name': 'MANAGEMENT'}]
        self.assertEqual(None, common.check_gateway_uniqueness(nets))

        nets = [{'deleted': False,
                 'cluster_id': '1',
                 'id': '1',
                 'network_type': 'PUBLICAPI',
                 'cidr': '192.168.1.1/24',
                 'custom_name': 'publicapi',
                 'vlan_id': None,
                 'gateway': '192.168.1.1',
                 'ip_ranges': [],
                 'name': 'PUBLICAPI'},
                {'deleted': False,
                 'cluster_id': '1',
                 'id': '2',
                 'network_type': 'DATAPLANE',
                 'cidr': '192.168.1.1/24',
                 'custom_name': 'phy1',
                 'vlan_id': None,
                 'gateway': '192.167.1.1',
                 'ip_ranges': [],
                 'name': 'physnet1'}]
        self.assertEqual(None, common.check_gateway_uniqueness(nets))

    def test_check_gateway_uniqueness_error(self):
        nets = [{'deleted': False,
                 'cluster_id': '1',
                 'id': '1',
                 'network_type': 'PUBLICAPI',
                 'cidr': '192.168.1.1/24',
                 'custom_name': 'publicapi',
                 'vlan_id': None,
                 'gateway': '192.168.1.1',
                 'ip_ranges': [],
                 'name': 'PUBLICAPI'},
                {'deleted': False,
                 'cluster_id': '1',
                 'id': '2',
                 'network_type': 'MANAGEMENT',
                 'cidr': '192.168.1.1/24',
                 'custom_name': 'management',
                 'vlan_id': None,
                 'gateway': '192.168.1.1',
                 'ip_ranges': [],
                 'name': 'MANAGEMENT'},
                {'deleted': False,
                 'cluster_id': '1',
                 'id': '3',
                 'network_type': 'STORAGE',
                 'cidr': '99.99.1.1/24',
                 'custom_name': 'storage',
                 'vlan_id': None,
                 'gateway': '99.99.1.1',
                 'ip_ranges': [],
                 'name': 'STORAGE'}]

        self.assertRaises(exc.HTTPBadRequest,
                          common.check_gateway_uniqueness, nets)
