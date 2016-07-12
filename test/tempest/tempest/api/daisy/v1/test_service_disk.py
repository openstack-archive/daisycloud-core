
from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception
from daisyclient import exc as client_exc
import copy
from fake.logical_network_fake import FakeLogicNetwork as logical_fake

class DaisyServiceDiskTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyServiceDiskTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.service_disk_add_meta = {'service':'glance'}
                                                
        cls.service_disk_update_meta = {'service':'db',
                                        'disk_location':'share',
                                        'data_ips':'10.43.177.1,10.43.177.2',
                                        'size':'1',
                                        'lun':'0'}
                         
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

    #STC-A-Daisy_Service_Disk-0001
    def test_add_service_disk(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.service_disk_add_meta['role_id'] = role.id
        
        service_disk_info = self.add_service_disk(**self.service_disk_add_meta)
        self.assertEqual('glance', service_disk_info.service, "test_add_service_disk failed")
        self.delete_service_disk(service_disk_info.id)
    
    #STC-A-Daisy_Service_Disk-0002
    def test_add_same_service_disk_in_same_role(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.service_disk_add_meta['role_id'] = role.id
        
        service_disk_info = self.add_service_disk(**self.service_disk_add_meta)
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                '400 Bad Request: disk service glance has existed in role %s (HTTP 400)'% role.id,
                                self.add_service_disk, **self.service_disk_add_meta)
        self.delete_service_disk(service_disk_info.id)
    
    #STC-A-Daisy_Service_Disk-0003
    def test_add_service_disk_with_wrong_service(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        add_meta = {}
        add_meta['service'] = 'test_service'
        add_meta['role_id'] = role.id
        
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                "400 Bad Request: service '%s' is not supported (HTTP 400)" % add_meta['service'],
                                self.add_service_disk, **add_meta)
    
    #STC-A-Daisy_Service_Disk-0004
    def test_add_service_disk_with_wrong_location(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        add_meta = {}
        add_meta['service'] = 'glance'
        add_meta['role_id'] = role.id
        add_meta['disk_location'] = 'test_location'
        
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                "400 Bad Request: disk_location %s is not supported (HTTP 400)" % add_meta['disk_location'],
                                self.add_service_disk, **add_meta)
    
    #STC-A-Daisy_Service_Disk-0005
    def test_update_service_disk(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.service_disk_add_meta['role_id'] = role.id
        service_disk_info = self.add_service_disk(**self.service_disk_add_meta)
        
        service_disk_update_info = self.update_service_disk(service_disk_info.id, **self.service_disk_update_meta)
        self.assertEqual('db', service_disk_update_info.service, "test_update_service_disk failed")
        self.delete_service_disk(service_disk_update_info.id)
    
    #STC-A-Daisy_Service_Disk-0006
    def test_update_service_disk_with_wrong_location(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.service_disk_add_meta['role_id'] = role.id
        service_disk_info = self.add_service_disk(**self.service_disk_add_meta)
        
        update_meta = {'disk_location':'test_location'}
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                "400 Bad Request: disk_location '%s' is not supported (HTTP 400)" % update_meta['disk_location'],
                                self.update_service_disk, service_disk_info.id, **update_meta)
    
    #STC-F-Daisy_Service_Disk-0007
    def test_update_service_disk_with_wrong_service(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.service_disk_add_meta['role_id'] = role.id
        service_disk_info = self.add_service_disk(**self.service_disk_add_meta)
        
        update_meta = {'service':'test_service'}
        self.assertRaisesMessage(client_exc.HTTPBadRequest,
                                "400 Bad Request: service '%s' is not supported (HTTP 400)" % update_meta['service'],
                                self.update_service_disk, service_disk_info.id, **update_meta)
        self.delete_service_disk(service_disk_info.id)
    
    #STC-F-Daisy_Service_Disk-0008
    def test_list_service_disk(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.service_disk_add_meta['role_id'] = role.id
        service_disk_info = self.add_service_disk(**self.service_disk_add_meta)
        
        service_disk_meta={}
        service_disk_flag=False
        list_service_disk=self.list_service_disk(**service_disk_meta)
        query_service_disk_list = [service_disk_info for service_disk_info in list_service_disk]
        if query_service_disk_list:
            service_disk_flag=True
        self.assertTrue(service_disk_flag, "test_list_service_disk error")
        self.delete_service_disk(service_disk_info.id)

    #STC-A-Daisy_Service_Disk-0009
    def test_get_service_disk_detail(self):
        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id
        role=self.add_role(**self.role_meta)
        self.service_disk_add_meta['role_id'] = role.id
        service_disk_info = self.add_service_disk(**self.service_disk_add_meta)
        
        service_disk_detail_info = self.get_service_disk_detail(service_disk_info.id)
        self.assertEqual("glance", service_disk_detail_info.service, "test_get_cinder_volume_detail failed")
        self.delete_service_disk(service_disk_info.id)

    def tearDown(self):
        if self.service_disk_add_meta.get('role_id',None):
            self.delete_role(self.service_disk_add_meta['role_id'])
            del self.service_disk_add_meta['role_id']
        if self.role_meta.get('cluster_id',None):
            self.delete_cluster(self.role_meta['cluster_id'])
            del self.role_meta['cluster_id']

        super(DaisyServiceDiskTest, self).tearDown()
        
