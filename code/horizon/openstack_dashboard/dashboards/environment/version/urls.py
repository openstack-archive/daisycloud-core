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

from openstack_dashboard.dashboards.environment.version import views

VERSION = r'^(?P<version_id>[^/]+)/%s$'

urlpatterns = patterns(
    'openstack_dashboard.dashboards.environment.version.views',
    url(r'^$', views.VersionView.as_view(), name='index'),
    url(r'upload$', views.upload_version, name='upload'),
    url(VERSION % 'update_version',
        views.UpdateVersionView.as_view(),
        name='update_version'),
    url(r'get_appointed_system_versions/$',
        views.get_appointed_system_versions,
        name='get_appointed_system_versions'),
    url(r'get_headstrong_server_files/$',
        views.get_headstrong_server_files,
        name='get_headstrong_server_files'),
    url(r'get_version_file_types/$',
        views.get_version_file_types,
        name='get_version_file_types'),
    url(r'get_appointed_patch_files/$',
        views.get_appointed_patch_files,
        name='get_appointed_patch_files'),
    url(r'check_disk_space_and_file_exist/$',
        views.check_disk_space_and_file_exist,
        name='check_disk_space_and_file_exist'),
    url(r'get_appointed_system_packages/$',
        views.get_appointed_system_packages,
        name='get_appointed_system_packages'),
)
