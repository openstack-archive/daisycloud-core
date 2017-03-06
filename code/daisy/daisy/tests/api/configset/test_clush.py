import os
import mock
import webob
import copy
import subprocess
from daisy import test
from daisy.context import RequestContext
from daisy.common import exception
from daisy.api.configset import clush


class TestClush(test.TestCase):

    def setUp(self):
        super(TestClush, self).setUp()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        self.controller = clush.config_clushshell(self.req)

    def tearDown(self):
        super(TestClush, self).tearDown()

    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.configset.clush.run')
    def test_copy_without_reverse(self, mock_do_run, mock_do_check_output):
        def mock_check_output(scrip, stderr, shell):
            cmd.append(scrip)

        cmd = []
        mock_do_run.return_value = None
        mock_do_check_output.side_effect = mock_check_output
        clush.copy(['127.0.0.1', '127.0.0.2'], ['test.py'], '/home')
        self.assertIn(
            'clush -S -w 127.0.0.1,127.0.0.2 --copy test.py --dest /home/',
            cmd)

    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.configset.clush.run')
    def test_copy_with_reverse(self, mock_do_run, mock_do_check_output):
        def mock_check_output(scrip, stderr, shell):
            cmd.append(scrip)

        cmd = []
        mock_do_run.return_value = None
        mock_do_check_output.side_effect = mock_check_output
        clush.copy(['127.0.0.1', '127.0.0.2'], ['test.py'], '/home', True)
        self.assertIn(
            'clush -S -w 127.0.0.1,127.0.0.2 --rcopy test.py --dest /home/',
            cmd)

    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.configset.clush.run')
    def test_copy_with_exec(self, mock_do_run, mock_do_check_output):
        def mock_check_output(*args, **kwargs):
            e = subprocess.CalledProcessError(1, 'test')
            e.output = 'test error'
            raise e

        mock_do_run.return_value = None
        mock_do_check_output.side_effect = mock_check_output
        self.assertRaises(webob.exc.HTTPBadRequest,
                          clush.copy,
                          ['127.0.0.1', '127.0.0.2'], ['test.py'], '/home')

    @mock.patch('subprocess.check_output')
    def test_run(self, mock_do_check_output):
        def mock_check_output(scrip, stderr, shell):
            cmd.append(scrip)

        cmd = []
        mock_do_check_output.side_effect = mock_check_output
        clush.run(['127.0.0.1', '127.0.0.2'], ['test'])
        self.assertIn('clush -S -w 127.0.0.1,127.0.0.2 "test"', cmd)

    @mock.patch('subprocess.check_output')
    def test_run_no_allow_fail(self, mock_do_check_output):
        def mock_check_output(*args, **kwargs):
            e = subprocess.CalledProcessError(1, 'test')
            e.output = 'test error'
            raise e

        mock_do_check_output.side_effect = mock_check_output
        clush.run(['127.0.0.1', '127.0.0.2'], ['test'], True)

    @mock.patch('subprocess.check_output')
    def test_run_allow_fail(self, mock_do_check_output):
        def mock_check_output(*args, **kwargs):
            e = subprocess.CalledProcessError(1, 'test')
            e.output = 'test error'
            raise e

        mock_do_check_output.side_effect = mock_check_output
        self.assertRaises(webob.exc.HTTPBadRequest,
                          clush.run, ['127.0.0.1', '127.0.0.2'], ['test'])

