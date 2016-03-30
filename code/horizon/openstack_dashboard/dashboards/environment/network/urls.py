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

from openstack_dashboard.dashboards.environment.network import views
from openstack_dashboard.dashboards.environment.network.subnets import views as subnet_views

CLUSTER = r'^(?P<cluster_id>[^/]+)/%s$'
CLUSTER1 = r'^(?P<cluster_id>[^/]+)/%s$'
CLUSTERLOGICNET = r'^(?P<logicnet_id>[^/]+)/%s$'
CLUSTERLOGICNET2 = r'^(?P<cluster_id>[^/]+)/(?P<logicnet_id>[^/]+)/%s$'

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.network.views',
    url(r'^$', views.NetworkView.as_view(), name='index'),
    url(r'modify/$', views.NetworkModify, name='netmodify'),
    url(r'^(?P<cluster_id>[^/]+)/routes/$', views.RouteView.as_view(), name='route'),
    url(r'^(?P<cluster_id>[^/]+)/routes/create/$', views.RouteCreateView.as_view(), name='create'),
    url(CLUSTER % '', views.NetworkView.as_view(), name='overview'),
    url(CLUSTERLOGICNET % 'logicnet/detail', views.DetailView.as_view(), name='logicnetdetail'),
    url(CLUSTER1 % 'logicnet', views.LogicnetsView.as_view(), name='logicnet'),
    url(CLUSTER1 % 'logicnet/create', views.CreateView.as_view(), name='create_logicnet'),
    url(CLUSTERLOGICNET2 % 'logicnet/subnets/create', subnet_views.CreateView.as_view(), name='logicnet_addsubnet'),
)






