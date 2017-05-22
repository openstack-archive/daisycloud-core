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
import unittest
import webob
from daisyclient.v1 import client
from daisyclient.v1 import version_patchs
from daisyclient.common import http

endpoint = 'http://127.0.0.1:29292'
client_mata = {'ssl_compression': True, 'insecure': False, 'timeout': 600,
               'cert': None, 'key': None, 'cacert': ''}
version_meta = {'name': 'version1'}


class TestVersionPatchManager(unittest.TestCase):
    def setUp(self):
        super(TestVersionPatchManager, self).setUp()
        self.client = http.HTTPClient(endpoint, **client_mata)
        self.manager = version_patchs.VersionPatchManager(self.client)

    @mock.patch('daisyclient.common.http.HTTPClient._request')
    def test_add_version_patch(self, mock_do_request):
        def mock_request(method, url, **kwargs):
            resp = webob.Response()
            resp.status_code = 200
            body = {'version_patch': {'status': 'unused',
                                      'name': 'version1'}}
            return resp, body

        mock_do_request.side_effect = mock_request
        version = self.manager.add(**version_meta)
        self.assertEqual("version1", version.name)

    @mock.patch('daisyclient.common.http.HTTPClient._request')
    def test_get_version_patch(self, mock_do_request):
        def mock_request(method, url, **kwargs):
            resp = webob.Response()
            resp.status_code = 200
            body = {'version_patch': {u'status': u'unused',
                                      u'name': u'version1'}}
            return resp, body

        version_id = "1234"
        mock_do_request.side_effect = mock_request
        version = self.manager.get(version_id)
        self.assertEqual("version1", version.name)

    @mock.patch('daisyclient.common.http.HTTPClient._request')
    def test_update_version_patch(self, mock_do_request):
        def mock_request(method, url, **kwargs):
            resp = webob.Response()
            resp.status_code = 200
            body = {'version_patch': {u'status': u'unused',
                                      u'name': u'version1'}}
            return resp, body

        version_id = "1"
        mock_do_request.side_effect = mock_request
        versions = self.manager.update(version_id, **version_meta)
        self.assertEqual("version1", versions.name)
