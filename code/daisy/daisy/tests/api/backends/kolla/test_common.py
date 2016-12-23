import mock
import webob
from webob.exc import HTTPForbidden
from daisy.context import RequestContext
from daisy.api.backends import common
from daisy import test


class DottableDict(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self

    def allowDotting(self, state=True):
        if state:
            self.__dict__ = self
        else:
            self.__dict__ = dict()


class TestCommon(test.TestCase):
    _log_handler = MockLoggingHandler()

    def setUp(self):
        super(TestCommon, self).setUp()

    @mock.patch('daisy.api.backends.tecs.common.if_used_shared_storage')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    def test_check_vlan_nic_and_join_vlan_network_with_invalid_nic_name(
            self, mock_get_host, mock_get_cluster_metadata, mock_use_storage):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '1'
        host_list = ['1']
        networks = [{'network_type': 'DATAPLANE'},
                    {'network_type': 'MANAGEMENT',
                     'cidr': '10.43.178.1/24',
                     'vlan_id': '56',
                     'name': 'management'}]
        return_host_detail = {'name': 'host1',
                              'interfaces': [{'ip': '10.43.178.129',
                                              'type': 'vlan',
                                              'name': 'eth0',
                                              'assigned_networks': []}]}
        mock_get_host.return_value = return_host_detail
        mock_get_cluster_metadata.return_value = {}
        mock_use_storage.return_value = (True, None)
        self.assertRaises(HTTPForbidden,
                          common.check_vlan_nic_and_join_vlan_network,
                          req, cluster_id, host_list, networks)

    @mock.patch('oslo_utils.importutils.import_module')
    @mock.patch('daisy.api.backends.common.get_cluster_roles_detail')
    def test_if_used_shared_storage_with_share(self, mock_get_role,
                                               mock_import_module):
        def get_disk_array_info(*args, **kwargs):
            return ['test'], {}, ()
        obj = DottableDict({'get_disk_array_info': get_disk_array_info})
        mock_get_role.return_value = [{'name': 'CONTROLLER_HA',
                                       'deployment_backend': 'tecs',
                                       'id': '123'}]
        mock_import_module.return_value = obj
        req = webob.Request.blank('/')
        use_share_disk = common.if_used_shared_storage(req, '123')
        self.assertEqual(use_share_disk, True)

    @mock.patch('oslo_utils.importutils.import_module')
    @mock.patch('daisy.api.backends.common.get_cluster_roles_detail')
    def test_if_used_shared_storage_without_share(self, mock_get_role,
                                                  mock_import_module):
        def get_disk_array_info(*args, **kwargs):
            return [], {}, ()
        obj = DottableDict({'get_disk_array_info': get_disk_array_info})
        mock_get_role.return_value = [{'name': 'CONTROLLER_HA',
                                       'deployment_backend': 'tecs',
                                       'id': '123'}]
        mock_import_module.return_value = obj
        req = webob.Request.blank('/')
        use_share_disk = common.if_used_shared_storage(req, '123')
        self.assertEqual(use_share_disk, False)
