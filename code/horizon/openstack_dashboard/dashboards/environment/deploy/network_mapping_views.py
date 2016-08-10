#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

import json

from django import http
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django import template
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from horizon import messages
from horizon import exceptions
from horizon import tables

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.cluster import role \
    as cluster_role
from openstack_dashboard.dashboards.environment.deploy import actions
from openstack_dashboard.dashboards.environment.deploy import wizard_cache
from openstack_dashboard.dashboards.environment.deploy import deploy_rule_lib
from openstack_dashboard.dashboards.environment.host import views as host_views

import logging
LOG = logging.getLogger(__name__)


def get_host_network_url(net_planes, interface):
    for net_plane in net_planes:
        for assigned_network in interface["assigned_networks"]:
            if net_plane.name == assigned_network["name"]:
                assigned_network["network_type"] = net_plane.network_type
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
        net_planes = api.daisy.network_list(request, cluster_id)
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
                        host_info["roles"] = cluster_role.\
                            get_roles_detail(request, host.role, cluster_id)
                bond_names = []
                bond_interfaces = [i for i in host.interfaces
                                   if i['type'] == 'bond']
                for interface in bond_interfaces:
                    bond_names.append(interface["slave1"])
                    bond_names.append(interface["slave2"])
                for interface in host.interfaces:
                    interface_value = get_host_network_url(net_planes,
                                                           interface)
                    if interface['type'] == 'ether':
                        if interface["name"] not in bond_names:
                            host_info["interfaces"].append({
                                "key": interface["name"],
                                "value": interface_value
                            })
                    else:
                        if interface['type'] != "vlan":
                            host_info["interfaces"].append({
                                "key": interface["name"],
                                "value": interface_value
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
    template_name = 'environment/host/host_roles.html'
    context = {
        "host_id": host["host_id"],
        "roles": host["roles"],
    }
    return template.loader.render_to_string(template_name, context)


class NetworkMappingTable(tables.DataTable):
    host_name = tables.Column("name",
                              verbose_name=_("Name"))
    roles = tables.Column(cluster_role.get_role_html_detail,
                          verbose_name=_("Roles"))

    def __init__(self, request, data=None, needs_form_wrapper=None, **kwargs):
        super(NetworkMappingTable, self).__init__(request,
                                                  data,
                                                  needs_form_wrapper,
                                                  **kwargs)
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
            filter_net_planes = ["DEPLOYMENT", "EXTERNAL"]
            network_list = api.daisy.network_list(self.request,
                                                  self.kwargs["cluster_id"])
            for network in network_list:
                if network.network_type not in filter_net_planes:
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

        c = self.get_current_cluster(context['clusters'],
                                     context["cluster_id"])
        if c:
            context["current_cluster"] = c.name
            context["segment_type"] = c.segmentation_type
            context['networks'] = [n for n in context['networks']]
        else:
            context["current_cluster"] = ""

        wizard_cache.set_cache(context['cluster_id'], "networkmapping", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])

        return context


def clean_none_attr(dict):
    for key in dict.keys():
        if dict[key] is None:
            del dict[key]

    if 'created_at' in dict:
        del dict['created_at']

    if 'updated_at' in dict:
        del dict['updated_at']

    if 'id' in dict:
        del dict['id']


def netplane_in_list(name, net_list):
    for net in net_list:
        if net['name'] == name:
            return True

    return False


@csrf_exempt
def update_interface_net_plane(interfaces_old, eth_ports):
    interfaces = [i for i in interfaces_old]

    # clean none attr
    for interface in interfaces:
        clean_none_attr(interface)
        if interface["type"] == 'bond':
            interface["slaves"] = [interface['slave1'], interface['slave2']]
            del interface['slave1']
            del interface['slave2']

    # update new net plane
    for interface in interfaces:
        for eth_port in eth_ports:
            if interface["name"] != eth_port["name"]:
                continue
            new_net_planes = []
            for in_assigned_network in eth_port['assigned_networks']:
                new_net_plane = {"name": in_assigned_network["name"]}
                for assigned_network in interface["assigned_networks"]:
                    if in_assigned_network["name"] == \
                            assigned_network["name"]:
                        new_net_plane["ip"] = assigned_network["ip"]
                new_net_planes.append(new_net_plane)
            interface["assigned_networks"] = new_net_planes
            interface["vswitch_type"] = eth_port["vswitch_type"]

    return interfaces


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
            host_interfaces = \
                update_interface_net_plane(host_dict["interfaces"], eth_ports)
            ha_role = deploy_rule_lib.get_ha_role(request, cluster_id)
            host_dict["interfaces"] = host_interfaces
            network_list = api.daisy.network_list(request, cluster_id)
            backends = host_views.get_backend_type_by_role_list(request)
            deploy_rule_lib.host_net_plane_rule(ha_role,
                                                host_dict,
                                                network_list,
                                                backends)
            api.daisy.host_update(request,
                                  host_id,
                                  cluster=cluster_id,
                                  interfaces=host_interfaces)
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


@csrf_exempt
def net_mapping_check(request, cluster_id):
    response = HttpResponse()
    try:
        rule_context = deploy_rule_lib.get_rule_context(request, cluster_id)
        deploy_rule_lib.hosts_net_plane_rule(rule_context)
    except Exception, e:
        LOG.info("net_mapping_check failed!%s", e)
        messages.error(request, e)
        exceptions.handle(request, e)
        response.status_code = 500
        return response
    response.status_code = 200
    return response
