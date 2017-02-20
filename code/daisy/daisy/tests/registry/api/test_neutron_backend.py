from daisy.context import RequestContext
import daisy.db
from daisy.db.sqlalchemy import models
from daisy.registry.api.v1 import neutron_backend as registry_neutron_backend
from daisy import test
import webob


class TestRegistryNeutronBackend(test.TestCase):

    def setUp(self):
        super(TestRegistryNeutronBackend, self).setUp()
        self.controller = registry_neutron_backend.Controller()

    def test_neutron_backend_add(self):
        role_id = 'd04cfa48-c3ad-477c-b2ac-95bee758218b'
        neutron_backend_id = 'd134fa48-c3ad-477c-b2ac-95bee758218b'
        body = {'neutron_backend': {'role_id': role_id,
                                    'neutron_backend_id': neutron_backend_id}}
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(
            is_admin=True, user='fake user',
            tenant='fake tenant')
        self.db_api = daisy.db.get_api()
        assigned_neutron_backend_ref = models.NeutronBackend()
        neutron_backend = \
            self.controller.neutron_backend_add(
                self.req, body)
        self.assertEqual(daisy.db.sqlalchemy.models.NeutronBackend,
                         type(neutron_backend['neutron_backend']))
