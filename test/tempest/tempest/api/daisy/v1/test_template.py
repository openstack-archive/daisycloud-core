
from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception
from daisyclient import exc as client_exc
import copy

class DaisyTemplateTest(base.BaseDaisyTest):
    @classmethod
    def resource_setup(cls):
        super(DaisyTemplateTest, cls).resource_setup()

    def test_template_add(self):
        template = {'name':'template', 'type':'tecs'}
        template_add = self.template_add(**template)
        self.assertEqual('tecs', template_add.type, "test_template_add failed")
        self.template_delete(template_add.id)
    
    def test_template_update(self):
        template = {'name':'template', 'type':'tecs'}
        template_add = self.template_add(**template)
        update_info = {'content':'cluster_info', 'hosts':'host_template'}
        template_update = self.template_update(template_add.id, **update_info)
        self.assertEqual('tecs', template_update.type, "test_template_update failed")
        self.assertEqual('cluster_info', template_update.content, "test_template_update failed")
        self.template_delete(template_add.id)
        
    def test_template_detail(self):
        template = {'name':'template_cluster', 'type':'zenic'}
        template_add = self.template_add(**template)
        template_detail = self.template_detail(template_add.id)
        self.assertEqual('zenic', template_detail.type, "template_detail failed")
        self.assertEqual('template_cluster', template_detail.name, "template_detail failed")
        self.template_delete(template_add.id)
        
    def test_template_list(self):
        template = {'name':'template_cluster', 'type':'zenic'}
        template_add1 = self.template_add(**template)
        template = {'name':'template_cluster2', 'type':'zenic'}
        template_add2 = self.template_add(**template)
        filter={'type':'zenic'}
        template_lists = self.template_list(filter=filter)
        flag = True
        for template in template_lists:
            if template.type != 'zenic':
                falg = False
        self.assertEqual(True, flag, "template_list failed")
        self.template_delete(template_add1.id)
        self.template_delete(template_add2.id)
        
    def test_template_delete(self):
        template = {'name':'template_cluster', 'type':'zenic'}
        template_add = self.template_add(**template)
        self.template_delete(template_add.id)

    def test_export_db_to_json(self):
        cluster_meta = {'name':'test', 'description':'nothing'}
        cluster_info = self.add_cluster(**cluster_meta)
        kwargs = {'cluster_name': u'test', 'template_name': u'template'}
        template_info = self.export_db_to_json(**kwargs)
        self.assertEqual('template', template_info.name, "export_db_to_json failed")

        
    def test_import_json_to_template(self):
        #kwargs = {'template': '{"name": "template", "content": {"cluster": {"description": "nothing", "routers": [], "logic_networks": [], "owner": null, "auto_scale": 0, "networking_parameters": {"vni_range": [null, null], "public_vip": null, "net_l23_provider": null, "base_mac": null, "gre_id_range": [null, null], "vlan_range": [null, null], "segmentation_type": null}}, "networks": [{"description": "For vxlan interactive", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": null, "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "VXLAN", "type": "default", "gateway": null, "vlan_id": null, "name": "VXLAN"}, {"description": "Network plane for vms", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": "ovs", "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "PRIVATE", "type": "default", "gateway": null, "vlan_id": null, "name": "PRIVATE"}, {"description": "For public api", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "PUBLIC", "type": "default", "gateway": null, "vlan_id": null, "name": "PUBLIC"}, {"description": "Storage network plane", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "STORAGE", "type": "default", "gateway": null, "vlan_id": null, "name": "STORAGE"}, {"description": "For external interactive", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "EXTERNAL", "type": "default", "gateway": null, "vlan_id": null, "name": "EXTERNAL"}, {"description": "For internal API and AMQP", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "MANAGEMENT", "type": "default", "gateway": null, "vlan_id": null, "name": "MANAGEMENT"}, {"description": "For deploy the infrastructure", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "DEPLOYMENT", "type": "default", "gateway": null, "vlan_id": null, "name": "DEPLOYMENT"}], "roles": [{"config_set_id": "testCONTROLLER_HA", "deployment_backend": "tecs", "description": "Controller role,backup type is HA,active/standby", "disk_location": "local", "glance_lv_size": 0, "vip": null, "db_lv_size": 0, "ntp_server": null, "type": "default", "nova_lv_size": 0, "name": "CONTROLLER_HA"}, {"config_set_id": "testCOMPUTER", "deployment_backend": "tecs", "description": "Compute role", "disk_location": "local", "glance_lv_size": 0, "vip": null, "db_lv_size": 0, "ntp_server": null, "type": "default", "nova_lv_size": 0, "name": "COMPUTER"}, {"config_set_id": "testCONTROLLER_LB", "deployment_backend": "tecs", "description": "Controller role,backup type is loadbalance", "disk_location": "local", "glance_lv_size": 0, "vip": null, "db_lv_size": 0, "ntp_server": null, "type": "default", "nova_lv_size": 0, "name": "CONTROLLER_LB"}], "cinder_volumes": [],"services_disk":[]}, "hosts": "", "type": "tecs", "description": null}'}
        kwargs = {'template': '{"name": "template", "content": {"cluster": {"description": "nothing","name": "template_Clsuter"}},"hosts": "","type": "tecs","description": "nothing"}'}
        template_info = self.import_json_to_template(**kwargs)
        self.assertEqual('template', template_info.name, "export_db_to_json failed")
        self.template_delete(template_info.id)
        
    def test_import_template_to_db(self):
        kwargs = {'template': '{"name": "template", "content": {"cluster": {"description": "nothing", "routers": [], "logic_networks": [], "owner": null, "auto_scale": 0, "networking_parameters": {"vni_range": [null, null], "public_vip": null, "net_l23_provider": null, "base_mac": null, "gre_id_range": [null, null], "vlan_range": [null, null], "segmentation_type": null}}, "networks": [{"description": "For vxlan interactive", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": null, "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "VXLAN", "type": "default", "gateway": null, "vlan_id": null, "name": "VXLAN"}, {"description": "Network plane for vms", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": "ovs", "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "PRIVATE", "type": "default", "gateway": null, "vlan_id": null, "name": "PRIVATE"}, {"description": "For public api", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "PUBLIC", "type": "default", "gateway": null, "vlan_id": null, "name": "PUBLIC"}, {"description": "Storage network plane", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "STORAGE", "type": "default", "gateway": null, "vlan_id": null, "name": "STORAGE"}, {"description": "For external interactive", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "EXTERNAL", "type": "default", "gateway": null, "vlan_id": null, "name": "EXTERNAL"}, {"description": "For internal API and AMQP", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "MANAGEMENT", "type": "default", "gateway": null, "vlan_id": null, "name": "MANAGEMENT"}, {"description": "For deploy the infrastructure", "alias": null, "ip": null, "ip_ranges": [], "mtu": 1500, "capability": "high", "physnet_name": null, "ml2_type": null, "vlan_end": 4094, "vlan_start": 1, "cidr": "192.168.1.1/24", "network_type": "DEPLOYMENT", "type": "default", "gateway": null, "vlan_id": null, "name": "DEPLOYMENT"}], "roles": [{"config_set_id": "testCONTROLLER_HA", "deployment_backend": "tecs", "description": "Controller role,backup type is HA,active/standby", "disk_location": "local", "glance_lv_size": 0, "vip": null, "db_lv_size": 0, "ntp_server": null, "type": "default", "nova_lv_size": 0, "name": "CONTROLLER_HA"}, {"config_set_id": "testCOMPUTER", "deployment_backend": "tecs", "description": "Compute role", "disk_location": "local", "glance_lv_size": 0, "vip": null, "db_lv_size": 0, "ntp_server": null, "type": "default", "nova_lv_size": 0, "name": "COMPUTER"}, {"config_set_id": "testCONTROLLER_LB", "deployment_backend": "tecs", "description": "Controller role,backup type is loadbalance", "disk_location": "local", "glance_lv_size": 0, "vip": null, "db_lv_size": 0, "ntp_server": null, "type": "default", "nova_lv_size": 0, "name": "CONTROLLER_LB"}], "cinder_volumes": [], "services_disk":[]}, "hosts": "", "type": "tecs", "description": null}'}
        #kwargs = {'template': '{"name": "template", "content": {"cluster": {"description": "nothing","name": "template_clsuter"}},"hosts": "","type": "tecs","description": "nothing"}'}
        template_info = self.import_json_to_template(**kwargs)
        self.assertEqual('template', template_info.name, "import_template_to_db failed")
        
        template_kwargs = {'template_name': u'template', 'cluster': u'db_template_cluster'}
        template_db_info = self.import_template_to_db(**template_kwargs)
        self.assertEqual('db_template_cluster', template_db_info.name, "import_template_to_db failed")
        filter_cluster_meta = {'name': "db_template_cluster"}
        list_clusters = self.list_filter_clusters(**filter_cluster_meta)
        flag=True
        for cluster in list_clusters:
            if cluster.name != 'db_template_cluster':
                flag = False
                break
        self.assertEqual(True, flag, "import_template_to_db failed")
        
        self.template_delete(template_info.id)
        
    def tearDown(self):
        self._clean_all_template()
        self._clean_all_cluster()
        super(DaisyTemplateTest, self).tearDown()
        
