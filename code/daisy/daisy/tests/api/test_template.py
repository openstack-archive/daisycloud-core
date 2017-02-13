import mock
import webob
from daisy.context import RequestContext
import daisy.registry.client.v1.api as registry
from daisy import test
from daisy.api.v1 import template
from webob.exc import HTTPForbidden
from webob.exc import HTTPBadRequest


cluster = {u'vlan_end': None,
           u'updated_at': u'2016-07-19T02:16:05.000000',
           u'owner': None,
           u'networking_parameters': {
               u'vni_range': [None, None],
               u'public_vip': u'192.168.1.4',
               u'net_l23_provider': None,
               u'base_mac': u'',
               u'gre_id_range': [None,
                                 None],
               u'vlan_range': [None, None],
               u'segmentation_type': None},
           u'gre_id_start': None,
           u'deleted_at': None,
           u'networks': [
               u'd3d60abf-c8d1-49ec-9731-d500b1ef4acb',
               u'bc99206e-0ac2-4b6e-9cd3-d4cdd11c208e',
               u'8518a8a5-e5fb-41ba-877f-eef386e3376f',
               u'8048a7d7-7b85-4621-837c-adea08acdbbd',
               u'6aacb625-99f2-4a95-b98f-ec0af256eb55',
               u'4ad601b0-19e2-4feb-b41a-6e3af5153e2a'],
           u'hwm_ip': u'1.1.1.2',
           u'id': u'4d3156ba-a4a5-4f41-914c-7a148170f281',
           u'base_mac': u'',
           u'auto_scale': 0,
           u'target_systems': u'os+tecs',
           u'vni_end': None,
           u'gre_id_end': None,
           u'nodes': [
               u'6e3a0ab9-fff6-459b-8bf1-9b6681efbfb0',
               u'd25666c1-651a-4cd7-875a-41a52fddaf6b',
               u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
               u'4b6970c5-ef1d-4599-a1d7-70175a888e6d'],
           u'description': u'',
           u'deleted': False,
           u'routers': [],
           u'logic_networks': [],
           u'net_l23_provider': None,
           u'vlan_start': None,
           u'name': u'test',
           u'created_at': u'2016-07-18T02:34:52.000000',
           u'public_vip': u'192.168.1.4',
           u'use_dns': 1,
           u'vni_start': None,
           u'segmentation_type': None}


return_template = [{'name': 'test',
                    'hosts': None,
                    'content': u'{"cluster":{"description": "",'
                    u'"routers": [],'
                    u'"hwm_ip": "",'
                    u'"logic_networks": [],'
                    u'"auto_scale": 0,'
                    u'"use_dns": 1,'
                    u'"target_systems": "os+tecs",'
                    u'"networking_parameters":'
                    u'{"public_vip": "192.168.2.10",'
                    u'"base_mac": ""},'
                    u'"tecs_version_id": "d48fbec7-8764-4d44-'
                    u'b27a-fba7bbcc57d9"},'
                    u'"networks":[{"ip_ranges": [],'
                    u'"cidr": "10.43.178.1/24",'
                    u'"network_type": "DATAPLANE",'
                    u'"name": "physnet1"},'
                    u'{"ip_ranges": [],'
                    u'"cidr": "192.168.1.1/24",'
                    u'"network_type": "MANAGEMENT",'
                    u'"name": "MANAGEMENT"},'
                    u'{"ip_ranges": [],'
                    u'"cidr": "192.168.2.1/24",'
                    u'"network_type": "PUBLICAPI",'
                    u'"name": "PUBLICAPI"}],'
                    u'"roles":[{"name": "CONTROLLER_HA", '
                    u'"config_set_id": "1"},'
                    u'{"name": "CONTROLLER_LB",'
                    u'"config_set_id": "2"},'
                    u'{"name": "COMPUTER",'
                    u'"config_set_id": "3"}],'
                    u'"cinder_volumes":[],'
                    u'"services_disk":[]}',
                    u'type': u'tecs'}]


networks = [{"name": "physnet1",
             'id': '1'},
            {"name": "MANAGEMENT",
             'id': '2'},
            {"name": "PUBLICAPI",
             'id': '3'}]

roles = [{"name": "CONTROLLER_HA",
          'id': '1'},
         {"name": "CONTROLLER_LB",
          'id': '2'},
         {"name": "COMPUTER",
          'id': '3'}]


class TestTemplate(test.TestCase):

    def setUp(self):
        super(TestTemplate, self).setUp()
        self.controller = template.Controller()

    def test_del_cluster_params(self):
        self.controller._del_cluster_params(cluster)
        self.assertEqual(None, cluster.get('base_mac', None))
        self.assertEqual(None, cluster.get('name', None))
        self.assertEqual(None, cluster.get('networks', None))
        self.assertEqual(None, cluster.get('vlan_start', None))
        self.assertEqual(None, cluster.get('vlan_end', None))
        self.assertEqual(None, cluster.get('vni_start', None))
        self.assertEqual(None, cluster.get('vni_end', None))
        self.assertEqual(None, cluster.get('gre_id_start', None))
        self.assertEqual(None, cluster.get('gre_id_end', None))

    def test_get_template_detail(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template_id = "123"
        registry.template_detail_metadata = mock.Mock(
            return_value={"template_name": "test"})
        template_meta = self.controller.get_template_detail(req, template_id)
        self.assertEqual("test", template_meta['template']['template_name'])

    def test_update_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template_id = "123"
        template = {}
        registry.update_template_metadata = mock.Mock(
            return_value={"template_name": "test"})
        template_meta = self.controller.update_template(
            req, template_id, template)
        self.assertEqual("test", template_meta['template']['template_name'])

    def test_add_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template = {"template_name": "test"}
        registry.add_template_metadata = mock.Mock(
            return_value={"template_name": "test"})
        template_meta = self.controller.add_template(req, template)
        self.assertEqual("test", template_meta['template']['template_name'])

    def test_get_template_lists(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        self.controller._get_query_params = mock.Mock(
            return_value={'filter': {}})
        template = {"template_name": "test"}
        registry.template_lists_metadata = mock.Mock(return_value=[])
        templates = self.controller.get_template_lists(req)
        self.assertEqual([], templates['template'])

    def test_get_services_disk(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        role = {'id': '1', 'name': 'COMPUTER'}
        registry.list_service_disk_metadata = mock.Mock(return_value=[])
        service_disk = self.controller._get_services_disk(req, role)
        self.assertEqual([], service_disk)

    def test_delete_template(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template_id = "123"
        registry.delete_template_metadata = mock.Mock(return_value={""})
        template = self.controller.delete_template(req, template_id)
        self.assertEqual(200, template.status_code)

    def test_export_db_to_json(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template = {'cluster_name': 'cluster1', 'description': 'desc'}
        registry.get_clusters_detail = mock.Mock(return_value={})
        self.assertRaises(
            HTTPForbidden, self.controller.export_db_to_json, req, template)

    @mock.patch('daisy.registry.client.v1.api.'
                'list_optical_switch_metadata')
    def test_get_optical_switchs(self, mock_list_optical_switch):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        role = {'id': '1',
                'name': 'CONTROLLER_HA'}
        optical_switchs = [{'role_id': '1',
                            'created_at': '12:23',
                            'updated_at': '12:23',
                            'deleted': '12:23',
                            'deleted_at': '12:23',
                            'id': '1234'}]
        mock_list_optical_switch.return_value = optical_switchs
        optical_switchs_return = self.controller._get_optical_switchs(req,
                                                                      role)
        self.assertEqual('CONTROLLER_HA', optical_switchs_return[0]['role_id'])

    def test_import_optical_switchs_to_db(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        optical_switchs = [{'role_id': 'CONTROLLER_HA'}]
        roles = [{'id': '2',
                  'name': 'CONTROLLER_LB'}]
        self.assertRaises(HTTPBadRequest,
                          self.controller._import_optical_switchs_to_db,
                          req, optical_switchs, roles)

    @mock.patch('daisy.registry.client.v1.api.update_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.hwm_list_metadata')
    @mock.patch('daisy.registry.client.v1.api.add_service_disk_metadata')
    @mock.patch('daisy.registry.client.v1.api.add_optical_switch_metadata')
    @mock.patch('daisy.registry.client.v1.api.add_cinder_volume_metadata')
    @mock.patch('daisy.registry.client.v1.api.update_role_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_roles_detail')
    @mock.patch('daisy.registry.client.v1.api.update_network_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.add_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_clusters_detail')
    @mock.patch('daisy.registry.client.v1.api.template_lists_metadata')
    def test_import_template_to_db_without_optical_switchs(
            self, mock_get_template, mock_get_cluster, mock_add_cluster,
            mock_get_networks, mock_update_network, mock_get_roles,
            mock_update_role, mock_add_cinder_volume, mock_add_optical_switch,
            mock_add_service_disk, mock_hwm_list, mock_update_cluster_meta):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        template = {'cluster': 'test', 'template_name': 'test'}
        mock_get_template.return_value = return_template
        mock_get_cluster.return_value = []
        mock_add_cluster.return_value = cluster
        mock_get_networks.return_value = networks
        mock_update_network.return_value = []
        mock_get_roles.return_value = roles
        mock_update_role.return_value = []
        mock_add_cinder_volume.return_value = []
        mock_add_optical_switch.return_value = []
        mock_add_service_disk.return_value = []
        mock_hwm_list.return_value = [{'id': 'hwm_id', 'hwm_ip': '1.1.1.2'}, ]
        mock_update_cluster_meta.return_value = []
        self.assertEqual('4d3156ba-a4a5-4f41-914c-7a148170f281',
                         self.controller.
                         import_template_to_db(req, template)
                         ['template']['id'])
