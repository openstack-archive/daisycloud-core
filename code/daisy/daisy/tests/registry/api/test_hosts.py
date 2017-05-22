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
import daisy.db
import webob
from daisy.context import RequestContext
from daisy.common import utils
from daisy.common import exception
from daisy.registry.api.v1 import hosts as registry_hosts
from daisy.db.sqlalchemy import models
from daisy.tests import test_utils


def fake_config_set_destroy(config_set_id):
    if config_set_id == 'd134fa48-c3ad-477c-b2ac-95bee758218a':
        return exception.NotFound
    elif config_set_id == 'd134fa48-c3ad-477c-b2ac-95bee758218b':
        return exception.Forbidden
    elif config_set_id == 'd134fa48-c3ad-477c-b2ac-95bee758218c':
        return exception.Invalid


class TestHost(test.TestCase):

    def setUp(self):
        super(TestHost, self).setUp()
        self.controller = registry_hosts.Controller()

    @mock.patch("daisy.registry.api.v1.hwms.Controller.hwm_list")
    @mock.patch('daisy.db.sqlalchemy.api.host_get')
    @mock.patch('daisy.db.sqlalchemy.api.get_host_interface')
    @mock.patch('daisy.db.sqlalchemy.api.cluster_host_member_find')
    def test_get_host(self, mock_cluster_host_member_find,
                      mock_get_host_interface, mock_host_get, mock_hwm_list):
        id = 'd04cfa48-c3ad-477c-b2ac-95bee7582181'
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        self.db_api = daisy.db.get_api()
        mock_hwm_list.return_value = {}
        #controller = registry_hwm.Controller()
        #controller.hwm_list = mock.Mock(return_value={})
        host_role_ref = models.Host()
        mock_cluster_host_member_find.return_value = {}
        mock_host_get.return_value = host_role_ref
        mock_get_host_interface.return_value = {}
        #self.db_api.host_get = mock.Mock(return_value=host_role_ref)
        #self.db_api.get_host_interface = mock.Mock(return_value={})
        #self.db_api.cluster_host_member_find = mock.Mock(return_value={})
        utils.get_host_hw_info = mock.Mock(return_value={})
        host = self.controller.get_host(self.req, id)
        self.assertEqual(daisy.db.sqlalchemy.models.Host, type(host['host']))

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.host_update')
    @mock.patch('daisy.db.sqlalchemy.api.host_get')
    def test_add_host_with_config_set_notfound(self,
                                               mock_host_get,
                                               mock_host_update,
                                               mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218a'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218a'
        body = {"host": {'id': host_id,
                         'config_set_id': config_set_id}}
        mock_host_get.return_value = {'config_set_id': config_set_id}
        mock_host_update.return_value = {'id': host_id}
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.add_host(self.req, body)
        expect_host_meta = {'host': {'id': host_id}}
        self.assertEqual(actual_data, expect_host_meta)

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.host_update')
    @mock.patch('daisy.db.sqlalchemy.api.host_get')
    def test_add_host_with_config_set_forbidden(self,
                                                mock_host_get,
                                                mock_host_update,
                                                mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218b'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218b'
        body = {"host": {'id': host_id,
                         'config_set_id': config_set_id}}
        mock_host_get.return_value = {'config_set_id': config_set_id}
        mock_host_update.return_value = {'id': host_id}
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.add_host(self.req, body)
        expect_msg = "Forbidden to delete config_set %s" % config_set_id
        self.assertEqual(actual_data.message, expect_msg)

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.host_update')
    @mock.patch('daisy.db.sqlalchemy.api.host_get')
    def test_add_host_with_config_set_unable_delete(self,
                                                    mock_host_get,
                                                    mock_host_update,
                                                    mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218c'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218c'
        body = {"host": {'id': host_id,
                         'config_set_id': config_set_id}}
        mock_host_get.return_value = {'config_set_id': config_set_id}
        mock_host_update.return_value = {'id': host_id}
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.add_host(self.req, body)
        expect_msg = "Unable to delete config_set %s" % config_set_id
        self.assertEqual(actual_data.message, expect_msg)

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.role_host_member_delete')
    @mock.patch('daisy.db.sqlalchemy.api.cluster_host_member_find')
    @mock.patch('daisy.db.sqlalchemy.api.host_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.get_host_interface')
    def test_delete_host_with_config_set_notfound(
            self,
            mock_get_host_interface,
            mock_host_destroy,
            mock_cluster_host_member_find,
            mock_role_host_member_delete,
            mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218a'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218a'
        mock_get_host_interface.return_value = None
        host_meta = {'id': host_id, 'config_set_id': config_set_id}
        host_meta_ref = test_utils.DottableDict(host_meta)
        mock_host_destroy.return_value = host_meta_ref
        mock_cluster_host_member_find.return_value = None
        mock_role_host_member_delete.return_value = None
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.delete_host(self.req, host_id)
        self.assertEqual(actual_data, {'host': host_meta})

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.role_host_member_delete')
    @mock.patch('daisy.db.sqlalchemy.api.cluster_host_member_find')
    @mock.patch('daisy.db.sqlalchemy.api.host_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.get_host_interface')
    def test_delete_host_with_config_set_forbidden(
            self,
            mock_get_host_interface,
            mock_host_destroy,
            mock_cluster_host_member_find,
            mock_role_host_member_delete,
            mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218b'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218b'
        mock_get_host_interface.return_value = None
        host_meta = {'id': host_id, 'config_set_id': config_set_id}
        host_meta_ref = test_utils.DottableDict(host_meta)
        mock_host_destroy.return_value = host_meta_ref
        mock_cluster_host_member_find.return_value = None
        mock_role_host_member_delete.return_value = None
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.delete_host(self.req, host_id)
        expect_msg = "Forbidden to delete config_set %s" % config_set_id
        self.assertEqual(actual_data.message, expect_msg)

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.role_host_member_delete')
    @mock.patch('daisy.db.sqlalchemy.api.cluster_host_member_find')
    @mock.patch('daisy.db.sqlalchemy.api.host_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.get_host_interface')
    def test_delete_host_with_config_set_unable_delete(
            self,
            mock_get_host_interface,
            mock_host_destroy,
            mock_cluster_host_member_find,
            mock_role_host_member_delete,
            mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218c'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218c'
        mock_get_host_interface.return_value = None
        host_meta = {'id': host_id, 'config_set_id': config_set_id}
        host_meta_ref = test_utils.DottableDict(host_meta)
        mock_host_destroy.return_value = host_meta_ref
        mock_cluster_host_member_find.return_value = None
        mock_role_host_member_delete.return_value = None
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.delete_host(self.req, host_id)
        expect_msg = "Unable to delete config_set %s" % config_set_id
        self.assertEqual(actual_data.message, expect_msg)

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.host_update')
    @mock.patch('daisy.db.sqlalchemy.api.host_get')
    def test_update_host_with_config_set_notfound(self,
                                                  mock_host_get,
                                                  mock_host_update,
                                                  mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218a'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218a'
        body = {"host": {'config_set_id': config_set_id}}
        mock_host_get.return_value = {'config_set_id': config_set_id}
        mock_host_update.return_value = {'id': host_id}
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.update_host(self.req, host_id, body)
        expect_host_meta = {'host': {'id': host_id}}
        self.assertEqual(actual_data, expect_host_meta)

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.host_update')
    @mock.patch('daisy.db.sqlalchemy.api.host_get')
    def test_update_host_with_config_set_forbidden(self,
                                                   mock_host_get,
                                                   mock_host_update,
                                                   mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218b'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218b'
        body = {"host": {'config_set_id': config_set_id}}
        mock_host_get.return_value = {'config_set_id': config_set_id}
        mock_host_update.return_value = {'id': host_id}
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.update_host(self.req, host_id, body)
        expect_msg = "Forbidden to delete config_set %s" % config_set_id
        self.assertEqual(actual_data.message, expect_msg)

    @mock.patch('daisy.db.sqlalchemy.api.config_set_destroy')
    @mock.patch('daisy.db.sqlalchemy.api.host_update')
    @mock.patch('daisy.db.sqlalchemy.api.host_get')
    def test_update_host_with_config_set_unable_delete(
            self,
            mock_host_get,
            mock_host_update,
            mock_config_set_destroy):
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        host_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218c'
        config_set_id = 'd134fa48-c3ad-477c-b2ac-95bee758218c'
        body = {"host": {'config_set_id': config_set_id}}
        mock_host_get.return_value = {'config_set_id': config_set_id}
        mock_host_update.return_value = {'id': host_id}
        mock_config_set_destroy.side_effect = \
            fake_config_set_destroy(config_set_id)
        actual_data = self.controller.update_host(self.req, host_id, body)
        expect_msg = "Unable to delete config_set %s" % config_set_id
        self.assertEqual(actual_data.message, expect_msg)
