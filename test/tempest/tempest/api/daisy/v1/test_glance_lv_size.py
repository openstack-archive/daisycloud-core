
from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception
from daisyclient import exc as client_exc
from fake.logical_network_fake import FakeLogicNetwork as logical_fake

NORMAL_GLANCE_LV_VALUE = 50000
ILLEGAL_GLANCE_LV_VALUE = 900000
NEGATIVE_GLANCE_LV_VALUE = -50000

class DaisyRoleGlanceLVSizeTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyRoleGlanceLVSizeTest, cls).resource_setup()
        cls.fake = logical_fake()
        cls.daisy_data = {'description': 'default',
                            'name': '4c09b4b2788a',
                            'ipmi_addr': '10.43.203.230',
                            'ipmi_user':'zteroot',
                            'ipmi_passwd':'superuser',
                            'interfaces': [{'name': 'enp132s0f0',
                                            "mac": '4c:09:b4:b2:78:8a',
                                            "ip": '99.99.1.60',
                                            'is_deployment': 'True',
                                            'pci': '0000:84:00.0',
                                            'netmask': '255.255.255.0'},
                                            {'name': 'enp132s0f1',
                                            "mac": '4c:09:b4:b2:78:8b',
                                            'pci': '0000:84:00.1',
                                            'is_deployment': 'False',}],
                            'os_status': 'init',
                            'dmi_uuid': '03000200-0400-0500-0006-000700080009'}

        cls.cluster_meta = {'description': 'desc',
                            'logic_networks': [{'name': 'external1',
                            'physnet_name': 'phynet3',
                            'segmentation_id': 200,
                            'segmentation_type': 'vlan',
                            'shared': True,
                            'subnets': [{'cidr': '99.99.1.0/24',
                                         'dns_nameservers': ['8.8.4.4',
                                                             '8.8.8.8'],
                                         'floating_ranges': [['99.99.1.2',
                                                              '99.99.1.200']],
                                         'gateway': '99.99.1.1',
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

        cls.ironic_data = {'uuid':'03000200-0400-0500-0006-000700080009',
                            'mac': '4c:09:b4:b2:78:8a',
                            'patch':[{'op': 'add',
                                    'path': '/disks/sda',
                                    'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                                'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                                'model': '',
                                                'name': 'sda',
                                                'removable': '',
                                                'size': ' 200127266816 bytes'}},
                                    {'op': 'add',
                                    'path': '/disks/sdb',
                                    'value': {'disk': 'ip-192.163.1.237:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-0',
                                                'extra': ['', ''],
                                                'model': '',
                                                'name': 'sdb',
                                                'removable': '',
                                                'size': ' 136870912000 bytes'}},
                                    {'op': 'add',
                                    'path': '/disks/sdc',
                                    'value': {'disk': 'ip-192.163.1.237:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-1',
                                                'extra': ['', ''],
                                                'model': '',
                                                'name': 'sdc',
                                                'removable': '',
                                                'size': ' 122122547200 bytes'}}]}

        cls.role_meta={'name':'test_role',
                       'description':'test'}

        cls.glance_service={'name':'glance',
                            'description':'glance_test_service'}

        cls.other_service={'name':'test_service',
                            'description':'other_test_service'}

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

    def ironic_discover_nodes(self):
        self.ironic_client.physical_node.update(self.ironic_data['uuid'],
                                                self.ironic_data['mac'],
                                                self.ironic_data['patch'])
        return self.daisy_client.hosts.add(**self.daisy_data)

    def delete_ironic_discover_nodes(self, host_id):
        self.daisy_client.hosts.delete(host_id)

    #STC-F-Daisy_Role_Set_Glance_LV_Size-0001
    def test_update_role_with_glance_lv_size_and_services(self):
        glance_lv_value = NORMAL_GLANCE_LV_VALUE
        host_info=self.ironic_discover_nodes()

        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id

        service_info=self.add_service(**self.glance_service)
        self.role_meta['services']=[service_info.id]
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'nodes':[host_info.id],
                            'glance_lv_size':glance_lv_value}
        self.role_meta['id']=add_role_info.id
        self.role_meta['nodes']=[host_info.id]
        self.role_meta['glance_lv_size']=glance_lv_value

        update_role_info=self.update_role(add_role_info.id, **update_role_meta)
        self.assertEqual(glance_lv_value, update_role_info.glance_lv_size, 
                        "test_update_role_with_glance_lv_size_and_services failed")


    #STC-F-Daisy_Role_Set_Glance_LV_Size-0002
    def test_update_role_with_glance_lv_size_and_wrong_services(self):
        glance_lv_value = NORMAL_GLANCE_LV_VALUE
        host_info=self.ironic_discover_nodes()

        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id

        service_info=self.add_service(**self.other_service)
        self.role_meta['services']=[service_info.id]
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'nodes':[host_info.id],
                            'glance_lv_size':glance_lv_value}

        self.assertRaisesMessage(client_exc.HTTPForbidden,
                    "403 Forbidden: service 'glance' is not in role %s, so can't set the size of glance lv. (HTTP 403)"\
                    % self.role_meta['name'],
                    self.update_role, add_role_info.id, **update_role_meta)
        self.role_meta['id']=add_role_info.id
        self.role_meta['nodes']=[host_info.id]

    #STC-F-Daisy_Role_Set_Glance_LV_Size-0003
    def test_update_role_with_glance_lv_size_and_add_glance_services(self):
        glance_lv_value = NORMAL_GLANCE_LV_VALUE
        host_info=self.ironic_discover_nodes()

        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id

        service_info=self.add_service(**self.other_service)
        self.role_meta['services']=[service_info.id]
        add_role_info=self.add_role(**self.role_meta)

        update_service_info=self.add_service(**self.glance_service)
        update_role_meta = {'nodes':[host_info.id],
                            'services':[update_service_info.id],
                            'glance_lv_size':glance_lv_value}

        self.role_meta['nodes']=[host_info.id]
        self.role_meta['glance_lv_size']=glance_lv_value
        self.role_meta['services'].append(update_service_info.id)

        update_role_info=self.update_role(add_role_info.id, **update_role_meta)
        self.assertEqual(glance_lv_value, update_role_info.glance_lv_size,
                        "test_update_role_with_glance_lv_size_and_add_glance_services failed")
        self.role_meta['id']=add_role_info.id


    #STC-F-Daisy_Role_Set_Glance_LV_Size-0004
    def test_add_role_with_glance_lv_size_and_services(self):
        glance_lv_value = NORMAL_GLANCE_LV_VALUE
        host_info=self.ironic_discover_nodes()

        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id

        service_info=self.add_service(**self.glance_service)
        self.role_meta['glance_lv_size']=glance_lv_value
        self.role_meta['services']=[service_info.id]
        self.role_meta['nodes']=[host_info.id]

        add_role_info=self.add_role(**self.role_meta)
        self.role_meta['id']=add_role_info.id
        self.assertEqual(glance_lv_value, add_role_info.glance_lv_size,
                        "test_add_role_with_glance_lv_size_and_services failed")

    #STC-F-Daisy_Role_Set_Glance_LV_Size-0005
    def test_add_role_with_glance_lv_size_and_other_services(self):
        glance_lv_value = NORMAL_GLANCE_LV_VALUE
        host_info=self.ironic_discover_nodes()

        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id

        service_info=self.add_service(**self.other_service)
        self.role_meta['glance_lv_size']=glance_lv_value
        self.role_meta['services']=[service_info.id]
        self.role_meta['nodes']=[host_info.id]

        self.assertRaisesMessage(client_exc.HTTPForbidden,
                    "403 Forbidden: service 'glance' is not in role %s, so can't set the size of glance lv. (HTTP 403)"% self.role_meta['name'],
                    self.add_role, **self.role_meta)

        #STC-F-Daisy_Role_Set_Glance_LV_Size-0006
    def test_update_role_with_negative_glance_lv_size_and_services(self):
        glance_lv_value = NEGATIVE_GLANCE_LV_VALUE
        host_info=self.ironic_discover_nodes()

        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id

        service_info=self.add_service(**self.glance_service)
        self.role_meta['services']=[service_info.id]
        add_role_info=self.add_role(**self.role_meta)

        update_role_meta = {'nodes':[host_info.id],
                            'glance_lv_size':glance_lv_value}


        self.role_meta['nodes']=[host_info.id]
        self.role_meta['glance_lv_size']=glance_lv_value
        self.role_meta['id']=add_role_info.id

        self.assertRaisesMessage(client_exc.HTTPForbidden,
                                "403 Forbidden: glance_lv_size can't be negative except -1. (HTTP 403)",
                                self.update_role, add_role_info.id,**update_role_meta)

    #STC-F-Daisy_Role_Set_Glance_LV_Size-0007
    def test_add_role_with_negative_glance_lv_size_and_services(self):
        glance_lv_value = NEGATIVE_GLANCE_LV_VALUE
        host_info=self.ironic_discover_nodes()

        self.private_network_add()
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id']=cluster_info.id

        service_info=self.add_service(**self.glance_service)
        self.role_meta['glance_lv_size']=glance_lv_value
        self.role_meta['services']=[service_info.id]
        self.role_meta['nodes']=[host_info.id]

        self.assertRaisesMessage(client_exc.HTTPForbidden,
                                "403 Forbidden: glance_lv_size can't be negative except -1. (HTTP 403)",
                                self.add_role, **self.role_meta)

    def tearDown(self):
        if self.role_meta.get('glance_lv_size',None):
            del self.role_meta['glance_lv_size']
        if self.role_meta.get('nodes',None):
            del self.role_meta['nodes']
        if self.role_meta.get('id',None):
            self.delete_role(self.role_meta['id'])
            del self.role_meta['id']
        if self.role_meta.get('services',None):
            for service_id in self.role_meta['services']:
                self.delete_service(service_id)
            del self.role_meta['services']
        if self.role_meta.get('cluster_id',None):
            self.delete_cluster(self.role_meta['cluster_id'])
            del self.role_meta['cluster_id']
        self._clean_all_host()
        self._clean_all_cluster()
        self.private_network_delete
        super(DaisyRoleGlanceLVSizeTest, self).tearDown()
