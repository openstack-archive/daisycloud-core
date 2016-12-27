import mock
import webob
from daisy import test
from daisy.api.backends.kolla import install
from daisy.context import RequestContext
import subprocess
import daisy.api.backends.common as daisy_cmn
from daisy.api.backends.kolla import api
from daisy.api.backends.osinstall.pxe import install

def subprocesscall(cmd):
    subprocess.call(cmd, shell=True,
                    stdout=open('/dev/null', 'w'),
                    stderr=subprocess.STDOUT)

class OSInstall(test.TestCase):

    def setUp(self):
        super(OSInstall, self).setUp()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')

    @mock.patch('daisy.api.backends.common.update_db_host_status') 
    @mock.patch('subprocess.check_output')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    def test__os_thread_bin(self, mock_subprocess_call, mock_do_check_output, mock_do_db_host_status):
        cmd = 'mkdir -p /var/log/daisy/daisy_update/'
        subprocesscall(cmd)
        mock_do_check_output.return_value = 'upgrade OS successfully' 
        mock_subprocess_call.return_value = ''
        host_ip = '127.0.0.1'
        host_id = ''
        update_file = ''
        update_script = ''
        install._os_thread_bin(self.req, host_ip, host_id, update_file, update_script)
        log_file = '/var/log/daisy/daisy_update/127.0.0.1_update_os.log'
        all_the_text = open('%s' % log_file).read()
        self.assertIn('upgrade OS successfully', all_the_text)
        cmd = 'rm -rf /var/log/daisy'
        subprocesscall(cmd) 
