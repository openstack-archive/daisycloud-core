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

from openstack_dashboard.dashboards.environment.system import views
from openstack_dashboard.dashboards.environment.system \
    import system_config_views

HWM = r'^(?P<hwm_id>[^/]+)/%s$'

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.system.views',
    url(r'^$', views.SystemView.as_view(), name='index'),
    url(r'backup$', views.backup_system, name='backup'),
    url(r'restore$', views.restore_system, name='restore'),
    url(r'restore_system_force$',
        views.restore_system_force,
        name='restore_system_force'),
    url(r'^systemconfig$', system_config_views.SystemConfigView.as_view(),
        name='systemconfig'),
    url(r'^modify_systemconfig$',
        system_config_views.modify_systemconfig,
        name='modify_systemconfig'),
    url(r'^set_pxeserver$',
        system_config_views.set_pxeserver,
        name='set_pxeserver'),
)
