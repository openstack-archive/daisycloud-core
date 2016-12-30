import mock
import time
import unittest
from daisy.api.backends.osinstall.pxe import install as os
import webob
import exceptions


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


class Mockthread():

    def __init__(self, *args, **kwargs):
        pass

    def setDaemon(self, flag):
        pass

    def start(self):
        pass

    def join(self):
        pass


class TestOs(unittest.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(TestOs, self).setUp()
        self.req = webob.Request.blank('/')

    def tearDown(self):
        super(TestOs, self).tearDown()

    @mock.patch('subprocess.check_output')
    def test_get_host_location_of_cisco(self, mock_check_output):
        host_detail = {
            "ipmi_passwd": "zteroot",
            "ipmi_user": "superuser",
            "ipmi_addr": "127.0.0.1",
            "id": "123456789"
        }
        mock_check_output.return_value = "chassis-1/blade-1"
        location = os.get_host_location_of_cisco(host_detail)
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
                          os.get_host_location_of_cisco,
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
        os.set_pxe_start_of_cisco(host_detail)
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
                          os.set_pxe_start_of_cisco,
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
        os.set_reboot_of_cisco(host_detail)
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
                          os.set_reboot_of_cisco,
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
        os.set_disk_start_of_cisco(host_detail)
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
                          os.set_disk_start_of_cisco,
                          host_detail)

    @mock.patch(
        'daisy.api.backends.osinstall.pxe.'
        'install.OSInstall._set_disk_start_mode')
    @mock.patch('daisy.api.backends.common.os_install_start_time')
    @mock.patch(
        'daisy.api.backends.osinstall.pxe.install.get_install_progress')
    def test__query_host_progress(self,
                                  mock_do_get_install_progress,
                                  mock_do_os_install_start_time,
                                  mock_do__set_disk_start_mode):

        host_detail = {'id': 'host123', 'interfaces': '',
                       'dhcp_mac': '00:00:00:00:00:00'}
        host_status = {'os_progress': '', 'os_status': '',
                       'messages': '', 'count': '0'}
        host_last_status = {'os_progress': ''}
        mock_do_get_install_progress.return_value = {
            'return_code': '0', 'progress': '100'}
        mock_do_os_install_start_time.side_effect = time.time() + 600
        mock_do__set_disk_start_mode.return_value = {}
        self.assertEqual(None,
                         os.OSInstall._query_host_progress(
                             os.OSInstall(self.req, '123'), host_detail,
                             host_status, host_last_status))

    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    @mock.patch(
        'daisy.api.backends.osinstall.pxe.install._cmp_os_version')
    @mock.patch('threading.Thread')
    @mock.patch(
        'daisy.api.backends.common.update_db_host_status')
    @mock.patch(
        'daisy.api.backends.osinstall.pxe.install._get_host_os_version')
    @mock.patch('daisy.api.backends.common.get_host_detail')
    def test_upgrade_os(self, mock_do_get_host_detail,
                        mock_do_get_host_os_version,
                        mock_do_update_db_host_status,
                        mock_do_thread,
                        mock_do_cmp_os_version,
                        mock_do_get_host_metadata):
        hosts_list = [{'id': 'host123', 'ip': '127.0.0.1'}]
        update_object = 'vplat'
        update_file = 'centos6.iso'
        version_id = []
        version_patch_id = []
        update_script = ''
        mock_do_get_host_detail.return_value = {'root_pwd': 'ossdbg1'}
        mock_do_get_host_os_version.return_value = 'centos7.iso'
        mock_do_update_db_host_status.return_value = []
        mock_do_thread.side_effect = Mockthread
        mock_do_cmp_os_version.return_value = 0
        mock_do_get_host_metadata.return_value = {
            'os_status': 'init', 'message': ''}
        self.assertEqual(None,
                         os.upgrade_os(self.req, version_id,
                                       version_patch_id,
                                       update_script,
                                       update_file,
                                       hosts_list,
                                       update_object))
