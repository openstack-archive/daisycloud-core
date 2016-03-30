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
from django.template import defaultfilters as filters
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

from daisyclient.v1 import client as daisy_client

import json

from horizon import messages
from horizon import exceptions
from horizon import forms
from horizon import tables

from openstack_dashboard import api

from openstack_dashboard.dashboards.environment.deploy import actions
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

import logging
LOG = logging.getLogger(__name__)


def get_host_network_url(interface):
    template_name = 'environment/deploy/hosts_net_work.html'
    context = {
        "interface": interface
    }
    return template.loader.render_to_string(template_name, context)


def get_host_table_dynamic_heads(hosts):
    dynamic_heads = []
    total = 0
    for host in hosts:
        count = 0
        for interface in host["interfaces"]:
            count += 1
        if total < count:
            total = count
    for i in range(total):
        dynamic_heads.append("eth" + str(i))
    return dynamic_heads


@csrf_exempt
def get_host_list(request, cluster_id):
    host_list = []
    try:
        cluster = api.daisy.cluster_get(request, cluster_id)
        if not hasattr(cluster, 'nodes'):
            return host_list
        for node in cluster.nodes:
            host = api.daisy.host_get(request, node)
            if hasattr(host, "interfaces"):
                host_info = {
                    "host_id": host.id,
                    "name": host.name,
                    "roles": None,
                    "interfaces": []
                }
                if hasattr(host, "role"):
                    if len(host.role):
                        host.role.sort()
                        host_info["roles"] = host.role
                bond_names = []
                bond_interfaces = [i for i in host.interfaces if i['type'] == 'bond']
                for interface in bond_interfaces:
                    bond_names.append(interface["slave1"])
                    bond_names.append(interface["slave2"])
                for interface in host.interfaces:
                    if interface['type'] == 'ether':
                        if interface["name"] not in bond_names:
                            host_info["interfaces"].append({
                                "key": interface["name"],
                                "value": get_host_network_url(interface)
                            })
                    else:
                        host_info["interfaces"].append({
                            "key": interface["name"],
                            "value": get_host_network_url(interface)
                        })
                host_info["interfaces"].sort()
                host_list.append(host_info)
    except Exception:
        exceptions.handle(request,
                          _('Unable to retrieve host list.'))
    return host_list


class NetWorkMappingFilterAction(tables.FilterAction):
    def filter(self, table, hosts, filter_string):
        pass


class ToggleMappingAction(actions.OperateRegionAction):
    name = "toggle_mapping"
    verbose_name = _("Config Netplane")


def get_host_role_url(host):
    template_name = 'environment/overview/host_roles.html'
    context = {
        "host_id": host["host_id"],
        "roles": host["roles"],
    }
    return template.loader.render_to_string(template_name, context)


class NetworkMappingTable(tables.DataTable):
    host_name = tables.Column("name",
                              verbose_name=_("Name"))
    roles = tables.Column(get_host_role_url,
                          verbose_name=_('Roles'))

    def __init__(self, request, data=None, needs_form_wrapper=None, **kwargs):
        super(NetworkMappingTable, self).__init__(request, data, needs_form_wrapper, **kwargs)
        try:
            hosts = get_host_list(request, kwargs["cluster_id"])
            dynamic_heads = get_host_table_dynamic_heads(hosts)
            count = 0
            for dynamic_head in dynamic_heads:
                count += 1
                column = tables.Column(dynamic_head,
                                       verbose_name=_("Net Port") + str(count))
                column.table = self
                self.columns[dynamic_head] = column
                self._populate_data_cache()
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to dynamic table head.'))

    def get_object_id(self, datum):
        return datum["host_id"]

    class Meta(object):
        name = 'network_mapping'
        verbose_name = _("Network Mapping")
        multi_select = True   
        table_actions = (NetWorkMappingFilterAction, ToggleMappingAction)


class NetworkMappingView(tables.DataTableView):
    table_class = NetworkMappingTable
    template_name = "environment/deploy/network_mapping.html"

    def get_data(self):
        hosts_data = []
        hosts = get_host_list(self.request, self.kwargs["cluster_id"])
        for host in hosts:
            host_info = {
                "host_id": host["host_id"],
                "name": host["name"],
                "roles": host["roles"]}
            i = 0
            for interface in host["interfaces"]:
                host_info["eth" + str(i)] = interface["value"]
                i += 1
            hosts_data.append(host_info)

        return hosts_data

    def get_net_plane(self):
        network_data = []
        try:
            network_list = api.daisy.network_list(self.request,
                                                  self.kwargs["cluster_id"])
            for network in network_list:
                network_info = {
                    "id": network.id,
                    "name": network.name,
                    "type": network.network_type}
                network_data.append(network_info)
            network_data.sort(key=lambda x: x['name'])
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve network list.'))
        return network_data

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c
        return None

    def get_context_data(self, **kwargs):
        context = super(NetworkMappingView, self).get_context_data(**kwargs)
        context['cluster_id'] = self.kwargs["cluster_id"]
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context['networks'] = self.get_net_plane()

        c = self.get_current_cluster(context['clusters'], context["cluster_id"])
        if c:
            context["current_cluster"] = c.name
            context["segment_type"] = c.segmentation_type

            if context["segment_type"] == 'vlan' or context["segment_type"] == 'flat':
                context['networks']  = [n 
                    for n in context['networks']  if n['name'] != "VXLAN"]
            if context["segment_type"] == 'vxlan':
                context['networks']  = [n 
                    for n in context['networks']  if n['name'] != "PRIVATE"]

        else:
            context["current_cluster"] = ""  


        wizard_cache.set_cache(context['cluster_id'], "networkmapping", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])

        return context


def clean_none_attr(dict):
    for key in dict.keys():
        if dict[key] == None:
            del dict[key]
    if dict.has_key('created_at'):
        del dict['created_at']

    if dict.has_key('updated_at'):
        del dict['updated_at']

    if dict.has_key('id'):
        del dict['id']


def netplane_in_list(name, net_list):
    for net in net_list:
        if net['name'] == name:
            return True

    return False


@csrf_exempt
def update_interfaces(interfaces_old, eth_ports):
    ether_interfaces = [i for i in interfaces_old if i['type'] == 'ether']
    bond_interfaces = [i for i in interfaces_old if i['type'] == 'bond']

    for ether in ether_interfaces:
        clean_none_attr(ether)
        for eth_port in eth_ports:
            if ether['name'] == eth_port['name']:
                ether['assigned_networks'] = eth_port['assigned_networks']
                if eth_port.get("vswitch_type"):
                    ether["vswitch_type"] = eth_port['vswitch_type']
                break

    for bond in bond_interfaces:
        clean_none_attr(bond)
        for eth_port in eth_ports:
            if bond['name'] == eth_port['name']:
                bond['assigned_networks'] = eth_port['assigned_networks']
                if eth_port.get("vswitch_type"):
                    bond["vswitch_type"] = eth_port['vswitch_type']                
                bond["slaves"] = [bond['slave1'], bond['slave2']]
                del bond['slave1']
                del bond['slave2']
                break
    ether_interfaces.extend(bond_interfaces)
    return ether_interfaces


@csrf_exempt
def assign_net_work(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    eth_ports = data["eth_ports"]

    try:
        for host_id in hosts:
            host = api.daisy.host_get(request, host_id)
            host_dict = host.to_dict()
            host_dict['cluster'] = cluster_id
            host_interfaces = update_interfaces(host_dict["interfaces"], eth_ports)
            api.daisy.host_update(request, host_id, cluster=cluster_id, interfaces=host_interfaces)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        return response

    response.status_code = 200
    return response


@csrf_exempt
def net_mapping_next(request, cluster_id):
    wizard_cache.set_cache(cluster_id, "networkmapping", 2)
    url = reverse('horizon:environment:deploy:hosts_config',
                  args=[cluster_id])
    response = http.HttpResponseRedirect(url)
    return response