import mock
import json
import webob
from daisy.context import RequestContext
# import daisy.registry.client.v1.api as registry
from daisy import test
from daisy.api.v1 import host_template
# from webob.exc import HTTPNotFound
# from webob.exc import HTTPForbidden


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
               'root_disk': 'sda',
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

    @mock.patch("daisy.api.v1.controller.BaseController."
                "get_host_meta_or_404")
    @mock.patch("daisy.registry.client.v1.api.get_host_metadata")
    @mock.patch("daisy.registry.client.v1.api.host_template_lists_metadata")
    @mock.patch("daisy.registry.client.v1.api.get_clusters_detail")
    @mock.patch("daisy.api.v1.host_template.Controller._judge_ssh_host")
    @mock.patch("daisy.registry.client.v1.api.update_host_metadata")
    def test_template_to_host(self, mock_do_update_host_metadata,
                              mock_do_judge_ssh_host,
                              mock_do_get_clusters_detail,
                              mock_do_host_template_list,
                              mock_do_get_host_meta,
                              mock_do_get_host_meta_or_404):

        def mock_get_host_meta_or_404(*args, **kwargs):
            return host_detail

        def mock_get_host_meta(*args, **kwargs):
            return host_detail

        def mock_host_template_lists(*args, **kwargs):
            return [{'hosts': json.dumps([host_detail])}]

        def mock_get_clusters_detail(*args, **kwargs):
            return [{
                "id": "93ca3165-1a82-4c4a-914f-65279827e46e",
                "name": "test"}]

        def mock_judge_ssh_host(*args, **kwargs):
            return False

        def mock_update_host_metadata(*args, **kwargs):
            return host_detail

        mock_do_update_host_metadata.side_effect = mock_update_host_metadata
        mock_do_judge_ssh_host.side_effect = mock_judge_ssh_host
        mock_do_get_clusters_detail.side_effect = mock_get_clusters_detail
        mock_do_host_template_list.side_effect = mock_host_template_lists
        mock_do_get_host_meta.side_effect = mock_get_host_meta
        mock_do_get_host_meta_or_404.side_effect = mock_get_host_meta_or_404

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_template = {'host_template_name': 'test',
                         'cluster_name': "11",
                         'host_id': "123"}
        ret = self.controller.template_to_host(req, host_template)
        actual = {
            'host_template': host_detail}
        self.assertEqual(actual, ret)