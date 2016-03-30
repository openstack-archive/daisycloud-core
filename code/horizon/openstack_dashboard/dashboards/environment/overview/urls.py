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

from openstack_dashboard.dashboards.environment.overview \
    import views as overview_views
from openstack_dashboard.dashboards.environment.cluster \
    import views as cluster_views

CLUSTER = r'^(?P<cluster_id>[^/]+)/%s$'
HOST = r'^(?P<host_id>[^/]+)/%s$'
TEMPLATE = r'^(?P<template_id>[^/]+)/%s$'

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.overview.views',
    url(r'^$', overview_views.OverviewView.as_view(), name='index'),
    url(r'^hosts/$', overview_views.HostsView.as_view(), name='hosts'),
    url(r'^templates/$',
        overview_views.TemplatesView.as_view(),
        name='templates'),
    url(HOST % 'addtocluster',
        overview_views.AddHostsToClusterView.as_view(),
        name='addtocluster'),
    url(r'^create/$', overview_views.cluster_create, name='create'),
    url(r'^cluster_create_by_template/$',
        overview_views.cluster_create_by_template,
        name='cluster_create_by_template'),
    url(r'delete/$', cluster_views.ClusterDelete, name='clusterdelete'),
    url(r'get_cluster/$', overview_views.GetCluster, name='get_cluster'),
    url(r'get_clusters/$', overview_views.GetClusters, name='get_clusters'),
    url(r'modify_cluster/$',
        overview_views.ModifyCluster,
        name='modify_cluster'),
    url(r'generate_cluster_template/$',
        overview_views.generate_cluster_template,
        name='generate_cluster_template'),
    url(r'import_template/$',
        overview_views.ImportTemplateView.as_view(),
        name='import_template'),
    url(TEMPLATE % 'template_detail',
        overview_views.TemplateDetailView.as_view(),
        name='template_detail'),
    url(TEMPLATE % 'download_template_file',
        overview_views.download_template_file,
        name='download_template_file'),
    url(TEMPLATE % 'instance_cluster_template',
        overview_views.InstanceClusterTemplateView.as_view(),
        name='instance_cluster_template'),
)
