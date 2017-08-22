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

from django import http
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy
from django import template

from horizon import messages
from horizon import exceptions
from horizon import tables

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy import actions
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

import logging
LOG = logging.getLogger(__name__)


def get_host_role_url(host):
    template_name = 'environment/deploy/hosts_role.html'
    context = {
        "host_id": host["host_id"],
        "roles": host["roles"],
    }
    return template.loader.render_to_string(template_name, context)


class DeleteRole(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Role",
            u"Delete Roles",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted Role",
            u"Deleted Roles",
            count
        )

    def delete(self, request, obj_id):
        try:
            api.daisy.host_update(request,
                                  obj_id,
                                  cluster=self.table.kwargs["cluster_id"],
                                  role=[])
        except Exception:
            raise


class ManuallyAssignRole(actions.ManuallyAssignRoleAction):
    name = "manually_assign_role"
    verbose_name = _("Manually Assign Role")


class HostsTable(tables.DataTable):
    name = tables.Column("name",
                         verbose_name=_("Name"))
    roles = tables.Column(get_host_role_url,
                          verbose_name=_('Roles'))

    def get_object_id(self, datum):
        return datum["host_id"]

    class Meta(object):
        name = "hosts"
        verbose_name = _("Hosts")
        table_actions = (ManuallyAssignRole, DeleteRole, )
        # table_actions_menu = ( )


class IndexView(tables.DataTableView):
    table_class = HostsTable
    template_name = 'environment/deploy/hosts_role_assignment.html'
    page_title = _("Host")

    def get_data(self):
        hosts_data = []
        try:
            cluster = api.daisy.cluster_get(self.request,
                                            self.kwargs["cluster_id"])

            if not hasattr(cluster, 'nodes'):
                return hosts_data

            for node in cluster.nodes:
                host = api.daisy.host_get(self.request, node)
                roles = []
                if hasattr(host, "role"):
                    roles = host.role
                    roles.sort()
                hosts_data.append({
                    "host_id": host.id,
                    "name": host.name,
                    "roles": roles
                })
        except Exception, e:
            messages.error(self.request, e)
            LOG.info('Unable to retrieve host list.')
        return hosts_data

    def get_roles_data(self):
        roles_data = []
        try:
            role_list = api.daisy.role_list(self.request)
            roles = [role for role in role_list
                     if role.cluster_id == self.kwargs["cluster_id"]]
            for role in roles:
                roles_data.append({
                    "id": role.id,
                    "name": role.name
                })
            roles_data.sort(key=lambda x: x['name'])
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve host list.'))

        return roles_data

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c.name
        return ""

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        roles = self.get_roles_data()
        self.table.roles = roles
        context["roles"] = roles
        context["cluster_id"] = self.kwargs["cluster_id"]
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        wizard_cache.set_cache(context['cluster_id'],
                               "hosts_role_assignment", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])
        context["current_cluster"] = \
            self.get_current_cluster(context['clusters'],
                                     context["cluster_id"])

        return context


@csrf_exempt
def assign_host_role(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    roles = data["roles"]

    try:
        for host_id in hosts:
            api.daisy.host_update(request,
                                  host_id,
                                  cluster=cluster_id,
                                  role=roles)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("assign role to host failed!")
        return response

    response.status_code = 200
    return response


@csrf_exempt
def hosts_role_assignment_next(request, cluster_id):
    wizard_cache.set_cache(cluster_id, "hosts_role_assignment", 2)
    url = reverse('horizon:environment:deploy:bonding',
                  args=[cluster_id])
    response = http.HttpResponseRedirect(url)
    return response
