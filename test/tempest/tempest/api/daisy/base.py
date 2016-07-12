# Copyright 2013 IBM Corp.
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

from oslo_log import log as logging
from six import moves

from tempest import config
import tempest.test
from nose.tools import set_trace
from daisyclient.v1 import client as daisy_client
from daisyclient.common import utils
import copy
from ironicclient import client as ironic_client

CONF = config.CONF

LOG = logging.getLogger(__name__)


class BaseDaisyTest(tempest.test.BaseTestCase):

    @classmethod
    def skip_checks(cls):
        super(BaseDaisyTest, cls).skip_checks()

    @classmethod
    def resource_setup(cls):
        super(BaseDaisyTest, cls).resource_setup()
        cls.daisy_version = 1.0
        cls.daisy_endpoint=CONF.daisy.daisy_endpoint
        cls.daisy_client = daisy_client.Client(version=cls.daisy_version, endpoint=cls.daisy_endpoint)
        cls.ironic_client=ironic_client.get_client(1, os_auth_token='fake',ironic_url='http://127.0.0.1:6385/v1')

    @classmethod
    def resource_cleanup(cls):
        super(BaseDaisyTest, cls).resource_cleanup()

    @classmethod
    def add_cluster(self, **cluster_meta):
        add_cluster_info = self.daisy_client.clusters.add(**cluster_meta)
        return add_cluster_info

    @classmethod
    def update_cluster(self, cluster_id, **cluster_meta):
        update_cluster_info = self.daisy_client.clusters.update(cluster_id, **cluster_meta)
        return update_cluster_info

    @classmethod
    def list_clusters(self, **cluster_meta):
        #cluster_meta['filters'] = cluster_meta
        clusters_info = self.daisy_client.clusters.list(**cluster_meta)
        return clusters_info

    @classmethod
    def list_filter_clusters(self, **cluster_meta):
        cluster_meta['filters'] = cluster_meta
        clusters_info = self.daisy_client.clusters.list(**cluster_meta)
        return clusters_info

    @classmethod
    def get_cluster(self, cluster_id):
        cluster_info = self.daisy_client.clusters.get(cluster_id)
        return cluster_info

    @classmethod
    def _clean_all_cluster(self):
        clusters_list_generator = self.daisy_client.clusters.list()
        clusters_list = [clusters for clusters in clusters_list_generator]
        if clusters_list:
            for cluster in clusters_list:
                self.delete_cluster(cluster)

    @classmethod
    def add_hwm(self, **hwm_meta):
        hwm_info = self.daisy_client.hwm.add(**hwm_meta)
        return hwm_info

    @classmethod
    def delete_hwm(self, hwm_meta):
        self.daisy_client.hwm.delete(hwm_meta)

    @classmethod
    def update_hwm(self, hwm_id, **hwm_meta):
        hwm_info = self.daisy_client.hwm.update(hwm_id, **hwm_meta)
        return hwm_info

    @classmethod
    def _clean_all_hwm(self):
        hwm_list_generator = self.daisy_client.hwm.list()
        hwm_list = [hwms for hwms in hwm_list_generator]
        if hwm_list:
            for hwm in hwm_list:
                self.delete_hwm(hwm)

    @classmethod
    def list_hwm(self, **hwm_meta):
        hwm_meta['filters'] = hwm_meta
        hwm_list = self.daisy_client.hwm.list(**hwm_meta)
        return hwm_list

    @classmethod
    def get_hwm_detail(self, hwm_meta):
        hwm_detail = self.daisy_client.hwm.get(hwm_meta)
        return hwm_detail

    @classmethod
    def add_host(self, **host_meta):
        host_info = self.daisy_client.hosts.add(**host_meta)
        return host_info

    @classmethod
    def delete_host(self, host_meta):
        self.daisy_client.hosts.delete(host_meta)

    @classmethod
    def update_host(self, host_id,**host_meta):
        host_info = self.daisy_client.hosts.update(host_id,**host_meta)
        return host_info

    @classmethod
    def _clean_all_host(self):
        hosts_list_generator = self.daisy_client.hosts.list()
        hosts_list = [hosts for hosts in hosts_list_generator]
        if hosts_list:
            for host in hosts_list:
                self.delete_host(host)

    @classmethod
    def list_host(self, **host_meta):
        host_meta['filters']=host_meta
        host_list = self.daisy_client.hosts.list(**host_meta)
        return host_list

    @classmethod
    def get_host_detail(self, host_meta):
        host_detail = self.daisy_client.hosts.get(host_meta)
        return host_detail

    @classmethod
    def add_discover_host(self, **host_meta):
        host_info = self.daisy_client.hosts.add_discover_host(**host_meta)
        return host_info

    @classmethod
    def update_discover_host(self, host_id, **host_meta):
        host_info = self.daisy_client.hosts.update_discover_host(host_id,**host_meta)
        return host_info

    @classmethod
    def delete_discover_host(self, host_meta):
        self.daisy_client.hosts.delete_discover_host(host_meta)

    @classmethod
    def list_discover_host(self, **host_meta):
        host_meta['filters']=host_meta
        host_list = self.daisy_client.hosts.list_discover_host(**host_meta)
        return host_list

    @classmethod
    def get_discover_host_detail(self, host_meta):
        host_detail = self.daisy_client.hosts.get_discover_host_detail(host_meta)
        return host_detail

    @classmethod
    def discover_host(self, **host_meta):
        host_discovery = self.daisy_client.hosts.discover_host(**host_meta)
        return host_discovery

    @classmethod
    def _clean_all_discover_host(self):
        host_meta = {}
        hosts_list_generator = self.daisy_client.hosts.list_discover_host(**host_meta)
        hosts_list = [hosts for hosts in hosts_list_generator]
        if hosts_list:
            for host in hosts_list:
                self.delete_discover_host(host)

    @classmethod
    def add_network(self, **network_meta):
        network_info = self.daisy_client.networks.add(**network_meta)
        return network_info

    @classmethod
    def get_network(self, network_id):
        network_info = self.daisy_client.networks.get(network_id)
        return network_info

    @classmethod
    def list_network(self, **network_meta):
        network = {'sort_key': 'name', 'sort_dir': 'asc','filters':network_meta}
        network_infos = self.daisy_client.networks.list(**network)
        return network_infos

    @classmethod
    def update_network(self, network_id , **network_meta):
        network_info = self.daisy_client.networks.update(network_id , **network_meta)
        return network_info

    @classmethod
    def delete_network(self, network_id):
        self.daisy_client.networks.delete(network_id)

    @classmethod
    def list_roles(self, **role_meta):
        roles_info = self.daisy_client.roles.list(**role_meta)
        return roles_info

    @classmethod
    def add_role(self, **role_meta):
        roles_info = self.daisy_client.roles.add(**role_meta)
        return roles_info

    @classmethod
    def get_role(self, role_id):
        role_info = self.daisy_client.roles.get(role_id)
        return role_info

    @classmethod
    def delete_role(self, role_id):
        self.daisy_client.roles.delete(role_id)

    @classmethod
    def update_role(self, role_id, **role_meta):
        role_info = self.daisy_client.roles.update(role_id, **role_meta)
        return role_info

    @classmethod
    def install(self, **install_meta):
        install_info = self.daisy_client.install.install(**install_meta)
        return install_info

    @classmethod
    def get_cluster_id(self, cluster_meta):
        if not cluster_meta:
            cluster_list = self.daisy_client.clusters.list()
            for cluster in cluster_list:
                cluster_id={'cluster_id':cluster.id}
        else:
            cluster_id={'cluster_id':cluster_meta}
        return cluster_id

    @classmethod
    def get_uninstall_status(self, **cluster_id):
        nodes=self.daisy_client.uninstall.query_progress(**cluster_id)
        return nodes

    @classmethod
    def delete_cluster(self, cluster_meta):
        self.daisy_client.clusters.delete(cluster_meta)

    @classmethod
    def uninstall(self, **cluster_id):
        self.daisy_client.uninstall.uninstall(**cluster_id)

    @classmethod
    def update(self, **cluster_id):
        self.daisy_client.update.update(**cluster_id)

    @classmethod
    def get_update_status(self, **cluster_id):
        nodes=self.daisy_client.update.query_progress(**cluster_id)
        return nodes

    @classmethod
    def list_components(self, **component_meta):
        components_info = self.daisy_client.components.list(**component_meta)
        return components_info

    @classmethod
    def add_component(self, component_id, **component_meta):
        component_info = self.daisy_client.components.add(component_id ,**component_meta)
        return component_info

    @classmethod
    def get_component(self, component_id):
        component_info = self.daisy_client.components.get(component_id)
        return component_info

    @classmethod
    def update_component(self, component_id, **component_meta):
        component_info = self.daisy_client.components.update(component_id, **component_meta)
        return component_info

    @classmethod
    def add_config(self, **config_meta):
        config_info = self.daisy_client.configs.add(**config_meta)
        return config_info

    @classmethod
    def get_config(self,config_id):
        config_meta={}
        config_info = self.daisy_client.configs.get(config_id,**config_meta)
        return config_info

    def delete_config(self,config_id):
        config={'config':[config_id]}
        self.daisy_client.configs.delete(**config)

    @classmethod
    def _clean_all_config(self):
        configs_list_generator = self.daisy_client.configs.list()
        configs_list = [configs for configs in configs_list_generator]
        if configs_list:
            for config in configs_list:
                config={'config':[config.id]}
                self.daisy_client.configs.delete(**config)
    @classmethod
    def list_config(self):
        configs_list = self.daisy_client.configs.list()
        return configs_list

    @classmethod
    def cluster_config_set_update(self,**config_set):
        config_set=self.daisy_client.config_sets.cluster_config_set_update(**config_set)
        return config_set

    @classmethod
    def cluster_config_set_progress(self,**config_set):
        config_set=self.daisy_client.config_sets.cluster_config_set_progress(**config_set)
        return config_set

    @classmethod
    def add_config_set(self,**config_set):
        config_set=self.daisy_client.config_sets.add(**config_set)
        return config_set

    @classmethod
    def update_config_set(self,config_set_id,**config_set):
        config_set=self.daisy_client.config_sets.update(config_set_id,**config_set)
        return config_set

    @classmethod
    def get_config_set(self,config_set_id):
        config_set=self.daisy_client.config_sets.get(config_set_id)
        return config_set

    def list_config_set(self):
        config_set_list=self.daisy_client.config_sets.list()
        return config_set_list

    def delete_config_set(self, config_set_id):
        self.daisy_client.config_sets.delete(config_set_id)

    @classmethod
    def _clean_all_config_set(self):
        config_set_list_generator = self.daisy_client.config_sets.list()
        config_set_list = [config_set for config_set in config_set_list_generator]
        if config_set_list:
            for config_set in config_set_list:
                self.daisy_client.config_sets.delete(config_set.id)

    @classmethod
    def add_config_file(self,**config_file):
        config_file=self.daisy_client.config_files.add(**config_file)
        return config_file

    @classmethod
    def update_config_file(self,config_file_id,**config_file):
        config_file=self.daisy_client.config_files.update(config_file_id,**config_file)
        return config_file

    @classmethod
    def get_config_file(self,config_file_id):
        config_file=self.daisy_client.config_files.get(config_file_id)
        return config_file

    def list_config_file(self):
        config_file_list=self.daisy_client.config_files.list()
        return config_file_list

    def delete_config_file(self, config_file_id):
        self.daisy_client.config_files.delete(config_file_id)

    @classmethod
    def _clean_all_config_file(self):
        config_file_list_generator = self.daisy_client.config_files.list()
        config_file_list = [config_file for config_file in config_file_list_generator]
        if config_file_list:
            for config_file in config_file_list:
                self.daisy_client.config_files.delete(config_file.id)

    @classmethod
    def list_service(self, **service_meta):
        services_info = self.daisy_client.services.list(**service_meta)
        return services_info

    @classmethod
    def add_service(self, **service_meta):
        service_info = self.daisy_client.services.add(**service_meta)
        return service_info

    @classmethod
    def get_service(self, service_id):
        service_info = self.daisy_client.services.get(service_id)
        return service_info

    @classmethod
    def delete_service(self, service_id):
        self.daisy_client.services.delete(service_id)

    @classmethod
    def update_service(self, service_id, **service_meta):
        service_info = self.daisy_client.services.update(service_id, **service_meta)
        return service_info

    @classmethod
    def list_component(self, **component_meta):
        components_info = self.daisy_client.components.list(**component_meta)
        return components_info

    @classmethod
    def add_component(self, **component_meta):
        component_info = self.daisy_client.components.add(**component_meta)
        return component_info

    @classmethod
    def get_component(self, component_id):
        component_info = self.daisy_client.components.get(component_id)
        return component_info

    @classmethod
    def delete_component(self, component_id):
        self.daisy_client.components.delete(component_id)

    @classmethod
    def update_component(self, component_id, **component_meta):
        component_info = self.daisy_client.components.update(component_id, **component_meta)
        return component_info

    @classmethod
    def add_cinder_volume(self, **cinder_volume_meta):
        cinder_volume_info = self.daisy_client.disk_array.cinder_volume_add(**cinder_volume_meta)
        return cinder_volume_info

    @classmethod
    def update_cinder_volume(self, cinder_volume_id, **cinder_volume_meta):
        cinder_volume_info = self.daisy_client.disk_array.cinder_volume_update(cinder_volume_id,**cinder_volume_meta)
        return cinder_volume_info

    @classmethod
    def delete_cinder_volume(self, cinder_volume_id):
        self.daisy_client.disk_array.cinder_volume_delete(cinder_volume_id)

    @classmethod
    def list_cinder_volume(self, **cinder_volume_meta):
        cinder_volume_meta['filters']=cinder_volume_meta
        cinder_volume_list = self.daisy_client.disk_array.cinder_volume_list(**cinder_volume_meta)
        return cinder_volume_list

    @classmethod
    def get_cinder_volume_detail(self, cinder_volume_id):
        cinder_volume_info = self.daisy_client.disk_array.cinder_volume_detail(cinder_volume_id)
        return cinder_volume_info

    @classmethod
    def add_service_disk(self, **service_disk_meta):
        service_disk_info = self.daisy_client.disk_array.service_disk_add(**service_disk_meta)
        return service_disk_info

    @classmethod
    def update_service_disk(self, service_disk_id, **service_disk_meta):
        service_disk_info = self.daisy_client.disk_array.service_disk_update(service_disk_id,**service_disk_meta)
        return service_disk_info

    @classmethod
    def delete_service_disk(self, service_disk_id):
        self.daisy_client.disk_array.service_disk_delete(service_disk_id)

    @classmethod
    def list_service_disk(self, **service_disk_meta):
        service_disk_meta['filters']=service_disk_meta
        service_disk_list = self.daisy_client.disk_array.service_disk_list(**service_disk_meta)
        return service_disk_list

    @classmethod
    def get_service_disk_detail(self, service_disk_id):
        service_disk_detail = self.daisy_client.disk_array.service_disk_detail(service_disk_id)
        return service_disk_detail

    @classmethod
    def _clean_all_physical_node(self):
        physical_node_list_generator = self.ironic_client.physical_node.list()
        physical_node_list = [physical_node for physical_node in physical_node_list_generator]
        if physical_node_list:
            for physical_node in physical_node_list:
                self.ironic_client.physical_node.delete(physical_node.uuid)

    @classmethod
    def template_add(self, **template):
        template = self.daisy_client.template.add(**template)
        return template

    @classmethod
    def template_update(self, template_id, **template):
        template = self.daisy_client.template.update(template_id, **template)
        return template

    @classmethod
    def template_detail(self, template_id):
        template = self.daisy_client.template.get(template_id)
        return template

    @classmethod
    def template_list(self, **kwargs):
        template = self.daisy_client.template.list(**kwargs)
        return template

    @classmethod
    def template_delete(self, template_id):
        template = self.daisy_client.template.delete(template_id)
        return template

    @classmethod
    def export_db_to_json(self, **kwargs):
        template = self.daisy_client.template.export_db_to_json(**kwargs)
        return template

    @classmethod
    def import_json_to_template(self, **kwargs):
        template = self.daisy_client.template.import_json_to_template(**kwargs)
        return template
        import_template_to_db

    @classmethod
    def import_template_to_db(self, **kwargs):
        template = self.daisy_client.template.import_template_to_db(**kwargs)
        return template

    @classmethod
    def _clean_all_template(self):
        template_generator = self.daisy_client.template.list()
        templates = [template for template in template_generator]
        if templates:
            for template in templates:
                self.template_delete(template.id)

    @classmethod
    def host_to_template(self, **kwargs):
        host_template = self.daisy_client.template.host_to_template(**kwargs)
        return host_template

    @classmethod
    def template_to_host(self, **kwargs):
        hosts = self.daisy_client.template.template_to_host(**kwargs)
        return hosts

    @classmethod
    def host_template_list(self, **kwargs):
        host_templates = self.daisy_client.template.host_template_list(**kwargs)
        return host_templates

    @classmethod
    def delete_host_template(self, **kwargs):
        template = self.daisy_client.template.delete_host_template(**kwargs)
        return template
