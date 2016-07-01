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

from openstack_dashboard.dashboards.environment.host \
    import views as host_views

HOST = r'^(?P<host_id>[^/]+)/%s$'

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.host.views',
    url(r'^$', host_views.HostsView.as_view(), name='index'),
    url(HOST % 'addtocluster',
        host_views.AddHostsToClusterView.as_view(),
        name='addtocluster'),
    url(HOST % 'sshdiscover',
        host_views.SshDiscoverOneHostView.as_view(),
        name='sshdiscover'),
)
