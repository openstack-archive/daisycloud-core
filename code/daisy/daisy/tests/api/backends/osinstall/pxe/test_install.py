import mock
import webob
from daisy import test
from daisy.context import RequestContext
import subprocess
from daisy.api.backends.osinstall.pxe import install
from daisy.db.sqlalchemy import api
from daisy.common import exception


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

    def debug(self, message, *args, **kwargs):
        self.messages['debug'].append(message)

    def info(self, message, *args, **kwargs):
        self.messages['info'].append(message)

    def error(self, message, *args, **kwargs):
        self.messages['error'].append(message)

    def reset(self):
        for message in self.messages:
            del self.messages[message][:]


class TestOsInstall(test.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(TestOsInstall, self).setUp()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        self._log_handler.reset()

    @mock.patch('daisy.api.backends.common.update_db_host_status')
    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    @mock.patch('daisy.api.backends.osinstall.pxe.install._exec_upgrade')
    def test__os_thread_bin(self, mock_exec_upgrade, mock_subprocess_call,
                            mock_do_check_output, mock_do_db_host_status):
        cmd = 'mkdir -p /var/log/daisy/daisy_update/'
        subprocesscall(cmd)
        mock_do_check_output.return_value = 'OS upgraded successfully'
        mock_subprocess_call.return_value = ''
        host_ip = '127.0.0.1'
        host_meta = {'id': '123', 'root_pwd': 'ossdbg1'}
        update_file = ''
        update_object = "vplat"
        vpatch_id = '1'
        mock_exec_upgrade.return_value = 'OS upgraded successfully'
        install._os_thread_bin(self.req, host_ip, host_meta, update_file,
                               vpatch_id, update_object)
        log_file = '/var/log/daisy/daisy_update/127.0.0.1_update_os.log'
        all_the_text = open('%s' % log_file).read()
        self.assertIn('OS upgraded successfully', all_the_text)
        cmd = 'rm -rf /var/log/daisy'
        subprocesscall(cmd)

    @mock.patch("daisy.api.backends.common.set_role_status_and_progress")
    @mock.patch("daisy.api.backends.common.update_db_host_status")
    @mock.patch('logging.Logger')
    def test_begin_install_os_with_error_ipmi(self,
                                              mock_log,
                                              mock_update_host,
                                              mock_set_role):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '1'

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
        mock_log.side_effect = self._log_handler
        mock_set_role.side_effect = set_role
        mock_update_host.return_value = {}
        install.OSInstall(req, cluster_id, False).\
            _begin_install_os(hosts_detail, cluster_id)
        self.assertTrue(mock_set_role.called)

    @mock.patch("daisy.api.backends.osinstall.pxe."
                "install.OSInstall._set_power_reset")
    @mock.patch("daisy.api.backends.osinstall.pxe."
                "install.OSInstall._install_os_for_baremetal")
    @mock.patch("daisy.api.backends.osinstall.pxe."
                "install.OSInstall._set_boot_pxe")
    @mock.patch("daisy.api.backends.common.update_db_host_status")
    @mock.patch('logging.Logger')
    def test_begin_install_os_with_write_ipmi(self, mock_log,
                                              mock_update_host,
                                              mock_set_boot_pxe,
                                              mock_install_os_for_baremetal,
                                              mock_set_power_reset):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '1'

        class InstallMock():
            def __init__(self):
                pass

            def install_os_for_baremetal(self, host_detail):
                pass

            def set_power_reset(self, host_detail, impi_result_flag):
                pass

        hosts_detail = [{'id': '1'}]
        mock_log.side_effect = self._log_handler
        mock_update_host.return_value = {}
        mock_set_boot_pxe.return_value = True
        mock_install_os_for_baremetal.side_effect = \
            InstallMock().install_os_for_baremetal
        mock_set_power_reset.side_effect = InstallMock().set_power_reset
        install.OSInstall(req, cluster_id, False).\
            _begin_install_os(hosts_detail, cluster_id)
        self.assertTrue(mock_install_os_for_baremetal.called)
        self.assertTrue(mock_set_power_reset.called)

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
            install.OSInstall(req,
                              cluster_id,
                              False)._install_os_for_baremetal,
            host_detail)

    @mock.patch("daisy.api.backends.osinstall.pxe.install.upgrade_os")
    @mock.patch("daisy.api.backends.common.get_cluster_networks_detail")
    @mock.patch("daisy.api.backends.common.get_host_detail")
    @mock.patch("daisy.api.backends.common.get_host_network_ip")
    @mock.patch("daisy.api.backends.common.check_ping_hosts")
    @mock.patch("daisy.api.backends.common.get_local_deployment_ip")
    @mock.patch('daisy.api.backends.common.update_db_host_status')
    def test_upgrade_no_local_ip(self, mock_update_db_host,
                                 mock_get_local_deployment_ip,
                                 mock_check_ping_hosts,
                                 mock_get_host_network_ip,
                                 mock_get_host_detail,
                                 mock_get_cluster_networks_detail,
                                 mock_upgrade_os):
        req = webob.Request.blank('/')
        cluster_id = "123"
        version_id = "1"
        version_patch_id = ""
        update_file = "test"
        hosts_list = ['123', '345']
        update_object = "vplat"
        mock_get_cluster_networks_detail.return_value = {}
        mock_get_host_detail.return_value = {'root_pwd': 'ossdbg'}
        mock_get_host_network_ip.return_value = "1.1.1.1"
        mock_check_ping_hosts.return_value = {}
        mock_get_local_deployment_ip.return_value = ""
        mock_update_db_host.return_value = 'ok'
        mock_upgrade_os.return_value = {}
        install._cmp_os_version = mock.Mock(return_value=1)
        install._get_host_os_version = mock.Mock(return_value=1)
        install.upgrade_os = mock.Mock(return_value={})
        install.upgrade(self, req, cluster_id, version_id, version_patch_id,
                        update_file, hosts_list, update_object)
        self.assertTrue(mock_update_db_host.called)

    @mock.patch("daisy.api.backends.osinstall.pxe.install.upgrade_os")
    @mock.patch("daisy.api.backends.common.get_cluster_networks_detail")
    @mock.patch("daisy.api.backends.common.get_host_detail")
    @mock.patch("daisy.api.backends.common.get_host_network_ip")
    @mock.patch("daisy.api.backends.common.check_ping_hosts")
    @mock.patch("daisy.api.backends.common.get_local_deployment_ip")
    @mock.patch('daisy.api.backends.common.update_db_host_status')
    def test_upgrade_has_local_ip(self, mock_update_db_host,
                                  mock_get_local_deployment_ip,
                                  mock_check_ping_hosts,
                                  mock_get_host_network_ip,
                                  mock_get_host_detail,
                                  mock_get_cluster_networks_detail,
                                  mock_upgrade_os):
        req = webob.Request.blank('/')
        cluster_id = "123"
        version_id = "1"
        version_patch_id = "12"
        update_file = "test"
        hosts_list = ['123', '345']
        update_object = "redhat"
        mock_get_local_deployment_ip.return_value = "1.1.1.1"
        mock_check_ping_hosts.return_value = {}
        mock_get_host_network_ip.return_value = "1.1.1.1"
        mock_get_host_detail.return_value = {}
        mock_get_cluster_networks_detail.return_value = {}
        #daisy_cmn.get_cluster_networks_detail = mock.Mock(return_value={})
        #daisy_cmn.get_host_detail = mock.Mock(return_value={})
        #daisy_cmn.get_host_network_ip = mock.Mock(return_value="1.1.1.1")
        #daisy_cmn.check_ping_hosts = mock.Mock(return_value={})
        #daisy_cmn.get_local_deployment_ip = mock.Mock(return_value="1.1.1.1")
        mock_update_db_host.return_value = 'ok'
        mock_upgrade_os.return_value = {}
        #install.upgrade_os = mock.Mock(return_value={})
        install.upgrade(self, req, cluster_id, version_id, version_patch_id,
                        update_file, hosts_list, update_object)
        self.assertFalse(mock_update_db_host.called)

    @mock.patch("daisy.api.backends.osinstall.pxe.install.upgrade_os")
    @mock.patch("daisy.api.backends.common.get_cluster_networks_detail")
    @mock.patch("daisy.api.backends.common.get_host_detail")
    @mock.patch("daisy.api.backends.common.get_host_network_ip")
    @mock.patch("daisy.api.backends.common.check_ping_hosts")
    @mock.patch("daisy.api.backends.common.get_local_deployment_ip")
    @mock.patch('daisy.api.backends.common.update_db_host_status')
    def test_upgrade_with_equal_version(self, mock_update_db_host,
                                        mock_get_local_deployment_ip,
                                        mock_check_ping_hosts,
                                        mock_get_host_network_ip,
                                        mock_get_host_detail,
                                        mock_get_cluster_networks_detail,
                                        mock_upgrade_os):
        req = webob.Request.blank('/')
        cluster_id = "123"
        version_id = "1"
        version_patch_id = ""
        update_file = "test"
        hosts_list = ['123', '345']
        update_object = "vplat"
        mock_get_cluster_networks_detail.return_value = {}
        mock_get_host_detail.return_value = {'root_pwd': 'ossdbg'}
        mock_get_host_network_ip.return_value = "1.1.1.1"
        mock_check_ping_hosts.return_value = {}
        mock_get_local_deployment_ip.return_value = ""
        mock_update_db_host.return_value = 'ok'
        mock_upgrade_os.return_value = {}
        install._cmp_os_version = mock.Mock(return_value=-1)
        install._get_host_os_version = mock.Mock(return_value=1)
        install.upgrade_os = mock.Mock(return_value={})
        install.upgrade(self, req, cluster_id, version_id, version_patch_id,
                        update_file, hosts_list, update_object)
        self.assertTrue(mock_update_db_host.called)

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
        install._os_thread_bin(self.req, host_ip, host_meta, update_file,
                               vpatch_id, update_object)
        self.assertEqual(5, mock_subprocess_call.call_count)

    @mock.patch("daisy.api.backends.osinstall.pxe.install."
                "_exec_upgrade")
    @mock.patch("daisy.api.backends.common.subprocess_call")
    @mock.patch("subprocess.check_output")
    @mock.patch('daisy.api.backends.common.update_db_host_status')
    @mock.patch('daisy.api.backends.common.check_reboot_ping')
    def test_os_thread_bin_with_reboot(self, mock_do_reboot_ping,
                                       mock_do_update_db_status,
                                       mock_check_output, mock_subprocess_call,
                                       mock_exec_upgrade):
        def mock_reboot_ping(*args, **kwargs):
            return

        def mock_update_db_status(req, host_id, host_meta):
            return

        def mock_execupgrade(*args, **kwargs):
            retcode = 255
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = "system reboot"
            raise error

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
        update_file = "test.txt"
        update_object = "vplat"
        vpatch_id = ""
        mock_exec_upgrade.side_effect = mock_execupgrade
        exec_result = 'upgrade successfully'
        mock_check_output.return_value = exec_result
        install._os_thread_bin(self.req, host_ip, host_meta, update_file,
                               vpatch_id, update_object)
        self.assertEqual(5, mock_subprocess_call.call_count)

    @mock.patch('daisy.api.backends.common.update_db_host_status')
    @mock.patch("daisy.api.backends.common.get_host_detail")
    @mock.patch('daisy.api.backends.osinstall.pxe.install.'
                'os_thread_bin')
    def test_upgrade_os_active(self, mock_os_thread_in,
                               mock_get_host_detail, mock_do_update_db_status):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        version_id = "1"
        version_patch_id = ""
        update_file = "test"
        hosts_list = [{'10.43.177.1': {'id': "1"}}]
        update_object = "vplat"
        mock_do_update_db_status.return_value = {}
        mock_get_host_detail.return_value = {'os_status': 'active'}
        mock_os_thread_in.return_value = {}
        install.upgrade_os(req, version_id, version_patch_id, update_file,
                           hosts_list, update_object)

    @mock.patch('daisy.api.backends.common.update_db_host_status')
    @mock.patch("daisy.api.backends.common.get_host_detail")
    @mock.patch('daisy.api.backends.osinstall.pxe.install.'
                'os_thread_bin')
    def test_upgrade_os_failed(self, mock_os_thread_in,
                               mock_get_host_detail, mock_do_update_db_status):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        version_id = "1"
        version_patch_id = ""
        update_file = "test"
        hosts_list = [{'10.43.177.1': {'id': "1"}}]
        update_object = "vplat"
        mock_do_update_db_status.return_value = {}
        mock_get_host_detail.return_value = {'os_status': 'updating'}
        mock_os_thread_in.return_value = {}
        install.upgrade_os(req, version_id, version_patch_id, update_file,
                           hosts_list, update_object)

    @mock.patch('subprocess.check_output')
    def test_exec_upgrade_with_vplat(self, mock_check_output):
        host_ip = '127.0.0.1'
        vpatch_id = ""
        update_file = "test"
        update_object = "vplat"
        exec_result = 'OS upgraded successfully'
        mock_check_output.return_value = exec_result
        result = install._exec_upgrade(host_ip, vpatch_id, update_file,
                                       update_object, None)
        self.assertEqual(exec_result, result)

    @mock.patch('subprocess.check_output')
    def test_exec_upgrade_with_redhat7(self, mock_check_output):
        host_ip = '127.0.0.1'
        vpatch_id = "redhatpatch"
        update_file = "test.tar.gz"
        update_object = "redhat 7.0"
        exec_result = 'OS upgraded successfully'
        mock_check_output.return_value = exec_result
        result = install._exec_upgrade(host_ip, vpatch_id, update_file,
                                       update_object, None)
        self.assertEqual(exec_result, result)

    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    def test_exec_upgrade_with_patch(self, mock_call, mock_check_output):
        host_ip = '127.0.0.1'
        vpatch_id = "1234"
        update_file = "test.tar.gz"
        update_object = "vplat"
        exec_result = 'OS upgraded successfully'
        mock_call.return_value = ''
        mock_check_output.return_value = exec_result
        result = install._exec_upgrade(host_ip, vpatch_id, update_file,
                                       update_object, None)
        self.assertEqual(exec_result, result)

    @mock.patch('daisy.api.backends.osinstall.pxe.install.'
                '_os_thread_bin')
    def test_os_thread_bin(self, mock_thread_in):
        host_ip = '127.0.0.1'
        host_meta = {'id': '123', 'root_pwd': 'ossdbg1'}
        update_file = ''
        update_object = "vplat"
        vpatch_id = '1'
        mock_thread_in.return_value = '1'
        install.os_thread_bin(self.req, host_ip, host_meta, update_file,
                              vpatch_id, update_object)
