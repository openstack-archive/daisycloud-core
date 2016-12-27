import mock
import webob
from daisy import test
from daisy.api.backends.kolla import install
from daisy.context import RequestContext
import subprocess
import daisy.api.backends.common as daisy_cmn
from daisy.api.backends.kolla import api

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

class TestApi(test.TestCase):

    def setUp(self):
        super(TestApi, self).setUp()
        self.api = api.API()
        self.req = webob.Request.blank('/')
    
    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    def test_prepare_ssh_discovered_node(self, mock_subprocess_call, mock_do_check_output):
        mock_do_check_output.return_value = 'trustme ok!' 
        mock_subprocess_call.return_value = ''
        discover_host_meta = {'ip': '127.0.0.1', 'passwd': 'ossdbg1'}
        self.api.prepare_ssh_discovered_node(self.req, 'fp', discover_host_meta) 
