
from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception
from daisyclient import exc as client_exc
from fake.logical_network_fake import FakeLogicNetwork as logical_fake
import daisy.registry.client.v1.api as registry
from webob.exc import HTTPBadRequest


class DaisyRolePublicVipTest(base.BaseDaisyTest):
    @classmethod
    def resource_setup(cls):
        super(DaisyRolePublicVipTest, cls).resource_setup()
        cls.fake = logical_fake()
        cls.cluster_meta = {'description': 'desc',
                            'logic_networks': [{'name': 'external1',
                            'physnet_name': 'phynet3',
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
        cls.role_meta = {'name': 'test_role', 'description': 'test'}
        cls.public_vip = '10.43.203.111'

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

    def private_network_delete(self):
        self.delete_network(self.private_network_id)
        self.delete_network(self.private_network_id1)
        self.delete_network(self.private_network_id2)

    #STC-F-Daisy_Role_Set_Public_Vip-0001
    def test_update_ha_role_with_public_vip(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)

        roles = self.list_roles(**{'cluster': cluster_info.id})
        ha_id = [role.id for role in roles if role.name == 'CONTROLLER_HA' and role.cluster_id == cluster_info.id]
        update_role_meta = {}
        update_role_meta['cluster_id'] = cluster_info.id
        update_role_meta['public_vip'] = self.public_vip
        update_role_info = self.update_role(ha_id[0], **update_role_meta)

        self.assertEqual(self.public_vip, update_role_info.public_vip,
                         "test_add_role_with_public_vip failed")
        self.private_network_delete()
        self.delete_cluster(cluster_info.id)

    #STC-A-Daisy_Role_Set_Public_Vip-0002
    def test_update_other_role_with_public_vip(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        add_role_info = self.add_role(**self.role_meta)

        update_role_meta = {'public_vip': self.public_vip}

        self.assertRaisesMessage(client_exc.HTTPForbidden,
                    "403 Forbidden: The role %s need no public_vip (HTTP 403)"\
                    % self.role_meta['name'], self.update_role, add_role_info.id, **update_role_meta)
        self.role_meta['id'] = add_role_info.id
        self.private_network_delete()

    #STC-F-Daisy_DNS-0001
    def test_add_cluster_with_dns(self):
        use_dns = 1
        self.private_network_add()
        self.cluster_meta['use_dns'] = use_dns
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.assertEqual(use_dns, cluster_info.use_dns, "test_add_cluster_with_dns failed")
        self.private_network_delete()
        self.delete_cluster(cluster_info.id)

    def tearDown(self):
        if self.role_meta.get('public_vip', None):
            del self.role_meta['public_vip']

        if self.role_meta.get('id', None):
            self.delete_role(self.role_meta['id'])
            del self.role_meta['id']

        if self.role_meta.get('cluster_id', None):
            self.delete_cluster(self.role_meta['cluster_id'])
            del self.role_meta['cluster_id']

        super(DaisyRolePublicVipTest, self).tearDown()
