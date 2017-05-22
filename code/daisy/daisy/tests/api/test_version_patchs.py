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
import webob
import json as jsonutils
from daisy.api.v1 import version_patchs
from daisy.context import RequestContext
from daisy import test


def set_version_meta():
    version_patch_meta = {}
    version_patch_meta["name"] = "test_version"
    version_patch_meta["description"] = "111"
    version_patch_meta["status"] = "used"
    return version_patch_meta


class TestVersionsPatchApiConfig(test.TestCase):
    def setUp(self):
        super(TestVersionsPatchApiConfig, self).setUp()
        self.controller = version_patchs.Controller()

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.'
                'do_request')
    def test_add_version_patch(self, mock_do_request):
        version_patch_meta = set_version_meta()
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            if method == 'POST':
                post_result = {
                    u'version_patch': {u'status': u'used',
                                       u'name': u'name3',
                                       u'deleted': False, u'checksum': None,
                                       u'created_at': u'2016-07-12',
                                       u'description': None,
                                       u'status': u'used',
                                       u'deleted_at': None,
                                       u'size': None}}
                res.read.return_value = jsonutils.dumps(post_result)
                return res

        mock_do_request.side_effect = fake_do_request
        add_version = self.controller.add_version_patch(req,
                                                        version_patch_meta)
        self.assertEqual("name3",
                         add_version['version_patch_meta']['name'])

    def test_add_version_patch_with_no_name(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        version_meta = {}
        version_meta["description"] = "111"
        self.assertRaises(ValueError, self.controller.add_version_patch, req,
                          version_meta)

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.'
                'do_request')
    def test_update_version_patch(self, mock_do_request):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            if method == "GET":
                get_result = {
                    "version_patch": {"status": "unused",
                                      "name": "ssh2.exe",
                                      "checksum": "60489112c272fbf",
                                      "size": 1089536,
                                      "id": "1",
                                      "description": "1",
                                      "deleted": 0}}
                res.read.return_value = jsonutils.dumps(get_result)
                return res
            elif method == 'PUT':
                post_result = {
                    u'version_patch': {u'status': u'unused',
                                       u'name': u'test',
                                       u'deleted': 0,
                                       u'checksum': None,
                                       u'description': None,
                                       u'deleted_at': None,
                                       u'size': None}}
                res.read.return_value = jsonutils.dumps(post_result)
                return res

        mock_do_request.side_effect = fake_do_request

        version_patch = {}
        version_patch["name"] = "test"
        version_patch["description"] = "111"
        version_patch_id = "1"
        add_version = self.controller.update_version_patch(req,
                                                           version_patch_id,
                                                           version_patch)
        self.assertEqual("test",
                         add_version['version_patch_meta']['name'])

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.'
                'do_request')
    def test_get_version_patch(self, mock_do_request):
        version_patch_id = "34811a0e66792a979e99"
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            if method == "GET":
                get_result = {
                    "version_patch": {"status": "unused",
                                      "name": "ssh2.exe",
                                      "checksum": "60489112c2c0862fbf",
                                      "size": 1089536,
                                      "id": "34811a0e66792a979e99",
                                      "description": "azsdadsad"}}
                res.read.return_value = jsonutils.dumps(get_result)
                return res

        mock_do_request.side_effect = fake_do_request
        version = self.controller.get_version_patch(req, version_patch_id)
        self.assertEqual(version_patch_id,
                         version['version_patch_meta']['id'])

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.'
                'do_request')
    def test_delete_version_patch(self, mock_do_request):
        version_patch_id = "34811a0e-a69f-4dd3-bbfb-66792a979e99"
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')

        def fake_do_request(method, path, **params):
            res = mock.Mock()
            if method == "GET":
                get_result = {
                    "version_patch": {"status": "unused",
                                      "name": "ssh2.exe",
                                      "checksum": "60489112c277862fbf",
                                      "size": 1089536,
                                      "id": "34811a0e-a69f-2a979e99",
                                      "description": "azsad"}}
                res.read.return_value = jsonutils.dumps(get_result)
                return res
            elif method == "DELETE":
                result = {
                    "version_patch": {"status": "unused",
                                      "name": "ssh2.exe",
                                      "checksum": "60489112c277a18147b",
                                      "created_at": "2016-07-12",
                                      "size": 1089536,
                                      "updated_at": "2016-07-12",
                                      "id": "34811a0e-a69f-4dd3",
                                      "description": "azsdadsad"}}
                res.read.return_value = jsonutils.dumps(result)
                return res

        mock_do_request.side_effect = fake_do_request
        version = self.controller.delete_version_patch(req, version_patch_id)
        self.assertEqual(200, version.status_code)

    @mock.patch('daisy.registry.client.v1.api.'
                'add_host_patch_history_metadata')
    def test_add_host_patch_history(self, mock_add_history):
        history_meta = {'patch_name': 'test'}
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')

        mock_add_history.return_value = history_meta
        add_history = self.controller.add_host_patch_history(req, history_meta)
        self.assertEqual({'patch_history_meta': history_meta}, add_history)

    @mock.patch('daisy.registry.client.v1.api.'
                'list_host_patch_history_metadata')
    def test_list_host_patch_history(self, mock_list_history):
        history_meta = {'patch_name': 'test'}
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        mock_list_history.return_value = history_meta
        historys = self.controller.list_host_patch_history(req)
        self.assertEqual({'patch_history_meta': history_meta}, historys)

    @mock.patch('daisy.registry.client.v1.api.'
                'list_host_patch_history_metadata')
    def test_list_host_patch_history_with_except(self, mock_list_history):
        def mock_history(*args, **kwargs):
            raise webob.exc.HTTPBadRequest

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        mock_list_history.side_effect = mock_history
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.list_host_patch_history, req)
