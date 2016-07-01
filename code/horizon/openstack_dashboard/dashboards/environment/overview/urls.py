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

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.overview.views',
    url(r'get_hwmip/$', overview_views.Get_hwmip, name='get_hwmip'),
    url(r'^$', overview_views.OverviewView.as_view(), name='index'),
    url(r'^create/$', overview_views.cluster_create, name='create'),
    url(r'delete/$', cluster_views.ClusterDelete, name='clusterdelete'),
    url(r'get_cluster/$', overview_views.GetCluster, name='get_cluster'),
    url(r'get_clusters/$', overview_views.GetClusters, name='get_clusters'),
)
