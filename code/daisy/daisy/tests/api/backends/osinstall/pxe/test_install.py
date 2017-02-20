import mock
import unittest
import webob
import exceptions
import subprocess
from daisy.api.backends.osinstall.pxe import install as os
from daisy.db.sqlalchemy import api
from daisy.context import RequestContext


def update_host_meta(req):
    host_ref = {'id': '1',
                'name': 'host_1',
                'tecs_version_id': '1',
                'os_status': 'active',
                'os_progress': 100}
    host_id = '1'
    host_meta = {'os_message': 'Invalid ipmi information '
                               'configed for host',
                 'os_status': 'install-failed'}
    api.host_add(req.context, host_ref)
    host_update_info = api.host_update(req.context,
                                       host_id,
                                       host_meta)
    return host_update_info


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
        os._os_thread_bin(self.req, host_ip, host_id, update_file,
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
        mock_update_host.side_effect = update_host_meta(req)
        host_get_info = api.host_get(req.context, '1')
        api.host_destroy(req.context, '1')
        mock_set_role.side_effect = set_role
        OSInstall(req, cluster_id)._begin_install_os(hosts_detail, cluster_id)
        self.assertIn('install-failed', host_get_info['os_status'])

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
        self.assertRaises(exception.NotFound,
                          OSInstall(req, cluster_id)._install_os_for_baremetal,
                          host_detail)
