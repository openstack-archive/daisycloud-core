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
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy
from django.core import urlresolvers
from horizon import tables
from horizon import messages
from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.cluster import role \
    as cluster_role
from openstack_dashboard.dashboards.environment.deploy import wizard_cache
from openstack_dashboard.dashboards.environment.template \
    import views as template_views
from openstack_dashboard.dashboards.environment.host \
    import views as host_views
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
        return urlresolvers.reverse(self.url,
                                    args=(self.table.kwargs["cluster_id"],))


class DeleteHost(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Remove Host",
            u"Remove Hosts",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Remove Host",
            u"Remove Hosts",
            count
        )

    name = "delete"
    verbose_name = "delete"

    def _allowed(self, request, datum):
        return True

    def delete(self, request, host_id):
        api.daisy.delete_host_from_cluster(request,
                                           self.table.kwargs["cluster_id"],
                                           host_id)


def get_cluster_id(request, cluster_name):
    try:
        clusters = api.daisy.cluster_list(request)
        for cluster in clusters:
            if cluster.name == cluster_name:
                return cluster.id
    except Exception, e:
        messages.error(request, e)


class ReDeployHost(tables.BatchAction):
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
    classes = ("btn-danger",)

    def _allowed(self, request, datum):
        return True

    def action(self, request, host_id):
        try:
            api.daisy.host_update(request, host_id, os_status="init")
        except Exception, e:
            messages.error(request, e)


def get_install_status(host_detail):
    role_status = host_detail.get("role_status", None)
    '''
    deploy_info = host_views.get_deploy_info(host_detail["host_os_status"],
                                             role_status)
    '''
    LOG.info("hi kolla: %s" % host_detail["backends"][0])
    deploy_info = host_views.\
        get_backends_deploy_info(list(host_detail["backends"]),
                                 host_detail["host_os_status"],
                                 role_status)
    return _(deploy_info.get("i18n", 'unknown'))


def get_current_version(host_detail):
    template_name = 'environment/cluster/current_version.html'
    context = {"host_current_version": host_detail["host_current_version"]}
    return template.loader.render_to_string(template_name, context)


def get_progress(host):
    dot = "......"
    global dot_count
    os_indeterminate_states = ["init", "installing", "updating"]
    role_indeterminate_states = ["init", "installing",
                                 "uninstalling", "updating"]
    os_status = host["host_os_status"]
    role_status = host.get("host_role_status", None)

    dot_count += 1
    if dot_count == 7:
        dot_count = 1

    if os_status in os_indeterminate_states \
            and host["host_messages"]:
        host["host_messages"] += dot[0:dot_count]

    if role_status in role_indeterminate_states \
            and host["role_messages"]:
        host["role_messages"] += dot[0:dot_count]

    deploy_info = host_views.get_deploy_info(os_status, role_status,
                                             host["host_os_progress"],
                                             host["host_messages"],
                                             host["host_role_progress"],
                                             host["role_messages"])
    context = {
        "progress": deploy_info.get("progress", 0),
        "message": deploy_info.get("message", " "),
        "bar_type": deploy_info.get("bar_type", "progress-bar-info")}
    template_name = 'environment/cluster/_host_progress.html'
    return template.loader.render_to_string(template_name, context)


class HostsTable(tables.DataTable):
    name = tables.Column('host_name', verbose_name=_('Name'))
    host_role = tables.Column(cluster_role.get_role_html_detail,
                              verbose_name=_("Roles"))
    manager_ip = tables.Column('host_manager_ip', verbose_name=_('Manager Ip'))
    host_current_version = tables.Column(get_current_version,
                                         verbose_name=_('Installed Version'))
    install_status = tables.Column(get_install_status,
                                   verbose_name=_('Status'))
    progress = tables.Column(get_progress,
                             verbose_name=_('progress'))
    host_os_status = tables.Column('os_status',
                                   verbose_name=_('host_os_status'),
                                   hidden=True)
    host_role_status = tables.Column('host_role_status',
                                     verbose_name=_('host_role_status'),
                                     hidden=True)
    host_status = tables.Column('host_status',
                                verbose_name=_('host_status'),
                                hidden=True)


    def __init__(self, request, data=None, needs_form_wrapper=None, **kwargs):
        super(HostsTable, self).__init__(request,
                                         data,
                                         needs_form_wrapper,
                                         **kwargs)
        cluster_info = api.daisy.cluster_get(request, kwargs['cluster_id'])
        setattr(self, "target_systems", cluster_info.target_systems)
        # set some columns hide
        hidden_columns = ["host_role"]
        for column in self.columns.values():
            if column.__dict__["name"] in hidden_columns:
                hidden_found = 'hidden' in column.classes
                if cluster_info.target_systems == "os" and not hidden_found:
                    column.classes.append('hidden')
                elif cluster_info.target_systems != "os" and hidden_found:
                    column.classes.remove('hidden')

    def get_object_id(self, datum):
        return datum["host_id"]

    class Meta(object):
        name = "host"
        verbose_name = _("Host")
        table_actions = (AddHost, ReDeployHost, DeleteHost)
        row_actions = (DeleteHost, template_views.GenerateTemplate)
