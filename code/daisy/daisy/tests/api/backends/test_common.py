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
        mock_get_roles.return_value = [{'id': '1'}]
        mock_get_role_host.return_value = [{'host_id': '1'}]
        common.set_role_status_and_progress(req, cluster_id, opera, status,
                                            backend_name, host_id)
        self.assertFalse(mock_update_role_host.called)
