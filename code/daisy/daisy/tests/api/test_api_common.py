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

    def test_valid_ip_ranges_with_cidr(self):
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
        cidr = '12.10.1.2/24'
        common.valid_ip_ranges_with_cidr(ip_ranges, cidr)

    def test_valid_ip_ranges_with_cidr_invalid_startip(self):
        ip_ranges = [
            {
                'start': '13.18.1.5',
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
        cidr = '12.10.1.2/24'
        self.assertRaises(exc.HTTPForbidden,
                          common.valid_ip_ranges_with_cidr,
                          ip_ranges,
                          cidr)

    def test_valid_ip_ranges_with_cidr_invalid_endip(self):
        ip_ranges = [
            {
                'start': '12.18.1.5',
                'cidr': '12.18.1.1/24',
                'end': '13.18.1.5',
                'gateway': '12.18.1.2'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.5'
            },
        ]
        cidr = '12.10.1.2/24'
        self.assertRaises(exc.HTTPForbidden,
                          common.valid_ip_ranges_with_cidr,
                          ip_ranges,
                          cidr)

    def test_valid_ip_ranges_with_cidr_invalid_gateway(self):
        ip_ranges = [
            {
                'start': '12.18.1.5',
                'cidr': '12.18.1.1/24',
                'end': '12.18.1.9',
                'gateway': '12.18.1.5'
            },
            {
                'start': '112.18.1.15',
                'cidr': '112.18.1.1/24',
                'end': '112.18.1.15',
                'gateway': '112.18.1.5'
            },
        ]
        cidr = '12.10.1.2/24'
        self.assertRaises(exc.HTTPBadRequest,
                          common.valid_ip_ranges_with_cidr,
                          ip_ranges,
                          cidr)

    def test_valid_ip_ranges_with_cidr_cidr_overlapped(self):
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
        cidr = '12.18.1.1/26'
        self.assertRaises(exc.HTTPBadRequest,
                          common.valid_ip_ranges_with_cidr,
                          ip_ranges,
                          cidr)

    def test_valid_network_range(self):
        range = [1, 4094]
        network_meta = {}
        vlan_start = 'vlan_start'
        vlan_end = 'vlan_end'
        value_start = 1
        value_end = 4095
        network_meta[vlan_start] = value_start
        try:
            common.valid_network_range(self.req, network_meta)
        except exc.HTTPBadRequest as e:
            msg = "%s and %s must be appeared "\
                  "at the same time" % (vlan_start, vlan_end)
            self.assertEqual(e.explanation, msg)

        network_meta[vlan_end] = value_end
        try:
            common.valid_network_range(self.req, network_meta)
        except exc.HTTPBadRequest as e:
            msg = "%s:%d and %s:%d must be in %d~%d and " \
                  "start:%d less than end:%d"\
                  % (vlan_start, value_start, vlan_end, value_end,
                      range[0], range[1], value_start, value_end)
            self.assertEqual(e.explanation, msg)

        network_meta[vlan_end] = value_end-1
        result = common.valid_network_range(self.req, network_meta)
        self.assertEqual(result, None)

        svlan_start = 'svlan_start'
        svlan_end = 'svlan_end'
        network_meta[svlan_start] = value_start
        try:
            common.valid_network_range(self.req, network_meta)
        except exc.HTTPBadRequest as e:
            msg = "%s and %s must be appeared "\
                  "at the same time" % (svlan_start, svlan_end)
            self.assertEqual(e.explanation, msg)

        network_meta[svlan_end] = value_end
        try:
            common.valid_network_range(self.req, network_meta)
        except exc.HTTPBadRequest as e:
            msg = "%s:%d and %s:%d must be in %d~%d " \
                  "and start:%d less than end:%d"\
                  % (svlan_start, value_start, svlan_end,
                      value_end, range[0], range[1], value_start, value_end)
            self.assertEqual(e.explanation, msg)

        network_meta[svlan_end] = value_end-1
        result = common.valid_network_range(self.req, network_meta)
        self.assertEqual(result, None)
