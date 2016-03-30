# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
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


from django.conf.urls import patterns
from django.conf.urls import url

from openstack_dashboard.dashboards.environment.deploy import views
from openstack_dashboard.dashboards.environment.deploy \
    import select_host_views
from openstack_dashboard.dashboards.environment.deploy import os_config_views
from openstack_dashboard.dashboards.environment.deploy \
    import network_mapping_views
from openstack_dashboard.dashboards.environment.deploy \
    import hosts_role_assignment_views
from openstack_dashboard.dashboards.environment.deploy \
    import hosts_config_views
from openstack_dashboard.dashboards.environment.deploy \
    import network_config_views
from openstack_dashboard.dashboards.environment.deploy import bonding_views

CLUSTER = r'^(?P<cluster_id>[^/]+)/%s$'
CLUSTER_HOST = r'^(?P<cluster_id>[^/]+)/(?P<host_id>[^/]+)/%s$'

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.deploy.views',
    url(r'^$', views.DeployView.as_view(), name='index'),
    url(CLUSTER % 'dodeploy', views.do_deploy, name='dodeploy'),
    url(r'get_deploy_info_time/$',
        views.get_deploy_info_time,
        name='get_deploy_info_time'),
    url(CLUSTER % 'addhost', views.AddHostView.as_view(), name='addhost'),
    url(CLUSTER % 'overview', views.DeployView.as_view(), name='overview'),
    url(CLUSTER % 'hosts', views.HostsView.as_view(), name='hosts'),
    url(CLUSTER % 'hosts_role_assignment',
        hosts_role_assignment_views.IndexView.as_view(),
        name='hosts_role_assignment'),
    url(CLUSTER % 'assign_host_role',
        hosts_role_assignment_views.assign_host_role,
        name='assign_host_role'),
    url(r'get_role_info/$',
        hosts_role_assignment_views.get_role_info,
        name='get_role_info'),
    url(r'set_role_info/$',
        hosts_role_assignment_views.set_role_info,
        name='set_role_info'),
    url(r'get_ha_role_info/$',
        hosts_role_assignment_views.get_ha_role_info,
        name='get_ha_role_info'),
    url(r'set_ha_role_info/$',
        hosts_role_assignment_views.set_ha_role_info,
        name='set_ha_role_info'),
    url(CLUSTER % 'hosts_role_assignment_next',
        hosts_role_assignment_views.hosts_role_assignment_next,
        name='hosts_role_assignment_next'),
    url(CLUSTER % 'hosts_config',
        hosts_config_views.IndexView.as_view(),
        name='hosts_config'),
    url(CLUSTER % 'set_host_config',
        hosts_config_views.set_host_config,
        name='set_host_config'),
    url(CLUSTER % 'removehost',
        views.remove_host,
        name='removehost'),
    url(CLUSTER_HOST % 'nics',
        views.HostNicsView.as_view(),
        name='nics'),
    url(CLUSTER_HOST % 'updatenics',
        views.update_host_nics,
        name='updatenics'),
    url(CLUSTER_HOST % 'updateipmis',
        views.update_host_ipmis,
        name='updateipmis'),
    url(CLUSTER % 'selecthosts',
        select_host_views.SelectHostsView.as_view(),
        name='selecthosts'),
    url(CLUSTER % 'ipmiconf',
        select_host_views.conf_ipmi,
        name='confipmi'),
    url(CLUSTER % 'startdiscover',
        select_host_views.start_discover,
        name='startdiscover'),
    url(CLUSTER % 'list_discover_host',
        select_host_views.list_discover_host,
        name='list_discover_host'),
    url(CLUSTER % 'get_discover_result', 
        select_host_views.get_discover_result,
        name='get_discover_result'),
    url(CLUSTER % 'allocatehost',
        select_host_views.allocate_host,
        name='allocatehost'),
    url(CLUSTER_HOST % 'instance_host_template',
        select_host_views.InstanceHostTemplateView.as_view(),
        name='instance_host_template'),
    url(CLUSTER % 'batch_instance_template',
        select_host_views.batch_instance_template,
        name='batch_instance_template'),
    url(CLUSTER % 'osconfig',
        os_config_views.OSConfigView.as_view(),
        name='osconfig'),
    url(CLUSTER % 'os_config_next',
        os_config_views.os_config_next,
        name='os_config_next'),
    url(CLUSTER % 'networkmapping',
        network_mapping_views.NetworkMappingView.as_view(),
        name='networkmapping'),
    url(CLUSTER % 'assign_net_work',
        network_mapping_views.assign_net_work,
        name='assign_net_work'),
    url(CLUSTER % 'net_mapping_next',
        network_mapping_views.net_mapping_next,
        name='net_mapping_next'),
    url(CLUSTER % 'network',
        network_config_views.NetworkConfigView.as_view(),
        name='network'),
    url(CLUSTER % 'network_next',
        network_config_views.network_next,
        name='network_next'),
    url(CLUSTER % 'add_net_plane',
        network_config_views.add_net_plane,
        name='add_net_plane'),
    url(CLUSTER % 'bonding',
        bonding_views.BondingView.as_view(),
        name='bonding'),
    url(CLUSTER % 'bond_net_port',
        bonding_views.bond_net_port,
        name='bond_net_port'),
    url(CLUSTER % 'un_bond_net_port',
        bonding_views.un_bond_net_port,
        name='un_bond_net_port'),
    url(CLUSTER % 'bond_net_port_next',
        bonding_views.bond_net_port_next,
        name='bond_net_port_next'),
)
