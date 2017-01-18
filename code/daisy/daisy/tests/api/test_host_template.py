import mock
import webob
import json
import os
from daisy.context import RequestContext
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn
from daisy import test
from daisy.api.v1 import host_template
from webob.exc import HTTPNotFound
from webob.exc import HTTPForbidden


host_detail = {'id': '7739d9d9-93ca-480f-bde4-3b4c1052e63a',
               'name': "test",
               'dhcp_mac': "dd",
               'config_set_id': '82b659eb-0c95-4cb9-a55a-57dba1b19309',
               'root_pwd': 'test',
               'ipmi_user': 'admin',
               'ipmi_passwd': 'superuser',
               'ipmi_addr': "10.43.177.1",
               'os_version_file': 'test',
               'swap_lv_size': '1000',
               'db_lv_size': '1000',
               'discover_mode': 'PXE',
               'mongodb_lv_size': '1000',
               'group_list': 'core',
               'disks': {"sda": {"name": "sda", "extra":
                   ["scsi-350000396582a129c", "wwn-0x50000396582a129c"],
                                 "removable": "", "model": "", "disk":
                   "pci-0000:01:00.0-sas-0x50000396582a129e-lun-0",
                                 "size": " 600127266816 bytes"}},
               'interfaces': [
                   {'assigned_networks': [{'ip': '196.168.1.7',
                                           'name': 'MANAGEMENT',
                                           'network_type': 'MANAGEMENT',
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
                                           'network_type': 'PUBLICAPI',
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
               'memory': {"total": "       264122576 kB",
                           "phy_memory_1":
                               {"maximum_capacity": " 256 GB",
                                "devices_5": {
                                    "frequency": " 1333 MHz",
                                    "type": " DDR3", "size": " 16384 MB"},
                                "devices_4": {"frequency": " 1333 MHz",
                                              "type": " DDR3",
                                              "size": " 16384 MB"},
                                "devices_7": {"frequency": " 1333 MHz",
                                              "type": " DDR3",
                                              "size": " 16384 MB"},
                                "devices_6": {"frequency": " 1333 MHz",
                                              "type": " DDR3",
                                              "size": " 16384 MB"},
                                "devices_1": {"frequency": " 1333 MHz",
                                              "type": " DDR3",
                                              "size": " 16384 MB"},
                                "devices_3": {"frequency": " 1333 MHz",
                                              "type": " DDR3",
                                              "size": " 16384 MB"},
                                "devices_2": {"frequency": " 1333 MHz",
                                              "type": " DDR3",
                                              "size": " 16384 MB"},
                                "slots": " 8",
                                "devices_8": {"frequency": " 1333 MHz",
                                              "type": " DDR3",
                                              "size": " 16384 MB"}}, }}

hwm_host_detail = {'id': '7739d9d9-93ca-480f-bde4-3b4c1052e63a',
                   'name': "test",
                   'dhcp_mac': "dd",
                   'config_set_id': '82b659eb-0c95-4cb9-a55a-57dba309',
                   'root_pwd': 'test',
                   'ipmi_user': 'admin',
                   'ipmi_passwd': 'superuser',
                   'ipmi_addr': "10.43.177.1",
                   'os_version_file': 'test',
                   'swap_lv_size': '1000',
                   'db_lv_size': '1000',
                   'mongodb_lv_size': '1000',
                   'group_list': 'core',
                   'hwm_id': '111',
                   'hwm_ip': '127.0.0.1',
                   'discover_mode': ''}


class TestHostTemplate(test.TestCase):

    def setUp(self):
        super(TestHostTemplate, self).setUp()
        self.controller = host_template.Controller()

    def test_filter_params(self):
        hoat_meta = self.controller._filter_params(host_detail)
        self.assertEqual(None, hoat_meta.get('memory', None))
        self.assertEqual(None, hoat_meta.get('disks', None))
        self.assertEqual(None, hoat_meta.get('os_status', None))
        self.assertEqual(None, hoat_meta.get('cpu', None))
        self.assertEqual(None, hoat_meta.get('ipmi_addr', None))
        self.assertEqual(None, hoat_meta.get('status', None))
        self.assertEqual(None, hoat_meta.get('messages', None))
        self.assertEqual(None, hoat_meta.get('id', None))

    def test_get_host_template_detail(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template_id = "123"
        registry.host_template_detail_metadata = mock.Mock(
            return_value={"host_template_name": "test"})
        host_template_meta = \
            self.controller.get_host_template_detail(req, template_id)
        self.assertEqual(
            "test", host_template_meta['host_template']['host_template_name'])

    def test_update_host_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template_id = "123"
        host_template = {}
        registry.update_host_template_metadata = mock.Mock(
            return_value={"host_template_name": "test"})
        host_template_meta = self.controller.update_host_template(
            req, template_id, host_template)
        self.assertEqual(
            "test", host_template_meta['host_template']['host_template_name'])

    def test_add_host_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {"host_template_name": "test"}
        registry.add_host_template_metadata = mock.Mock(
            return_value={"host_template_name": "test"})
        host_template_meta = self.controller.add_host_template(
            req, host_template)
        self.assertEqual(
            "test", host_template_meta['host_template']['host_template_name'])

    def test_get_host_template_lists(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        self.controller._get_query_params = mock.Mock(
            return_value={'filter': {}})
        registry.host_template_lists_metadata = mock.Mock(return_value=[])
        hosts = self.controller.get_host_template_lists(req)
        self.assertEqual({}, hosts['host_template'])

    def test_host_to_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test'}
        self.get_host_meta_or_404 = mock.Mock(return_value=host_detail)
        host_template_meta = self.controller.host_to_template(
            req, host_template)
        self.assertEqual(
            'test', host_template_meta['host_template']['host_template_name'])

    def test_template_to_host(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test'}
        self.get_host_meta_or_404 = mock.Mock(return_value=host_detail)
        self.assertRaises(
            HTTPNotFound, self.controller.template_to_host, req, host_template)

    def test_template_to_host_with_no_pxe_hwm(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test',
                         'cluster_name': "11", 'host_id': "123"}
        hwm_host_detail['discover_mode'] = ''
        self.get_host_meta_or_404 = mock.Mock(return_value=hwm_host_detail)
        registry.get_host_metadata = mock.Mock(return_value=hwm_host_detail)
        registry.host_template_lists_metadata = \
            mock.Mock(return_value=[{'hosts': hwm_host_detail}])
        self.assertRaises(HTTPForbidden,
                          self.controller.template_to_host, req, host_template)

    def test_template_to_host_with_pxe_hwm(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test',
                         'cluster_name': "11", 'host_id': "123"}
        hwm_host_detail['discover_mode'] = 'PXE'
        self.get_host_meta_or_404 = mock.Mock(return_value=hwm_host_detail)
        registry.get_host_metadata = mock.Mock(return_value=hwm_host_detail)
        registry.host_template_lists_metadata =\
            mock.Mock(return_value=[{'hosts': json.dumps([hwm_host_detail])}])
        registry.get_clusters_detail = mock.Mock(return_value=[{'id': '1'}])
        self.controller._judge_ssh_host = mock.Mock(return_value={'2'})
        daisy_cmn.add_ssh_host_to_cluster_and_assigned_network = \
            mock.Mock(return_value={})
        result = self.controller.template_to_host(req, host_template)
        actual = {'host_template': {'cluster_name': '11',
                                    'host_id': '123',
                                    'host_template_name': 'test'}}
        self.assertEqual(actual, result)

    def test_template_to_host_with_ssh(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test',
                         'cluster_name': "11", 'host_id': "123"}
        host_detail['discover_mode'] = 'SSH'
        registry.get_host_metadata = mock.Mock(return_value=host_detail)
        registry.host_template_lists_metadata = mock.Mock(
            return_value=[{'hosts': json.dumps([host_detail])}])
        registry.get_clusters_detail = mock.Mock(return_value=[{'id': '1'}])
        self.controller._judge_ssh_host = mock.Mock(return_value=True)
        daisy_cmn.add_ssh_host_to_cluster_and_assigned_network =\
            mock.Mock(return_value={})
        registry.update_host_metadata = mock.Mock(return_value=host_template)
        result = self.controller.template_to_host(req, host_template)
        actual = {'host_template': {'cluster_name': '11',
                                    'host_id': '123',
                                    'host_template_name': 'test'}}
        self.assertEqual(actual, result)
        self.assertEqual(2, registry.get_host_metadata.call_count)

    def test_delete_host_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test'}
        self.get_host_meta_or_404 = mock.Mock(return_value=host_detail)
        self.assertRaises(HTTPNotFound,
                          self.controller.delete_host_template,
                          req, host_template)

    def test_delete_host_template_with_host_template_null(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test',
                         'cluster_name': "cluster"}
        registry.host_template_lists_metadata = mock.Mock(return_value=[])
        self.assertRaises(
            HTTPNotFound, self.controller.delete_host_template,
            req, host_template)
