
from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception
from daisyclient import exc as client_exc
import copy
from fake.logical_network_fake import FakeLogicNetwork as logical_fake

class DaisyRoleTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyRoleTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.host_meta = {'name': 'test_add_host',
                         'description': 'test_tempest'}
        cls.host_meta_interfaces ={'type':'ether',
           'name': 'eth1',
           'mac': 'fe80::f816:3eff',
           'ip': '10.43.177.121',
           'netmask': '255.255.254.0',
           'is_deployment': 'True',
           'assigned_networks': ['MANAGEMENT','DEPLOYMENT'],
           'slaves':'eth1'}

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
                            'physnet_name': 'phynet3',
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
        cls.role_meta={'name':'test_role',
                       'description':'test'}

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

    def test_add_role(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)

        self.assertEqual("test_role", role.name,"test_add_role failed")
        self.delete_role(role.id)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_cluster(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role_with_cluster=self.add_role(**self.role_meta)

        self.assertEqual("init", role_with_cluster.status,"test_add_role_with_cluster failed")
        self.delete_role(role_with_cluster.id)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_config_set_id(self):
        config_set={'name':'add_config_set',
                    'description':'config_set'}
        add_config_set=self.add_config_set(**config_set)
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        self.role_meta['config_set_id']=add_config_set.id
        role_meta_with_config_set_id=self.add_role(**self.role_meta)

        self.assertEqual("init", role_meta_with_config_set_id.status,"test_add_role_with_config_set_id failed")
        self.delete_role(role_meta_with_config_set_id.id)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_nodes(self):
        host_info=self.add_host(**self.host_meta)
        self.role_meta['nodes']=[host_info.id]
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role_meta_with_nodes=self.add_role(**self.role_meta)

        self.assertEqual("init", role_meta_with_nodes.status,"test_add_role_with_nodes failed")
        self.delete_role(role_meta_with_nodes.id)
        self.delete_host(host_info.id)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_error_nodes(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        self.role_meta['nodes']=['c79e1d0d-a889-4b11-b77d-9dbbed455bb']

        for host_id in self.role_meta['nodes']:
            self.assertRaisesMessage(client_exc.HTTPNotFound,
                "404 Not Found: The resource could not be found.: Host with identifier %s not found (HTTP 404)" % host_id,
                 self.add_role, **self.role_meta)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_error_cluster(self):
        self.role_meta['cluster_id']='c79e1d0d-a889-4b11-b77d-9dbbed455bb'

        self.assertRaisesMessage(client_exc.HTTPNotFound,
                "404 Not Found: The resource could not be found.: Cluster with identifier %s not found (HTTP 404)" % self.role_meta['cluster_id'],
                 self.add_role, **self.role_meta)

    def test_add_role_with_error_services(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        self.role_meta['services']=['c79e1d0d-a889-4b11-b77d-9dbbed455bb']

        for service_id in self.role_meta['services']:
            self.assertRaisesMessage(client_exc.HTTPNotFound,
                "404 Not Found: The resource could not be found.: Service with identifier %s not found (HTTP 404)" % service_id,
                 self.add_role, **self.role_meta)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_error_config_set_id(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        self.role_meta['config_set_id']='c79e1d0d-a889-4b11-b77d-9dbbed455bb'

        self.assertRaisesMessage(client_exc.HTTPNotFound,
                "404 Not Found: The resource could not be found.: config_set with identifier %s not found (HTTP 404)" % self.role_meta['config_set_id'],
                 self.add_role, **self.role_meta)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_services(self):
        service_meta={'name':'service_test_role',
                       'description':'test_role'}
        service_info=self.add_service(**service_meta)
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        self.role_meta['services']=[service_info.id]
        role_with_services=self.add_role(**self.role_meta)
        self.assertEqual("init", role_with_services.status,"test_add_role_with_services failed")
        self.delete_role(role_with_services.id)
        self.delete_service(service_info.id)
        self.delete_cluster(cluster_info.id)

    def test_add_role_with_type_and_vip(self):
        self.role_meta['type']='template'
        self.role_meta['vip']='10.43.177.251'
        add_role=self.add_role(**self.role_meta)

        self.assertEqual("init", add_role.status,"test_add_role_with_type_and_vip failed")
        self.delete_role(add_role.id)

    def test_update_role_with_cluster(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'name': 'test_update_role',
                            'description': 'test_tempest'}
        update_role_info=self.update_role(add_role_info.id,**update_role_meta)

        self.assertEqual("test_update_role", update_role_info.name, "test_update_role_with_cluster failed")
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_error_cluster(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)
        self.role_meta['cluster_id']='c79e1d0d-a889-4b11-b77d-9dbbed455bb'

        ex = self.assertRaises(client_exc.Forbidden, self.update_role, add_role_info.id,**self.role_meta)
        self.assertIn("Can't update the cluster of the role.", str(ex))
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_error_config_set_id(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)
        self.role_meta['config_set_id']='c79e1d0d-a889-4b11-b77d-9dbbed455bb'

        self.assertRaisesMessage(client_exc.HTTPNotFound,
                "404 Not Found: The resource could not be found.: config_set with identifier %s not found (HTTP 404)" % self.role_meta['config_set_id'],
                 self.update_role, add_role_info.id,**self.role_meta)
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_error_nodes(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)
        self.role_meta['nodes']=['c79e1d0d-a889-4b11-b77d-9dbbed455bb']

        for host_id in self.role_meta['nodes']:
            self.assertRaisesMessage(client_exc.HTTPNotFound,
                    "404 Not Found: The resource could not be found.: Host with identifier %s not found (HTTP 404)" % host_id,
                     self.update_role, add_role_info.id,**self.role_meta)
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_error_services(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)
        self.role_meta['services']=['c79e1d0d-a889-4b11-b77d-9dbbed455bb']

        for service_id in self.role_meta['services']:
            self.assertRaisesMessage(client_exc.HTTPNotFound,
                    "404 Not Found: The resource could not be found.: Service with identifier %s not found (HTTP 404)" % service_id,
                     self.update_role, add_role_info.id,**self.role_meta)
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_cluster_and_config_set_id(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)
        config_set={'name':'add_config_set',
                    'description':'config_set'}
        add_config_set=self.add_config_set(**config_set)
        update_role_meta = {'name': 'test_update_role',
                            'description': 'test_tempest',
                            'config_set_id':add_config_set.id,
                            'cluster_id':cluster_info.id}

        update_role_info=self.update_role(add_role_info.id,**update_role_meta)

        self.assertEqual("test_update_role", update_role_info.name,"test_update_role_with_cluster_and_config_set_id failed")
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_nodes_and_services(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)
        host_info=self.add_host(**self.host_meta)
        self.role_meta['nodes']=[host_info.id]

        service_meta={'name':'service_test_role',
                      'description':'test_role'}
        service_info=self.add_service(**service_meta)
        self.role_meta['services']=[service_info.id]

        update_role_meta = {'name': 'test_update_role',
                            'description': 'test_tempest',
                            'nodes':[host_info.id],
                            'services':[service_info.id]}

        update_role_info=self.update_role(add_role_info.id,**update_role_meta)

        self.assertEqual("test_update_role", update_role_info.name,"test_update_role_with_cluster_and_config_set_id failed")
        self.delete_role(add_role_info.id)
        self.delete_service(service_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_type_and_vip(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'name': 'test_update_role',
                            'description': 'test_tempest',
                            'type':'custom',
                            'vip':'10.43.177.250'}
        update_role_info=self.update_role(add_role_info.id,**update_role_meta)

        self.assertEqual("test_update_role", update_role_info.name,"test_update_role_with_cluster failed")
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_db_vip(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'name': 'test_update_role',
                            'description': 'test_tempest',
                            'type':'custom',
                            'db_vip':'10.43.177.250'}
        update_role_info=self.update_role(add_role_info.id,**update_role_meta)

        self.assertEqual("test_update_role", update_role_info.name,"test_update_role_with_db_vip failed")
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_glance_vip(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'name': 'test_update_role',
                            'description': 'test_tempest',
                            'type':'custom',
                            'glance_vip':'10.43.177.250'}
        update_role_info=self.update_role(add_role_info.id,**update_role_meta)

        self.assertEqual("test_update_role", update_role_info.name,"test_update_role_with_glance_vip failed")
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_public_vip(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'name': 'test_update_role',
                            'description': 'test_tempest',
                            'type':'custom',
                            'public_vip':'10.43.177.250'}
        update_role_info=self.update_role(add_role_info.id,**update_role_meta)

        self.assertEqual("test_update_role", update_role_info.name,"test_update_role_with_public_vip failed")
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)


    def test_list_role(self):
        role_meta={}
        role_flag=False
        list_role=self.list_roles(**role_meta)
        query_role_list = [role_info for role_info in list_role]
        if query_role_list:
            role_flag=True
        self.assertTrue(role_flag, "test_list_role error")

    def test_list_role_with_cluster_id(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        kwargs={'cluster_id':cluster_info.id}
        role_list_meta = {'filters': kwargs}
        list_role=self.list_roles(**role_list_meta)
        query_role_list = [role_info for role_info in list_role]
        for query_role in query_role_list:
            self.assertTrue(query_role.cluster_id, cluster_info.id)
        self.delete_cluster(cluster_info.id)

    def test_list_role_with_error_cluster_id(self):
        kwargs={'cluster_id':'c79e1d0d-a889-4b11-b77d-9dbbed455bb'}
        role_list_meta = {'filters': kwargs}
        self.assertRaisesMessage(client_exc.HTTPNotFound,
            "404 Not Found: The resource could not be found.: Cluster with identifier %s not found (HTTP 404)" % kwargs['cluster_id'],
             self.list_roles, **role_list_meta)

    def test_get_role_detail(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        add_role_info=self.add_role(**self.role_meta)

        get_role=self.get_role(add_role_info.id)

        self.assertEqual('test_role', get_role.name)
        self.delete_role(add_role_info.id)
        self.delete_cluster(cluster_info.id)

    def test_role_delete(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.delete_role(role.id)
        self.delete_cluster(cluster_info.id)

    def tearDown(self):
        if self.role_meta.get('cluster_id',None):
           del self.role_meta['cluster_id']
        if self.role_meta.get('nodes',None):
           del self.role_meta['nodes']
        if self.role_meta.get('services',None):
           del self.role_meta['services']
        if self.role_meta.get('config_set_id',None):
           del self.role_meta['config_set_id']
        if self.role_meta.get('type', None):
           del self.role_meta['type']
        self._clean_all_host()
        self._clean_all_cluster()
        self._clean_all_config_set()
        super(DaisyRoleTest, self).tearDown()
