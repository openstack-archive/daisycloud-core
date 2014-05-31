from daisy.context import RequestContext
import daisy.db
from daisy.db.sqlalchemy import models
from daisy.registry.api.v1 import networks as registry_networks
from daisy import test
import mock
import webob


class TestRegistryNetwork(test.TestCase):

    def setUp(self):
        super(TestRegistryNetwork, self).setUp()

    def test_get_assigned_networks_by_network_id(self):
        id = '1'
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(
            is_admin=True, user='fake user',
            tenant='fake tenant')
        self.db_api = daisy.db.get_api()
        assigned_network_ref = models.AssignedNetworks()
        self.db_api.get_assigned_networks_by_network_id = \
            mock.Mock(return_value=assigned_network_ref)
        registry_network_controller = registry_networks.Controller()
        assigned_network = \
            registry_network_controller.get_assigned_networks_by_network_id(
                self.req, id)
        self.assertEqual(daisy.db.sqlalchemy.models.AssignedNetworks,
                         type(assigned_network['network']))
