# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging

from django import template
from django.template.defaultfilters import title
from django.utils.http import urlencode
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import npgettext_lazy
from django.utils.translation import ungettext_lazy
from django.utils.translation import pgettext_lazy
from django.core import urlresolvers
from django.core.urlresolvers import reverse

from horizon import exceptions
from horizon import messages
from horizon import tables
from horizon.utils import filters
from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

LOG = logging.getLogger(__name__)
dot_count = 0


class AddHost(tables.LinkAction):
    name = "add"
    verbose_name = _("Add Host")
    url = "horizon:environment:deploy:selecthosts"
    icon = "plus"
    classes = ('btn-primary',)

    def get_link_url(self):
        wizard_cache.clean_cache(self.table.kwargs["cluster_id"])
        return urlresolvers.reverse(self.url, args=(self.table.kwargs["cluster_id"],))


class DeleteHost(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Host",
            u"Delete Hosts",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted Host",
            u"Deleted Hosts",
            count
        )

    name = "delete"
    verbose_name = "delete"

    def delete(self, request, host_id):
        api.daisy.delete_host_from_cluster(request, self.table.kwargs["cluster_id"], host_id)


class GenerateTemplate(tables.LinkAction):
    name = "generate"
    verbose_name = _("Generate Host Template")
    url = "horizon:environment:cluster:generate_host_template"
    classes = ("ajax-modal", "btn-generate-template")

    def get_link_url(self, datum):
        cluster_id = self.table.kwargs["cluster_id"]
        host_id = self.table.get_object_id(datum)
        base_url = reverse(self.url, args=(cluster_id, host_id))
        return base_url

    def allowed(self, request, host):
        return host["host_os_status"] == 'active' and host["host_role_status"] == "active"


def get_cluster_id(request, cluster_name):
    try:
        clusters = api.daisy.cluster_list(request)
        for cluster in clusters:
            if cluster.name == cluster_name:
                return cluster.id
    except Exception, e:
        messages.error(request, e)


class ReDeployHost(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"ReDeploy Host",
            u"ReDeploy Hosts",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"ReDeploy Host",
            u"ReDeploy Hosts",
            count
        )

    name = "redeploy_host"
    verbose_name = "ReDeploy Host"

    def delete(self, request, host_id):
        try:
            host = api.daisy.host_get(request, host_id)
            cluster_name = host.cluster
            cluster_id = get_cluster_id(request, cluster_name)
            api.daisy.delete_host_from_cluster(request, cluster_id, host_id)
            api.daisy.host_update(request, host_id,
                                  os_status="init")
        except Exception, e:
            messages.error(request, e)


def get_progress(host):
    dot = "......"

    global dot_count
    dot_count += 1
    if dot_count == 7:
        dot_count = 1
        
    if ((host["host_os_status"] == 'init' or \
          host["host_os_status"] == 'installing' or \
          host["host_os_status"] == 'updating') and \
        host["host_messages"] != ''):
        host["host_messages"] += dot[0:dot_count]
    if ((host["host_role_status"] == 'init' or \
         host["host_role_status"] == 'installing' or \
         host["host_role_status"] == 'uninstalling' or \
         host["host_role_status"] == 'updating') and \
        host["role_messages"] != '' and \
        host["role_messages"] != None):
        host["role_messages"] += dot[0:dot_count]
    if host["host_os_status"] == 'init' and host["host_role_status"] == 'init':
        context = {
            "progress": 0,
            "message": host["host_messages"],
            "bar_type": 'progress-bar-info'
        }
    elif host["host_os_status"] == 'installing':
        context = {
            "progress": host["host_os_progress"],
            "message": host["host_messages"],
            "bar_type": 'progress-bar-info'
        }
    elif host["host_os_status"] == 'install-failed':
        context = {
            "progress":  host["host_os_progress"],
            "message": host["host_messages"],
            "bar_type": 'progress-bar-danger'
        }
    elif host["host_os_status"] == 'updating':
        context = {
            "progress":  host["host_os_progress"],
            "message": host["host_messages"],
            "bar_type": 'progress-bar-update'
        }
    elif host["host_os_status"] == 'update-failed':
        context = {
            "progress":  host["host_os_progress"],
            "message": host["host_messages"],
            "bar_type": 'progress-bar-danger'
        }
    elif host["host_os_status"] == 'active' and host["host_role_status"] == 'init':
        context = {
            "progress": host["host_role_progress"],
            "message": host["role_messages"],
            "bar_type": 'progress-bar-info'
        }
    elif host["host_os_status"] == 'active' and host["host_role_status"] is None:
        context = {
            "progress": host["host_os_status"],
            "message": host["host_message"],
            "bar_type": 'progress-bar-success'
        }
    elif host["host_os_status"] == 'active' and host["host_role_status"] == 'installing':
        context = {
            "progress": host["host_role_progress"],
            "message": host["role_messages"],
            "bar_type": 'progress-bar-info'
        }
    elif host["host_os_status"] == 'active' and host["host_role_status"] == 'updating':
        context = {
            "progress": host["host_role_progress"],
            "message": host["role_messages"],
            "bar_type": 'progress-bar-update'
        }
    elif host["host_os_status"] == 'active' and host["host_role_status"] == "uninstalling":
        context = {
            "progress": host["host_role_progress"],
            "message": host["role_messages"],
            "bar_type": 'progress-bar-uninstall'
        }
    elif host["host_role_status"] == 'install-failed':
        context = {
            "progress":  host["host_role_progress"],
            "message": host["role_messages"],
            "bar_type": 'progress-bar-danger'
        }
    elif host["host_role_status"] == 'update-failed':
        context = {
            "progress":  host["host_role_progress"],
            "message": host["role_messages"],
            "bar_type": 'progress-bar-danger'
        }
    elif host["host_role_status"] == "uninstall-failed":
        context = {
            "progress": host["host_role_progress"],
            "message": host["role_messages"],
            "bar_type": 'progress-bar-danger'
        }
    elif host["host_os_status"] == 'active' and host["host_role_status"] == "active":
        context = {
            "progress": 100,
            "message": host["role_messages"],
            "bar_type": 'progress-bar-success'
        }
    else:
        context = {
            "progress": 0,
            "message": " ",
            "bar_type": 'progress-bar-info'
        }

    template_name = 'environment/cluster/_host_progress.html'
    return template.loader.render_to_string(template_name, context)


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, host_id):
        try:
            qp = {"cluster_id": self.table.kwargs["cluster_id"]}
            host_list = api.daisy.host_list(request, filters=qp)
            host_manage_ip = ""
            for host in host_list:
                if host.os_progress is None:
                    host.os_progress = 0
                if host.messages is None:
                    host.messages = ""

                if host.id == host_id:
                    host_detail = api.daisy.host_get(request, host.id)
                    if hasattr(host_detail, "interfaces"):
                        for nic in host_detail.interfaces:
                            nic_assigned_networks = nic['assigned_networks']
                            for network in nic_assigned_networks:
                                if network["name"] == 'MANAGEMENT':
                                    host_manage_ip = network["ip"]
                    else:
                        host_manage_ip = ""

                    if not hasattr(host, 'role_progress'):
                        host.role_progress = 0

                    if not hasattr(host, 'role_status'):
                        host.role_status = ""

                    if not hasattr(host, "role_messages"):
                        host.role_messages = ""

                    return {"host_name": host.name,
                            "host_manager_ip": host_manage_ip,
                            "host_os_progress": host.os_progress,
                            "host_os_status": host.os_status,
                            "host_role_progress": host.role_progress,
                            "host_role_status": host.role_status,
                            "host_messages": host.messages,
                            "role_messages": host.role_messages,
                            "host_id": host.id}

        except Exception as e:
            LOG.error("wmh dbg: e=%s" % e)

class HostsTable(tables.DataTable):

    STATUS_CHOICES = (
    ("", True),
    )

    OS_STATUS_CHOICES = (
        ("init",None),
        ("installing",None),
        ("install-failed",False),
        ("updating",None),
        ("update-failed",False),
        ("active",True),
    )

    ROLE_STATUS_CHOICES = (
        ("",None),
        ("init",None),
        ("installing",None),
        ("uninstalling",None),
        ("install-failed",False),
        ("uninstall-failed",False),
        ("updating",None),
        ("update-failed",False),
        ("active",True),
    )
    name = tables.Column('host_name', verbose_name=_('Name'))
    manager_ip = tables.Column('host_manager_ip', verbose_name=_('Manager Ip'))
    progress = tables.Column(get_progress,
                             verbose_name=_('progress'))
    host_os_status = tables.Column('host_os_status',
                             verbose_name=_('host_os_status'),
                             hidden=True,
                             status=True,
                             status_choices=OS_STATUS_CHOICES)
    host_role_status = tables.Column('host_role_status',
                             verbose_name=_('host_role_status'),
                             hidden=True,
                             status=True,
                             status_choices=ROLE_STATUS_CHOICES)
    def get_object_id(self, datum):
        return datum["host_id"]

    class Meta(object):
        name = "host"
        verbose_name = _("Host")
        status_columns = ["host_os_status","host_role_status"]
        table_actions = (AddHost, DeleteHost, ReDeployHost)
        row_actions = (DeleteHost, GenerateTemplate, ReDeployHost)
        row_class = UpdateRow
