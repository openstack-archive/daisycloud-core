# Copyright 2011 OpenStack Foundation
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


#from daisy.api.v1 import images
from daisy.api.v1 import hosts
from daisy.api.v1 import clusters
from daisy.api.v1 import template
from daisy.api.v1 import components
from daisy.api.v1 import services
from daisy.api.v1 import roles
from daisy.api.v1 import members
from daisy.api.v1 import config_files
from daisy.api.v1 import config_sets
from daisy.api.v1 import configs
from daisy.api.v1 import networks
from daisy.api.v1 import install
from daisy.api.v1 import disk_array
from daisy.api.v1 import host_template
from daisy.common import wsgi

class API(wsgi.Router):

    """WSGI router for Glance v1 API requests."""

    def __init__(self, mapper):
        reject_method_resource = wsgi.Resource(wsgi.RejectMethodController())

        '''images_resource = images.create_resource()

        mapper.connect("/",
                       controller=images_resource,
                       action="index")
        mapper.connect("/images",
                       controller=images_resource,
                       action='index',
                       conditions={'method': ['GET']})
        mapper.connect("/images",
                       controller=images_resource,
                       action='create',
                       conditions={'method': ['POST']})
        mapper.connect("/images",
                       controller=reject_method_resource,
                       action='reject',
                       allowed_methods='GET, POST',
                       conditions={'method': ['PUT', 'DELETE', 'HEAD',
                                              'PATCH']})
        mapper.connect("/images/detail",
                       controller=images_resource,
                       action='detail',
                       conditions={'method': ['GET', 'HEAD']})
        mapper.connect("/images/detail",
                       controller=reject_method_resource,
                       action='reject',
                       allowed_methods='GET, HEAD',
                       conditions={'method': ['POST', 'PUT', 'DELETE',
                                              'PATCH']})
        mapper.connect("/images/{id}",
                       controller=images_resource,
                       action="meta",
                       conditions=dict(method=["HEAD"]))
        mapper.connect("/images/{id}",
                       controller=images_resource,
                       action="show",
                       conditions=dict(method=["GET"]))
        mapper.connect("/images/{id}",
                       controller=images_resource,
                       action="update",
                       conditions=dict(method=["PUT"]))
        mapper.connect("/images/{id}",
                       controller=images_resource,
                       action="delete",
                       conditions=dict(method=["DELETE"]))
        mapper.connect("/images/{id}",
                       controller=reject_method_resource,
                       action='reject',
                       allowed_methods='GET, HEAD, PUT, DELETE',
                       conditions={'method': ['POST', 'PATCH']})

        members_resource = members.create_resource()

        mapper.connect("/images/{image_id}/members",
                       controller=members_resource,
                       action="index",
                       conditions={'method': ['GET']})
        mapper.connect("/images/{image_id}/members",
                       controller=members_resource,
                       action="update_all",
                       conditions=dict(method=["PUT"]))
        mapper.connect("/images/{image_id}/members",
                       controller=reject_method_resource,
                       action='reject',
                       allowed_methods='GET, PUT',
                       conditions={'method': ['POST', 'DELETE', 'HEAD',
                                              'PATCH']})
        mapper.connect("/images/{image_id}/members/{id}",
                       controller=members_resource,
                       action="show",
                       conditions={'method': ['GET']})
        mapper.connect("/images/{image_id}/members/{id}",
                       controller=members_resource,
                       action="update",
                       conditions={'method': ['PUT']})
        mapper.connect("/images/{image_id}/members/{id}",
                       controller=members_resource,
                       action="delete",
                       conditions={'method': ['DELETE']})
        mapper.connect("/images/{image_id}/members/{id}",
                       controller=reject_method_resource,
                       action='reject',
                       allowed_methods='GET, PUT, DELETE',
                       conditions={'method': ['POST', 'HEAD', 'PATCH']})
        mapper.connect("/shared-images/{id}",
                       controller=members_resource,
                       action="index_shared_images")'''


        hosts_resource = hosts.create_resource()

        mapper.connect("/nodes",
                       controller=hosts_resource,
                       action='add_host',
                       conditions={'method': ['POST']})
        mapper.connect("/nodes/{id}",
                       controller=hosts_resource,
                       action='delete_host',
                       conditions={'method': ['DELETE']})
        mapper.connect("/nodes/{id}",
                       controller=hosts_resource,
                       action='update_host',
                       conditions={'method': ['PUT']})
        mapper.connect("/nodes",
                       controller=hosts_resource,
                       action='detail',
                       conditions={'method': ['GET']})
                       
        mapper.connect("/nodes/{id}",
                       controller=hosts_resource,
                       action='get_host',
                       conditions={'method': ['GET']})
        mapper.connect("/discover_host/",
                       controller=hosts_resource,
                       action='discover_host',
                       conditions={'method': ['POST']})

        mapper.connect("/discover/nodes",
                       controller=hosts_resource,
                       action='add_discover_host',
                       conditions={'method': ['POST']})
                       
        mapper.connect("/discover/nodes/{id}",
                       controller=hosts_resource,
                       action='delete_discover_host',
                       conditions={'method': ['DELETE']})
                       
        mapper.connect("/discover/nodes",
                       controller=hosts_resource,
                       action='detail_discover_host',
                       conditions={'method': ['GET']})
                       
        mapper.connect("/discover/nodes/{id}",
                       controller=hosts_resource,
                       action='update_discover_host',
                       conditions={'method': ['PUT']})

        mapper.connect("/discover/nodes/{discover_host_id}",
                       controller=hosts_resource,
                       action='get_discover_host_detail',
                       conditions={'method': ['GET']})
                       
        clusters_resource = clusters.create_resource()
        
        mapper.connect("/clusters",
                       controller=clusters_resource,
                       action='add_cluster',
                       conditions={'method': ['POST']})
        mapper.connect("/clusters/{id}",
                       controller=clusters_resource,
                       action='delete_cluster',
                       conditions={'method': ['DELETE']})
        mapper.connect("/clusters/{id}",
                       controller=clusters_resource,
                       action='update_cluster',
                       conditions={'method': ['PUT']})                

        mapper.connect("/clusters",
                       controller=clusters_resource,
                       action='detail',
                       conditions={'method': ['GET']})
                       
        mapper.connect("/clusters/{id}",
                       controller=clusters_resource,
                       action='get_cluster',
                       conditions={'method': ['GET']})
               
                       
        mapper.connect("/clusters/{id}",
                       controller=clusters_resource,
                       action='update_cluster',
                       conditions={'method': ['PUT']})                

        template_resource = template.create_resource()
        mapper.connect("/template",
                       controller=template_resource,
                       action='add_template',
                       conditions={'method': ['POST']})
        
        mapper.connect("/template/{template_id}",
                       controller=template_resource,
                       action='update_template',
                       conditions={'method': ['PUT']})
        
                       
        mapper.connect("/template/{template_id}",
                       controller=template_resource,
                       action='delete_template',
                       conditions={'method': ['DELETE']})
                            
        mapper.connect("/template/lists",
                       controller=template_resource,
                       action='get_template_lists',
                       conditions={'method': ['GET']})
                       
        mapper.connect("/template/{template_id}",
                       controller=template_resource,
                       action='get_template_detail',
                       conditions={'method': ['GET']})
                  
        mapper.connect("/export_db_to_json",
                       controller=template_resource,
                       action='export_db_to_json',
                       conditions={'method': ['POST']})
                       
        mapper.connect("/import_json_to_template",
                       controller=template_resource,
                       action='import_json_to_template',
                       conditions={'method': ['POST']})

        mapper.connect("/import_template_to_db",
                       controller=template_resource,
                       action='import_template_to_db',
                       conditions={'method': ['POST']})

                       
        host_template_resource = host_template.create_resource()
        mapper.connect("/host_template",
                       controller=host_template_resource,
                       action='add_host_template',
                       conditions={'method': ['POST']})
        mapper.connect("/host_template/{template_id}",
                       controller=host_template_resource,
                       action='update_host_template',
                       conditions={'method': ['PUT']})               
        mapper.connect("/host_template",
                       controller=host_template_resource,
                       action='delete_host_template',
                       conditions={'method': ['PUT']})
        mapper.connect("/host_template/lists",
                       controller=host_template_resource,
                       action='get_host_template_lists',
                       conditions={'method': ['GET']})  
        mapper.connect("/host_template/{template_id}",
                       controller=host_template_resource,
                       action='get_host_template_detail',
                       conditions={'method': ['GET']})     
        mapper.connect("/host_to_template",
                       controller=host_template_resource,
                       action='host_to_template',
                       conditions={'method': ['POST']})
        mapper.connect("/template_to_host",
                       controller=host_template_resource,
                       action='template_to_host',
                       conditions={'method': ['PUT']})
        
        components_resource = components.create_resource()
        mapper.connect("/components",
                       controller=components_resource,
                       action='add_component',
                       conditions={'method': ['POST']})
        mapper.connect("/components/{id}",
                       controller=components_resource,
                       action='delete_component',
                       conditions={'method': ['DELETE']})
        mapper.connect("/components/detail",
                       controller=components_resource,
                       action='detail',
                       conditions={'method': ['GET']})    
        mapper.connect("/components/{id}",
                       controller=components_resource,
                       action='get_component',
                       conditions={'method': ['GET']})  
        mapper.connect("/components/{id}",
                       controller=components_resource,
                       action='update_component',
                       conditions={'method': ['PUT']})   
        
        services_resource = services.create_resource()
        mapper.connect("/services",
                       controller=services_resource,
                       action='add_service',
                       conditions={'method': ['POST']})
        mapper.connect("/services/{id}",
                       controller=services_resource,
                       action='delete_service',
                       conditions={'method': ['DELETE']})
        mapper.connect("/services/detail",
                       controller=services_resource,
                       action='detail',
                       conditions={'method': ['GET']})    
        mapper.connect("/services/{id}",
                       controller=services_resource,
                       action='get_service',
                       conditions={'method': ['GET']})  
        mapper.connect("/services/{id}",
                       controller=services_resource,
                       action='update_service',
                       conditions={'method': ['PUT']})   

        roles_resource = roles.create_resource()
        mapper.connect("/roles",
                       controller=roles_resource,
                       action='add_role',
                       conditions={'method': ['POST']})
        mapper.connect("/roles/{id}",
                       controller=roles_resource,
                       action='delete_role',
                       conditions={'method': ['DELETE']})
        mapper.connect("/roles/detail",
                       controller=roles_resource,
                       action='detail',
                       conditions={'method': ['GET']})    
        mapper.connect("/roles/{id}",
                       controller=roles_resource,
                       action='get_role',
                       conditions={'method': ['GET']})  
        mapper.connect("/roles/{id}",
                       controller=roles_resource,
                       action='update_role',
                       conditions={'method': ['PUT']})  

        members_resource = members.create_resource()
        mapper.connect("/clusters/{cluster_id}/nodes/{host_id}",
                       controller=members_resource,
                       action="add_cluster_host",
                       conditions={'method': ['PUT']})
        mapper.connect("/clusters/{cluster_id}/nodes/{host_id}",
                       controller=members_resource,
                       action="delete_cluster_host",
                       conditions={'method': ['DELETE']})
  #      mapper.connect("/clusters/{cluster_id}/nodes/{host_id}",
 #                      controller=members_resource,
 #                      action="get_cluster_hosts",
 #                      conditions={'method': ['GET']})
 #       mapper.connect("/clusters/{cluster_id}/nodes",
 #                      controller=members_resource,
  #                     action="get_cluster_hosts",
 #                      conditions={'method': ['GET']})
 #       mapper.connect("/multi_clusters/nodes/{host_id}",
 #                      controller=members_resource,
 #                      action="get_host_clusters",
 #                      conditions={'method': ['GET']})

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
                   action="detail",
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
                   action="detail",
                   conditions={'method': ['GET']})
                   
        mapper.connect("/config_sets/{id}",
                   controller=config_sets_resource,
                   action="get_config_set",
                   conditions=dict(method=["GET"]))  
        mapper.connect("/cluster_config_set_update",
                   controller=config_sets_resource,
                   action="cluster_config_set_update",
                   conditions={'method': ['POST']})
                   
        mapper.connect("/cluster_config_set_progress",
                   controller=config_sets_resource,
                   action="cluster_config_set_progress",
                   conditions={'method': ['POST']})

        configs_resource = configs.create_resource()

        mapper.connect("/configs",
                   controller=configs_resource,
                   action="add_config",
                   conditions={'method': ['POST']})
                   
        mapper.connect("/configs_delete",
                   controller=configs_resource,
                   action="delete_config",
                   conditions={'method': ['DELETE']})
                   
        mapper.connect("/configs/detail",
                   controller=configs_resource,
                   action="detail",
                   conditions={'method': ['GET']})
                   
        mapper.connect("/configs/{id}",
                   controller=configs_resource,
                   action="get_config",
                   conditions=dict(method=["GET"]))   

        networks_resource = networks.create_resource()

        mapper.connect("/networks",
                       controller=networks_resource,
                       action='add_network',
                       conditions={'method': ['POST']})
        mapper.connect("/networks/{network_id}",
                       controller=networks_resource,
                       action='delete_network',
                       conditions={'method': ['DELETE']})
        mapper.connect("/networks/{network_id}",
                       controller=networks_resource,
                       action='update_network',
                       conditions={'method': ['PUT']})
        mapper.connect("/clusters/{id}/networks",
                       controller=networks_resource,
                       action='detail',
                       conditions={'method': ['GET']})
                       
        mapper.connect("/networks/{id}",
                       controller=networks_resource,
                       action='get_network',
                       conditions={'method': ['GET']})

        mapper.connect("/networks",
               controller=networks_resource,
               action='get_all_network',
               conditions={'method': ['GET']})

        install_resource = install.create_resource()

        mapper.connect("/install",
                       controller=install_resource,
                       action='install_cluster',
                       conditions={'method': ['POST']})
    
        mapper.connect("/export_db",
                       controller=install_resource,
                       action='export_db',
                       conditions={'method': ['POST']})
                       
        mapper.connect("/uninstall/{cluster_id}",
                       controller=install_resource,
                       action='uninstall_cluster',
                       conditions={'method': ['POST']})
        mapper.connect("/uninstall/{cluster_id}",
                       controller=install_resource,
                       action='uninstall_progress',
                       conditions={'method': ['GET']})

        mapper.connect("/update/{cluster_id}",
                       controller=install_resource,
                       action='update_cluster',
                       conditions={'method': ['POST']})
                       
        mapper.connect("/update/{cluster_id}",
                       controller=install_resource,
                       action='update_progress',
                       conditions={'method': ['GET']})
                       
        mapper.connect("/disk_array/{cluster_id}",
                       controller=install_resource,
                       action='update_disk_array',
                       conditions={'method': ['POST']})
                       
        #mapper.connect("/update/{cluster_id}/versions/{versions_id}",
        #               controller=update_resource,
        #               action='update_cluster_version',
        #               conditions={'method': ['POST']})
        
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
                       
        super(API, self).__init__(mapper)
        
          
