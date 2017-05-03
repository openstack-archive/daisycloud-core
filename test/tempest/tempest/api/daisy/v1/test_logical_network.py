
import copy

from daisyclient import exc as client_exc
from tempest.api.daisy import base
from tempest import config
from fake.logical_network_fake import FakeLogicNetwork as logical_fake

CONF = config.CONF


class TecsLogicalNetworkTest(base.BaseDaisyTest):
    LOGICAL_FILTER = ['name', 'physnet_name', 'segmentation_id',
                      'segmentation_type', 'shared', 'type']
    SUBNET_FILTER = ['name', 'dns_nameservers', 'floating_ranges',
                     'gateway', 'cidr']
    ROUTER_FILTER = ['name', 'description',
                     'external_logic_network', 'subnets']

    @classmethod
    def resource_setup(cls):
        super(TecsLogicalNetworkTest, cls).resource_setup()
        cls.fake = logical_fake()

    def _verify_logical_params(self, cluster_meta, fake_logical):
        cluster_meta['logic_networks'] = \
            [dict(filter(lambda paris: paris[0]
                         in TecsLogicalNetworkTest.LOGICAL_FILTER,
                         logic_network.items()))
             for logic_network in cluster_meta['logic_networks']]

        tmp_fake_logical = [dict(filter(lambda paris:
                                        paris[0] in
                                        TecsLogicalNetworkTest.LOGICAL_FILTER,
                                        logic_network.items()))
                            for logic_network in fake_logical]
        if cluster_meta['logic_networks'] != tmp_fake_logical:
            cluster_meta['logic_networks'].reverse()

        return tmp_fake_logical

    def _verify_router_params(self, cluster_meta):
        cluster_meta['routers'] = \
            [dict(filter(lambda paris: paris[0] in
                         TecsLogicalNetworkTest.ROUTER_FILTER,
                         router.items()))
             for router in cluster_meta['routers']]
        for router in cluster_meta['routers']:
            router['subnets'] = copy.deepcopy(list(set(router['subnets'])))

    def private_network_add(self):
        # add network plane
        private_network_params = self.fake.fake_private_network_parameters()
        private_network_params = self.add_network(**private_network_params)
        self.private_network_id = private_network_params.id
        return copy.deepcopy(private_network_params)

    def private_network_delete(self):
        self.delete_network(self.private_network_id)

    # STC-F-Daisy_Logical_Network-0001
    def test_add_all_params(self):
        private_network = self.private_network_add()
        fake_cluster = self.fake.fake_cluster_parameters(private_network)
        fake_logical = self.fake.fake_logical_parameters(private_network)
        fake_routers = self.fake.fake_router_parameters()
        fake_network = self.fake.fake_network_parameters()

        fake_cluster.update({'networking_parameters': fake_network,
                             'logic_networks': fake_logical,
                             'routers': fake_routers})

        cluster_info = self.add_cluster(**fake_cluster)
        cluster_meta = self.get_cluster(cluster_info.id).to_dict()

        self.assertEqual(cluster_meta.get('networking_parameters', None),
                         fake_network)

        fake_logical = self._verify_logical_params(cluster_meta, fake_logical)
        self.assertEqual(cluster_meta.get('logic_networks', None),
                         fake_logical)

        self._verify_router_params(cluster_meta)
        self.assertEqual(cluster_meta.get('routers', None), fake_routers)

        self.delete_cluster(cluster_info.id)

    # STC-A-Daisy_Logical_Network-0004
    def test_add_without_logical_parameters_exc(self):
        fake_cluster = self.fake.fake_cluster_parameters()
        fake_routers = self.fake.fake_router_parameters()
        fake_network = self.fake.fake_network_parameters()

        fake_cluster.update({'networking_parameters': fake_network,
                             'routers': fake_routers})

        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request\n"
            "Logic_network flat1 is not valid range.\n    (HTTP 400)",
            self.add_cluster, **fake_cluster)

    # STC-F-Daisy_Logical_Network-0002
    def test_add_network_params_only(self):
        fake_cluster = self.fake.fake_cluster_parameters()
        fake_network = self.fake.fake_network_parameters()

        fake_cluster.update({'networking_parameters': fake_network})

        cluster_info = self.add_cluster(**fake_cluster)
        cluster_meta = self.get_cluster(cluster_info.id).to_dict()

        self.assertEqual(cluster_meta.get('networking_parameters', None),
                         fake_network)
        self.delete_cluster(cluster_info.id)

    # STC-F-Daisy_Logical_Network-0003
    def test_add_network_and_logical_params(self):
        private_network = self.private_network_add()
        fake_cluster = self.fake.fake_cluster_parameters(private_network)
        fake_logical = self.fake.fake_logical_parameters(private_network)
        fake_network = self.fake.fake_network_parameters()

        fake_cluster.update({'networking_parameters': fake_network,
                             'logic_networks': fake_logical})

        cluster_info = self.add_cluster(**fake_cluster)
        cluster_meta = self.get_cluster(cluster_info.id).to_dict()

        self.assertEqual(cluster_meta.get('networking_parameters', None),
                         fake_network)

        fake_logical = self._verify_logical_params(cluster_meta, fake_logical)
        self.assertEqual(cluster_meta.get('logic_networks', None),
                         fake_logical)
        self.delete_cluster(cluster_info.id)

    # STC-A-Daisy_Logical_Network-0007
    def test_routers_params_valid_check_exc(self):
        private_network = self.private_network_add()
        fake_cluster = self.fake.fake_cluster_parameters(private_network)
        fake_logical = self.fake.fake_logical_parameters(private_network)
        fake_network = self.fake.fake_network_parameters()
        fake_router = self.fake.fake_router_parameters2()

        fake_cluster.update({'networking_parameters': fake_network,
                             'logic_networks': fake_logical,
                             'routers': fake_router})
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request\nLogic network's subnets is all related "
            "with a router, it's not allowed.\n    (HTTP 400)",
            self.add_cluster, **fake_cluster)

        tmp_fake_router1 = copy.deepcopy(fake_router)
        tmp_fake_router1[0]['name'] = "test"
        fake_cluster.update({'routers': tmp_fake_router1})
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request\nLogic network's subnets is all related with a "
            "router, it's not allowed.\n    (HTTP 400)",
            self.add_cluster, **fake_cluster)

        tmp_fake_router2 = copy.deepcopy(fake_router)
        tmp_fake_router2[0]['external_logic_network'] = "test"
        fake_cluster.update({'routers': tmp_fake_router2})
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request\n"
            "Logic_network test is not valid range.\n    (HTTP 400)",
            self.add_cluster, **fake_cluster)

        tmp_fake_router3 = copy.deepcopy(fake_router)
        tmp_fake_router3[0]['subnets'] = ['test']
        fake_cluster.update({'routers': tmp_fake_router3})
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request\nSubnet test is not valid range.\n    (HTTP 400)",
            self.add_cluster, **fake_cluster)
        self.private_network_delete()

        # TODO:name

    # STC-A-Daisy_Logical_Network-0008
    def test_subnets_params_valid_check_exc(self):
        private_network = self.private_network_add()
        fake_cluster = self.fake.fake_cluster_parameters(private_network)
        fake_logical = self.fake.fake_logical_parameters(private_network)
        fake_network = self.fake.fake_network_parameters()

        tmp_fake_logical1 = copy.deepcopy(fake_logical)
        tmp_fake_logical1[0]['subnets'] = self.fake.fake_subnet_parameters2()
        fake_cluster.update({'networking_parameters': fake_network,
                             'logic_networks': tmp_fake_logical1})
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request\n"
            "Between floating ip range can not be overlap.\n    (HTTP 400)",
            self.add_cluster, **fake_cluster)

        tmp_fake_logical2 = copy.deepcopy(
            self.fake.fake_logical_parameters2())
        tmp_fake_logical2[0].update({'subnets':
                                     self.fake.fake_subnet_parameters2()})
        tmp_fake_logical2[0]['subnets'][0].update({'floating_ranges': []})
        tmp_fake_logical2[0]['subnets'][1].update({'floating_ranges': []})

        fake_cluster.update({'logic_networks': tmp_fake_logical2})
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request\nSubnet name segment is repetition.\n    "
            "(HTTP 400)",
            self.add_cluster, **fake_cluster)
        self.private_network_delete()

    # STC-A-Daisy_Logical_Network-0009
    def test_update_all_params(self):
        private_network = self.private_network_add()
        fake_cluster = self.fake.fake_cluster_parameters(private_network)
        fake_network = self.fake.fake_network_parameters()
        fake_logical = self.fake.fake_logical_parameters(private_network)

        # add
        fake_cluster.update({'networking_parameters': fake_network,
                             'logic_networks': fake_logical,
                             'routers': self.fake.fake_router_parameters()})
        cluster_id1 = self.add_cluster(**fake_cluster).id

        fake_cluster.update({'networking_parameters': fake_network,
                             'logic_networks': fake_logical,
                             'routers': self.fake.fake_router_parameters()})

        # update
        cluster_id2 = self.update_cluster(cluster_id1, **fake_cluster)
        cluster_meta = self.get_cluster(cluster_id2).to_dict()

        # check
        self.assertEqual(cluster_meta.get('networking_parameters', None),
                         fake_network)

        tmp_fake_logical = self._verify_logical_params(cluster_meta,
                                                       fake_logical)
        self.assertEqual(cluster_meta.get('logic_networks', None),
                         tmp_fake_logical)

        self._verify_router_params(cluster_meta)
        self.assertEqual(cluster_meta.get('routers', None),
                         self.fake.fake_router_parameters())

        self.delete_cluster(cluster_id2)

    # STC-A-Daisy_Logical_Network-0010
    def test_get_all_params(self):
        private_network = self.private_network_add()
        fake_cluster = self.fake.fake_cluster_parameters(private_network)
        fake_logical = self.fake.fake_logical_parameters(private_network)
        fake_routers = self.fake.fake_router_parameters()
        fake_network = self.fake.fake_network_parameters()

        fake_cluster.update({'networking_parameters': fake_network,
                             'logic_networks': fake_logical,
                             'routers': fake_routers})

        cluster_info = self.add_cluster(**fake_cluster)
        cluster_meta = self.get_cluster(cluster_info.id).to_dict()

        self.assertEqual(cluster_meta.get('networking_parameters', None),
                         fake_network)

        fake_logical = self._verify_logical_params(cluster_meta, fake_logical)
        self.assertEqual(cluster_meta.get('logic_networks', None),
                         fake_logical)

        self._verify_router_params(cluster_meta)
        self.assertEqual(cluster_meta.get('routers', None), fake_routers)

        self.delete_cluster(cluster_info.id)

    # STC-A-Daisy_Logical_Network-0011
    def test_delete_all_params(self):
        fake_cluster = self.fake.fake_cluster_parameters()

        cluster_info = self.add_cluster(**fake_cluster)
        cluster_meta = self.get_cluster(cluster_info.id).to_dict()

        default_networking_parameters = {u'base_mac': None,
                                         u'gre_id_range': [None, None],
                                         u'net_l23_provider': None,
                                         u'public_vip': None,
                                         u'segmentation_type': None,
                                         u'vlan_range': [None, None],
                                         u'vni_range': [None, None]}
        self.assertEqual(default_networking_parameters,
                         cluster_meta.get('networking_parameters', None))
        self.assertEqual([], cluster_meta.get('logic_networks', None))
        self.assertEqual([], cluster_meta.get('routers', None))

        self.delete_cluster(cluster_info.id)

    def tearDown(self):
        super(TecsLogicalNetworkTest, self).tearDown()
