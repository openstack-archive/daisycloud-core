from tempest.api.daisy import base
from tempest import config
from nose.tools import set_trace
from daisyclient import exc as client_exc
import copy
from fake.logical_network_fake import FakeLogicNetwork as logical_fake

CONF = config.CONF


class DaisyCinderVolumeTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyCinderVolumeTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.cinder_volume_add_meta = \
            {'disk_array': [{'management_ips': '10.43.177.1,10.43.177.2',
                             'pools': 'pool1,pool2',
                             'user_name': 'rooot',
                             'user_pwd': 'pwd',
                             'volume_driver': 'KS3200_FCSAN',
                             'volume_type': 'KISP-1'}]}

        cls.cinder_volume_update_meta = {'management_ips': '10.43.177.3',
                                         'pools': 'pool3',
                                         'user_name': 'rooot',
                                         'user_pwd': 'pwd',
                                         'volume_driver': 'KS3200_FCSAN',
                                         'volume_type': 'KISP-1'}

        cls.cluster_meta = \
            {'description': 'desc',
             'logic_networks': [{'name': 'external1',
                                 'physnet_name': 'phynet2',
                                 'segmentation_id': 200,
                                 'segmentation_type': 'vlan',
                                 'shared': True,
                                 'subnets': [{'cidr': '192.168.1.0/24',
                                              'dns_nameservers': ['8.8.4.4',
                                                                  '8.8.8.8'],
                                              'floating_ranges':
                                                  [['192.168.1.2',
                                                    '192.168.1.200']],
                                              'gateway': '192.168.1.1',
                                              'name': 'subnet2'},
                                             {'cidr': '172.16.1.0/24',
                                              'dns_nameservers': ['8.8.4.4',
                                                                  '8.8.8.8'],
                                              'floating_ranges':
                                                  [['172.16.1.130',
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
                                              'floating_ranges':
                                                  [['192.168.2.130',
                                                    '192.168.2.254']],
                                              'gateway': '192.168.2.1',
                                              'name': 'subnet123'}],
                                 'type': 'internal'},
                                {'name': 'internal1',
                                 'physnet_name': 'phynet3',
                                 'segmentation_id': '777',
                                 'segmentation_type': 'vlan',
                                 'shared': False,
                                 'subnets': [{'cidr': '192.168.31.0/24',
                                              'dns_nameservers':
                                                  ['8.8.4.4',
                                                   '8.8.8.8'],
                                              'floating_ranges':
                                                  [['192.168.31.130',
                                                    '192.168.31.254']],
                                              'gateway': '192.168.31.1',
                                              'name': 'subnet3'},
                                             {'cidr': '192.168.4.0/24',
                                              'dns_nameservers': ['8.8.4.4',
                                                                  '8.8.8.8'],
                                              'floating_ranges':
                                                  [['192.168.4.130',
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
        cls.role_meta = {'name': 'test_role',
                         'description': 'test'}

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
        set_trace()
        self.delete_network(self.private_network_id)
        self.delete_network(self.private_network_id1)
        self.delete_network(self.private_network_id2)

    def test_add_cinder_volume(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id

        cinder_volume_info = self.add_cinder_volume(
            **self.cinder_volume_add_meta)
        self.assertEqual('10.43.177.1,10.43.177.2',
                         cinder_volume_info.management_ips,
                         "test_add_cinder_volume failed")
        self.delete_cinder_volume(cinder_volume_info.id)

    def test_add_same_cinder_volume(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id
        self.cinder_volume_add_meta['role_id']

        cinder_volume_info = self.add_cinder_volume(
            **self.cinder_volume_add_meta)
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                 "400 Bad Request: cinder_volume array disks "
                                 "conflict with cinder_volume %s (HTTP 400)" %
                                 cinder_volume_info.id,
                                 self.add_cinder_volume,
                                 **self.cinder_volume_add_meta)
        self.delete_cinder_volume(cinder_volume_info.id)

    def test_add_cinder_volume_with_wrong_role(self):
        self.cinder_volume_add_meta['role_id'] = \
            'af47d81c-7ae4-4148-a801-b4a5c6a52074'

        self.assertRaisesMessage(client_exc.HTTPNotFound,
                                 "404 Not Found: The resource could not be "
                                 "found.: Role with identifier "
                                 "af47d81c-7ae4-4148-a801-b4a5c6a52074 not "
                                 "found (HTTP 404)",
                                 self.add_cinder_volume,
                                 **self.cinder_volume_add_meta)
        del self.cinder_volume_add_meta['role_id']

    def test_add_cinder_volume_with_wrong_driver(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id
        self.cinder_volume_add_meta['disk_array'][0]['volume_driver'] = \
            'test_driver'

        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                 "400 Bad Request: volume_driver test_driver "
                                 "is not supported (HTTP 400)",
                                 self.add_cinder_volume,
                                 **self.cinder_volume_add_meta)
        del self.cinder_volume_add_meta['role_id']
        self.cinder_volume_add_meta['disk_array'][0]['volume_driver'] = \
            'KS3200_FCSAN'

    def test_update_cinder_volume(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id
        cinder_volume_info = self.add_cinder_volume(
            **self.cinder_volume_add_meta)

        cinder_volume_update_info = self.update_cinder_volume(
            cinder_volume_info.id,
            **self.cinder_volume_update_meta)
        self.assertEqual('10.43.177.3',
                         cinder_volume_update_info.management_ips,
                         "test_update_cinder_volume failed")
        self.delete_cinder_volume(cinder_volume_info.id)

    def test_update_to_same_cinder_volume(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id
        cinder_volume_info = self.add_cinder_volume(
            **self.cinder_volume_add_meta)

        cinder_volume_add_meta1 = {'disk_array':
                                   [{'management_ips':
                                     '10.43.177.3,10.43.177.4',
                                     'pools': 'pool1,pool2',
                                     'user_name': 'rooot',
                                     'user_pwd': 'pwd',
                                     'volume_driver': 'KS3200_FCSAN',
                                     'volume_type': 'KISP-1'}]}
        cinder_volume_add_meta1['role_id'] = role.id
        cinder_volume_info1 = self.add_cinder_volume(
            **cinder_volume_add_meta1)
        update_meta = {'management_ips': '10.43.177.1,10.43.177.2'}
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request: cinder_volume array disks conflict with "
            "cinder_volume %s (HTTP 400)" % cinder_volume_info.id,
            self.update_cinder_volume,
            cinder_volume_info1.id,
            **update_meta)

        self.delete_cinder_volume(cinder_volume_info.id)
        self.delete_cinder_volume(cinder_volume_info1.id)

    def test_update_cinder_volume_with_wrong_driver(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id
        cinder_volume_info = self.add_cinder_volume(
            **self.cinder_volume_add_meta)

        update_meta = {'volume_driver': 'test_driver'}
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request: volume_driver test_driver is not supported"
            " (HTTP 400)",
            self.update_cinder_volume, cinder_volume_info.id, **update_meta)
        self.delete_cinder_volume(cinder_volume_info.id)

    def test_list_cinder_volume(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id
        cinder_volume_info = self.add_cinder_volume(
            **self.cinder_volume_add_meta)

        cinder_volume_meta = {}
        cinder_volume_flag = False
        list_cinder_volume = self.list_cinder_volume(**cinder_volume_meta)
        query_cinder_volume_list = [volume_info for volume_info
                                    in list_cinder_volume]

        if query_cinder_volume_list:
            cinder_volume_flag = True
        self.assertTrue(cinder_volume_flag, "test_list_cinder_volume error")
        self.delete_cinder_volume(cinder_volume_info.id)

    def test_get_cinder_volume_detail(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        role = self.add_role(**self.role_meta)
        self.cinder_volume_add_meta['role_id'] = role.id
        cinder_volume_info = self.add_cinder_volume(
            **self.cinder_volume_add_meta)

        cinder_volume_detail_info = self.get_cinder_volume_detail(
            cinder_volume_info.id)
        self.assertEqual("10.43.177.1,10.43.177.2",
                         cinder_volume_detail_info.management_ips,
                         "test_get_cinder_volume_detail failed")
        self.delete_cinder_volume(cinder_volume_info.id)

    def tearDown(self):
        if self.cinder_volume_add_meta.get('role_id', None):
            self.delete_role(self.cinder_volume_add_meta['role_id'])
            del self.cinder_volume_add_meta['role_id']
        if self.role_meta.get('cluster_id', None):
            self.delete_cluster(self.role_meta['cluster_id'])
            del self.role_meta['cluster_id']

        super(DaisyCinderVolumeTest, self).tearDown()
