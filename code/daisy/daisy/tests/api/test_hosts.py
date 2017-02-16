import mock
from daisy import test
from daisy.api.v1 import hosts
from daisy.context import RequestContext
import webob


class MockLoggingHandler():

    """Mock logging handler to check for expected logs.

    Messages are available from an instance's ``messages`` dict, in order,
    indexed by a lowercase log level string (e.g., 'debug', 'info', etc.).
    """

    def __init__(self):
        self.messages = {'debug': [], 'info': [], 'warning': [], 'error': []}

    def debug(self, message, *args, **kwargs):
        self.messages['debug'].append(message)

    def info(self, message, *args, **kwargs):
        self.messages['info'].append(message)

    def error(self, message, *args, **kwargs):
        self.messages['error'].append(message)

    def reset(self):
        for message in self.messages:
            del self.messages[message][:]


class TestHostsApiConfig(test.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(TestHostsApiConfig, self).setUp()
        self.controller = hosts.Controller()
        self._log_handler.reset()

    @mock.patch('daisy.registry.client.v1.api.delete_host_metadata')
    @mock.patch('subprocess.call')
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    def test_delete_install_unfinished_host(self, mock_get_host,
                                            mock_call,
                                            mock_delete_host):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def del_mac(cmd, shell, stdout, stderr):
            pass
        host_id = '1'
        mock_get_host.return_value = {'interfaces': [{'mac': '1'}]}
        mock_call.side_effect = del_mac
        mock_delete_host.return_value = {}
        self.controller.delete_host(req, host_id)
        response = self.controller.delete_host(req, host_id)
        self.assertEqual(200, response.status_code)
