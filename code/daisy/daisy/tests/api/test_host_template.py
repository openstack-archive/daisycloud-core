import mock
import json
import webob
from daisy.context import RequestContext
import daisy.registry.client.v1.api as registry
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
               'mongodb_lv_size': '1000',
               'group_list': 'core',
               'disks': {"sda":
                             {"name": "sda",
                              "extra": ["scsi-350000396582a129c",
                                        "wwn-0x50000396582a129c"],
                              "removable": "",
                              "model": "",
                              "disk": "pci-0000:01:00.0-sas-"
                                      "0x50000396582a129e-lun-0",
                              "size": " 600127266816 bytes"},
                         "sdb":
                             {"name": "sdb",
                              "extra": ["scsi-35000039668110618",
                                        "wwn-0x5000039668110618"],
                              "removable": "",
                              "model": "",
                              "disk": "pci-0000:01:00.0-sas-"
                                      "0x500003966811061a-lun-0",
                              "size": " 600127266816 bytes"}
                         },
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
               'memory':
                   {"total": "       264122576 kB",
                    "phy_memory_1":
                        {"maximum_capacity": " 256 GB",
                         "devices_5":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"},
                         "devices_4":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"},
                         "devices_7":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"},
                         "devices_6":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"},
                         "devices_1":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"},
                         "devices_3":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"},
                         "devices_2":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"},
                         "slots": " 8",
                         "devices_8":
                             {"frequency": " 1333 MHz",
                              "type": " DDR3",
                              "size": " 16384 MB"}
                         },
                    }
               }

hwm_host_detail = {'id': '7739d9d9-93ca-480f-bde4-3b4c1052e63a',
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
                   'mongodb_lv_size': '1000',
                   'group_list': 'core',
                   'hwm_id': '111',
                   'hwm_ip': '127.0.0.1'
                   }


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
        host_template_meta = self.controller.get_host_template_detail(
            req, template_id)
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
        host_template = {"host_template_name": "test"}
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
        self.assertRaises(HTTPNotFound, self.controller.template_to_host,
                          req, host_template)

    def test_template_to_host_with_hwm(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test',
                         'cluster_name': "11",
                         'host_id': "123"}
        self.get_host_meta_or_404 = mock.Mock(return_value=hwm_host_detail)
        registry.get_host_metadata = mock.Mock(return_value=hwm_host_detail)
        registry.host_template_lists_metadata = mock.Mock(
            return_value=[{'hosts': json.dumps([host_detail])}])
        self.assertRaises(HTTPForbidden, self.controller.template_to_host,
                          req, host_template)

    def test_delete_host_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test'}
        self.get_host_meta_or_404 = mock.Mock(return_value=host_detail)
        self.assertRaises(HTTPNotFound, self.controller.delete_host_template,
                          req, host_template)

    def test_delete_host_template_with_host_template_null(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test',
                         'cluster_name': "cluster"}
        registry.host_template_lists_metadata = mock.Mock(return_value=[])
        self.assertRaises(HTTPNotFound, self.controller.delete_host_template,
                          req, host_template)
