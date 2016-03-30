#
# Copyright ZTE
# Daisy Tools Dashboard
#

from django.http import HttpResponse
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django import shortcuts

import json

from horizon import exceptions
from horizon import messages
from horizon import tables, forms
from horizon import workflows

from openstack_dashboard.dashboards.environment.network import tables as nettables
from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.network import tables as network_tables
from openstack_dashboard.dashboards.environment.network import forms as route_forms
from openstack_dashboard.dashboards.environment.network import workflows as cur_workflows
from openstack_dashboard.dashboards.environment.network.subnets import tables as subnet_tables
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

import logging
LOG = logging.getLogger(__name__)


class NetworkView(generic.TemplateView):
    template_name = "environment/network/index.html"

    def get_context_data_ext(self, cls, **kwargs):
        context = super(NetworkView, self).get_context_data(**kwargs)

        qp = {'ID': cls.kwargs["cluster_id"]}
        try:
            networks = api.daisy.network_list(cls.request, cls.kwargs["cluster_id"])
        except Exception:
            exceptions.handle(cls.request, "network_list failed!")
            networks = []

        networks_list = [net.__dict__ for net in networks]
        networks_list.sort(key=lambda x: x['name'])
        context["networks"] = networks_list
        return context

    def get_context_data(self, **kwargs):
        context = super(NetworkView, self).get_context_data(**kwargs)

        qp = {'ID': self.kwargs["cluster_id"]}
        try:
            networks = api.daisy.network_list(self.request, 
                                              self.kwargs["cluster_id"])
        except Exception:
            exceptions.handle(self.request, "network_list failed!")
            networks = []

        networks_list = [net for net in networks]
        context["network"] = {"networks": networks_list, 
                              "cluster_id": self.kwargs["cluster_id"]}
        return context


@csrf_exempt
def NetworkModify(request):
    response = HttpResponse()
    data = json.loads(request.body)

    cluster_id = ""
    nets = data["nets"]
    netplane_param = {"PUBLIC": ["cidr", "gateway", "ip_ranges", "vlan_id", "description"],
                      "DEPLOYMENT": ["cidr", "gateway", "ip_ranges", "vlan_id", "description"],
                      "MANAGEMENT": ["cidr", "gateway", "ip_ranges", "vlan_id", "description"],
                      "PRIVATE": ["vlan_start", "vlan_end", "description"],
                      "STORAGE": ["cidr", "gateway", "ip_ranges", "vlan_id",  "description"],
                      "EXTERNAL": ["cidr", "gateway", "ip_ranges", "vlan_start", "vlan_end", "description"],
                      "VXLAN": ["cidr", "gateway", "ip_ranges", "description"],
                     }
    try:
        for net in nets:
            net_params = {
                "name": net["name"],
                "cluster_id": net["cluster_id"],
                }
            network_type = net["network_type"]
            for param in netplane_param[network_type]:
                    net_params[param] = net[param]

            LOG.info("########net_params = %s" % net_params)
            api.daisy.network_update(request, net["id"], **net_params)

    except Exception as e:
        LOG.error('wmh dbg: e=%s' % e)
        messages.error(request, e)
        response.status_code = 500
        return response

    response.status_code = 200
    return response


class LogicnetsView(tables.DataTableView):
    table_class = nettables.NetworksTable
    template_name = 'environment/network/logic_net_index.html'
    page_title = _("Logic Networks")

    def get_data(self):
        networks = []
        try:
            cluster_id = self.kwargs['cluster_id']
            cluster_info = api.daisy.cluster_get(self.request, cluster_id)
            networks = cluster_info.logic_networks
            msg = ('Logicnets ~~~~~~~~~~~~~~~ %s') % networks
            LOG.info(msg)
        except Exception:
            networks = []
            msg = _('Network list can not be retrieved.')
            exceptions.handle(self.request, msg)
        return networks


class CreateView(workflows.WorkflowView):
    workflow_class = cur_workflows.CreateNetwork
    ajax_template_name = 'environment/network/create.html'


class DetailView(tables.MultiTableView):
    table_classes = (subnet_tables.SubnetsTable,)
    template_name = 'environment/network/detail.html'
    page_title = _("Network Details: {{ network.name }}")

    def get_subnets_data(self):
        try:
            network = self._get_data()
            LOG.info("**** get_subnet_data networks=%s" % network )
            subnets = []
            if network:
               subnets = network['subnets']
        except Exception:
            subnets = []
            msg = _('Subnet list can not be retrieved.')
            exceptions.handle(self.request, msg)
        return subnets

    def _get_data(self):
        try:
            LOG.info("**** _data logicnet_id=%s" % self.kwargs['logicnet_id'])
            logicnet_id = self.kwargs['logicnet_id'].split("#")[1]
            cluster_id = self.kwargs['logicnet_id'].split("#")[0]
            LOG.info("**** _data logicnet_id=%s" % logicnet_id )
            LOG.info("**** _data cluster_id=%s" % cluster_id )
            msg = ('DetailView logicnet_id:%s   cluster_id:%s') % (logicnet_id, cluster_id)
            LOG.info(msg)

            cluster_info = api.daisy.cluster_get(self.request, cluster_id)
            _logic_networks = cluster_info.logic_networks
            LOG.info("****_data logic_networks=%s" % _logic_networks )
            for alogic in _logic_networks:
                if(alogic['id'] == logicnet_id):
                    return alogic
        except Exception:
            msg = _('Unable to retrieve details for network "%s".') \
                % (logicnet_id)
            exceptions.handle(self.request, msg,
                              redirect=self.get_redirect_url())
        return {}

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        msg = ('DetailView enter ~~~~~')
        LOG.info(msg)
        network = self._get_data()
        context["network"] = network
        return context

    @staticmethod
    def get_redirect_url():
        return reverse_lazy('horizon:environment:network:index')


class RouteView(tables.DataTableView):
    table_class = network_tables.RouteTable
    template_name = "environment/network/route.html"

    def get_data(self):
        cluster_id = self.kwargs['cluster_id']
        cluster = api.daisy.cluster_get(self.request, cluster_id)
        return cluster.routers


class RouteCreateView(forms.ModalFormView):
    form_class = route_forms.CreateRouteForm
    template_name = 'environment/network/createRoute.html'

    def get_success_url(self):
        cluster_id = self.kwargs["cluster_id"]
        url = "/dashboard/environment/network/" + cluster_id + "/routes/"
        return url

    def get_context_data(self, **kwargs):
        context = super(RouteCreateView, self).get_context_data(**kwargs)
        cluster_id = self.kwargs["cluster_id"]
        submit_url = "/dashboard/environment/network/" + cluster_id + "/routes/create/"
        context['submit_url'] = submit_url
        return context