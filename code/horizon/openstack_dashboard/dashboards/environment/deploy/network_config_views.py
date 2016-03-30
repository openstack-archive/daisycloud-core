#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

from django import http
from django.http import HttpResponse
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django import shortcuts
from django import template
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

import json

from horizon import messages
from horizon import exceptions

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.network \
    import views as network_views
from openstack_dashboard.dashboards.environment.deploy \
    import wizard_cache

import logging
LOG = logging.getLogger(__name__)


class NetworkConfigView(generic.TemplateView):
    template_name = "environment/deploy/network_config.html"

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c
        return None

    def get_context_data(self, **kwargs):
        context = super(NetworkConfigView, self).get_context_data(**kwargs)
        context["network"] = \
            network_views.NetworkView().get_context_data_ext(self, **kwargs)

        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        c = self.get_current_cluster(context['clusters'], context["cluster_id"])
        if c:
            context["current_cluster"] = c.name
            context["segment_type"] = c.segmentation_type

            if context["segment_type"] == 'vlan' or context["segment_type"] == 'flat':
                context["network"]["networks"] = [n 
                    for n in context["network"]["networks"] if n["name"] != "VXLAN"]
            if context["segment_type"] == 'vxlan':
                context["network"]["networks"] = [n 
                    for n in context["network"]["networks"] if n["name"] != "PRIVATE"]

        else:
            context["current_cluster"] = ""            

        wizard_cache.set_cache(context['cluster_id'], "network", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])
        
        return context


@csrf_exempt
def network_next(request, cluster_id):
    wizard_cache.set_cache(cluster_id, "network", 2)
    url = reverse('horizon:environment:deploy:networkmapping',
                  args=[cluster_id])
    response = http.HttpResponseRedirect(url)
    LOG.info("url %s", url)
    return response


@csrf_exempt
def add_net_plane(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    net_plane_params = {
        "PUBLIC": ["cidr", "gateway", "ip_ranges", "vlan_id", "description"],
        "DEPLOYMENT": ["cidr", "gateway", "ip_ranges", "description"],
        "MANAGEMENT": ["cidr", "gateway", "ip_ranges", "vlan_id", "description"],
        "PRIVATE": ["vlan_start", "vlan_end", "description"],
        "STORAGE": ["cidr", "gateway", "ip_ranges", "vlan_id",  "description"],
        "EXTERNAL": ["cidr", "gateway", "ip_ranges", "vlan_start", "vlan_end", "description"],
        "VXLAN": ["cidr", "gateway", "ip_ranges", "description"]}

    try:
        net_plane = {
            "name": data["name"],
            "network_type": data["network_type"],
            "description": data["description"],
            "cluster_id": cluster_id}
        for param in net_plane_params[data["network_type"]]:
            net_plane[param] = data[param]
            if net_plane[param] == "":
                net_plane[param] = None
        LOG.info("########net_plane = %s" % net_plane)
        api.daisy.net_plane_add(request, **net_plane)
    except Exception as e:
        LOG.info("add_net_plane:%s", e)
        messages.error(request, e)
        response.status_code = 500
        return response

    response.status_code = 200
    return response


