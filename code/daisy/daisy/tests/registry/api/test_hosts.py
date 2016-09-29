import mock
from daisy import test
import daisy.db
import webob
from daisy.context import RequestContext
from oslo.serialization import jsonutils
from daisy.common import exception
from daisy.common import utils
from daisyclient import client as daisy_client
from daisy.registry.api.v1 import hwms as registry_hwm
from daisy.registry.api.v1 import hosts as registry_hosts
from daisy.db.sqlalchemy import models


class TestHost(test.TestCase):
    def setUp(self):
        super(TestHost, self).setUp()

    def test_get_host(self):
        id = 'd04cfa48-c3ad-477c-b2ac-95bee7582181'
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        self.db_api = daisy.db.get_api()
        controller = registry_hwm.Controller()
        controller.hwm_list = mock.Mock(return_value={})
        host_role_ref = models.Host()
        self.db_api.host_get = mock.Mock(return_value=host_role_ref)
        self.db_api.get_host_interface = mock.Mock(return_value={})
        self.db_api.cluster_host_member_find = mock.Mock(return_value={})
        utils.get_host_hw_info = mock.Mock(return_value={})
        host_controller = registry_hosts.Controller()
        host = host_controller.get_host(self.req, id)
        self.assertEqual(daisy.db.sqlalchemy.models.Host, type(host['host']))
        self.assertEqual("", host['host'].position)

