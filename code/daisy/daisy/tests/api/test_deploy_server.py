import mock
import webob
from daisy import test
from daisy.context import RequestContext
from daisy.api.v1 import deploy_server


class MockStdout():

    def __init__(self):
        pass

    def readline(self):
        return ''


class MockPopen():

    def __init__(self, returncode):
        self.returncode = returncode
        self.stdout = MockStdout()

    def wait(self):
        pass


class DeployServerFuncs(test.TestCase):

    def setUp(self):
        super(DeployServerFuncs, self).setUp()
        self.controller = deploy_server.Controller()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')

    @mock.patch("commands.getstatusoutput")
    def test_get_nics(self, mock_do_getstatusoutput):
        def mock_getstatusoutput(*args, **kwargs):
            return (0, 'docker0: eth0: eth1: ')

        mock_do_getstatusoutput.side_effect = mock_getstatusoutput
        nics = self.controller.get_nics()
        self.assertEqual(set(['docker0', 'eth1', 'eth0']), nics)

    @mock.patch("commands.getstatusoutput")
    def test_get_pxe_nic(self, mock_do_getstatusoutput):
        def mock_getstatusoutput(*args, **kwargs):
            return (0, 'bond0:100')

        mock_do_getstatusoutput.side_effect = mock_getstatusoutput
        pxe_nic = self.controller.get_pxe_nic("99.99.1.5")
        self.assertEqual("bond0", pxe_nic)

    @mock.patch("daisy.registry.client.v1.api.get_all_networks")
    @mock.patch("daisy.api.v1.deploy_server.Controller.get_nics")
    @mock.patch("daisy.api.v1.deploy_server.Controller.get_pxe_nic")
    def test_list_deploy_server(self, mock_do_get_pxe_nic,
                                mock_do_get_nics,
                                mock_do_get_all_networks):

        def mock_get_all_networks(*args, **kwargs):
            return [{"ip": "99.99.1.5"}]

        def mock_get_nics(*args, **kwargs):
            return set(['docker0', 'eth1', 'eth0'])

        def mock_get_pxe_nic(*args, **kwargs):
            return "bond0"

        mock_do_get_all_networks.side_effect = mock_get_all_networks
        mock_do_get_nics.side_effect = mock_get_nics
        mock_do_get_pxe_nic.side_effect = mock_get_pxe_nic
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        actual = {'deploy_servers': [
            {
                'ip': '99.99.1.5',
                'nics': set(['docker0', 'eth0', 'eth1']),
                'pxe_nic': 'bond0'
            }]}
        deploy_servers = self.controller.list_deploy_server(req)
        self.assertEqual(actual, deploy_servers)

    @mock.patch("daisy.registry.client.v1.api.get_all_networks")
    @mock.patch("daisy.api.v1.deploy_server.Controller.get_nics")
    @mock.patch("daisy.api.v1.deploy_server.Controller.get_pxe_nic")
    def test_list_more_deploy_server(self, mock_do_get_pxe_nic,
                                     mock_do_get_nics,
                                     mock_do_get_all_networks):

        def mock_get_all_networks(*args, **kwargs):
            return [{"ip": "99.99.1.5"}, {"ip": "99.99.1.5"}]

        def mock_get_nics(*args, **kwargs):
            return set(['docker0', 'eth1', 'eth0'])

        def mock_get_pxe_nic(*args, **kwargs):
            return "bond0"

        mock_do_get_all_networks.side_effect = mock_get_all_networks
        mock_do_get_nics.side_effect = mock_get_nics
        mock_do_get_pxe_nic.side_effect = mock_get_pxe_nic
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.list_deploy_server,
                          req)

    @mock.patch("subprocess.Popen")
    def test_pxe_env_check(self, mock_do_popen):

        def mock_popen(*args, **kwargs):
            _popen = MockPopen(0)
            return _popen

        mock_do_popen.side_effect = mock_popen
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        deploy_server_meta = {
            "deployment_interface": "bond0",
            "server_ip": "99.99.1.5"}
        actual = {'deploy_server_meta': {'return_code': 0}}

        result = self.controller.pxe_env_check(req, deploy_server_meta)
        self.assertEqual(actual, result)

    @mock.patch("subprocess.Popen")
    def test_pxe_env_check_call_process_error(self, mock_do_popen):

        def mock_popen(*args, **kwargs):
            e = subprocess.CalledProcessError(0, 'test')
            e.output = 'test error'
            raise e

        mock_do_popen.side_effect = mock_popen
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        deploy_server_meta = {
            "deployment_interface": "bond0",
            "server_ip": "99.99.1.5"}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.pxe_env_check,
                          req, deploy_server_meta)

    @mock.patch("subprocess.Popen")
    def test_pxe_env_check_error(self, mock_do_popen):

        def mock_popen(*args, **kwargs):
            _popen = MockPopen(1)
            return _popen

        mock_do_popen.side_effect = mock_popen
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        deploy_server_meta = {
            "deployment_interface": "bond0",
            "server_ip": "99.99.1.5"}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.pxe_env_check,
                          req, deploy_server_meta)
