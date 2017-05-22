# Copyright 2012 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

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
