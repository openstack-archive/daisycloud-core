
from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisyclient import exc as client_exc


class DaisyRoleNovaLvSizeTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyRoleNovaLvSizeTest, cls).resource_setup()
        cls.cluster_meta = {
            'description': 'desc',
            'name': 'test'
        }

        cls.role_meta = {'description': 'test'}

    def test_update_role_with_nova_lv_size(self):
        cluster_info = self.add_cluster(**self.cluster_meta)
        self.role_meta['cluster_id'] = cluster_info.id
        kwargs={'cluster_id':cluster_info.id}
        role_list_meta = {'filters': kwargs}
        list_role=self.list_roles(**role_list_meta)
        query_role_list = [role_info for role_info in list_role if role_info.name == 'COMPUTER']
        self.role_meta['nova_lv_size'] = 5120
        update_role_info = self.update_role(query_role_list[0].id, **self.role_meta)
        self.assertEqual(
            5120, update_role_info.nova_lv_size,
            "test_update_role_with_nova_lv_size failed")
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_nova_lv_size_for_no_cluster(self):
        cluster_info = self.add_cluster(**self.cluster_meta)
        kwargs={'cluster_id':cluster_info.id}
        role_list_meta = {'filters': kwargs}
        list_role=self.list_roles(**role_list_meta)
        query_role_list = [role_info for role_info in list_role if role_info.name == 'COMPUTER']
        self.role_meta['nova_lv_size'] = 5120
        self.assertRaisesMessage(
            client_exc.HTTPForbidden,
            "403 Forbidden: Access was denied to this resource.: "
            "The cluster_id parameter can not be None! (HTTP 403)",
            self.update_role, query_role_list[0].id, **self.role_meta)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_nova_lv_size_for_no_computer(self):
        cluster_info = self.add_cluster(**self.cluster_meta)
        kwargs={'cluster_id':cluster_info.id}
        role_list_meta = {'filters': kwargs}
        list_role=self.list_roles(**role_list_meta)
        query_role_list = [role_info for role_info in list_role if role_info.name == 'CONTROLLER_HA']
        self.role_meta['nova_lv_size'] = 5120
        self.assertRaisesMessage(
            client_exc.HTTPForbidden,
            "403 Forbidden: The role is not COMPUTER, it can't set logic"
            " volume disk for nova. (HTTP 403)",
            self.update_role, query_role_list[0].id, **self.role_meta)
        self.delete_cluster(cluster_info.id)

    def test_update_role_with_negative_nova_lv_size(self):
        cluster_info = self.add_cluster(**self.cluster_meta)
        kwargs={'cluster_id':cluster_info.id}
        role_list_meta = {'filters': kwargs}
        list_role=self.list_roles(**role_list_meta)
        query_role_list = [role_info for role_info in list_role if role_info.name == 'COMPUTER']
        self.role_meta ['nova_lv_size'] = -100
        self.assertRaisesMessage(
            client_exc.HTTPForbidden,
            "403 Forbidden: The nova_lv_size must be -1 or [0, N). "
            "(HTTP 403)",
            self.update_role, query_role_list[0].id, **self.role_meta)
        self.delete_cluster(cluster_info.id)

    def tearDown(self):
        if self.role_meta.get('nova_lv_size', None):
            del self.role_meta['nova_lv_size']
        if self.role_meta.get('nodes', None):
            for host_id in self.role_meta['nodes']:
                self.delete_ironic_discover_nodes(host_id)
            del self.role_meta['nodes']
        if self.role_meta.get('cluster_id', None):
            del self.role_meta['cluster_id']

        self._clean_all_host()
        self._clean_all_cluster()
        super(DaisyRoleNovaLvSizeTest, self).tearDown()

