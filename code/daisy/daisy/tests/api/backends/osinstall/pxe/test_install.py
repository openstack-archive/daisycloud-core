import mock
import unittest
import webob
import exceptions
import subprocess
from daisy.api.backends.osinstall.pxe import install
from daisy.context import RequestContext
from daisy.common import exception
import daisy.api.backends.common as daisy_cmn
from daisy import test


def subprocesscall(cmd):
    subprocess.call(cmd, shell=True,
                    stdout=open('/dev/null', 'w'),
                    stderr=subprocess.STDOUT)


class MockLoggingHandler():
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


class TestOs(unittest.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(TestOs, self).setUp()
        self.req = webob.Request.blank('/')
        self._log_handler.reset()

    def tearDown(self):
        super(TestOs, self).tearDown()

    @mock.patch('daisy.api.backends.common.update_db_host_status')
    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    def test__os_thread_bin(self, mock_subprocess_call,
                            mock_do_check_output, mock_do_db_host_status):
        cmd = 'mkdir -p /var/log/daisy/daisy_update/'
        subprocesscall(cmd)
        mock_do_check_output.return_value = 'upgrade OS successfully'
        mock_subprocess_call.return_value = ''
        host_ip = '127.0.0.1'
        host_id = ''
        update_file = ''
        update_script = ''
        install._os_thread_bin(self.req, host_ip, host_id, update_file,
                          update_script)
        log_file = '/var/log/daisy/daisy_update/127.0.0.1_update_os.log'
        all_the_text = open('%s' % log_file).read()
        self.assertIn('upgrade OS successfully', all_the_text)
        cmd = 'rm -rf /var/log/daisy'
        subprocesscall(cmd)

    @mock.patch('subprocess.check_output')
    def test_get_host_location_of_cisco(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "ipmi_addr": "127.0.0.1",
            "id": "123456789"
        }
        mock_check_output.return_value = "chassis-1/blade-1"
        location = install.get_host_location_of_cisco(host_detail)
        self.assertRaises(mock_check_output.called)
        self.assertEqual("1/1", location)

    @mock.patch('subprocess.check_output')
    def test_get_host_location_of_cisco_with_error_cmd(self,
                                                       mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "ipmi_addr": "127.0.0.1",
            "id": "123456789"
        }
        mock_check_output.side_effect = exceptions.Exception
        self.assertRaises(mock_check_output.called)
        self.assertRaises(exceptions.Exception,
                          install.get_host_location_of_cisco,
                          host_detail)

    @mock.patch('subprocess.check_output')
    def test_set_pxe_start_of_cisco(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "location": "1/1",
            "id": "123456789"
        }
        mock_check_output.return_value = "ok"
        install.set_pxe_start_of_cisco(host_detail)
        self.assertRaises(mock_check_output.called)

    @mock.patch('subprocess.check_output')
    def test_set_pxe_start_of_cisco_with_error_cmd(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "location": "1/1",
            "id": "123456789"
        }
        mock_check_output.side_effect = exceptions.Exception
        self.assertRaises(mock_check_output.called)
        self.assertRaises(exceptions.Exception,
                          install.set_pxe_start_of_cisco,
                          host_detail)

    @mock.patch('subprocess.check_output')
    def test_set_reboot_of_cisco(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "location": "1/1",
            "id": "123456789"
        }
        mock_check_output.return_value = "ok"
        install.set_reboot_of_cisco(host_detail)
        self.assertRaises(mock_check_output.called)

    @mock.patch('subprocess.check_output')
    def test_set_reboot_of_cisco_with_error_cmd(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "location": "1/1",
            "id": "123456789"
        }
        mock_check_output.side_effect = exceptions.Exception
        self.assertRaises(mock_check_output.called)
        self.assertRaises(exceptions.Exception,
                          install.set_reboot_of_cisco,
                          host_detail)

    @mock.patch('subprocess.check_output')
    def test_set_disk_start_of_cisco(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "location": "1/1",
            "id": "123456789"
        }
        mock_check_output.return_value = "ok"
        install.set_disk_start_of_cisco(host_detail)
        self.assertRaises(mock_check_output.called)

    @mock.patch('subprocess.check_output')
    def test_set_disk_start_of_cisco_with_error_cmd(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "location": "1/1",
            "id": "123456789"
        }
        mock_check_output.side_effect = exceptions.Exception
        self.assertRaises(mock_check_output.called)
        self.assertRaises(exceptions.Exception,
                          install.set_disk_start_of_cisco,
                          host_detail)


class TestInstall(test.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(TestInstall, self).setUp()
        self.req = webob.Request.blank('/')
        self._log_handler.reset()

    def tearDown(self):
        super(TestInstall, self).tearDown()

    @mock.patch("daisy.api.backends.common.set_role_status_and_progress")
    @mock.patch("daisy.api.backends.common.update_db_host_status")
    @mock.patch('logging.Logger')
    @mock.patch("daisy.api.backends.common.subprocess_call")
    def test_begin_install_os_with_error_ipmi(self,
                                              mock_subprocess,
                                              mock_log,
                                              mock_update_host,
                                              mock_set_role):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '1'

        def check_version(tecs_version):
            pass

        def set_role(req, cluster_id, opera, status, backend_name, host_id):
            pass

        def update_host_meta(req, host_id, host_meta):
            pass

        hosts_detail = [{'os_version_file': 'tecs',
                         'memory': {'total': 102400},
                         'disks': {'sda': {'disk': 'abc',
                                           'removable': 'abc',
                                           'name': 'sda',
                                           'size': '102400'}},
                         'system': {'manufacturer': 'abc'},
                         'ipmi_addr': '',
                         'ipmi_user': 'zteroot',
                         'ipmi_passwd': 'superuser',
                         'id': '1',
                         'swap_lv_size': 51200}]
        mock_subprocess.side_effect = check_version
        mock_log.side_effect = self._log_handler
        mock_update_host.side_effect = update_host_meta
        mock_set_role.side_effect = set_role
        install.OSInstall(req, cluster_id)._begin_install_os(hosts_detail,
                                                        cluster_id)
        self.assertTrue(mock_set_role.called)

    @mock.patch("daisy.api.backends.common.subprocess_call")
    def test_install_os_for_baremetal_with_no_version_file(self,
                                                           mock_subprocess):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')

        def subprocess_return(cmd):
            msg = "execute cmd failed by subprocess call"
            raise exception.SubprocessCmdFailed(message=msg)
        cluster_id = '1'
        host_detail = {'os_version_file': 'mimosa.iso'}
        mock_subprocess.side_effect = subprocess_return
        self.assertRaises(
            exception.NotFound,
            install.OSInstall(req, cluster_id)._install_os_for_baremetal,
            host_detail)

    @mock.patch('daisy.api.backends.common.update_db_host_status')
    def test_upgrade_no_local_ip(self, mock_update_db_host):
        req = webob.Request.blank('/')
        cluster_id = "123"
        version_id = "1"
        version_patch_id = "12"
        update_script = "test.txt"
        update_file = "test"
        hosts_list = ['123', '345']
        update_object = "redhat"
        daisy_cmn.get_cluster_networks_detail = mock.Mock(return_value={})
        daisy_cmn.get_host_detail = mock.Mock(return_value={})
        daisy_cmn.get_host_network_ip = mock.Mock(return_value="1.1.1.1")
        daisy_cmn.check_ping_hosts = mock.Mock(return_value={})
        daisy_cmn.get_local_deployment_ip = mock.Mock(return_value="")
        mock_update_db_host.return_value = 'ok'
        install.upgrade_os = mock.Mock(return_value={})
        install.upgrade(self, req, cluster_id, version_id, version_patch_id,
                        update_file, update_script, hosts_list, update_object)
        self.assertTrue(mock_update_db_host.called)

    @mock.patch('daisy.api.backends.common.update_db_host_status')
    def test_upgrade_has_local_ip(self, mock_update_db_host):
        req = webob.Request.blank('/')
        cluster_id = "123"
        version_id = "1"
        version_patch_id = "12"
        update_script = "test.txt"
        update_file = "test"
        hosts_list = ['123', '345']
        update_object = "redhat"
        daisy_cmn.get_cluster_networks_detail = mock.Mock(return_value={})
        daisy_cmn.get_host_detail = mock.Mock(return_value={})
        daisy_cmn.get_host_network_ip = mock.Mock(return_value="1.1.1.1")
        daisy_cmn.check_ping_hosts = mock.Mock(return_value={})
        daisy_cmn.get_local_deployment_ip = mock.Mock(return_value="1.1.1.1")
        mock_update_db_host.return_value = 'ok'
        install.upgrade_os = mock.Mock(return_value={})
        install.upgrade(self, req, cluster_id, version_id, version_patch_id,
                        update_file, update_script, hosts_list, update_object)
        self.assertFalse(mock_update_db_host.called)

    @mock.patch("daisy.api.backends.common.subprocess_call")
    @mock.patch("subprocess.check_output")
    @mock.patch('daisy.api.backends.common.update_db_host_status')
    @mock.patch('daisy.api.backends.common.check_reboot_ping')
    def test_os_thread_bin_nomal(self, mock_do_reboot_ping,
                                 mock_do_update_db_status,
                                 mock_check_output, mock_subprocess_call):
        def mock_reboot_ping():
            return

        def mock_update_db_status(req, host_id, host_meta):
            return

        mock_do_reboot_ping.side_effect = mock_reboot_ping
        mock_do_update_db_status.side_effect = mock_update_db_status
        mock_subprocess_call.return_value = None
        cmd = 'mkdir -p /var/log/daisy/daisy_update/'
        subprocesscall(cmd)
        cmd1 = "touch /var/log/daisy/daisy_update/10.43.177.1_update" \
               "_os.log"
        subprocesscall(cmd1)
        host_ip = "10.43.177.1"
        host_meta = {'id': '123', 'root_pwd': 'ossdbg1'}
        log_file = '/var/log/daisy/daisy_update/%s_update_os.log' \
                   % host_ip
        update_file = "test.txt"
        update_object = "vplat"
        vpatch_id = ""
        exec_result = 'upgrade successfully'
        mock_check_output.return_value = exec_result
        install._os_thread_bin(self.req, host_ip, host_meta['id'], update_file,
                               update_object)
        self.assertEqual(6, mock_subprocess_call.call_count)
        self.assertEqual(1, mock_check_output.call_count)
