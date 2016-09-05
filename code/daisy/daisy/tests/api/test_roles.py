import mock
import webob
from oslo.serialization import jsonutils
from daisy.api.v1 import roles
from daisy import context
from daisy import test


def set_role_meta():
    role_meta = {}
    role_meta["name"] = "test_role"
    role_meta["description"] = "111"
    return role_meta


class TestRolesApiConfig(test.TestCase):

    def setUp(self):
        super(TestRolesApiConfig, self).setUp()
        self.controller = roles.Controller()

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    def test_add_role(self, mock_do_request):
        role_meta = set_role_meta()
        req = webob.Request.blank('/')
        req.context = context.RequestContext(is_admin=True,
                                             user='fake user',
                                             tenant='fake tenamet')

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            cluster_id = 'test-1234-1234-1244'
            if method == "GET":
                get_result = {'roles':
                              [{'cluster_id': None,
                                'name': 'HA',
                                'description': 'nothing'},
                               {'cluster_id': None,
                                  'name': 'LB',
                                'description': 'nothing'},
                               {'cluster_id': cluster_id,
                                  'name': 'test_role',
                                'description': 'nothing'}
                               ]
                              }
                res.read.return_value = jsonutils.dumps(get_result)
                return res
            elif method == 'POST':
                post_result = {'role': {'db_vip': None}}
                res.read.return_value = jsonutils.dumps(post_result)
                return res

        mock_do_request.side_effect = fake_do_request
        add_role = self.controller.add_role(req, role_meta)
        self.assertEqual({'role_meta': {u'db_vip': None}}, add_role)

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    def test_add_role_with_repeated_name(self, mock_do_request):
        role_meta = set_role_meta()
        req = webob.Request.blank('/')
        req.context = context.RequestContext(is_admin=True,
                                             user='fake user',
                                             tenant='fake tenamet')

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            cluster_id = 'test-1234-1234-1244'
            if method == "GET":
                get_result = {'roles':
                              [{'cluster_id': None,
                                'name': 'HA',
                                'description': 'nothing'},
                               {'cluster_id': None,
                                'name': 'test_role',
                                'description': 'nothing'},
                                  {'cluster_id': cluster_id,
                                   'name': 'test_role',
                                   'description': 'nothing'}
                               ]
                              }
                res.read.return_value = jsonutils.dumps(get_result)
                return res
            elif method == 'POST':
                post_result = {'role': {'db_vip': None}}
                res.read.return_value = jsonutils.dumps(post_result)
                return res

        mock_do_request.side_effect = fake_do_request
        # "The role %s has already been in the the template role." % role_name
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller.add_role, req, role_meta)

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    def test_add_template_role_with_cluster_raise_exception(self,
                                                            mock_do_request):
        role_meta = set_role_meta()
        cluster_id = 'test-1234-1234-1244'
        role_meta['cluster_id'] = cluster_id
        role_meta['type'] = 'template'
        req = webob.Request.blank('/')
        req.context = context.RequestContext(is_admin=True,
                                             user='fake user',
                                             tenant='fake tenamet')

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            print 'path', path
            if method == "GET":
                if path == '/clusters/%s' % cluster_id:
                    get_result = {
                        u'vlan_end': None,
                        u'networking_parameters': {
                            u'vni_range': [
                                None,
                                None
                            ],
                            u'public_vip': None,
                            u'net_l23_provider': None,
                            u'base_mac': u'',
                            u'gre_id_range': [
                                None,
                                None
                            ],
                            u'vlan_range': [
                                None,
                                None
                            ],
                            u'segmentation_type': u'vlan'
                        },
                        u'owner': None,
                        u'gre_id_start': None,
                        u'deleted_at': None,
                        u'networks': [],
                        u'id': cluster_id,
                        u'base_mac': u'',
                        u'auto_scale': 0,
                        u'vni_end': None,
                        u'gre_id_end': None,
                        u'nodes': [],
                        u'description': u'',
                        u'deleted': False,
                        u'routers': [],
                        u'logic_networks': [],
                        u'net_l23_provider': None,
                        u'vlan_start': None,
                        u'name': u'testtt',
                        u'public_vip': None,
                        u'use_dns': 1,
                        u'vni_start': None,
                        u'segmentation_type': u'vlan'
                    }
                    res.read.return_value = jsonutils.dumps(get_result)
                    return res
                else:
                    get_result = {'roles':
                                  [{'cluster_id': None,
                                    'name': 'HA',
                                    'description': 'nothing'},
                                   {'cluster_id': None,
                                    'name': 'LB',
                                    'description': 'nothing'},
                                      {'cluster_id': cluster_id,
                                       'name': 'test',
                                       'description': 'nothing'}
                                   ]
                                  }
                    res.read.return_value = jsonutils.dumps(get_result)
                    return res
            elif method == 'POST':
                post_result = {'role': {'db_vip': None}}
                res.read.return_value = jsonutils.dumps(post_result)
                return res

        mock_do_request.side_effect = fake_do_request
        # add_role = self.controller.add_role(req, role_meta)
        # webob.exc.HTTPForbidden:
        # Tht template role cannot be added to any cluster.
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller.add_role, req, role_meta)
