import mock
import webob
from oslo_serialization import jsonutils
from daisy.api.v1 import disk_array
from daisy.context import RequestContext
import daisy.registry.client.v1.api as registry
from daisy import test


def fake_do_request_for_get_roles(method, path, **params):
    res = mock.Mock()
    if method == "GET":
        get_result = {'roles': [{'id': 'role_id_1'},
                                {'id': 'role_id_2'}]}
        res.read.return_value = jsonutils.dumps(get_result)
        return res


def set_cinder_volume_list():
    cinder_vol_lists = [
        {
            'management_ips': '10.43.178.9',
            'data_ips': '10.43.178.19',
            'role_id': 'badb5177-4659-4b40-8e46-856ef5a121e0',
            'volume_type': 'ext4',
            'user_pwd': 'pwd',
            'volume_driver': 'FUJITSU_ETERNUS',
            'root_pwd': 'root',
            'pools': 'pool2,pool3',
            'backend_index': 'FUJITSU_ETERNUS-1',
            'resource_pools': None,
            'user_name': 'user',
            'id': '77a3eec6-6cf0-4f84-82a4-e9339d824b3a'
        },
        {
            'management_ips': '10.43.178.9',
            'data_ips': '10.43.178.19',
            'role_id': 'badb5177-4659-4b40-8e46-856ef5a121e0',
            'volume_type': 'ext4',
            'user_pwd': 'pwd',
            'volume_driver': 'FUJITSU_ETERNUS',
            'root_pwd': 'root',
            'pools': 'pool3,pool4',
            'backend_index': 'FUJITSU_ETERNUS-2',
            'resource_pools': 'resource_pools',
            'user_name': 'user',
            'id': 'a1a726c6-161e-4a79-9b2b-a627d4722417'
        }
    ]
    return cinder_vol_lists


def set_add_cinder_volume_info():
    add_cinder_volume_info = {
        'disk_array': "[{'management_ips': " +
                      "'10.43.178.9', 'data_ips': '10.43.178.19'," +
                      "'user_pwd': 'pwd', 'volume_type': 'ext4'," +
                      "'volume_driver': 'FUJITSU_ETERNUS', " +
                      "'root_pwd': 'root', 'pools': 'pool2,pool4'," +
                      "'resource_pools': 'resource_pools', " +
                      "'user_name': 'user'}]",
        'role_id': 'badb5177-4659-4b40-8e46-856ef5a121e0'}
    return add_cinder_volume_info


def returned_cinder_vol_info():
    cinder_vol_info = {
        'management_ips': '10.43.178.9',
        'data_ips': '10.43.178.19',
        'deleted': False,
        'role_id': 'badb5177-4659-4b40-8e46-856ef5a121e0',
        'volume_type': 'ext4',
        'user_pwd': 'pwd',
        'volume_driver': 'FUJITSU_ETERNUS',
        'root_pwd': 'root',
        'pools': 'pool2,pool4',
        'backend_index': 'FUJITSU_ETERNUS-1',
        'resource_pools': 'resource_pools',
        'user_name': 'user',
        'id': '77a3eec6-6cf0-4f84-82a4-e9339d824b3a'
    }
    return cinder_vol_info


class TestDiskArray(test.TestCase):

    def setUp(self):
        super(TestDiskArray, self).setUp()
        self.controller = disk_array.Controller()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True,
                                          user='fake user',
                                          tenant='fake tenamet')

    @mock.patch('daisy.registry.client.v1.client.'
                'RegistryClient.do_request')
    def test__get_cluster_roles(self, mock_do_request):
        cluster_id = "cluster_id_123"
        mock_do_request.side_effect = fake_do_request_for_get_roles
        cluster_roles = self.controller._get_cluster_roles(
            self.req, cluster_id)
        expect_roles_id = ['role_id_1', 'role_id_2']
        for role in cluster_roles:
            self.assertIn(role['id'], expect_roles_id)

    def test__get_cinder_volume_backend_index(self):
        cluster_id = "cluster_id_123"
        roles = [{'id': 'role_id_1'},
                 {'id': 'role_id_2'}]
        cinder_volume_id = '3'
        self.controller._get_cluster_roles =\
            mock.Mock(return_value=roles)
        cinder_volumes = [{'backend_index': 'KS3200_IPSAN-1',
                           'id': '1'},
                          {'backend_index': 'KS3200_IPSAN-2',
                           'id': '2'}]
        self.controller._cinder_volume_list =\
            mock.Mock(return_value=cinder_volumes)
        disk_array = {'volume_driver': 'KS3200_IPSAN'}
        backend_index = self.controller._get_cinder_volume_backend_index(
            self.req, disk_array, cluster_id, cinder_volume_id)
        self.assertEqual(backend_index, 'KS3200_IPSAN-3')

    @mock.patch('daisy.registry.client.v1.api.'
                'add_cinder_volume_metadata')
    def test_cinder_volume_add(self, mock_add_cinder_volume_metadata):
        self.controller._enforce =\
            mock.Mock(return_value=None)
        role_id = 'role_id_1'
        role_detail = {'id': role_id, 'cluster_id': 'cluster_id_123'}
        self.controller.get_role_meta_or_404 =\
            mock.Mock(return_value=role_detail)
        backend_index = 'KS3200_IPSAN-3'
        self.controller._get_cinder_volume_backend_index =\
            mock.Mock(return_value=backend_index)
        disk_array_meta = {'volume_driver': 'KS3200_IPSAN',
                           'data_ips': '1.1.1.1'}
        disk_meta = {
            'role_id': role_id, 'disk_array': unicode([disk_array_meta])}
        self.controller.cinder_volume_add(self.req, disk_meta)
        disk_array_meta['backend_index'] = backend_index
        disk_array_meta['role_id'] = role_id
        mock_add_cinder_volume_metadata.assert_called_once_with(
            self.req.context, disk_array_meta)

    @mock.patch('daisy.registry.client.v1.api.get_role_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'update_cinder_volume_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_cinder_volume_detail_metadata')
    def test_cinder_volume_update(self,
                                  mock_get_cinder_volume,
                                  mock_update_cinder_volume_metadata,
                                  mock_get_role):
        cinder_volume_id = '1'
        mock_get_cinder_volume.return_value = \
            {'id': '1',
             'management_ips': ['10.4.5.7'],
             'volume_driver': 'FUJITSU_ETERNUS',
             'root_pwd': 'aaaa',
             'data_ips': ['19.4.5.7'],
             'role_id': '1'}
        mock_get_role.return_value = {'cluster_id': '1'}
        disk_meta = {
            'management_ips': ['10.5.6.7'],
            'data_ips': ['13.5.8.9'],
            'root_pwd': 'bbbb'
        }
        mock_update_cinder_volume_metadata.return_value = \
            {'id': '1',
             'management_ips': ['10.5.6.7'],
             'volume_driver': 'FUJITSU_ETERNUS',
             'root_pwd': 'bbbb',
             'data_ips': ['13.5.8.9']}
        cinder_volume = self.controller.cinder_volume_update(
            self.req, cinder_volume_id, disk_meta)
        self.assertEqual('bbbb',
                         cinder_volume['disk_meta']['root_pwd'])

    def test_cinder_volume_add_with_resource_pool(self):
        role_detail = {'cluster_id': '0000-1111'}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_detail)

        backend_index = 'FUJITSU_ETERNUS-1'
        self.controller._get_cinder_volume_backend_index = \
            mock.Mock(return_value=backend_index)

        cinder_volume_lists = set_cinder_volume_list()
        registry.list_cinder_volume_metadata = \
            mock.Mock(return_value=cinder_volume_lists)
        cinder_vol_info = returned_cinder_vol_info()
        registry.add_cinder_volume_metadata = \
            mock.Mock(return_value=cinder_vol_info)

        add_info = set_add_cinder_volume_info()
        return_info = self.controller.cinder_volume_add(self.req, add_info)

        add_cinder_vol_info = eval(add_info['disk_array'])
        print add_cinder_vol_info
        self.assertEqual(add_cinder_vol_info[0]['root_pwd'],
                         return_info['disk_meta']['root_pwd'])
        self.assertEqual(add_cinder_vol_info[0]['resource_pools'],
                         return_info['disk_meta']['resource_pools'])

    def test_cinder_volume_update_without_role_id(self):
        add_info = set_add_cinder_volume_info()
        del add_info['role_id']
        cinder_vol_id = '77a3eec6-6cf0-4f84-82a4-e9339d824b3a'
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.cinder_volume_update,
                          self.req,
                          cinder_vol_id,
                          add_info)
        # self.assertRaisesRegexp will match the exception msg
        msg = "must be given"
        self.assertRaisesRegexp(webob.exc.HTTPBadRequest,
                                msg,
                                self.controller.cinder_volume_update,
                                self.req,
                                cinder_vol_id,
                                add_info)

    def test_cinder_volume_add_with_invalid_key(self):
        add_info = set_add_cinder_volume_info()
        add_info['disk_array'] = \
            "[{'management_ips': " + \
            "'10.43.178.9', 'data_ips': '10.43.178.19'," + \
            "'user_pwd': 'pwd', 'volume_type': 'ext4'," + \
            "'volume_driver': 'FUJITSU_ETERNUS', " + \
            "'root_pwd': 'root', 'invalid_key': 'pool2,pool4'," + \
            "'resource_pools': 'resource_pools', " + \
            "'user_name': 'user'}]"
        role_detail = {'cluster_id': '0000-1111'}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_detail)

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.cinder_volume_add,
                          self.req,
                          add_info)

        msg = "'invalid_key' must be given for cinder volume config"
        self.assertRaisesRegexp(webob.exc.HTTPBadRequest,
                                msg,
                                self.controller.cinder_volume_add,
                                self.req,
                                add_info)

    def test_cinder_volume_add_with_invalid_volume_driver(self):
        add_info = set_add_cinder_volume_info()
        add_info['disk_array'] = \
            "[{'management_ips': " + \
            "'10.43.178.9', 'data_ips': '10.43.178.19'," + \
            "'user_pwd': 'pwd', 'volume_type': 'ext4'," + \
            "'volume_driver': 'FUJITSU_ETERNUS-2', " + \
            "'root_pwd': 'root', 'pools': 'pool2,pool4'," + \
            "'resource_pools': 'resource,pools', " + \
            "'user_name': 'user'}]"

        role_detail = {'cluster_id': '0000-1111'}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_detail)

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.cinder_volume_add,
                          self.req,
                          add_info)

        msg = "volume_driver FUJITSU_ETERNUS-2 is not supported"
        self.assertRaisesRegexp(webob.exc.HTTPBadRequest,
                                msg,
                                self.controller.cinder_volume_add,
                                self.req,
                                add_info)

    def test_cinder_volume_add_without_root_pwd(self):
        role_detail = {'cluster_id': '0000-1111'}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_detail)
        add_info = {}
        add_info['role_id'] = 'badb5177-4659-4b40-8e46-856ef5a121e0'
        add_info['disk_array'] = \
            "[{'management_ips': " + \
            "'10.43.178.9', 'data_ips': '10.43.178.19'," + \
            "'user_pwd': 'pwd', 'volume_type': 'ext4'," + \
            "'volume_driver': 'FUJITSU_ETERNUS', " + \
            "'pools': 'pool1,pool4'," + \
            "'resource_pools': 'resource_pools', " + \
            "'user_name': 'user'}]"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.cinder_volume_add,
                          self.req,
                          add_info)

        msg = "root_pwd must be given when using FUJITSU Disk Array"
        self.assertRaisesRegexp(webob.exc.HTTPBadRequest,
                                msg,
                                self.controller.cinder_volume_add,
                                self.req,
                                add_info)

    def test_cinder_volume_add_with_root_pwd(self):
        role_detail = {'cluster_id': '0000-1111'}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_detail)
        cinder_vol_info = returned_cinder_vol_info()
        add_info = {}
        add_info['role_id'] = 'badb5177-4659-4b40-8e46-856ef5a121e0'
        add_info['disk_array'] = \
            "[{'management_ips': " + \
            "'10.43.178.9', 'data_ips': '10.43.178.19'," + \
            "'user_pwd': 'pwd', 'volume_type': 'ext4'," + \
            "'volume_driver': 'FUJITSU_ETERNUS', " + \
            "'pools': 'pool1,pool4', 'root_pwd': 'root'," + \
            "'resource_pools': 'resource_pools', " + \
            "'user_name': 'user'}]"
        cinder_vol_info['root_pwd'] = 'root'
        backend_index = 'FUJITSU_ETERNUS-1'
        self.controller._get_cinder_volume_backend_index = \
            mock.Mock(return_value=backend_index)
        registry.add_cinder_volume_metadata = \
            mock.Mock(return_value=cinder_vol_info)
        return_info = self.controller.cinder_volume_add(self.req, add_info)

        self.assertEqual('root', return_info['disk_meta']['root_pwd'])

    def test_cinder_volume_add_with_multi_resource_pools(self):
        role_detail = {'cluster_id': '0000-1111'}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_detail)
        add_info = {}
        add_info['role_id'] = 'badb5177-4659-4b40-8e46-856ef5a121e0'
        add_info['disk_array'] = \
            "[{'management_ips': " + \
            "'10.43.178.9', 'data_ips': '10.43.178.19'," + \
            "'user_pwd': 'pwd', 'volume_type': 'ext4'," + \
            "'volume_driver': 'FUJITSU_ETERNUS', " + \
            "'pools': 'pool1,pool4', 'root_pwd': 'root', " + \
            "'resource_pools': 'resource,pools', " + \
            "'user_name': 'user'}]"

        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.cinder_volume_add,
                          self.req,
                          add_info)

        msg = "Only one resource pool can be specified."
        self.assertRaisesRegexp(webob.exc.HTTPBadRequest,
                                msg,
                                self.controller.cinder_volume_add,
                                self.req,
                                add_info)

    @mock.patch('daisy.registry.client.v1.api.get_role_metadata')
    def test_cinder_volume_update_with_resource_pools(self, mock_get_role):
        cinder_volume_lists = set_cinder_volume_list()
        registry.list_cinder_volume_metadata = \
            mock.Mock(return_value=cinder_volume_lists)
        cinder_vol_info = returned_cinder_vol_info()
        self.controller.get_cinder_volume_meta_or_404 = \
            mock.Mock(return_value=cinder_vol_info)
        mock_get_role.return_value = {'cluster_id': '1'}
        disk_meta = {'resource_pools': 'pool3,pool4', 'root_pwd': 'root3'}
        cinder_vol_info['resource_pools'] = disk_meta['resource_pools']
        cinder_vol_info['root_pwd'] = disk_meta['root_pwd']
        registry.update_cinder_volume_metadata = \
            mock.Mock(return_value=cinder_vol_info)

        cinder_vol_id = '77a3eec6-6cf0-4f84-82a4-e9339d824b3a'
        return_info = self.controller.cinder_volume_update(self.req,
                                                           cinder_vol_id,
                                                           disk_meta)
        self.assertEqual('root3',
                         return_info['disk_meta']['root_pwd'])
        self.assertEqual('pool3,pool4',
                         return_info['disk_meta']['resource_pools'])

    def test_optical_switch_add(self):
        role_info = {'id': '1'}
        optical_switchs = {'fc_driver': 'brocade',
                           'switch_ip': '10.3.4.5',
                           'switch_port': '22',
                           'user_name': 'root',
                           'user_pwd': 'ossdbg1',
                           'fc_zoneing_policy': 'initiator'}
        optical_switch_meta = {'role_id': '1',
                               'switch_array':
                                   "[{'fc_driver': 'brocade',"
                                   "'switch_ip': '10.3.4.5',"
                                   " 'switch_port': '22',"
                                   " 'user_name': 'root',"
                                   "'user_pwd': 'ossdbg1',"
                                   "'fc_zoneing_policy': 'initiator'}]"}
        self.controller.get_role_meta_or_404 \
            = mock.Mock(return_value=role_info)
        registry.add_optical_switch_metadata \
            = mock.Mock(return_value=optical_switchs)
        optical_switch_info \
            = self.controller.optical_switch_add(self.req, optical_switch_meta)
        self.assertEqual({'disk_meta': optical_switchs}, optical_switch_info)

    def test_optical_switch_add_with_no_role_id(self):
        optical_switch_meta = {'switch_array':
                               "[{'fc_driver': 'brocade',"
                               "'switch_ip': '10.3.4.5',"
                               " 'switch_port': '22',"
                               " 'user_name': 'root',"
                               "'user_pwd': 'ossdbg1',"
                               "'fc_zoneing_policy': 'initiator'}]"}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.optical_switch_add,
                          self.req, optical_switch_meta)

    def test_optical_switch_add_with_error_param(self):
        role_info = {'id': '1'}
        optical_switch_meta = {'role_id': '1',
                               'switch_array':
                                   "[{'fc': 'brocade',"
                                   "'switch_ip': '10.3.4.5',"
                                   " 'switch_port': '22',"
                                   " 'user_name': 'root',"
                                   "'user_pwd': 'ossdbg1',"
                                   "'fc_zoneing_policy': 'initiator'}]"}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_info)
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.optical_switch_add,
                          self.req, optical_switch_meta)

    def test_optical_switch_add_with_no_support_fc_driver(self):
        role_info = {'id': '1'}
        optical_switch_meta = {'role_id': '1',
                               'switch_array':
                                   "[{'fc_driver': 'bro',"
                                   "'switch_ip': '10.3.4.5',"
                                   " 'switch_port': '22',"
                                   " 'user_name': 'root',"
                                   "'user_pwd': 'ossdbg1',"
                                   "'fc_zoneing_policy': 'initiator'}]"}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_info)
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.optical_switch_add,
                          self.req, optical_switch_meta)

    def test_optical_switch_add_with_no_support_fc_zoneing_policy(self):
        role_info = {'id': '1'}
        optical_switch_meta = {'role_id': '1',
                               'switch_array':
                                   "[{'fc_driver': 'brocade',"
                                   "'switch_ip': '10.3.4.5',"
                                   " 'switch_port': '22',"
                                   " 'user_name': 'root',"
                                   "'user_pwd': 'ossdbg1',"
                                   "'fc_zoneing_policy': 'initi'}]"}
        self.controller.get_role_meta_or_404 = \
            mock.Mock(return_value=role_info)
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.optical_switch_add,
                          self.req, optical_switch_meta)

    def test_optical_switch_update(self):
        role_info = {'id': 1}
        optical_switch_id = '1'
        optical_switch_meta_update = {
            'fc_driver': 'cisco',
            'fc_zoneing_policy': 'initiator-target'
        }
        optical_switchs = {'fc_driver': 'brocade',
                           'switch_ip': '10.3.4.5',
                           'switch_port': '22',
                           'user_name': 'root',
                           'user_pwd': 'ossdbg1',
                           'fc_zoneing_policy': 'initiator'}
        optical_switch_return = {'fc_driver': 'cisco',
                                 'switch_ip': '10.3.4.5',
                                 'switch_port': '22',
                                 'user_name': 'root',
                                 'user_pwd': 'ossdbg1',
                                 'fc_zoneing_policy': 'initiator-target'}

        self.controller.get_role_meta_or_404 \
            = mock.Mock(return_value=role_info)
        self.controller.get_optical_switch_meta_or_404 = \
            mock.Mock(return_value=optical_switchs)
        registry.update_optical_switch_metadata = \
            mock.Mock(return_value=optical_switch_return)
        optical_switch_update =\
            self.controller.optical_switch_update(self.req,
                                                  optical_switch_id,
                                                  optical_switch_meta_update)
        self.assertEqual('cisco',
                         optical_switch_update['disk_meta']['fc_driver'])
        self.assertEqual('initiator-target',
                         optical_switch_update[
                             'disk_meta']['fc_zoneing_policy'])

    def test_optical_switch_update_with_err_param(self):
        optical_switch_id = '1'
        optical_switch_meta_update = {'fc_aaa': 'cisco',
                                      'fc_zoneing_policy':
                                          'initiator-target'}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.optical_switch_update,
                          self.req, optical_switch_id,
                          optical_switch_meta_update)

    def test_optical_switch_update_with_no_support_fc_driver(self):
        optical_switch_id = '1'
        optical_switch_meta_update = {'fc_driver': 'sico',
                                      'fc_zoneing_policy':
                                          'initiator-target'}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.optical_switch_update,
                          self.req, optical_switch_id,
                          optical_switch_meta_update)

    def test_optical_switch_update_with_no_support_fc_zoneing_policy(self):
        optical_switch_id = '1'
        optical_switch_meta_update = {'fc_driver': 'cisco',
                                      'fc_zoneing_policy':
                                          'initiator-tar'}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.optical_switch_update,
                          self.req, optical_switch_id,
                          optical_switch_meta_update)

    @mock.patch('daisy.registry.client.v1.api.'
                'update_cinder_volume_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'list_cinder_volume_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_roles_detail')
    @mock.patch('daisy.registry.client.v1.api.get_role_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_cinder_volume_detail_metadata')
    def test_update_cinder_volume_with_same_volume_driver(
            self, mock_get_cinder_volume, mock_get_role, mock_get_roles,
            mock_get_cinder_volumes, mock_update_cinder_volume):
        cinder_volume_id = '1'
        disk_meta = {
            'volume_driver': 'FUJITSU_ETERNUS',
            'root_pwd': 'aaaaaaa',
            'data_ips': ['192.168.1.2']
        }
        mock_get_cinder_volume.return_value = {
            'role_id': '1', 'volume_driver': 'FUJITSU_ETERNUS',
            'data_ips': ['192.1.3.4']}
        mock_get_role.return_value = {'cluster_id': '1'}
        mock_get_roles.return_value = [{'id': '1'}]
        mock_get_cinder_volumes.return_value = [
            {'id': '1', 'backend_index': 'FUJITSU_ETERNUS-1'}]
        mock_update_cinder_volume.return_value = {}
        self.controller.cinder_volume_update(self.req, cinder_volume_id,
                                             disk_meta)
        self.assertEqual('FUJITSU_ETERNUS-1', disk_meta['backend_index'])

    @mock.patch('daisy.registry.client.v1.api.'
                'update_cinder_volume_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'list_cinder_volume_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_roles_detail')
    @mock.patch('daisy.registry.client.v1.api.get_role_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_cinder_volume_detail_metadata')
    def test_update_cinder_volume_with_another_volume_driver(
            self, mock_get_cinder_volume, mock_get_role, mock_get_roles,
            mock_get_cinder_volumes, mock_update_cinder_volume):
        cinder_volume_id = '2'
        disk_meta = {
            'volume_driver': 'FUJITSU_ETERNUS',
            'root_pwd': 'aaaaaaa',
            'data_ips': ['192.168.1.2']
        }
        mock_get_cinder_volume.return_value = {
            'role_id': '1', 'volume_driver': 'NETAPP_FCSAN',
            'data_ips': ''}
        mock_get_role.return_value = {'cluster_id': '1'}
        mock_get_roles.return_value = [{'id': '1'}]
        mock_get_cinder_volumes.return_value = [
            {'id': '1', 'backend_index': 'FUJITSU_ETERNUS-1'},
            {'id': '2', 'backend_index': 'NETAPP_FCSAN-1'}]
        mock_update_cinder_volume.return_value = {}
        self.controller.cinder_volume_update(self.req, cinder_volume_id,
                                             disk_meta)
        self.assertEqual('FUJITSU_ETERNUS-2', disk_meta['backend_index'])
