import mock
import webob
from daisy import test
from daisy.api.backends.kolla import install
from daisy.context import RequestContext
import subprocess
from oslo_serialization import jsonutils

mgnt_ip_list = ['192.168.1.21', '192.168.1.20', '192.168.1.22']
dns_name_ip = [{'host-192-168-1-21': '192.168.1.21'},
               {'host-192-168-1-20': '192.168.1.20'},
               {'lb-vip': '192.168.1.50'},
               {'host-192-168-1-22': '192.168.1.22'},
               {'ha-vip': '192.168.1.50'},
               {'public-vip': '10.43.203.114'},
               {'glance-vip': '192.168.1.50'},
               {'db-vip': '192.168.1.50'}]
ha_nodes_ip = ['192.168.1.21', '192.168.1.20']
roles = [{u'db_vip': None,
          u'status': u'init',
          u'outband_vip': None,
          u'mongodb_vip': None,
          u'vip': None,
          u'cluster_id': u'8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
          u'ntp_server': None,
          u'deleted_at': None,
          u'id': u'9994269b-376c-49df-a698-24ade6edb7f1',
          u'glance_lv_size': 0,
          u'provider_public_vip': None,
          u'db_lv_size': 0,
          u'progress': 0,
          u'type': u'default',
          u'nova_lv_size': 0,
          u'glance_vip': None,
          u'config_set_id': u'055d7ea7-13ab-4b3c-8b8f-f26cd1640ac4',
          u'description': u'Computer Role for kolla.',
          u'deleted': False,
          u'updated_at': u'2016-12-28T07:52:25.000000',
          u'role_type': u'COMPUTER',
          u'deployment_backend': u'kolla',
          u'name': u'COMPUTER',
          u'created_at': u'2016-12-28T07:51:15.000000',
          u'messages': None,
          u'public_vip': None,
          u'disk_location': u'local',
          u'config_set_update_progress': 0},
         {u'db_vip': None,
          u'status': u'init',
          u'outband_vip': None, u'mongodb_vip': None,
          u'vip': u'10.20.11.11',
          u'cluster_id': u'8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
          u'ntp_server': None,
          u'deleted_at': None,
          u'id': u'008dec06-f9fc-4ce1-be77-681e7c252c2d',
          u'glance_lv_size': 0, u'provider_public_vip': None,
          u'db_lv_size': 0, u'progress': 0, u'type': u'default',
          u'nova_lv_size': 0, u'glance_vip': None,
          u'config_set_id': u'1749523e-f7f4-4d18-843c-9e32cf8a9997',
          u'description': u'Controller Role for kolla.',
          u'deleted': False, u'updated_at': u'2016-12-28T07:52:25.000000',
          u'role_type': u'CONTROLLER_LB', u'deployment_backend': u'kolla',
          u'name': u'CONTROLLER_LB',
          u'created_at': u'2016-12-28T07:51:15.000000',
          u'messages': None, u'public_vip': None, u'disk_location': u'local',
          u'config_set_update_progress': 0}]
role_hosts = [{u'status': u'installing', u'deleted': False,
               u'created_at': u'2016-12-28T07:52:25.000000',
               u'messages': u'begin deploy openstack',
               u'updated_at': u'2016-12-28T07:52:25.000000',
               u'role_id': u'008dec06-f9fc-4ce1-be77-681e7c252c2d',
               u'progress': 60,
               u'host_id': u'9423980b-ec76-475a-b45f-558eb4b7dfed',
               u'deleted_at': None,
               u'id': u'4ae8c321-b053-49b1-ac36-e3fd24753ccb'}]
deploy_host_cfg = {'mgtip': u'10.20.11.3', 'pub_macname': u'ens3',
                   'sto_macname': u'ens3', 'mgt_macname': u'ens3',
                   'host_name': u'host-10-20-11-3'}
cluster_roles = [{'cluster_id': '8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
                  'db_vip': '196.168.1.4', 'deployment_backend': 'kolla',
                  'glance_vip': '196.168.1.3', 'vip': '196.168.1.2',
                  'id': 'ae166ec5-61fe-4997-900d-8bb86b988fa2',
                  'name': 'CONTROLLER_HA', 'ntp_server': None,
                  'public_vip': '10.43.177.100', 'status': 'init',
                  'outband_vip': ''},
                 {'cluster_id': '8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
                  'db_vip': None, 'deployment_backend': 'kolla',
                  'glance_vip': None, 'vip': None,
                  'id': '96406e44-0e4d-4a82-a0d4-3eec01859026',
                  'name': 'COMPUTER', 'ntp_server': None,
                  'public_vip': None, 'status': 'init'},
                 {'cluster_id': '8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
                  'db_vip': None, 'deployment_backend': 'kolla',
                  'glance_vip': None, 'vip': '196.168.1.5',
                  'id': '065ccf12-9cda-4e09-a5f7-27359f24c33e',
                  'name': 'CONTROLLER_LB', 'ntp_server': None,
                  'public_vip': None, 'status': 'init'}]
cluster_networks = [{'capability': 'high',
                     'cluster_id': '8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
                     'id': 'ee027d1b-f6f8-482b-b1d3-3d6f5aab0d8f',
                     'ip': None, 'ip_ranges': [],
                     'ml2_type': None, 'name': 'MANAGEMENT',
                     'network_type': 'MANAGEMENT',
                     'physnet_name': 'physnet_enp132s0f0',
                     'segmentation_type': None, 'vlan_end': 4094,
                     'vlan_id': None, 'vlan_start': 1, 'vni_end': None,
                     'vni_start': None},
                    {'capability': 'high',
                     'cluster_id': '8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
                     'id': 'a27748a7-2c84-409a-8f34-b8c1f00bb3a4',
                     'ip': None, 'ip_ranges': [], 'ml2_type': None,
                     'name': 'PUBLICAPI', 'network_type': 'PUBLICAPI',
                     'physnet_name': 'physnet_enp132s0f1',
                     'segmentation_type': None, 'vlan_end': 4094,
                     'vlan_id': None, 'vlan_start': 1, 'vni_end': None,
                     'vni_start': None},
                    {'capability': 'high',
                     'cluster_id': '8ad27e36-f3e2-48b4-84b8-5b676c6fabde',
                     'id': '9388ed37-d8bf-4f44-ad22-1a1525c2b056',
                     'ip': None, 'ip_ranges': [{'end': '199.168.1.100',
                                                'start': '199.168.1.1'}],
                     'ml2_type': 'ovs', 'name': 'physnet1',
                     'network_type': 'DATAPLANE',
                     'physnet_name': 'physnet_enp132s0f3',
                     'segmentation_type': 'vxlan', 'vlan_end': 4094,
                     'vlan_id': None, 'vlan_start': 1, 'vni_end': 20000,
                     'vni_start': 1}]
cluster_meta = {'name': 'test', 'use_dns': 1,
                'networks': ['ee027d1b-f6f8-482b-b1d3-3d6f5aab0d8f',
                             'a27748a7-2c84-409a-8f34-b8c1f00bb3a4',
                             '9388ed37-d8bf-4f44-ad22-1a1525c2b056',
                             '84ff9a2a-9c99-4dee-b10e-6f5ee66737da',
                             '5059cd00-78cd-4d0a-acc6-5143a1692f47',
                             '460dbbc8-63c8-458c-a386-556b35b159ee'],
                'nodes': ['4e33c650-ab91-4564-ada5-e939bece23a5',
                          'e4801a04-7aa2-4966-8eed-38650b188a17',
                          '07278e9a-1bd5-4ae2-b1cf-38bbc0bd0d29',
                          '7739d9d9-93ca-480f-bde4-3b4c1052e63a']}
host1_meta = {'cluster': 'test', 'dvs_cps': '', 'dvs_high_cpset': '',
              'id': '7739d9d9-93ca-480f-bde4-3b4c1052e63a',
              'dvs_config_type': '',
              'interfaces': [{'assigned_networks': [{'ip': '196.168.1.7',
                                                     'name': 'MANAGEMENT',
                                                     'type': 'MANAGEMENT'}],
                              'host_id':
                                  '7739d9d9-93ca-480f-bde4-3b4c1052e63a',
                              'id': '293494b6-dfef-494d-968d-7a2fabe26dab',
                              'ip': '192.168.1.13', 'is_deployment': True,
                              'mac': '4c:09:b4:b2:81:8a', 'mode': None,
                              'name': 'enp132s0f0', 'netmask': '255.255.255.0',
                              'pci': '0000:84:00.0', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': ''},
                             {'assigned_networks': [{'ip': '192.168.1.3',
                                                     'name': 'PUBLICAPI',
                                                    'type': 'PUBLICAPI'}],
                              'host_id':
                                  '7739d9d9-93ca-480f-bde4-3b4c1052e63a',
                              'id': '5c9df2e4-7d9c-4e95-9648-eda314ddb8e1',
                              'ip': None, 'is_deployment': False,
                              'mac': '4c:09:b4:b2:81:8b', 'mode': None,
                              'name': 'enp132s0f1', 'netmask': None,
                              'pci': '0000:84:00.1', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': ''}],
              'isolcpus': None, 'name': 'host-196-168-1-7', 'os_cpus': '',
              'os_status': 'active', 'pci_high_cpset': '', 'position': '',
              'role': ['CONTROLLER_LB', 'CONTROLLER_HA'], 'vcp_pin_set': ''}


host2_meta = {'cluster': 'test', 'dvs_cps': '', 'dvs_high_cpset': '',
              'id': '4e33c650-ab91-4564-ada5-e939bece23a5',
              'dvs_config_type': '',
              'interfaces': [{'assigned_networks': [{'ip': '192.168.1.2',
                                                     'name': 'PUBLICAPI',
                                                     'type': 'PUBLICAPI'}],
                              'host_id':
                                  '4e33c650-ab91-4564-ada5-e939bece23a5',
                              'id': '83c2a3f5-05c7-4757-b057-e2f25466f43a',
                              'ip': None, 'is_deployment': False,
                              'mac': '4c:09:b4:b2:80:8b', 'mode': None,
                              'name': 'enp132s0f1', 'netmask': None,
                              'pci': '0000:84:00.1', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': ''},
                             {'assigned_networks': [{'ip': '196.168.1.6',
                                                     'name': 'MANAGEMENT',
                                                     'type': 'MANAGEMENT'}],
                              'host_id':
                                  '4e33c650-ab91-4564-ada5-e939bece23a5',
                              'id': 'e59e585a-49e6-4e81-83a2-b22dffd50a0d',
                              'ip': '192.168.1.12', 'is_deployment': True,
                              'mac': '4c:09:b4:b2:80:8a', 'mode': None,
                              'name': 'enp132s0f0', 'netmask': '255.255.255.0',
                              'pci': '0000:84:00.0', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': ''}],
              'isolcpus': None, 'name': 'host-196-168-1-6', 'os_cpus': '',
              'os_status': 'active', 'pci_high_cpset': '', 'position': '',
              'role': ['CONTROLLER_LB', 'CONTROLLER_HA'], 'vcpu_pin_set': ''}

host3_meta = {'cluster': 'test', 'dvs_cps': '', 'dvs_high_cpset': '',
              'id': '07278e9a-1bd5-4ae2-b1cf-38bbc0bd0d29',
              'dvs_config_type': '',
              'interfaces': [{'assigned_networks': [{'ip': '',
                                                     'name': 'physnet1',
                                                     'type': 'DATAPLANE'}],
                              'host_id':
                                  '07278e9a-1bd5-4ae2-b1cf-38bbc0bd0d29',
                              'id': '497acce0-3403-4ac6-8cd2-ebc21bcce49e',
                              'ip': None, 'is_deployment': False,
                              'mac': '4c:09:b4:b2:78:8d', 'mode': None,
                              'name': 'enp132s0f3', 'netmask': None,
                              'pci': '0000:84:00.3', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': 'dvs'},
                             {'assigned_networks': [{'ip': '196.168.1.8',
                                                     'name': 'MANAGEMENT',
                                                     'type': 'MANAGEMENT'}],
                              'host_id':
                                  '07278e9a-1bd5-4ae2-b1cf-38bbc0bd0d29',
                              'id': '6eb121ef-ae89-487d-96b9-eb7789103d51',
                              'ip': '192.168.1.10', 'is_deployment': True,
                              'mac': '4c:09:b4:b2:78:8a', 'mode': None,
                              'name': 'enp132s0f0', 'netmask': '255.255.255.0',
                              'pci': '0000:84:00.0', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': ''}],
              'isolcpus': None, 'name': 'host-196-168-1-8',
              'os_cpus': '', 'os_status': 'active', 'pci_high_cpset': '',
              'position': '', 'role': ['COMPUTER'], 'vcpu_pin_set': ''}
host4_meta = {'cluster': 'test', 'dvs_cps': '', 'dvs_high_cpset': '',
              'dvs_config_type': '',
              'id': 'e4801a04-7aa2-4966-8eed-38650b188a17',
              'interfaces': [{'assigned_networks': [{'ip': '',
                                                     'name': 'physnet1',
                                                     'type': 'DATAPLANE'}],
                              'host_id':
                                  'e4801a04-7aa2-4966-8eed-38650b188a17',
                              'id': '2131ebdd-5ac8-49e0-852e-90c223d01cce',
                              'ip': None, 'is_deployment': False,
                              'mac': '4c:09:b4:b2:79:8b', 'mode': None,
                              'name': 'enp132s0f1', 'netmask': None,
                              'pci': '0000:84:00.1', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': 'dvs'},
                             {'assigned_networks': [{'ip': '196.168.1.9',
                                                     'name': 'MANAGEMENT',
                                                     'type': 'MANAGEMENT'}],
                              'host_id':
                                  'e4801a04-7aa2-4966-8eed-38650b188a17',
                              'id': '299fc41d-dde5-45ca-be3b-c94693d2b9ce',
                              'ip': '192.168.1.11', 'is_deployment': True,
                              'mac': '4c:09:b4:b2:79:8a',
                              'mode': None, 'name': 'enp132s0f0',
                              'netmask': '255.255.255.0',
                              'pci': '0000:84:00.0', 'slave1': None,
                              'slave2': None, 'type': 'ether',
                              'vswitch_type': ''}],
              'isolcpus': None, 'name': 'host-196-168-1-9',
              'os_cpus': '', 'os_status': 'active', 'pci_high_cpset': '',
              'position': '', 'role': ['COMPUTER'], 'vcpu_pin_set': ''}

host5_meta = {u'os_version_id': None,
              u'config_set_id': None,
              u'root_disk': u'sda',
              u'os_status': u'active',
              u'discover_mode': u'PXE',
              u'updated_at': u'2016-12-28T08:00:03.000000',
              u'group_list': None, u'cluster': u'clustertest',
              u'hugepages': 0,
              u'dvsp_cpus': None,
              u'deleted_at': None,
              u'id': u'9423980b-ec76-475a-b45f-558eb4b7dfed',
              u'vcpu_pin_set': None,
              u'dvsv_cpus': None,
              u'hwm_ip': None,
              u'role': [u'CONTROLLER_LB', u'COMPUTER'],
              u'virtio_queue_size': None,
              u'dvs_config_desc': None,
              u'hwm_id': None,
              u'pci_high_cpuset': u'',
              u'status': u'with-role',
              u'description': u'default',
              u'dvsc_cpus': None,
              u'dmi_uuid': u'020BFFB8-7FF2-4147-88C1-2B6305A4E1C8',
              u'ipmi_passwd': None,
              u'dvs_config_type': None,
              u'resource_type': u'baremetal',
              u'position': u'',
              u'version_patch_id': None,
              u'tecs_version_id': None,
              u'flow_mode': None,
              u'ipmi_user': None,
              u'hugepagesize': u'1G',
              u'name': u'host-10-20-11-3',
              u'dvsblank_cpus': None,
              u'ipmi_addr': u'',
              u'root_pwd': u'ossdbg1',
              u'dvs_high_cpuset': None,
              u'dvs_cpus': None,
              u'root_lv_size': 102400}

host6_meta = {u'os_version_id': None,
              u'config_set_id': None,
              u'root_disk': u'sda',
              u'os_status': u'active',
              u'discover_mode': u'PXE',
              u'updated_at': u'2016-12-28T08:00:03.000000',
              u'group_list': None, u'cluster': u'clustertest',
              u'hugepages': 0,
              u'dvsp_cpus': None,
              u'deleted_at': None,
              u'id': u'9423980b-ec76-475a-b45f-558eb4b7dfed',
              u'interfaces': [{u'assigned_networks':
                                   [{u'ip': u'127.0.0.1',
                                     u'name': u'MANAGEMENT',
                                     u'type': u'MANAGEMENT'}],
                               u'host_id':
                                   u'9423980b-ec76-475a-b45f-558eb4b7dfed',
                               u'id': u'299fc41d-dde5-45ca-be3b-c94693d2b9ce',
                               u'ip': u'192.168.1.11', u'is_deployment': True,
                               u'mac': u'4c:09:b4:b2:79:8a',
                               u'mode': None, u'name': u'enp132s0f0',
                               u'netmask': u'255.255.255.0',
                               u'pci': u'0000:84:00.0', u'slave1': None,
                               u'slave2': None, u'type': u'ether',
                               u'vswitch_type': ''}],
              u'vcpu_pin_set': None,
              u'dvsv_cpus': None,
              u'hwm_ip': None,
              u'role': [u'CONTROLLER_LB', u'COMPUTER'],
              u'virtio_queue_size': None,
              u'dvs_config_desc': None,
              u'hwm_id': None,
              u'pci_high_cpuset': u'',
              u'status': u'with-role',
              u'description': u'default',
              u'dvsc_cpus': None,
              u'dmi_uuid': u'020BFFB8-7FF2-4147-88C1-2B6305A4E1C8',
              u'ipmi_passwd': None,
              u'dvs_config_type': None,
              u'resource_type': u'baremetal',
              u'position': u'',
              u'version_patch_id': None,
              u'tecs_version_id': None,
              u'flow_mode': None,
              u'ipmi_user': None,
              u'hugepagesize': u'1G',
              u'name': u'host-10-20-11-3',
              u'dvsblank_cpus': None,
              u'ipmi_addr': u'',
              u'root_pwd': u'ossdbg1',
              u'dvs_high_cpuset': None,
              u'dvs_cpus': None,
              u'root_lv_size': 102400}

assigned_network = {u'network_id': u'ee027d1b-f6f8-482b-b1d3-3d6f5aab0d8f',
                    u'ip': u'196.168.1.9',
                    u'created_at': u'2017-01-04T12:03:41.000000',
                    u'deleted': False,
                    u'updated_at': u'2017-01-04T12:03:41.000000',
                    u'interface_id': u'299fc41d-dde5-45ca-be3b-c94693d2b9ce',
                    u'vswitch_type': None,
                    u'mac': u'52:54:00:ac:ed:70',
                    u'deleted_at': None,
                    u'id': u'54079edb-4dff-4b1c-bd2d-695c2ae3ebd1'}


def subprocesscall(cmd):
    subprocess.call(cmd, shell=True,
                    stdout=open('/dev/null', 'w'),
                    stderr=subprocess.STDOUT)


class MockLoggingHandler(object):
    """Mock logging handler to check for expected logs.
    Messages are available from an instance's ``messages`` dict, in order,
    indexed by a lowercase log level string (e.g., 'debug', 'info', etc.).
    """

    def __init__(self):
        self.messages = {'debug': [], 'info': [], 'warning': [], 'error': []}

    def info(self, message, *args, **kwargs):
        self.messages['info'].append(message)

    def error(self, message, *args, **kwargs):
        self.messages['error'].append(message)

    def reset(self):
        for message in self.messages:
            del self.messages[message][:]


class ConfigBackend():
    def __init__(self, type, req):
        pass

    def push_config_by_hosts(self, par1, par2):
        pass


class Version():
    def __init__(self, filename):
        self.filename = filename
        pass

    def cached_version_string(self):
        return '3.0.2'


class TestInstall(test.TestCase):

    _log_handler = MockLoggingHandler()

    def setUp(self):
        super(TestInstall, self).setUp()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        self.installer = install.KOLLAInstallTask(
            self.req, '8ad27e36-f3e2-48b4-84b8-5b676c6fabde')

    @mock.patch('daisy.api.backends.kolla.common.get_computer_node_cfg')
    @mock.patch('daisy.api.backends.kolla.common.get_controller_node_cfg')
    @mock.patch('daisy.api.backends.kolla.common.get_host_detail')
    @mock.patch('daisy.api.backends.kolla.common.get_hosts_of_role')
    @mock.patch('daisy.api.backends.kolla.common.get_roles_detail')
    @mock.patch('daisy.api.backends.common.get_cluster_networks_detail')
    @mock.patch('daisy.api.backends.kolla.install._get_local_ip')
    @mock.patch('os.walk')
    def test_get_cluster_kolla_config(
            self, mock_do_walk, mock_do__get_local_ip,
            mock_do_get_cluster_networks_detail,
            mock_do_get_roles_detail,
            mock_do_get_hosts_of_role, mock_do_get_host_detail,
            mock_do_get_controller_node_cfg, mock_do_get_computer_node_cfg):
        cmd = 'mkdir -p /home/kolla_install/docker/'
        subprocesscall(cmd)
        cmd1 = 'touch /home/kolla_install/docker/test.version'
        subprocesscall(cmd1)
        f1 = open('/home/kolla_install/docker/test.version', 'a')
        f1.write('tag = 3.0.2')
        f1.close()
        cmd2 = 'touch /home/kolla_install/docker/all.yml'
        subprocesscall(cmd2)
        f2 = open('/home/kolla_install/docker/all.yml', 'a')
        f2.write('openstack_release : 3.0.2')
        f2.close()
        mock_do_walk.return_value = ('/home/kolla_install/docker/', [],
                                     ['test.version'])
        mock_do__get_local_ip.return_value = '127.0.0.1'
        mock_do_get_cluster_networks_detail.return_value = cluster_networks
        mock_do_get_roles_detail.return_value = roles
        mock_do_get_hosts_of_role.return_value = role_hosts
        mock_do_get_host_detail.return_value = host5_meta
        mock_do_get_controller_node_cfg.return_value = deploy_host_cfg
        mock_do_get_computer_node_cfg.return_value = {'mgtip': u'',
                                                      'pub_macname': u'',
                                                      'sto_macname': u'',
                                                      'mgt_macname': u'',
                                                      'host_name': u'',
                                                      'dat_macname': u'',
                                                      'ext_macname': u''}

        (kolla_config, mgt_ip_list, host_name_ip_list) =\
            install.get_cluster_kolla_config(
            self.req,
            '8ad27e36-f3e2-48b4-84b8-5b676c6fabde')
        self.assertEqual('3.0.2', kolla_config['Version'])
        cmd_end1 = 'rm -rf /home/kolla_install/docker/test.version'
        subprocesscall(cmd_end1)
        cmd_end2 = 'rm -rf /home/kolla_install/docker/all.yml'
        subprocesscall(cmd_end2)

    @mock.patch('daisy.api.backends.kolla.install._get_local_ip')
    @mock.patch('daisy.api.common.config_network_new')
    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    @mock.patch('daisy.api.backends.kolla.install.update_progress_to_db')
    @mock.patch('daisy.api.backends.kolla.install.update_host_progress_to_db')
    @mock.patch('daisy.api.backends.kolla.install.config_nodes_hosts')
    @mock.patch(
        'daisy.api.backends.kolla.install.update_all_host_progress_to_db')
    @mock.patch('daisy.api.backends.common.get_assigned_network')
    @mock.patch('daisy.api.backends.common.get_host_detail')
    @mock.patch('daisy.api.backends.common.get_cluster_roles_detail')
    @mock.patch('daisy.api.backends.common.get_cluster_networks_detail')
    @mock.patch('daisy.api.backends.common.get_hosts_of_role')
    @mock.patch('daisy.api.backends.kolla.install.generate_kolla_config_file')
    @mock.patch('daisy.api.backends.kolla.install.get_cluster_kolla_config')
    @mock.patch('subprocess.Popen.poll')
    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    def test__run(
            self, mock_subprocess_call, mock_do_check_output,
            mock_do_Popen, mock_do_get_cluster_kolla_config,
            mock_do_generate_kolla_config_file, mock_do_get_hosts_of_role,
            mock_do_get_cluster_networks_detail,
            mock_do_get_cluster_roles_detail,
            mock_do_get_host_detail, mock_do_get_assigned_network,
            mock_do_update_all_host_progress_to_db, mock_do_config_nodes_hosts,
            mock_do_update_host_progress_to_db, mock_do_update_progress_to_db,
            mock_do_request, mock_do_config_network_new, mock_do_get_local_ip):

        def mock_get_cluster_kolla_config(*args, **kwargs):
            return (kolla_config, mgt_ip_list, host_name_ip_list)

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            host_id = "9423980b-ec76-475a-b45f-558eb4b7dfed"
            if method == "GET" and path == "/nodes":
                list_result = {'nodes': [host6_meta]}
                res.read.return_value = jsonutils.dumps(list_result)
                return res
            if method == "GET" and path == "/nodes/%s" % host_id:
                get_result = {'host': host6_meta}
                res.read.return_value = jsonutils.dumps(get_result)
                return res
        cmd = 'mkdir -p /var/log/daisy'
        subprocesscall(cmd)
        mock_do_request.side_effect = fake_do_request
        mock_do_check_output.return_value = 'ok'
        mock_do_Popen.return_value = 0
        mock_do_get_hosts_of_role.return_value = role_hosts
        mock_do_get_cluster_networks_detail.return_value = cluster_networks
        mock_do_get_cluster_roles_detail.return_value = cluster_roles
        mock_do_get_host_detail.return_value = host6_meta
        mock_do_get_assigned_network.return_value = assigned_network
        mock_do_get_local_ip.return_value = '127.0.0.1'
        kolla_config = {}
        mgt_ip_list = ['127.0.0.1']
        host_name_ip_list = [{'localhost': '127.0.0.1'}]
        mock_do_get_cluster_kolla_config.side_effect = \
            mock_get_cluster_kolla_config
        self.installer._run()
        log_file = '/var/log/daisy/'\
                   'kolla_8ad27e36-f3e2-48b4-84b8-5b676c6fabde_deploy.log'
        all_the_text = open('%s' % log_file).read()
        self.assertIn('okokok', all_the_text)
        cmd = 'rm -rf /var/log/daisy'
        subprocesscall(cmd)
