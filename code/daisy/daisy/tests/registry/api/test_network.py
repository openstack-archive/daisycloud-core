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

from daisy.common import exception
from daisy.context import RequestContext
import daisy.db
from daisy.db.sqlalchemy import models
from daisy.registry.api.v1 import networks as registry_networks
from daisy import test
import mock
import webob


def fake_network_id(network_id):
    if network_id == '2':
        return exception.NotFound
    if network_id == '3':
        return exception.Conflict


class TestRegistryNetwork(test.TestCase):

    def setUp(self):
        super(TestRegistryNetwork, self).setUp()
        self.controller = registry_networks.Controller()

    @mock.patch('daisy.db.sqlalchemy.api.'
                'get_assigned_networks_by_network_id')
    def test_get_assigned_networks_by_network_id(
            self, mock_get_assigned_networks_by_network_id):
        id = '1'
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(
            is_admin=True, user='fake user',
            tenant='fake tenant')
        self.db_api = daisy.db.get_api()
        assigned_network_ref = models.AssignedNetworks()
        mock_get_assigned_networks_by_network_id.return_value = \
            assigned_network_ref
        #self.db_api.get_assigned_networks_by_network_id = \
        #    mock.Mock(return_value=assigned_network_ref)
        assigned_network = \
            self.controller.get_assigned_networks_by_network_id(
                self.req, id)
        self.assertEqual(daisy.db.sqlalchemy.models.AssignedNetworks,
                         type(assigned_network['network']))

    @mock.patch('daisy.db.sqlalchemy.api.'
                'get_assigned_networks_by_network_id')
    def test_get_assigned_networks_by_network_id_notfound(
            self, mock_get_assigned_networks_by_network_id):
        id = '2'
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        mock_get_assigned_networks_by_network_id.side_effect = \
            fake_network_id(id)
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller.get_assigned_networks_by_network_id,
                          self.req, id)

    @mock.patch('daisy.db.sqlalchemy.api.'
                'get_assigned_networks_by_network_id')
    def test_get_assigned_networks_by_network_id_exception(
            self, mock_get_assigned_networks_by_network_id):
        id = '3'
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        mock_get_assigned_networks_by_network_id.side_effect = \
            fake_network_id(id)
        self.assertRaises(exception.Conflict,
                          self.controller.get_assigned_networks_by_network_id,
                          self.req, id)
