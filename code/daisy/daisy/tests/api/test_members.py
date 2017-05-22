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
from daisy.context import RequestContext
from daisy import test
from daisy.api.v1 import members


class TestMembers(test.TestCase):
    def setUp(self):
        super(TestMembers, self).setUp()
        self.controller = members.Controller()

    @mock.patch('daisy.api.backends.common._judge_ssh_host')
    @mock.patch('daisy.registry.client.v1.api.update_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.delete_cluster_host')
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    def test_delete_cluster_host(self, mock_get_cluster, mock_get_host,
                                 mock_delete_cluster_host, mock_update_host,
                                 mock_judge_ssh_host):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '1'
        host_id = '1'
        mock_get_cluster.return_value = {'id': '1', 'deleted': 0}
        mock_get_host.return_value = {'id': '1', 'deleted': 0}
        mock_delete_cluster_host.return_value = []
        mock_judge_ssh_host.return_value = False
        mock_update_host.return_value = {}
        self.controller.delete_cluster_host(req, cluster_id, host_id)
        self.assertTrue(mock_update_host.called)
