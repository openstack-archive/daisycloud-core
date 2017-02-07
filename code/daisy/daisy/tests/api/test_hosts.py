import mock
from daisy import test
from daisy.api.v1 import hosts
from daisy.context import RequestContext
import webob


def set_host_meta():
    host_meta = {}
    host_meta['id'] = 'd04cfa48-c3ad-477c-b2ac-95bee7582181'
    return host_meta


def set_orig_host_meta():
    orig_host_meta = {}
    orig_host_meta['id'] = 'd04cfa48-c3ad-477c-b2ac-95bee7582181'
    return orig_host_meta


def set_discover_hosts_meta():

    fake_discover_hosts = \
        [{u'status': u'DISCOVERY_SUCCESSFUL',
          u'deleted': False,
          u'ip': u'10.43.203.132',
          u'created_at': u'2016-07-19T02:27:55.000000',
          u'updated_at': u'2016-07-19T02:28:18.000000',
          u'passwd': u'ossdbg1',
          u'mac': u'3c:da:2a:e3:23:47',
          u'cluster_id': None,
          u'user': u'root',
          u'host_id': u'f1367d9d-97f1-4d61-968c-07e6a25fb5ee',
          u'message': u'discover host for 10.43.203.132 successfully!',
          u'deleted_at': None,
          u'id': u'70a4a673-af06-4286-82b0-68a5af4dedc1'}]
    return fake_discover_hosts


def check_result(host_meta, discover_state):
    host_meta['discover_state'] = discover_state
    return host_meta


class MockLoggingHandler():

    """Mock logging handler to check for expected logs.

    Messages are available from an instance's ``messages`` dict, in order,
    indexed by a lowercase log level string (e.g., 'debug', 'info', etc.).
    """

    def __init__(self):
        self.messages = {'debug': [], 'info': [],
                         'warning': [], 'error': []}

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
        self.host_meta = {'id': '1',
                          'check_item': 'ipmi'}
        self._log_handler.reset()

    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_host_check_ipmi_with_hwm_discovered_host(self,
                                                      mock_get_host,
                                                      mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host = {'hwm_id': '1',
                'id': '1',
                'name': 'host_1'}
        mock_get_host.return_value = host
        mock_log.side_effect = self._log_handler
        self.assertEqual({
            'check_result': {
                'ipmi_check_result':
                    'host discovered by hwm do not need ipmi check'}},
            self.controller.host_check(req, self.host_meta))

    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_host_check_ipmi_with_active_host(self, mock_get_host, mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host = {'os_status': 'active',
                'id': '1',
                'name': 'host_1'}
        mock_get_host.return_value = host
        mock_log.side_effect = self._log_handler
        self.assertEqual({
            'check_result': {
                'ipmi_check_result':
                    'active host do not need ipmi check'}},
            self.controller.host_check(req, self.host_meta))

    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_host_check_ipmi_with_no_ipmi_addr(self, mock_get_host, mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host = {'id': '1',
                'name': 'test',
                'os_status': 'init',
                'ipmi_addr': None,
                'ipmi_user': 'zteroot',
                'ipmi_passwd': 'superuser'}
        mock_get_host.return_value = host
        mock_log.side_effect = self._log_handler
        self.assertEqual({
            'check_result': {
                'ipmi_check_result': "No ipmi address configed for "
                                     "host 1, please check"}},
                         self.controller.host_check(req, self.host_meta))

    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_host_check_ipmi_with_no_ipmi_user(self, mock_get_host, mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host = {'id': '1',
                'name': 'test',
                'os_status': 'init',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': None,
                'ipmi_passwd': 'superuser'}
        mock_get_host.return_value = host
        mock_log.side_effect = self._log_handler
        self.assertEqual({
            'check_result': {
                'ipmi_check_result': "No ipmi user configed for host "
                                     "1, please check"}},
                         self.controller.host_check(req, self.host_meta))

    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    @mock.patch('subprocess.Popen.communicate')
    def test_host_check_ipmi_with_no_ipmi_passwd(self,
                                                 mock_communicate,
                                                 mock_get_host,
                                                 mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host = {'id': '1',
                'name': 'test',
                'os_status': 'init',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': 'zteroot',
                'ipmi_passwd': None}
        mock_get_host.return_value = host
        mock_log.side_effect = self._log_handler
        mock_communicate.return_value = \
            ('', 'Unable to get Chassis Power Status')
        self.assertEqual({
            'check_result': {
                'ipmi_check_result': 'ipmi check failed'}},
            self.controller.host_check(req, self.host_meta))

    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    @mock.patch('subprocess.Popen.communicate')
    def test_host_check_ipmi_with_correct_ipmi_parameters(self,
                                                          mock_communicate,
                                                          mock_get_host,
                                                          mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host = {'id': '1',
                'name': 'host_1',
                'os_status': 'init',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': 'zteroot',
                'ipmi_passwd': 'superuser'}
        mock_get_host.return_value = host
        mock_log.side_effect = self._log_handler
        mock_communicate.return_value = ('Chassis Power is on', '')
        self.assertEqual({
            'check_result': {
                'ipmi_check_result': 'ipmi check successfully'}},
            self.controller.host_check(req, self.host_meta))

    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    @mock.patch('subprocess.Popen.communicate')
    def test_host_check_ipmi_with_error_ipmi_parameters(self,
                                                        mock_communicate,
                                                        mock_get_host,
                                                        mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host = {'id': '1',
                'os_status': 'init',
                'name': 'host_1',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': 'zteroot',
                'ipmi_passwd': 'superuser'}
        mock_get_host.return_value = host
        mock_log.side_effect = self._log_handler
        mock_communicate.return_value = \
            ('', 'Unable to get Chassis Power Status')
        self.assertEqual({
            'check_result': {
                'ipmi_check_result': 'ipmi check failed'}},
            self.controller.host_check(req, self.host_meta))
