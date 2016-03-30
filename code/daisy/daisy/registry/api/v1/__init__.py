# Copyright 2010-2011 OpenStack Foundation
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

from daisy.common import wsgi
from daisy.registry.api.v1 import members
from daisy.registry.api.v1 import hosts
from daisy.registry.api.v1 import config_files
from daisy.registry.api.v1 import config_sets
from daisy.registry.api.v1 import configs

from daisy.registry.api.v1 import networks
from daisy.registry.api.v1 import disk_array
from daisy.registry.api.v1 import template

def init(mapper):

    members_resource = members.create_resource()

    mapper.connect("/clusters/{cluster_id}/nodes/{host_id}",
                   controller=members_resource,
                   action="add_cluster_host",
                   conditions={'method': ['PUT']})
                   
    mapper.connect("/clusters/{cluster_id}/nodes/{host_id}",
                   controller=members_resource,
                   action="delete_cluster_host",
                   conditions={'method': ['DELETE']})
    mapper.connect("/clusters/{cluster_id}/nodes/{host_id}",
                   controller=members_resource,
                   action="get_cluster_hosts",
                   conditions={'method': ['GET']})
    mapper.connect("/clusters/{cluster_id}/nodes",
                   controller=members_resource,
                   action="get_cluster_hosts",
                   conditions={'method': ['GET']})
    mapper.connect("/multi_clusters/nodes/{host_id}",
                   controller=members_resource,
                   action="get_host_clusters",
                   conditions={'method': ['GET']})

    hosts_resource = hosts.create_resource()

    mapper.connect("/nodes",
                   controller=hosts_resource,
                   action="add_host",
                   conditions={'method': ['POST']})
                   
    mapper.connect("/nodes/{id}",
                   controller=hosts_resource,
                   action="delete_host",
                   conditions={'method': ['DELETE']})
                   
    mapper.connect("/nodes/{id}",
                   controller=hosts_resource,
                   action="update_host",
                   conditions={'method': ['PUT']})
                   
    mapper.connect("/nodes",
                   controller=hosts_resource,
                   action="detail_host",
                   conditions={'method': ['GET']})
                   
    mapper.connect("/nodes/{id}",
                   controller=hosts_resource,
                   action="get_host",
                   conditions=dict(method=["GET"]))
                   
    mapper.connect("/discover/nodes",
                   controller=hosts_resource,
                   action="add_discover_host",
                   conditions={'method': ['POST']})
    mapper.connect("/discover/nodes",
                   controller=hosts_resource,
                   action="detail_discover_host",
                   conditions={'method': ['GET']})
    mapper.connect("/discover/nodes/{id}",
                   controller=hosts_resource,
                   action="update_discover_host",
                   conditions={'method': ['PUT']})
                   
    mapper.connect("/discover/nodes/{discover_host_id}",
                   controller=hosts_resource,
                   action="get_discover_host",
                   conditions=dict(method=["GET"]))
                   
    mapper.connect("/discover/nodes/{id}",
                   controller=hosts_resource,
                   action="delete_discover_host",
                   conditions={'method': ['DELETE']})

    mapper.connect("/host-interface",
                   controller=hosts_resource,
                   action="get_host_interface",
                   conditions=dict(method=["GET"]))
    mapper.connect("/interfaces/{interface_id}/network/{network_id}",
                   controller=hosts_resource,
                   action="get_assigned_network",
                   conditions=dict(method=["GET"]))
    mapper.connect("/host-interfaces",
                   controller=hosts_resource,
                   action="get_all_host_interfaces",
                   conditions=dict(method=["PUT"]))

    mapper.connect("/clusters",
                   controller=hosts_resource,
                   action="add_cluster",
                   conditions={'method': ['POST']})
                   
    mapper.connect("/clusters/{id}",
                   controller=hosts_resource,
                   action="update_cluster",
                   conditions={'method': ['PUT']})

    mapper.connect("/clusters/{id}",
                   controller=hosts_resource,
                   action="delete_cluster",
                   conditions={'method': ['DELETE']})

    mapper.connect("/clusters",
                   controller=hosts_resource,
                   action='detail_cluster',
                   conditions={'method': ['GET']})
                       
    mapper.connect("/clusters/{id}",
                   controller=hosts_resource,
                   action="get_cluster",
                   conditions=dict(method=["GET"]))

                   
    mapper.connect("/components",
                   controller=hosts_resource,
                   action="add_component",
                   conditions={'method': ['POST']})
    mapper.connect("/components/{id}",
                   controller=hosts_resource,
                   action="delete_component",
                   conditions={'method': ['DELETE']})
    mapper.connect("/components/detail",
                   controller=hosts_resource,
                   action='detail_component',
                   conditions={'method': ['GET']})
    mapper.connect("/components/{id}",
                   controller=hosts_resource,
                   action="get_component",
                   conditions=dict(method=["GET"]))
    mapper.connect("/components/{id}",
                   controller=hosts_resource,
                   action="update_component",
                   conditions={'method': ['PUT']})
   
    mapper.connect("/services",
                   controller=hosts_resource,
                   action="add_service",
                   conditions={'method': ['POST']})
    mapper.connect("/services/{id}",
                   controller=hosts_resource,
                   action="delete_service",
                   conditions={'method': ['DELETE']})
    mapper.connect("/services/detail",
                   controller=hosts_resource,
                   action='detail_service',
                   conditions={'method': ['GET']})
    mapper.connect("/services/{id}",
                   controller=hosts_resource,
                   action="get_service",
                   conditions=dict(method=["GET"]))
    mapper.connect("/services/{id}",
                   controller=hosts_resource,
                   action="update_service",
                   conditions={'method': ['PUT']})

    mapper.connect("/roles",
                   controller=hosts_resource,
                   action="add_role",
                   conditions={'method': ['POST']})
    mapper.connect("/roles/{id}",
                   controller=hosts_resource,
                   action="delete_role",
                   conditions={'method': ['DELETE']})
    mapper.connect("/roles/detail",
                   controller=hosts_resource,
                   action='detail_role',
                   conditions={'method': ['GET']})
    mapper.connect("/roles/{id}",
                   controller=hosts_resource,
                   action="get_role",
                   conditions=dict(method=["GET"]))
    mapper.connect("/roles/{id}",
                   controller=hosts_resource,
                   action="update_role",
                   conditions={'method': ['PUT']})
    mapper.connect("/roles/{id}/services",
                   controller=hosts_resource,
                   action="role_services",
                   conditions={'method': ['GET']}) 
    mapper.connect("/roles/{id}/hosts",
                   controller=hosts_resource,
                   action="host_roles",
                   conditions={'method': ['GET']}) 
    mapper.connect("/roles/{id}/hosts",
                   controller=hosts_resource,
                   action="delete_role_hosts",
                   conditions={'method': ['DELETE']})
    mapper.connect("/roles/{id}/hosts",
                   controller=hosts_resource,
                   action="update_role_hosts",
                   conditions={'method': ['PUT']})
                   
    config_files_resource = config_files.create_resource()

    mapper.connect("/config_files",
                   controller=config_files_resource,
                   action="add_config_file",
                   conditions={'method': ['POST']})
                   
    mapper.connect("/config_files/{id}",
                   controller=config_files_resource,
                   action="delete_config_file",
                   conditions={'method': ['DELETE']})
                   
    mapper.connect("/config_files/{id}",
                   controller=config_files_resource,
                   action="update_config_file",
                   conditions={'method': ['PUT']})
                   
    mapper.connect("/config_files/detail",
                   controller=config_files_resource,
                   action="detail_config_file",
                   conditions={'method': ['GET']})
                   
    mapper.connect("/config_files/{id}",
                   controller=config_files_resource,
                   action="get_config_file",
                   conditions=dict(method=["GET"]))    

    config_sets_resource = config_sets.create_resource()

    mapper.connect("/config_sets",
                   controller=config_sets_resource,
                   action="add_config_set",
                   conditions={'method': ['POST']})
                   
    mapper.connect("/config_sets/{id}",
                   controller=config_sets_resource,
                   action="delete_config_set",
                   conditions={'method': ['DELETE']})
                   
    mapper.connect("/config_sets/{id}",
                   controller=config_sets_resource,
                   action="update_config_set",
                   conditions={'method': ['PUT']})
                   
    mapper.connect("/config_sets/detail",
                   controller=config_sets_resource,
                   action="detail_config_set",
                   conditions={'method': ['GET']})
                   
    mapper.connect("/config_sets/{id}",
                   controller=config_sets_resource,
                   action="get_config_set",
                   conditions=dict(method=["GET"]))

    configs_resource = configs.create_resource()

    mapper.connect("/configs",
                   controller=configs_resource,
                   action="add_config",
                   conditions={'method': ['POST']})
                   
    mapper.connect("/configs/{id}",
                   controller=configs_resource,
                   action="delete_config",
                   conditions={'method': ['DELETE']})
                   
    mapper.connect("/configs/{id}",
                   controller=configs_resource,
                   action="update_config",
                   conditions={'method': ['PUT']})

    mapper.connect("/configs/update_config_by_role_hosts",
               controller=configs_resource,
               action="update_config_by_role_hosts",
               conditions={'method': ['POST']})

    mapper.connect("/configs/detail",
                   controller=configs_resource,
                   action="detail_config",
                   conditions={'method': ['GET']})
                   
    mapper.connect("/configs/{id}",
                   controller=configs_resource,
                   action="get_config",
                   conditions=dict(method=["GET"])) 
                   
    networks_resource = networks.create_resource()                   

    mapper.connect("/clusters/{id}/networks",
                   controller=networks_resource,
                   action="detail_network",
                   conditions={'method': ['GET']})

    mapper.connect("/networks",
                   controller=networks_resource,
                   action="get_all_networks",
                   conditions={'method': ['GET']})

    # mapper.resource('network', 'networks',controller=networks_resource,
    #                 collection={'update_phyname_of_network':'POST', 'add_network':"POST"},
    #                 member={'get_network':'GET', 'update_network':'PUT', 'delete_network':'DELETE'})

    mapper.connect("/networks",
                   controller=networks_resource,
                   action="add_network",
                   conditions={'method': ['POST']})

    mapper.connect("/networks/{network_id}",
                   controller=networks_resource,
                   action="delete_network",
                   conditions={'method': ['DELETE']})

    mapper.connect("/networks/{network_id}",
                   controller=networks_resource,
                   action="update_network",
                   conditions={'method': ['PUT']})

    mapper.connect("/networks/{id}",
                   controller=networks_resource,
                   action="get_network",
                   conditions=dict(method=["GET"]))

    mapper.connect("/networks/update_phyname_of_network",
               controller=networks_resource,
               action="update_phyname_of_network",
               conditions=dict(method=["POST"]))

    config_interface_resource = hosts.create_resource()

    mapper.connect("/config_interface",
                   controller=config_interface_resource,
                   action="config_interface",
                   conditions={'method': ['POST']})

    array_resource = disk_array.create_resource()    
    mapper.connect("/service_disk",
                   controller=array_resource,
                   action='service_disk_add',
                   conditions={'method': ['POST']})
    mapper.connect("/service_disk/{id}",
                   controller=array_resource,
                   action='service_disk_delete',
                   conditions={'method': ['DELETE']})
    mapper.connect("/service_disk/{id}",
                   controller=array_resource,
                   action='service_disk_update',
                   conditions={'method': ['PUT']})
    mapper.connect("/service_disk/list",
                   controller=array_resource,
                   action='service_disk_list',
                   conditions={'method': ['GET']})
    mapper.connect("/service_disk/{id}",
                   controller=array_resource,
                   action='service_disk_detail',
                   conditions={'method': ['GET']})
                   
    mapper.connect("/cinder_volume",
                   controller=array_resource,
                   action='cinder_volume_add',
                   conditions={'method': ['POST']})
    mapper.connect("/cinder_volume/{id}",
                   controller=array_resource,
                   action='cinder_volume_delete',
                   conditions={'method': ['DELETE']})
    mapper.connect("/cinder_volume/{id}",
                   controller=array_resource,
                   action='cinder_volume_update',
                   conditions={'method': ['PUT']})
    mapper.connect("/cinder_volume/list",
                   controller=array_resource,
                   action='cinder_volume_list',
                   conditions={'method': ['GET']})
    mapper.connect("/cinder_volume/{id}",
                   controller=array_resource,
                   action='cinder_volume_detail',
                   conditions={'method': ['GET']})
    
    template_resource = template.create_resource()   
    mapper.connect("/template",
                   controller=template_resource,
                   action='template_add',
                   conditions={'method': ['POST']})
    mapper.connect("/template/{template_id}",
                   controller=template_resource,
                   action='template_update',
                   conditions={'method': ['PUT']})
    mapper.connect("/template/{template_id}",
                   controller=template_resource,
                   action='template_delete',
                   conditions={'method': ['DELETE']})
    mapper.connect("/template/list",
                   controller=template_resource,
                   action='template_list',
                   conditions={'method': ['GET']})
    mapper.connect("/template/{template_id}",
                   controller=template_resource,
                   action='template_detail',
                   conditions={'method': ['GET']})

    mapper.connect("/host_template",
                   controller=template_resource,
                   action='host_template_add',
                   conditions={'method': ['POST']})
    mapper.connect("/host_template/{template_id}",
                   controller=template_resource,
                   action='host_template_update',
                   conditions={'method': ['PUT']})
    mapper.connect("/host_template/{template_id}",
                   controller=template_resource,
                   action='host_template_delete',
                   conditions={'method': ['DELETE']})
    mapper.connect("/host_template/list",
                   controller=template_resource,
                   action='host_template_list',
                   conditions={'method': ['GET']})
    mapper.connect("/host_template/{template_id}",
                   controller=template_resource,
                   action='host_template_detail',
                   conditions={'method': ['GET']}) 
                   
class API(wsgi.Router):
    """WSGI entry point for all Registry requests."""

    def __init__(self, mapper):
        mapper = mapper or wsgi.APIMapper()

        init(mapper)

        super(API, self).__init__(mapper)
