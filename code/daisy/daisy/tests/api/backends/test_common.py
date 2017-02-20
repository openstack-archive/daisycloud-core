import mock
from daisy.api.backends import common
from daisy import test
import webob
from daisy.context import RequestContext


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

    @mock.patch('daisy.registry.client.v1.api.'
                'update_role_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_role_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_roles_detail')
    def test_set_role_status_and_progress_with_host_id(
            self, mock_get_roles, mock_get_role_host, mock_update_role_host):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        host_id = '2'
        cluster_id = '1'
        opera = 'install'
        status = {}
        backend_name = 'tecs'
        mock_get_roles.return_value = [{'id': '1',
                                        'deployment_backend': 'tecs'}]
        mock_get_role_host.return_value = [{'host_id': '1'}]
        common.set_role_status_and_progress(req, cluster_id, opera, status,
                                            backend_name, host_id)
        self.assertFalse(mock_update_role_host.called)

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
    def test_update_db_host_status_with_progress_is_zero(self, mock_do_update_host):
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
    def test_update_db_host_status_with_tecs_patch_id(self, mock_do_update_host):
        def mock_update_host(*args, **kwargs):
            return host_status

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        host_id = '123'
        tecs_patch_id= "456"
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
