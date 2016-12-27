import mock
import webob
from webob.exc import HTTPForbidden
from daisy.context import RequestContext
from daisy.api.backends import common
from daisy import test


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
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    def test_check_vlan_nic_and_join_vlan_network_with_invalid_nic_name(
            self, mock_get_host, mock_get_cluster_metadata):
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
        self.assertRaises(HTTPForbidden,
                          common.check_vlan_nic_and_join_vlan_network,
                          req, cluster_id, host_list, networks)
   
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
        self.assertIn('Setup trust', self._log_messages['info'])
