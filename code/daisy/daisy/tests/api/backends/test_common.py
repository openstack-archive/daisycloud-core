import mock
from daisy.api.backends import common
from daisy import test
import webob


class DottableDict(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self

    def allowDotting(self, state=True):
        if state:
            self.__dict__ = self
        else:
            self.__dict__ = dict()


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


class TestCommon(test.TestCase):
    _log_handler = MockLoggingHandler()

    def setUp(self):
        super(TestCommon, self).setUp()
        self._log_handler.reset()
        self._log_messages = self._log_handler.messages

    @mock.patch('logging.Logger.info')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    def test_trust_me(self, mock_do_subprocess_call, mock_log):
        def mock_subprocess_call(*args, **kwargs):
            pass
        ip = ['127.0.0.1']
        passwd = 'ossdbg1'
        mock_do_subprocess_call.side_effect = mock_subprocess_call
        mock_log.side_effect = self._log_handler.info
        common.trust_me(ip, passwd)
        self.assertIn("Setup trust to '127.0.0.1' successfully",
                      self._log_messages['info'])

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

    @mock.patch('daisy.registry.client.v1.api.update_host_metadata')
    def test_update_db_host_status(self, mock_do_update_host):
        def mock_update_host(*args, **kwargs):
            return host_status

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        host_id = '123'
        host_status = {"os_progress": 100, "os_status": "active",
                       "messages": "test"}
        mock_do_update_host.side_effect = mock_update_host
        host_info = common.update_db_host_status(req, host_id, host_status)
        self.assertEqual(100, host_info['os_progress'])
        self.assertEqual("active", host_info['os_status'])
        self.assertEqual("test", host_info['messages'])

    @mock.patch('daisy.registry.client.v1.api.update_host_metadata')
    def test_update_db_host_status_with_progress_is_zero(self,
                                                         mock_do_update_host):
        def mock_update_host(*args, **kwargs):
            return host_status

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        host_id = '123'
        host_status = {"os_progress": 0, "os_status": "init",
                       "messages": "test"}
        mock_do_update_host.side_effect = mock_update_host
        host_info = common.update_db_host_status(req, host_id, host_status)
        self.assertEqual(0, host_info['os_progress'])
        self.assertEqual("init", host_info['os_status'])
        self.assertEqual("test", host_info['messages'])

    @mock.patch('daisy.registry.client.v1.api.update_host_metadata')
    def test_update_db_host_status_with_version_id(self, mock_do_update_host):
        def mock_update_host(*args, **kwargs):
            return host_status

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        host_id = '123'
        version_id = "456"
        host_status = {"os_progress": 100, "os_status": "active",
                       "os_version_id": version_id}
        mock_do_update_host.side_effect = mock_update_host
        host_info = common.update_db_host_status(req, host_id, host_status,
                                                 version_id)
        self.assertEqual("456", host_info['os_version_id'])

    @mock.patch('daisy.registry.client.v1.api.update_host_metadata')
    def test_update_db_host_status_with_tecs_patch_id(self,
                                                      mock_do_update_host):
        def mock_update_host(*args, **kwargs):
            return host_status

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        host_id = '123'
        tecs_patch_id = "456"
        host_status = {"os_progress": 100, "os_status": "active",
                       "tecs_patch_id": tecs_patch_id}
        mock_do_update_host.side_effect = mock_update_host
        host_info = common.update_db_host_status(req, host_id, host_status)
        self.assertEqual("456", host_info['tecs_patch_id'])

    @mock.patch('daisy.registry.client.v1.api.update_host_metadata')
    def test_update_db_host_status_with_os_patch_id(self, mock_do_update_host):
        def mock_update_host(*args, **kwargs):
            return host_status

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        host_id = '123'
        version_patch_id = "456"
        host_status = {"os_progress": 100, "os_status": "active",
                       "version_patch_id": version_patch_id}
        mock_do_update_host.side_effect = mock_update_host
        host_info = common.update_db_host_status(req, host_id, host_status)
        self.assertEqual("456", host_info['version_patch_id'])
