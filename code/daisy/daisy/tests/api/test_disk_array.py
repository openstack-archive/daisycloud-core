import mock
import webob
from oslo.serialization import jsonutils
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
        }]
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
        'id': '77a3eec6-6cf0-4f84-82a4-e9339d824b3a'}
    return cinder_vol_info


class TestDiskArray(test.TestCase):

    def setUp(self):
        super(TestDiskArray, self).setUp()
        self.controller = disk_array.Controller()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True,
                                          user='fake user',
                                          tenant='fake tenamet')

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
        disk_array_1 = {'volume_driver': 'KS3200_IPSAN'}
        backend_index = disk_array.Controller()._get_cinder_volume_backend_index(
            self.req, disk_array_1, cluster_id, cinder_volume_id)
        self.assertEqual(backend_index, 'KS3200_IPSAN-3')

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
        self.controller.cinder_volume_update(self.req,
                                             cinder_volume_id, disk_meta)
        self.assertEqual('FUJITSU_ETERNUS-2', disk_meta['backend_index'])
