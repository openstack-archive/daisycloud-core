

import uuid
import pprint
import ConfigParser
import os
import subprocess
import time
import copy
try:
    import simplejson as json
    is_simplejson = True
except ImportError:
    import json

from daisyclient import exc as client_exc
from six import moves
from tempest.api.daisy import base
from tempest import config
from nose.tools import set_trace
from tempest import exceptions
from tempest_lib import exceptions as exceptions_lib

CONF = config.CONF

class TecsNetworkPlaneTest(base.BaseDaisyTest):

    def __int__(self):
        pass

    @classmethod
    def resource_setup(cls):
        super(TecsNetworkPlaneTest, cls).resource_setup()
        cls.network_data1 ={'name':'network_test1',
                            'description':'desc1',
                            'network_type':'DATAPLANE',
                            'type':'custom',
                            'cidr':'192.168.1.1/24',
                            'capability':'high',
                            'ml2_type':'ovs' 
                            }
        cls.network_data2 ={'name':'network_test2',
                            'description':'desc2',
                            'network_type':'DATAPLANE',
                            'type':'custom',
                            'cidr':'192.168.1.1/24',
                            'ml2_type': 'ovs'
                            }  

        cls.NETWORK_PARAMS = {
            'description': 'phynet1',
            'vlan_end': '1000',
            'ip_ranges': [{'start': '192.168.1.1', 'end': '192.168.1.16'}],
            'gateway': '192.168.1.1',
            'cluster_id': '',
            'vlan_start': '10',
            'cidr': '192.168.1.1/24',
            'type': 'custom',
            'network_type': 'DATAPLANE',
            'ml2_type': 'ovs',
            'name': 'phynet1',
            'mtu':1600,
            'vlan_id':""
        }

        cls.daisy_data_1 = {'description': 'default',
                            'name': '0007e9159900',
                            'ipmi_addr': '10.43.203.230',
                            'ipmi_user':'zteroot',
                            'ipmi_passwd':'superuser',
                            'interfaces':[
                                    {
                                        'type':'ether',
                                        'name':'enp8s0',
                                        'mac':'98:f5:37:e1:ae:99',
                                        'pci':'0000:03:00.1',
                                        'is_deployment': 'True',
                                        'ip':'99.99.1.70',
                                        'netmask':'255.255.255.0',
                                        'gateway':'99.99.1.1'
                                    },

                                    {
                                        'type':'ether',
                                        'name':'enp3s0f0',
                                        'mac':'90:e2:ba:8f:e5:54',
                                        'pci':'0000:03:00.0',
                                    },
                                    {
                                        'type':'ether',
                                        'name':'enp3s0f1',
                                        'mac':'90:e2:ba:8f:e5:55',
                                        'pci':'0000:08:00.0',
                                    },
                                    {
                                        'type':'ether',
                                        'name':'enp9s0',
                                        'mac':'98:f5:37:e1:ae:9a',
                                        'pci':'0000:09:00.0',
                                    }
                                ],
                            'os_status': 'init',
                            'dmi_uuid': '03000200-0400-0500-0006-000700080009'}

        cls.ironic_data_1 = {'uuid':'03000200-0400-0500-0006-000700080009',
                               'mac': '90:e2:ba:8f:e5:54',
                               'patch':[{'op': 'add',
                                        'path': '/disks/sda',
                                        'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                        'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                        'model': '',
                                        'name': 'sda',
                                        'removable': '',
                                        'size': ' 200127266818 bytes'}},
                                        {'op': 'add',
                                        'path': '/disks/sdb',
                                        'value': {'disk': 'ip-192.163.1.236:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-0',
                                        'extra': ['', ''],
                                        'model': '',
                                        'name': 'sdb',
                                        'removable': '',
                                        'size': ' 136870912008 bytes'}},
                                        {'op': 'add',
                                        'path': '/cpu/total',
                                        'value': 2
                                        },
                                        {'path': '/memory/total',
                                        'value': '1918888 kB',
                                        'op': 'add'},
                                        {'op': 'add',
                                        'path': '/disks/sdc',
                                        'value': {'disk': 'ip-192.163.1.236:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-1',
                                        'extra': ['', ''],
                                        'model': '',
                                        'name': 'sdc',
                                        'removable': '',
                                        'size': '122122547208 bytes'}}
                                        ]}
        cls.daisy_data_2 = {'description': 'default1',
                            'name': '0007e9159901',
                            'ipmi_addr': '10.43.203.231',
                            'ipmi_user':'zteroot',
                            'ipmi_passwd':'superuser',
                            'interfaces':[
                                    {
                                        'type':'ether',
                                        'name':'enp8s0',
                                        'mac':'98:f5:37:e1:af:16',
                                        'pci':'0000:08:00.1',
                                        # 'mode':None,
                                        'is_deployment': 'True',
                                        #'assigned_networks':['management1'],
                                        # 'slaves':None,
                                        #'ip':'192.168.1.203',
                                        'ip':'99.99.1.148',
                                        'netmask':'255.255.255.0',
                                        'gateway':'99.99.1.1'
                                    },
                                    {
                                        'type':'ether',
                                        'name':'enp3s0f1',
                                        'mac':'90:e2:ba:8f:df:38',
                                        'pci':'0000:03:00.1',
                                        # 'mode':None,
                                        # 'is_deployment':False,
                                        #'assigned_networks':['phynet1'],
                                        # 'slaves':None,
                                        # 'ip':None,
                                        # 'netmask':None,
                                        # 'gateway':None
                                    },
                                    {
                                        'type':'ether',
                                        'name':'enp3s0f2',
                                        'mac':'90:e2:ba:8f:df:39',
                                        'pci':'0000:03:00.0',
                                        # 'mode':None,
                                        # 'is_deployment':False,
                                        #'assigned_networks':['phynet2'],
                                        # 'slaves':None,
                                        # 'ip':None,
                                        # 'netmask':None,
                                        # 'gateway':None
                                    },
                                    {
                                        'type':'ether',
                                        'name':'enp9s0',
                                        'mac':'98:f5:37:e1:af:17',
                                        'pci':'0000:09:00.1',
                                        # 'mode':None,
                                        # 'is_deployment':True,
                                        #'assigned_networks':['deployment1'],
                                        # 'slaves':None,
                                        #'ip':'192.169.1.12',
                                        #'netmask':'255.255.255.0',
                                        # 'gateway':None
                                    }
                                ],
                            'os_status': 'init',
                            'dmi_uuid': '03000200-0400-0500-0006-000700080008'}
        cls.ironic_data_2 = {'uuid':'03000200-0400-0500-0006-000700080008',
                               'mac': '90:e2:ba:8f:df:38',
                               'patch':[{'op': 'add',
                                        'path': '/disks/sda',
                                        'value': {'disk': 'pci-0000:01:00.0-sas-0x500003956831a6da-lun-0',
                                        'extra': ['scsi-3500003956831a6d8', 'wwn-0x500003956831a6d8'],
                                        'model': '',
                                        'name': 'sda',
                                        'removable': '',
                                        'size': ' 200127266818 bytes'}},
                                        {'op': 'add',
                                        'path': '/disks/sdb',
                                        'value': {'disk': 'ip-192.163.1.236:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-0',
                                        'extra': ['', ''],
                                        'model': '',
                                        'name': 'sdb',
                                        'removable': '',
                                        'size': ' 136870912008 bytes'}},
                                        {'op': 'add',
                                        'path': '/cpu/total',
                                        'value': 2
                                        },
                                        {'path': '/memory/total',
                                        'value': '1918888 kB',
                                        'op': 'add'},
                                        {'op': 'add',
                                        'path': '/disks/sdc',
                                        'value': {'disk': 'ip-192.163.1.236:3260-iscsi-iqn.2099-01.cn.com.zte:usp.spr-4c:09:b4:b0:01:31-lun-1',
                                        'extra': ['', ''],
                                        'model': '',
                                        'name': 'sdc',
                                        'removable': '',
                                        'size': '122122547208 bytes'}}
                                        ]}

    def host_update(self, host_id, params=None):
        host_info1_rst = self.update_host(host_id, **params)
        self.assertEqual(host_info1_rst.id, params.get('id', None))
        self.assertEqual(host_info1_rst.dmi_uuid, params.get('dmi_uuid', None))
        self.assertEqual(host_info1_rst.ipmi_user, params.get('ipmi_user', None))
        self.assertEqual(host_info1_rst.ipmi_passwd, params.get('ipmi_passwd', None))
        self.assertEqual(host_info1_rst.ipmi_addr, params.get('ipmi_addr', None))
        # self.assertEqual(True, params.get('cluster', None) in host_info1_rst.cluster[0])
        self.assertEqual(host_info1_rst.os_status, params.get('os_status', None))
        self.assertEqual(host_info1_rst.os_version_file, params.get('os_version', None))
        # self.assertEqual(host_info1_rst.resource_type, params.get('resource-type', None))
        # self.assertEqual(host_info1_rst.role, params.get('role', None))
        # self.assertEqual(host_info1_rst.interfaces, params.get('interfaces', None))

        pprint.pprint(host_info1_rst)

    def private_network_add(self):
        # add network plane
        private_network_params1 = {
            'name' : 'phynet1',
            'description' : 'phynet1',
            'network_type':'DATAPLANE',
            'cluster_id':self.cluster_id,
            'type':'custom',
            'cidr':'192.169.1.1/25',
            'vlan_start':'101',
            'vlan_end':'1001',
            'ml2_type':'ovs'
        }
        self.private_id1 = self.network_add(private_network_params1)

        private_network_params2 = {
            'name' : 'phynet2',
            'description' : 'phynet2',
            'network_type':'DATAPLANE',
            'cluster_id':self.cluster_id,
            'type':'custom',
            'cidr':'192.169.2.1/24',
            'vlan_start':'101',
            'vlan_end':'1002',
            'ml2_type':'ovs'
        }
        self.private_id2 = self.network_add(private_network_params2)

        role_meta = {'cluster_id': self.cluster_id}
        network_list_genrator = self.list_network(**role_meta)
        network_list = [net for net in network_list_genrator]
        management_id  = [net.id for net in network_list if net.network_type == "MANAGEMENT"][0]
        management_network_params = {
            'name' : 'management1',
            'description' : 'management',
            'network_type':'MANAGEMENT',
            'type':'custom',
            'cidr':'192.169.1.1/24',
            'vlan_start':'11',
            'vlan_end':'1001',
            'capability':'high',
            'ip':'10.43.203.228',
            'gateway':'192.169.1.1'
        }
        self.network_update(management_id, cluster_id=self.cluster_id, params=management_network_params)

        deployment_id = [net.id for net in network_list if net.network_type == "DEPLOYMENT"][0]
        deployment_network_params = {
            'name' : 'deployment1',
            'description' : 'deployment',
            'network_type':'DEPLOYMENT',
            'type':'custom',
            'cidr':'192.169.1.1/26',
            'vlan_start':'11',
            'vlan_end':'1001',
            'capability':'high'
        }
        self.network_update(deployment_id, cluster_id=self.cluster_id, params=deployment_network_params)

        public_id = [net.id for net in network_list if net.network_type == "PUBLICAPI"][0]
        public_network_params = {
            'name' : 'public1',
            'description' : 'public',
            'network_type':'PUBLICAPI',
            'type':'custom',
            'cidr':'192.169.1.1/24',
            'vlan_start':'11',
            'vlan_end':'1001',
            'capability':'high'
        }
        self.network_update(public_id, cluster_id=self.cluster_id, params=public_network_params)

        external_id = [net.id for net in network_list if net.network_type == "EXTERNAL"][0]
        external_network_params = {
            'name' : 'external1',
            'description' : 'external',
            'network_type':'EXTERNAL',
            'type':'custom',
            'cidr':'192.169.1.1/24',
            'vlan_start':'11',
            'vlan_end':'1001',
            'capability':'high'
        }
        self.network_update(external_id, cluster_id=self.cluster_id, params=external_network_params)

        storage_id = [net.id for net in network_list if net.network_type == "STORAGE"][0]
        storage_network_params = {
            'name' : 'storage1',
            'description' : 'storage',
            'network_type':'STORAGE',
            'type':'custom',
            'cidr':'192.169.1.1/24',
            'vlan_start':'11',
            'vlan_end':'1001',
            'capability':'high'
        }
        self.network_update(storage_id, cluster_id=self.cluster_id, params=storage_network_params)

    def private_network_delete(self):
        self.network_delete(self.private_id1)
        self.network_delete(self.private_id2)

    def add_host_and_role_for_private_network(self, cluster_id):
        # TODO:discovery by ironic, add host info and role-------------
       # host_params1 = {
       #     'name':str(uuid.uuid1()),
      #      'description':'host1'
      #  }
        self.ironic_client.physical_node.update(self.ironic_data_1['uuid'],
                                                self.ironic_data_1['mac'],
                                                self.ironic_data_1['patch'])
        host_info1 = self.add_host(**self.daisy_data_1)
        self.assertEqual(self.daisy_data_1['name'], host_info1.name)
        host_id1 = host_info1.id

       # host_params2 = {
      #      'name':'host2',
      #      'description':'host2'
     #   }
        self.ironic_client.physical_node.update(self.ironic_data_2['uuid'],
                                                self.ironic_data_2['mac'],
                                                self.ironic_data_2['patch'])
        host_info2 = self.add_host(**self.daisy_data_2)
        self.assertEqual(self.daisy_data_2['name'], host_info2.name)
        host_id2 = host_info2.id
        # TODO:--------------------------------------------------------

        # get role
        roles_generator = self.list_roles()
        roles_list = [role for role in roles_generator if role.cluster_id == cluster_id]
        role_ha_id = [role.id for role in roles_list if role.name == 'CONTROLLER_HA'][0]
        role_lb_id = [role.id for role in roles_list if role.name == 'CONTROLLER_LB'][0]
        role_computer_id = [role.id for role in roles_list if role.name == 'COMPUTER'][0]

        # update host role
        role_meta = {'nodes':[host_id1,host_id2],
                     'vip': '10.43.203.111'}
        self.update_role(role_ha_id, **role_meta)
        self.update_role(role_lb_id, **role_meta)
        self.update_role(role_computer_id, **role_meta)
        host_info1 =self.get_host_detail(host_id1)
        self.assertEqual(True, set(host_info1.role).
                         issubset(set(['CONTROLLER_LB', 'COMPUTER', 'CONTROLLER_HA'])))
        host_info2 =self.get_host_detail(host_id1)
        self.assertEqual(True, set(host_info2.role).
                         issubset(set(['CONTROLLER_LB', 'COMPUTER', 'CONTROLLER_HA'])))
        return (host_id1, host_id2)

    def add_host_interface_for_private_network(self, *args):
        host_id1 = args[0]
        host_id2 = args[1]
        cluster_id = args[2]
        host_interface1 = {
            'id':host_id1,
            'dmi_uuid':'03000200-0400-0500-0006-000700080009',
            'ipmi_user':'zteroot',
            'ipmi_passwd':'superuser ',
            'ipmi_addr':'10.43.203.230',
            'cluster':cluster_id,
            'os_status':'init',
            'os_version':'/var/lib/daisy/tecs/CGSL_VPLAT-5.1-243-x86_64.iso',
            # 'resource_type':None,
            # 'role':None,
            'interfaces':[
                {
                    'type':'ether',
                    'name':'enp8s0',
                    'mac':'98:f5:37:e1:ae:99',
                    'pci':'0000:03:00.1',
                    # 'mode':None,
                    'is_deployment': 'True',
                    'assigned_networks':[{'name':'management1','ip':'192.169.1.124'}],
                    # 'slaves':None,
                    'ip':'192.169.1.124',
                    'netmask':'255.255.255.0',
                    'gateway':'192.169.1.1'
                },
                {
                    'type':'bond',
                    'name':'bond0',
                    'mac':'90:e2:ba:8f:e5:56',
                    # 'pci':None,
                    'mode':'0',
                    'pci':'0000:03:00.2',
                    # 'is_deployment':False,
                    'assigned_networks':[{'name':'phynet1'}],
                    'slaves':['enp3s0f1', 'enp3s0f0'],
                    # 'ip':None,
                    # 'netmask':None,
                    # 'gateway':None
                },
                {
                    'type':'ether',
                    'name':'enp3s0f0',
                    'mac':'90:e2:ba:8f:e5:54',
                    'pci':'0000:03:00.0',
                    # 'mode':None,
                    # 'is_deployment':False,
                    # 'assigned_networks':None,
                    # 'slaves':None,
                    # 'ip':None,
                    # 'netmask':None,
                    # 'gateway':None
                },
                {
                    'type':'ether',
                    'name':'enp3s0f1',
                    'mac':'90:e2:ba:8f:e5:55',
                    'pci':'0000:08:00.0',
                    # 'mode':None,
                    # 'is_deployment':False,
                    # 'assigned_networks':None,
                    # 'slaves':None,
                    # 'ip':None,
                    # 'netmask':None,
                    # 'gateway':None
                },
                {
                    'type':'ether',
                    'name':'enp9s0',
                    'mac':'98:f5:37:e1:ae:9a',
                    'pci':'0000:09:00.0',
                    # 'mode':None,
                    # 'is_deployment':True,
                    'assigned_networks':[{'name':'deployment1'}],
                    # 'slaves':None,
                    'ip':'192.169.1.11',
                    'netmask':'255.255.255.0',
                    # 'gateway':None
                }
            ]
        }
        self.host_update(host_id1, host_interface1)

        host_interface2 = {
            'id':host_id2,
            'dmi_uuid':'03000200-0400-0500-0006-000700080008',
            'ipmi_user':'zteroot',
            'ipmi_passwd':'superuser ',
            'ipmi_addr':'10.43.203.231',
            'cluster':cluster_id,
            'os_status':'init',
            'os_version':'/var/lib/daisy/tecs/CGSL_VPLAT-5.1-243-x86_64.iso',
            # 'resource_type':None,
            # 'role':None,
            'interfaces':[
                {
                    'type':'ether',
                    'name':'enp8s0',
                    'mac':'98:f5:37:e1:af:16',
                    'pci':'0000:08:00.1',
                    # 'mode':None,
                    'is_deployment': 'True',
                    'assigned_networks':[{'name':'management1','ip':'192.169.1.203'}],
                    # 'slaves':None,
                    'ip':'192.169.1.203',
                    'netmask':'255.255.255.0',
                    'gateway':'192.169.1.1'
                },
                {
                    'type':'ether',
                    'name':'enp3s0f1',
                    'mac':'90:e2:ba:8f:df:38',
                    'pci':'0000:03:00.1',
                    # 'mode':None,
                    # 'is_deployment':False,
                    'assigned_networks':[{'name':'phynet1'}],
                    # 'slaves':None,
                    # 'ip':None,
                    # 'netmask':None,
                    # 'gateway':None
                },
                {
                    'type':'ether',
                    'name':'enp3s0f2',
                    'mac':'90:e2:ba:8f:df:39',
                    'pci':'0000:03:00.0',
                    # 'mode':None,
                    # 'is_deployment':False,
                    'assigned_networks':[{'name':'phynet2'}],
                    # 'slaves':None,
                    # 'ip':None,
                    # 'netmask':None,
                    # 'gateway':None
                },
                {
                    'type':'ether',
                    'name':'enp9s0',
                    'mac':'98:f5:37:e1:af:17',
                    'pci':'0000:09:00.1',
                    # 'mode':None,
                    # 'is_deployment':True,
                    'assigned_networks':[{'name':'deployment1','ip':'192.169.1.12'}],
                    # 'slaves':None,
                    'ip':'192.169.1.12',
                    'netmask':'255.255.255.0',
                    # 'gateway':None
                }
            ]
        }
        self.host_update(host_id2, host_interface2)

    def del_host(self, *args):
        self.delete_host(args[0])
        self.assertRaisesMessage(client_exc.HTTPNotFound,
            "404 Not Found: The resource could not be found.:"
            " Network with identifier %s not found (HTTP 404)" % id,
            self.get_host_detail, args[0])

        self.delete_host(args[1])
        self.assertRaisesMessage(client_exc.HTTPNotFound,
            "404 Not Found: The resource could not be found.:"
            " Network with identifier %s not found (HTTP 404)11" % id,
            self.get_host_detail, args[1])

    def cluster_add(self):
        cluster_meta = {
            'description': 'desc',
            'name': str(uuid.uuid1()).split('-')[0]
        }
        # Precondition, we must add cluster first
        cluster_info = self.add_cluster(**cluster_meta)
        self.assertEqual(cluster_meta['name'], cluster_info.name, "cluster name is not correct")
        self.assertEqual(cluster_meta['description'], cluster_info.description,
                         "cluster add  interface execute failed")
        self.cluster_id = cluster_info.id
        self.NETWORK_PARAMS['cluster_id'] = cluster_info.id

        return cluster_info.id

    def cluster_delete(self, id):
        self.delete_cluster(id)

    def network_add(self, params=None):
        # add network params and check whether network is exist
        if not params:
            params = self.NETWORK_PARAMS
        pprint.pprint(params)
        network_add_rst = self.add_network(**params)
        self.assertEqual(network_add_rst.name, params.get('name', None))
        self.assertEqual(network_add_rst.description, params.get('description', None))
        self.assertEqual(network_add_rst.gateway, params.get('gateway', None))
        self.assertEqual(network_add_rst.cluster_id, params.get('cluster_id', None))
        self.assertEqual(network_add_rst.mtu, params.get('mtu', 1500))
        self.assertEqual(network_add_rst.vlan_id, params.get('vlan_id', None))
        self.assertEqual(str(network_add_rst.vlan_start), params.get('vlan_start', '1'))
        self.assertEqual(str(network_add_rst.vlan_end), params.get('vlan_end', '4094'))
        self.assertEqual(network_add_rst.network_type, params.get('network_type', None))
        self.assertEqual(network_add_rst.ip_ranges, params.get('ip_ranges', []))
        self.assertEqual(network_add_rst.ml2_type, params.get('ml2_type', None))
        self.assertEqual(network_add_rst.type, params.get('type', 'custom'))
        self.assertEqual(network_add_rst.cidr, params.get('cidr', None))
        #self.assertEqual(network_add_rst.capability, params.get('capability', None))
        network_info = self.get_network(network_add_rst.id)
        self.assertEqual(network_add_rst.id, network_info.id)
        pprint.pprint(network_add_rst)

        return network_add_rst.id

    def network_delete(self, id):
        # delete network check whether network is not exist
        self.delete_network(id)
        self.assertRaisesMessage(client_exc.HTTPNotFound,
            "404 Not Found: The resource could not be found.:"
            " Network with identifier %s not found (HTTP 404)" % id,
            self.get_network, id)

    def network_update(self, network_id, cluster_id=None, params=None):
        if not params:
            params = self.network_data2
        
        network_update_rst = self.update_network(network_id, **params)
        self.assertEqual(network_update_rst.name, params.get('name', "network plane update api error"))
        self.assertEqual(network_update_rst.description, params.get('description', "network plane update api error"))
        self.assertEqual(network_update_rst.gateway, params.get('gateway', None))
        self.assertEqual(network_update_rst.cluster_id, cluster_id)
        self.assertEqual(network_update_rst.mtu, params.get('mtu', 1500))
        self.assertEqual(network_update_rst.vlan_id, params.get('vlan_id', None))
        self.assertEqual(str(network_update_rst.vlan_start), params.get('vlan_start', '1'))
        self.assertEqual(str(network_update_rst.vlan_end), params.get('vlan_end', '4094'))
        self.assertEqual(network_update_rst.network_type, params.get('network_type', None))
        self.assertEqual(network_update_rst.ip_ranges, params.get('ip_ranges', []))
        self.assertEqual(network_update_rst.ml2_type, params.get('ml2_type', None))
        self.assertEqual(network_update_rst.type, params.get('type', 'custom'))
        self.assertEqual(network_update_rst.cidr, params.get('cidr', None))
        self.assertEqual(network_update_rst.capability, params.get('capability','high'))

        # network_info = self.get_network(network_id)
        # self.assertEqual(network_update_rst.id, network_info.id)
        pprint.pprint(network_update_rst)

    # base use case-----------------------------------------------
    def test_network_add_and_delete(self):
        # STC-F-daisy_Api-network-add-0001
        # STC-F-daisy_Api-network-delete-0002
        cluster_id = self.cluster_add()
        network_id = self.network_add()
        self.network_delete(network_id)
        self.cluster_delete(cluster_id)

    def test_network_add_with_same_name_excption(self):
        # STC-A-Daisy_API-network-add-with-same-name-0006
        cluster_id = self.cluster_add()
        network_params1 = {
            'name':'net2',
            'description':'net1',
            'network_type':'DATAPLANE',
            'cluster_id':cluster_id ,
            'ml2_type': 'ovs',
            'type':'custom'
        }

        network_params2 = {
            'name':'net2',
            'description':'net1',
            'network_type':'DATAPLANE',
            'cluster_id':cluster_id,
            'ml2_type': 'ovs'
        }

        network_id = self.network_add(network_params1)
        self.assertRaisesMessage(
            client_exc.HTTPConflict,
            "409 Conflict: There was a conflict when trying to complete your request.:"
            " Name of network isn't match case and %s already exits in the cluster. (HTTP 409)" %
            network_params2['name'],
            self.network_add, network_params2)

        self.network_delete(network_id)
        self.cluster_delete(cluster_id)

    
    def test_add_repeated_network_type_except_private_excption(self):
        # STC-A-Daisy_API-network-add-more-than-one-network-plane-0007
        cluster_id = self.cluster_add()
        network_params1 = {
            'name':'net1',
            'description':'net1',
            'network_type':'MANAGEMENT',
            'cluster_id':cluster_id,
            'type':'custom',
            'ml2_type': 'ovs'
        }

        ex = self.assertRaises(client_exc.HTTPConflict, self.network_add, network_params1)
        self.assertIn("The %s network plane %s must be unique, except DATAPLANE/STORAGE/HEARTBEAT network." %
                      (network_params1['network_type'], network_params1['name']), str(ex))

        # self.assertRaisesMessage(
            # client_exc.HTTPConflict,
            # "409 Conflict: There was a conflict when trying to complete your request.:"
            # " The type of networks:%s is same with db record which is all ready exit, "
            # "except PRIVATE network. (HTTP 409)" % network_params1['name'],
            # self.network_add, network_params1)

        self.cluster_delete(cluster_id)

    def test_network_plane_detail(self):
        # STC-F-daisy_Api-network-detail-0004
        cluster_id = self.cluster_add()
        network_data = copy.deepcopy(self.network_data1)
        network_data.update({'cluster_id':cluster_id})
        network_info = self.add_network(**network_data)
        get_network_info = self.get_network(network_info.id)
        self.assertEqual(get_network_info.cluster_id, cluster_id, "network cluster id get api error")
        self.assertEqual(get_network_info.name, self.network_data1['name'], "network plane get api error")
        self.assertEqual(get_network_info.description, self.network_data1['description'], "network plane get api error")
        self.assertEqual(get_network_info.network_type, self.network_data1['network_type'], "network plane get api error")
        self.assertEqual(get_network_info.type, self.network_data1['type'], "network plane get api error")
        self.assertEqual(get_network_info.cidr, self.network_data1['cidr'], "network plane get api error")
        self.cluster_delete(cluster_id)
        
    def test_network_plane_list(self):
        # STC-F-daisy_Api-network-list-0003
        cluster_id = self.cluster_add()
        role_meta1 = {'cluster_id': self.cluster_id}
        network_list = self.list_network(**role_meta1)
        network_list = [net for net in network_list if net.cluster_id]
        self.assertEqual(network_list[0].cluster_id, self.cluster_id)
        self.assertNotEqual(network_list, None, "network plane list api error")
        self.cluster_delete(cluster_id)

    def test_network_update(self):
        # STC-F-daisy_Api-network-update-0005
        cluster_id = self.cluster_add()
        network_data = copy.deepcopy(self.network_data1)
        network_data.update({'cluster_id':cluster_id})
        network_id = self.network_add(network_data)
        self.network_update(network_id, cluster_id=cluster_id)
        self.cluster_delete(cluster_id)
        #self.delete_network(network_id)

    def test_network_update_same_name_exctption(self):
        # STC-A-Daisy_API-update-network-with-same-name-0008
        cluster_id = self.cluster_add()
        network_params1 = {
            'name':'net1',
            'description':'net1',
            'network_type':'DEPLOYMENT',
            'type':'custom'
        }

        network_params2 = {
            'name':'net1',
            'description':'Net1',
            'network_type':'DEPLOYMENT',
            'type':'custom'
        }

        role_meta1 = {'cluster_id': self.cluster_id}
        network_list = self.list_network(**role_meta1)
        deployment_net = [net for net in network_list if net.network_type == "DEPLOYMENT"][0]
        deployment_id = deployment_net.id
        network_params1['cidr'] = deployment_net.cidr
        network_params2['cidr'] = deployment_net.cidr
        self.network_update(deployment_id, cluster_id=cluster_id, params=network_params1)
        self.assertRaisesMessage(
            client_exc.HTTPConflict,
            "409 Conflict: There was a conflict when trying to complete your request.:"
            " Name of network isn't match case and %s already exits in the cluster. (HTTP 409)" %
            network_params2['name'],
            self.network_update, deployment_id, cluster_id, network_params2)
        self.cluster_delete(cluster_id)
        #self.delete_network(deployment_id)
        

    # physic network use case---------------------------------------
    def test_private_network_add_and_delete(self):
        # STC-F-Daisy_Physical_Network_config_CLI-0001
        cluster_id = self.cluster_add()
        self.private_network_add()
        self.private_network_delete()
        self.cluster_delete(cluster_id)

    def test_host_add_for_private_network(self):
        # STC-F-Daisy_Physical_Network_config_CLI-0001
        cluster_id = self.cluster_add()
        (host_id1, host_id2) = self.add_host_and_role_for_private_network(cluster_id)

        # update host_interface for private network
        # self.add_host_interface_for_private_network(host_id1, host_id2, cluster_id)

        self.del_host(host_id1, host_id2)
        self.cluster_delete(cluster_id)

    def test_host_add_interface_for_private_network(self):
        # STC-F-Daisy_Physical_Network_config_CLI-0001
        cluster_id = self.cluster_add()
        self.private_network_add()
        (host_id1, host_id2) = self.add_host_and_role_for_private_network(cluster_id)

        # update host_interface for private network
        self.add_host_interface_for_private_network(host_id1, host_id2, cluster_id)
        self.del_host(host_id1, host_id2)
        self.cluster_delete(cluster_id)
    # install--------------------------------------------------------
    # def test_install_for_private_network(self):
    #     self.install_cluster_id = self.cluster_add()
    #     self.add_private_network()
    #     (host_id1, host_id2, role_ha_id, role_lb_id) = self.add_host_and_role_for_private_network()
    #     self.add_host_interface_for_private_network(host_id1, host_id1)
    #
    #     install_meta = {'cluster_id':self.install_cluster_id}
    #     install_info = self.install(**install_meta)
    #     self.assertEqual(install_info.status, "begin install","install interface execute failed")
    #
    #     # get progress for tecs installing
    #     time_step = 5
    #     # 1.5h
    #     time_out = self.time_out
    #
    #     ha_install_success = False
    #     lb_install_success = False
    #     all_install_success = False
    #     count = 0
    #     msg = ''
    #     while count < time_out:
    #         if not ha_install_success:
    #             role_ha_info = self.get_role(role_ha_id)
    #             if (role_ha_info.status == 'active' and
    #                 role_ha_info.progress == 100):
    #                 ha_install_success = True
    #             elif role_ha_info.status == 'install-failed':
    #                 msg ="tecs install failed"
    #                 break
    #
    #         if not lb_install_success:
    #             role_lb_info = self.get_role(role_lb_id)
    #             if (role_lb_info.status == 'active' and
    #                 role_lb_info.progress == 100):
    #                 lb_install_success = True
    #             elif role_lb_info.status == 'install-failed':
    #                 msg ="tecs install failed"
    #                 break
    #
    #         if lb_install_success and ha_install_success:
    #             all_install_success = True
    #             msg ="tecs install success"
    #             break
    #
    #         time.sleep(time_step)
    #         count += 1
    #
    #     if not all_install_success and count >= time_out:
    #         msg = "tecs install timeout"
    #     self.assertEqual(True, all_install_success, msg)
    #
    #     # check if network-configuration is install on host
    #     cmd1 = "clush -S -w %s rpm -qi network-configuration" % self.host_ip1
    #     is_rpm_exist = subprocess.call(cmd1, shell=True, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)
    #     self.assertEqual(is_rpm_exist,0, "network-configuration rpm is not installed in $s" % self.host_ip1)
    #     cmd2 = "clush -S -w %s rpm -qi network-configuration" % self.host_ip2
    #     is_rpm_exist = subprocess.call(cmd2, shell=True, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)
    #     self.assertEqual(is_rpm_exist,0, "network-configuration rpm is not installed in $s" % self.host_ip2)
    #
    # def test_check_mappings_json_and_tecs_conf(self):
    #     # STC-F-Daisy_Physic_Network_config-0003
    #     # check if mappings.json is genrate
    #     json_path = "/var/lib/daisy/tecs/mappings.json"
    #     self.assertTrue(os.path.exists(json_path))
    #     with open(json_path, 'r') as fp:
    #         content = fp.read()
    #     mappings_dict = json.load(content)
    #     mappings_test_dict = \
    #         {
    #         "hosts":
    #             {
    #             "10.43.203.228":
    #                 {
    #                     "phynet1":
    #                         {
    #                             "name": "bond0",
    #                             "pci2": "0000:03:00.0",
    #                             "ml2": "ovs,sriov(direct)",
    #                             "slave1": "enp3s0f1",
    #                             "mode": "0",
    #                             "slave2": "enp3s0f0",
    #                             "type": "bond",
    #                             "pci1": "0000:03:00.1"
    #                         }
    #                 },
    #             "10.43.203.229":
    #                 {
    #                     "phynet1": {
    #                         "ml2": "ovs",
    #                         "pci": "0000:03:00.1",
    #                         "type": "ether",
    #                         "name": "enp3s0f0"
    #                     },
    #                     "phynet2": {
    #                         "ml2": "ovs",
    #                         "pci": "0000:03:00.0",
    #                         "type": "ether",
    #                         "name": "enp3s0f1"
    #                     },
    #                 }
    #             }
    #         }
    #
    #     self.assertEqual(mappings_test_dict, mappings_dict)
    #
    #     # check if vlan_range has been wrote in tecs.conf
    #     json_path = "/var/lib/daisy/tecs/mappings.json"
    #     tecs_conf = "/var/lib/daisy/tecs/%s/tecs.conf" % self.install_cluster_id
    #     self.assertTrue(os.path.exists(tecs_conf))
    #     config = ConfigParser()
    #     config.read(tecs_conf)
    #     self.assertEqual(json_path, config.get("DEFAULT","CONFIG_NEUTRON_ML2_JSON_PATH"))
    #     self.assertEqual("phynet1:101:1001,phynet2:101:1002",
    #                      config.get("DEFAULT","CONFIG_NEUTRON_ML2_VLAN_RANGES"))
    #
    # def test_check_os_json(self):
    #     # STC-F-Daisy_Physical_Network_config-0004
    #     # 228
    #     try:
    #         exc_result = subprocess.check_output(
    #             'cat /home/os_install/os.json' % ("10.43.203.228",),
    #             shell=True, stderr=subprocess.STDOUT)
    #     except subprocess.CalledProcessError as e:
    #         self.assertEqual("", e.output.strip())
    #     else:
    #         os_json_dict = json.load(exc_result)
    #         host_interface_228 = os_json_dict.get('interfaces', None)
    #         private_host_interface_dict = \
    #             [host_interface_228 for assigned_network in host_interface_228['assigned_networks']
    #              if host_interface_228.get('assigned_networks', None)
    #              and assigned_network.get('network_type', None) == "PRIVATE"][0]
    #         private_assigned_networks_dict = private_host_interface_dict.get('assigned_networks', None)
    #
    #         # 228 host_interface info
    #         self.assertEqual(private_host_interface_dict.get('type', None), 'bond')
    #         self.assertEqual(private_host_interface_dict.get('name', None), 'bond0')
    #         self.assertEqual(private_host_interface_dict.get('mac', None), '90:e2:ba:8f:e5:55')
    #         self.assertEqual(private_host_interface_dict.get('mode', None), '0')
    #         self.assertEqual(private_host_interface_dict.get('netmask', None), None)
    #         self.assertEqual(private_host_interface_dict.get('ip', None), None)
    #         self.assertEqual(private_host_interface_dict.get('gateway', None), None)
    #         self.assertEqual(private_host_interface_dict.get('slave1', None), "enp3s0f1")
    #         self.assertEqual(private_host_interface_dict.get('slave2', None), "enp3s0f0")
    #         self.assertEqual(private_host_interface_dict.get('pci1', None), None)
    #         self.assertEqual(private_host_interface_dict.get('pci2', None), None)
    #
    #         # 228 network info
    #         self.assertEqual(private_assigned_networks_dict.get('physnet_name', None), 'physnet_bond0')
    #         self.assertEqual(private_assigned_networks_dict.get('network_type', None), 'PRIVATE')
    #         self.assertEqual(private_assigned_networks_dict.get('ml2_type', None), 'ovs,sriov(direct)')
    #         self.assertEqual(private_assigned_networks_dict.get('ip', None), None)
    #         self.assertEqual(private_assigned_networks_dict.get('netmask', None), None)
    #         self.assertEqual(private_assigned_networks_dict.get('gateway', None), None)
    #         self.assertEqual(private_assigned_networks_dict.get('capability', None), None)
    #
    #     # 229
    #     try:
    #         exc_result = subprocess.check_output(
    #             'cat /home/os_install/os.json' % ("10.43.203.229",),
    #             shell=True, stderr=subprocess.STDOUT)
    #     except subprocess.CalledProcessError as e:
    #         self.assertEqual("", e.output.strip())
    #     else:
    #         os_json_dict = json.load(exc_result)
    #         host_interface_228 = os_json_dict.get('interfaces', None)
    #         private_host_interface_dict = \
    #             [host_interface_228 for assigned_network in host_interface_228['assigned_networks']
    #              if host_interface_228.get('assigned_networks', None)
    #              and assigned_network.get('network_type', None) == "PRIVATE"][0]
    #         private_assigned_networks_dict = private_host_interface_dict.get('assigned_networks', None)
    #
    #         # 229 host_interface info
    #         self.assertEqual(private_host_interface_dict.get('type', None), 'ether')
    #         self.assertEqual(private_host_interface_dict.get('name', None), 'phynet1')
    #         self.assertEqual(private_host_interface_dict.get('mac', None), '90:e2:ba:8f:df:38')
    #         self.assertEqual(private_host_interface_dict.get('pci', None), "0000:03:00.1")
    #
    #         self.assertEqual(private_host_interface_dict.get('type', None), 'ether')
    #         self.assertEqual(private_host_interface_dict.get('name', None), 'phynet2')
    #         self.assertEqual(private_host_interface_dict.get('mac', None), '90:e2:ba:8f:df:39')
    #         self.assertEqual(private_host_interface_dict.get('pci', None), "0000:03:00.0")
    #
    #         # 229 network info
    #         self.assertEqual(private_assigned_networks_dict.get('physnet_name', None), None)
    #         self.assertEqual(private_assigned_networks_dict.get('network_type', None), 'PRIVATE')
    #         self.assertEqual(private_assigned_networks_dict.get('ml2_type', None), 'ovs')
    #         self.assertEqual(private_assigned_networks_dict.get('ip', None), None)
    #         self.assertEqual(private_assigned_networks_dict.get('netmask', None), None)
    #         self.assertEqual(private_assigned_networks_dict.get('gateway', None), None)
    #         self.assertEqual(private_assigned_networks_dict.get('capability', None), None)

    def test_dataplane_network(self):
        cluster_id = self.cluster_add()
        cluster_id_meta = {'cluster_id': cluster_id}
        network_list_genrator = self.list_network(**cluster_id_meta)
        network_list = [net for net in network_list_genrator]
        dataplane_id  = [net.id for net in network_list if net.network_type == "DATAPLANE"][0]
        get_network_info = self.get_network(dataplane_id)
        self.assertEqual(get_network_info.network_type, 'DATAPLANE', "network type is not DATAPLANE")

    def test_public_network(self):
        cluster_id = self.cluster_add()
        cluster_id_meta = {'cluster_id': cluster_id}
        network_list_genrator = self.list_network(**cluster_id_meta)
        network_list = [net for net in network_list_genrator]
        dataplane_id  = [net.id for net in network_list if net.network_type == "PUBLICAPI"][0]
        get_network_info = self.get_network(dataplane_id)
        self.assertEqual(get_network_info.network_type, 'PUBLICAPI', "network type is not PUBLICAPI")
        self.assertEqual(get_network_info.name, 'PUBLICAPI', "network name is not PUBLICAPI")

    def test_dataplane_network_with_segmention_type_use_vlan(self):
        cluster_id = self.cluster_add()
        vlan_network_params1 = {
            'name' : 'physnet3',
            'description' : 'physnet3',
            'network_type':'DATAPLANE',
            'cluster_id':self.cluster_id,
            'type':'custom',
            'vlan_start':'101',
            'vlan_end':'1001',
            'ml2_type':'ovs',
            'segmentation_type':'vlan'
        }
        network_add_rst = self.add_network(**vlan_network_params1)
        self.assertEqual(network_add_rst.__dict__['segmentation_type'], vlan_network_params1.get('segmentation_type', None))
        self.network_delete(network_add_rst.__dict__['id'])

    def test_dataplane_network_with_segmention_type_use_vxlan(self):
        cluster_id = self.cluster_add()
        vlan_network_params1 = {
            'name' : 'physnet3',
            'description' : 'physnet3',
            'network_type':'DATAPLANE',
            'cluster_id':self.cluster_id,
            'type':'custom',
            'vlan_start':'101',
            'vlan_end':'1001',
            'ml2_type':'ovs',
            'segmentation_type':'vxlan'
        }
        network_add_rst = self.add_network(**vlan_network_params1)
        self.assertEqual(network_add_rst.__dict__['segmentation_type'], 'vxlan')
        self.network_delete(network_add_rst.__dict__['id'])

    def test_dataplane_network_with_use_vxlan_and_vni_range(self):
        cluster_id = self.cluster_add()
        vlan_network_params1 = {
            'name' : 'physnet3',
            'description' : 'physnet3',
            'network_type':'DATAPLANE',
            'cluster_id':self.cluster_id,
            'type':'custom',
            'vlan_start':'101',
            'vlan_end':'1001',
            'ml2_type':'ovs',
            'segmentation_type':'vxlan',
            'vni_start':'5000',
            'vni_end':'50000'
        }
        network_add_rst = self.add_network(**vlan_network_params1)
        self.assertEqual(network_add_rst.__dict__['vni_start'], 5000)
        self.assertEqual(network_add_rst.__dict__['vni_end'], 50000)
        self.network_delete(network_add_rst.__dict__['id'])

    def test_dataplane_network_with_use_vxlan_and_vni_start_less_vni_end(self):
        cluster_id = self.cluster_add()
        vlan_network_params1 = {
            'name' : 'physnet3',
            'description' : 'physnet3',
            'network_type':'DATAPLANE',
            'cluster_id':self.cluster_id,
            'type':'custom',
            'vlan_start':'101',
            'vlan_end':'1001',
            'ml2_type':'ovs',
            'segmentation_type':'vxlan',
            'vni_start':'60000',
            'vni_end':'50000'
        }
        self.assertRaisesMessage(
            client_exc.HTTPBadRequest,
            "400 Bad Request: vni_start must be less than vni_end (HTTP 400)",
            self.add_network, **vlan_network_params1)

    def tearDown(self):
        self._clean_all_host()
        self._clean_all_cluster()
        #self._clean_all_physical_node()
        super(TecsNetworkPlaneTest, self).tearDown() 
