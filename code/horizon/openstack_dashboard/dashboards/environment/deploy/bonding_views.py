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

import json
import logging

from django import http
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django import template
from django.utils.translation import ugettext_lazy as _
from django.core.urlresolvers import reverse

from horizon import messages
from horizon import exceptions
from horizon import tables

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy import actions
from openstack_dashboard.dashboards.environment.deploy import wizard_cache
from openstack_dashboard.dashboards.environment.deploy import deploy_rule_lib

LOG = logging.getLogger(__name__)


def get_host_bond_net_port_url(interface):
    template_name = 'environment/deploy/hosts_net_port.html'
    context = {
        "interface": interface
    }
    return template.loader.render_to_string(template_name, context)


def get_host_role_url(host):
    template_name = 'environment/host/host_roles.html'
    context = {
        "host_id": host["host_id"],
        "roles": host["roles"],
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
                    "os_status": host.os_status,
                    "interfaces": []
                }
                if hasattr(host, "role"):
                    if len(host.role):
                        host.role.sort()
                        host_info["roles"] = host.role
                bond_names = []
                bond_interfaces = [i for i in host.interfaces
                                   if i['type'] == 'bond']
                for interface in bond_interfaces:
                    bond_names.append(interface["slave1"])
                    bond_names.append(interface["slave2"])
                for interface in host.interfaces:
                    if interface['type'] == 'ether':
                        if interface["name"] not in bond_names:
                            host_info["interfaces"].append({
                                "key": interface["name"],
                                "value": get_host_bond_net_port_url(interface)
                            })
                    else:
                        if interface['type'] != "vlan":
                            host_info["interfaces"].append({
                                "key": interface["name"],
                                "value": get_host_bond_net_port_url(interface)
                            })
                host_info["interfaces"].sort()
                host_list.append(host_info)
    except Exception, e:
        messages.error(request, e)
        LOG.info('Unable to retrieve host list.')
    return host_list


class HostBondingFilterAction(tables.FilterAction):
    def filter(self, table, hosts, filter_string):
        pass


class ToggleBondAction(actions.OperateRegionAction):
    name = "toggle_bonding"
    verbose_name = _("Bond Net Port")


class BondingTable(tables.DataTable):
    host_name = tables.Column("name",
                              verbose_name=_("Name"))
    roles = tables.Column(get_host_role_url,
                          verbose_name=_('Roles'))
    os_status = tables.Column("os_status",
                              verbose_name=_('OS Status'),
                              hidden=True)

    def __init__(self, request, data=None, needs_form_wrapper=None, **kwargs):
        super(BondingTable, self).__init__(request,
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
                              _('Unable to create dynamic table head.'))

    def get_object_id(self, datum):
        return datum["host_id"]

    class Meta(object):
        name = 'bond_net_port'
        verbose_name = _("Bond Net Port")
        multi_select = True
        table_actions = (HostBondingFilterAction, ToggleBondAction)


class BondingView(tables.DataTableView):
    table_class = BondingTable
    template_name = "environment/deploy/bonding.html"

    def get_data(self):
        hosts_data = []
        hosts = get_host_list(self.request, self.kwargs["cluster_id"])
        for host in hosts:
            host_info = {
                "host_id": host["host_id"],
                "name": host["name"],
                "roles": host["roles"],
                "os_status": host["os_status"]}
            i = 0
            for interface in host["interfaces"]:
                host_info["eth" + str(i)] = interface["value"]
                i += 1
            hosts_data.append(host_info)

        return hosts_data

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c.name
        return ""

    def get_context_data(self, **kwargs):
        context = super(BondingView, self).get_context_data(**kwargs)
        context['cluster_id'] = self.kwargs["cluster_id"]
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        wizard_cache.set_cache(context['cluster_id'], "bonding", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])
        context["current_cluster"] = \
            self.get_current_cluster(context['clusters'],
                                     context["cluster_id"])

        return context


@csrf_exempt
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


@csrf_exempt
def update_interfaces(interfaces_old, bond_params):
    ether_interfaces = [i for i in interfaces_old if i['type'] == 'ether']
    bond_interfaces = [i for i in interfaces_old if i['type'] == 'bond']

    for ether in ether_interfaces:
        clean_none_attr(ether)
    for bond in bond_interfaces:
        clean_none_attr(bond)
        bond["slaves"] = [bond['slave1'], bond['slave2']]
        del bond['slave1']
        del bond['slave2']
    bond_interfaces.append({
        "type": "bond",
        "name": bond_params["name"],
        "mode": bond_params["mode"],
        "bond_type": bond_params["bond_type"],
        "slaves": bond_params["net_ports"]
    })
    ether_interfaces.extend(bond_interfaces)
    return ether_interfaces


@csrf_exempt
def bond_net_port(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    bond_params = data["bond_params"]
    try:
        for host_id in hosts:
            host = api.daisy.host_get(request, host_id)
            deploy_rule_lib.net_port_4_net_map_rule(host.interfaces,
                                                    bond_params["net_ports"])
            host_dict = host.to_dict()
            host_dict['cluster'] = cluster_id
            host_interfaces = \
                update_interfaces(host_dict["interfaces"], bond_params)
            api.daisy.host_update(request,
                                  host_id,
                                  cluster=cluster_id,
                                  interfaces=host_interfaces)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("bond net port to host failed!")
        return response

    response.status_code = 200
    return response


@csrf_exempt
def un_bond_net_port(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    net_ports = data["net_ports"]
    try:
        for host_id in hosts:
            host = api.daisy.host_get(request, host_id)
            deploy_rule_lib.net_port_4_net_map_rule(host.interfaces,
                                                    net_ports)
            host_dict = host.to_dict()
            host_dict['cluster'] = cluster_id
            interfaces = []
            for interface in host_dict["interfaces"]:
                if interface["name"] not in net_ports:
                    interfaces.append(interface)
            for interface in interfaces:
                clean_none_attr(interface)
                if interface["type"] == "bond":
                    interface["slaves"] = \
                        [interface["slave1"], interface["slave2"]]
            api.daisy.host_update(request,
                                  host_id,
                                  cluster=cluster_id,
                                  interfaces=interfaces)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("bond net port to host failed!")
        return response
    response.status_code = 200
    return response


@csrf_exempt
def bond_net_port_next(request, cluster_id):
    wizard_cache.set_cache(cluster_id, "bonding", 2)
    url = reverse('horizon:environment:deploy:networkmapping',
                  args=[cluster_id])
    response = http.HttpResponseRedirect(url)
    LOG.info("url %s", url)
    return response
