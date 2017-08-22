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

from django import http
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse


from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

import logging
LOG = logging.getLogger(__name__)


class OSConfigView(generic.TemplateView):
    template_name = "environment/deploy/os_config.html"

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c.name
        return ""

    def get_context_data(self, **kwargs):
        context = super(OSConfigView, self).get_context_data(**kwargs)
        context['os_version'] = ['Centos OS 7', 'Redhat Enterprise Linux 7']
        context['cluster_id'] = self.kwargs["cluster_id"]
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        wizard_cache.set_cache(context['cluster_id'], "osconfig", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])
        context["current_cluster"] = self.get_current_cluster(
            context['clusters'], context["cluster_id"])
        return context


@csrf_exempt
def os_config_next(request, cluster_id):
    wizard_cache.set_cache(cluster_id, "osconfig", 2)
    url = reverse('horizon:environment:deploy:hosts_role_assignment',
                  args=[cluster_id])
    response = http.HttpResponseRedirect(url)
    LOG.info("url %s", url)
    return response
