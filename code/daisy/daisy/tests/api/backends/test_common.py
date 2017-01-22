import mock
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