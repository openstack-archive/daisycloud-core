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

from openstack_dashboard.dashboards.environment.template \
    import views as template_views

CLUSTER = r'^(?P<cluster_id>[^/]+)/%s$'
CLUSTER_HOST = r'^(?P<cluster_id>[^/]+)/(?P<host_id>[^/]+)/%s$'
TEMPLATE = r'^(?P<template_id>[^/]+)/%s$'

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.template.views',
    url(r'^$', template_views.TemplatesView.as_view(), name='index'),
    url(r'generate_cluster_template/$',
        template_views.generate_cluster_template,
        name='generate_cluster_template'),
    url(r'import_template/$',
        template_views.ImportTemplateView.as_view(),
        name='import_template'),
    url(TEMPLATE % 'template_detail',
        template_views.TemplateDetailView.as_view(),
        name='template_detail'),
    url(TEMPLATE % 'download_template_file',
        template_views.download_template_file,
        name='download_template_file'),
    url(TEMPLATE % 'instance_cluster_template',
        template_views.InstanceClusterTemplateView.as_view(),
        name='instance_cluster_template'),
    url(CLUSTER_HOST % 'instance_host_template',
        template_views.InstanceHostTemplateView.as_view(),
        name='instance_host_template'),
    url(CLUSTER % 'batch_instance_template',
        template_views.batch_instance_template,
        name='batch_instance_template'),
    url(CLUSTER_HOST % 'generate_host_template',
        template_views.GenerateHostTemplateView.as_view(),
        name='generate_host_template'),
)
