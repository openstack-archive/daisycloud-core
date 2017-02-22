import mock
import webob
import subprocess
from daisy import test
from daisy.context import RequestContext
from daisy.api.v1 import backup_restore


class TestBackupRestore(test.TestCase):

    def setUp(self):
        super(TestBackupRestore, self).setUp()
        self.controller = backup_restore.Controller()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True,
                                          user='fake user',
                                          tenant='fake tenant')

    @mock.patch('subprocess.check_output')
    @mock.patch("daisy.api.v1.backup_restore.Controller.check_file_format")
    def test_restore(self, mock_do_check_file_format,
                     mock_do_check_output):
        def mock_check_output(*args, **kwargs):
            pass

        def mock_check_file_format(*args, **kwargs):
            return True

        file_meta = {
            "backup_file_path": "/home/test.tar.gz"}
        mock_do_check_output.side_effect = mock_check_output
        mock_do_check_file_format.side_effect = mock_check_file_format
        result = self.controller.restore(self.req, file_meta)
        self.assertEqual(None, result)

    @mock.patch('subprocess.check_output')
    @mock.patch("daisy.api.v1.backup_restore.Controller.check_file_format")
    def test_restore_call_process_error(self, mock_do_check_file_format,
                                        mock_do_check_output):

        def mock_check_output(*args, **kwargs):
            e = subprocess.CalledProcessError(0, 'test')
            e.output = 'test error'
            raise e

        def mock_check_file_format(*args, **kwargs):
            return True

        file_meta = {
            "backup_file_path": "/home/test.tar.gz"}
        mock_do_check_output.side_effect = mock_check_output
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.restore,
                          self.req, file_meta)