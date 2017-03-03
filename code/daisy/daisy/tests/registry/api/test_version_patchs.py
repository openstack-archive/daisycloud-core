import mock
from daisy import test
import webob
from daisy.context import RequestContext
from daisy.common import exception
from daisy.registry.api.v1 import version_patchs


def fake_version_patch_add(host_id):
    if host_id == 'd134fa48-a':
        return exception.NotFound
    elif host_id == 'd134fa48-b':
        return exception.Forbidden
    elif host_id == 'd134fa48-c':
        return exception.Invalid


class TestVersionpatchs(test.TestCase):

    def setUp(self):
        super(TestVersionpatchs, self).setUp()
        self.controller = version_patchs.Controller()

    @mock.patch('daisy.db.sqlalchemy.api.add_host_patch_history')
    def test_add_host_patch_history(self, mock_add_patch_history):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48'
        patch_name = 'd134fa'
        body = {"patch_history": {'host_id': host_id,
                                  'patch_name': patch_name}}
        mock_add_patch_history.return_value = {'host_id': host_id,
                                               'patch_name': patch_name}
        actual_data = self.controller.add_host_patch_history(self.req, body)
        self.assertEqual(body, actual_data)
