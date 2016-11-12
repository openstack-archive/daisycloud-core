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


# from daisy.api.v1 import images
import os
from oslo_utils import importutils
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
from daisy.api.v1 import backend_types
from daisy.common import wsgi
from daisy.api.v1 import backup_restore
from daisy.api.v1 import versions
from daisy.api.v1 import version_patchs
from daisy.api.v1 import template_configs
from daisy.api.v1 import template_funcs
from daisy.api.v1 import template_services
from daisy.api.v1 import config_update


class API(wsgi.Router):

    """WSGI router for Daisy v1 API requests."""

    def __init__(self, mapper):
        wsgi.Resource(wsgi.RejectMethodController())

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

        mapper.connect("/pxe_discover/nodes",
                       controller=hosts_resource,
                       action='add_pxe_host',
                       conditions={'method': ['POST']})

        mapper.connect("/pxe_discover/nodes/{id}",
                       controller=hosts_resource,
                       action='update_pxe_host',
                       conditions={'method': ['PUT']})

        mapper.connect("/check",
                       controller=hosts_resource,
                       action='host_check',
                       conditions={'method': ['POST']})

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

        mapper.connect("/cluster_config_set_get",
                       controller=config_sets_resource,
                       action="cluster_config_set_get",
                       conditions={'method': ['GET']})
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

        mapper.connect("/optical_switch",
                       controller=array_resource,
                       action='optical_switch_add',
                       conditions={'method': ['POST']})
        mapper.connect("/optical_switch/list",
                       controller=array_resource,
                       action='optical_switch_list',
                       conditions={'method': ['GET']})
        mapper.connect("/optical_switch/{id}",
                       controller=array_resource,
                       action='optical_switch_update',
                       conditions={'method': ['PUT']})
        mapper.connect("/optical_switch/{id}",
                       controller=array_resource,
                       action='optical_switch_delete',
                       conditions={'method': ['DELETE']})

        backup_restore_resource = backup_restore.create_resource()

        mapper.connect("/backup",
                       controller=backup_restore_resource,
                       action='backup',
                       conditions={'method': ['POST']})
        mapper.connect("/restore",
                       controller=backup_restore_resource,
                       action='restore',
                       conditions={'method': ['POST']})
        mapper.connect("/backup_file_version",
                       controller=backup_restore_resource,
                       action='get_backup_file_version',
                       conditions={'method': ['POST']})
        mapper.connect("/version",
                       controller=backup_restore_resource,
                       action='version',
                       conditions={'method': ['POST']})

        backend_types_resource = backend_types.create_resource()
        mapper.connect("/backend_types",
                       controller=backend_types_resource,
                       action='get',
                       conditions={'method': ['POST']})

        versions_resource = versions.create_resource()
        mapper.connect("/versions",
                       controller=versions_resource,
                       action='add_version',
                       conditions={'method': ['POST']})
        mapper.connect("/versions/{id}",
                       controller=versions_resource,
                       action='delete_version',
                       conditions={'method': ['DELETE']})
        mapper.connect("/versions",
                       controller=versions_resource,
                       action='list_version',
                       conditions={'method': ['GET']})
        mapper.connect("/versions/{id}",
                       controller=versions_resource,
                       action='get_version',
                       conditions={'method': ['GET']})
        mapper.connect("/versions/{id}",
                       controller=versions_resource,
                       action='update_version',
                       conditions={'method': ['PUT']})

        version_patchs_resource = version_patchs.create_resource()
        mapper.connect("/version_patchs",
                       controller=version_patchs_resource,
                       action='add_version_patch',
                       conditions={'method': ['POST']})
        mapper.connect("/version_patchs/{id}",
                       controller=version_patchs_resource,
                       action='delete_version_patch',
                       conditions={'method': ['DELETE']})
        mapper.connect("/version_patchs/{id}",
                       controller=version_patchs_resource,
                       action='get_version_patch',
                       conditions={'method': ['GET']})
        mapper.connect("/version_patchs/{id}",
                       controller=version_patchs_resource,
                       action='update_version_patch',
                       conditions={'method': ['PUT']})

        template_configs_resource = template_configs.create_resource()
        mapper.connect("/template_configs/import_template_config",
                       controller=template_configs_resource,
                       action='import_template_config',
                       conditions={'method': ['POST']})

        mapper.connect("/template_configs/list",
                       controller=template_configs_resource,
                       action="list_template_config",
                       conditions={'method': ['GET']})

        mapper.connect("/template_configs/{id}",
                       controller=template_configs_resource,
                       action="get_template_config",
                       conditions=dict(method=["GET"]))

        template_funcs_resource = template_funcs.create_resource()
        mapper.connect("/template_funcs/import_template_func",
                       controller=template_funcs_resource,
                       action='import_template_func',
                       conditions={'method': ['POST']})

        mapper.connect("/template_funcs/list",
                       controller=template_funcs_resource,
                       action="list_template_func",
                       conditions={'method': ['GET']})

        mapper.connect("/template_funcs/{id}",
                       controller=template_funcs_resource,
                       action="get_template_func",
                       conditions=dict(method=["GET"]))

        template_services_resource = template_services.create_resource()
        mapper.connect("/template_services/list",
                       controller=template_services_resource,
                       action="list_template_service",
                       conditions={'method': ['GET']})

        mapper.connect("/template_services/{id}",
                       controller=template_services_resource,
                       action="get_template_service",
                       conditions=dict(method=["GET"]))

        config_update_resource = config_update.create_resource()
        mapper.connect("/config_update_gen/{cluster_id}",
                       controller=config_update_resource,
                       action='config_update_gen',
                       conditions={'method': ['PUT']})
        mapper.connect("/config_update_get/{cluster_id}",
                       controller=config_update_resource,
                       action='config_update_get',
                       conditions={'method': ['GET']})
        mapper.connect("/config_update_dispatch/{cluster_id}",
                       controller=config_update_resource,
                       action='config_update_dispatch',
                       conditions={'method': ['PUT']})

        path = os.path.join(os.path.abspath(os.path.dirname(
                                            os.path.realpath(__file__))),
                            'ext')
        for root, dirs, names in os.walk(path):
            filename = 'router.py'
            if filename in names:
                ext_name = root.split(path)[1].strip('/')
                print 'Found %s' % ext_name
                hwm_driver = "%s.router.APIExtension" % ext_name
                extension = importutils.import_object_ns('daisy.api.v1.ext',
                                                         hwm_driver,
                                                         mapper)
        super(API, self).__init__(mapper)
