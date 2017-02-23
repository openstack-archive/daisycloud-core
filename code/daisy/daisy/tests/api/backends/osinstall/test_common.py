import mock
from daisy.api.backends.osinstall import common
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

    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    def test_get_used_networks(self, mock_do_get_networks_detail,
                               mock_do_get_cluster_metadata):

        def mock_get_networks_detail(*args, **kwargs):
            return [{"name": 'MANAGEMENT', 'network_type': 'MANAGEMENT'}]

        def mock_get_cluster_metadata(*args, **kwargs):
            return {'id': '1', 'name': 'cluster1', 'target_systems': 'os'}

        mock_do_get_networks_detail.side_effect = mock_get_networks_detail
        mock_do_get_cluster_metadata.side_effect = mock_get_cluster_metadata

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '1'
        used_networks = common.get_used_networks(req, cluster_id)
        self.assertEqual(
            [{"name": 'MANAGEMENT', 'network_type': 'MANAGEMENT'}],
            used_networks)
