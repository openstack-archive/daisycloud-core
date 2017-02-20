import mock
import webob
from daisy.api.v1 import roles
from daisy.context import RequestContext
from daisy import test


def set_neutron_backend_meta():
    neutron_backend_meta = [{
        u'role_id': u'08f8301e-eb2e-4cea-8cba-3753380fd183',
        u'user_name': u'admin',
        u'user_pwd': u'admin',
        u'controller_ip': u'10.43.177.96',
        u'neutron_backends_type': u'sdn',
        u'sdn_type': u'ZENIC',
        u'id': u'3eeeee5b-4ac8-4b19-975c-26d6b32088e5',
        u'port': u'8181',
        u'updated_at': u'2017-01-13T03:07:26.000000',
        u'created_at': u'2017-01-12T03:07:26.000000',
        u'deleted_at': None,
        u'deleted': False}]
    return neutron_backend_meta


class TestNeutronBackendApiConfig(test.TestCase):
    def setUp(self):
        super(TestNeutronBackendApiConfig, self).setUp()
        self.controller = roles.Controller()

    @mock.patch('daisy.registry.client.v1.api.list_neutron_backend_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_role_metadata')
    def test_get_neutron_backend(self, mock_do_get_role,
                                 mock_list_metadata):
        neutron_backend_meta = set_neutron_backend_meta()
        role_id = '08f8301e-eb2e-4cea-8cba-3753380fd183'
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')

        def mock_get_role(*args, **kwargs):
            return {'deleted': 0}

        mock_do_get_role.side_effect = mock_get_role
        mock_list_metadata.return_value = neutron_backend_meta

        config = self.controller.get_role(
            req, role_id)
        self.assertEqual("ZENIC", config['role_meta'][
                         'neutron_backends_array'][0][
                         'neutron_agent_type'])

    @mock.patch('daisy.registry.client.v1.api.list_neutron_backend_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_role_metadata')
    def test_get_neutron_backend_with_wrong_id(self, mock_do_get_role,
                                               mock_list_metadata):
        neutron_backend_meta = set_neutron_backend_meta()
        role_id = 'test-1234-1234'
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')

        def mock_get_role(*args, **kwargs):
            return {'deleted': 0}

        def mock_list_metadata(*args, **kwargs):
            return neutron_backend_meta

        mock_do_get_role.side_effect = mock_get_role
        mock_list_metadata.side_effect = mock_list_metadata

        config = self.controller.get_role(
            req, role_id)
        self.assertEqual(None, config.get('neutron_backend_meta', None))
