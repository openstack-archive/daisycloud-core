#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
import json

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from horizon import forms
from horizon import messages
from horizon import tables
from horizon import exceptions

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.cluster import tables \
    as cluster_tables
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

import logging
LOG = logging.getLogger(__name__)


class ClusterView(tables.DataTableView):
    table_class = cluster_tables.HostsTable
    template_name = "environment/cluster/index.html"

    def get_clusters(self):
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        return cluster_lists

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c.name
        return ""

    def count_deploy_info(self, host_list):
        data = {"success_host_num": 0,
                "on_going_host_num": 0,
                "on_uninstalling_host_num": 0,
                "on_updating_host_num": 0,
                "undeploy_host_num": 0,
                "failed_host_num": 0}

        for host in host_list:
            if hasattr(host, 'role_status'):
                if host.role_status == "active" and host.os_status == "active":
                    data["success_host_num"] += 1
                elif host.role_status == "installing" \
                        or host.os_status == "installing":
                    data["on_going_host_num"] += 1
                elif host.role_status == "uninstalling":
                    data["on_uninstalling_host_num"] += 1
                elif host.role_status == "updating" \
                        or host.os_status == "updating":
                    data["on_updating_host_num"] += 1
                elif host.os_status == "init":
                    data["undeploy_host_num"] += 1
                else:
                    data["failed_host_num"] += 1
            else:
                if host.os_status == "active":
                    data["success_host_num"] += 1
                else:
                    data["failed_host_num"] += 1

        LOG.info("deploy info dbg: data=%s" % data)
        return data

    def get_context_data(self, **kwargs):
        context = super(ClusterView, self).get_context_data(**kwargs)
        context['clusters'] = self.get_clusters()
        context["pre_url"] = "/dashboard/environment/"
        context["cluster_id"] = self.kwargs["cluster_id"]
        context["current_cluster"] = \
            self.get_current_cluster(context['clusters'],
                                     context["cluster_id"])

        qp = {"cluster_id": context["cluster_id"]}
        host_list = api.daisy.host_list(self.request, filters=qp)
        context["data"] = self.count_deploy_info(host_list)
        return context

    def get_data(self):
        qp = {"cluster_id": self.kwargs["cluster_id"]}
        host_list = api.daisy.host_list(self.request, filters=qp)

        host_status_list = []
        host_manage_ip = ""
        role_messages = ""

        for host in host_list:
            if host.os_progress is None:
                host.os_progress = 0
            if host.messages is None:
                host.messages = ""
            if hasattr(host, "role_messages"):
                role_messages = host.role_messages

            host_detail = api.daisy.host_get(self.request, host.id)
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
            host_status_list.append({
                "host_name": host.name,
                "host_manager_ip": host_manage_ip,
                "host_os_progress": host.os_progress,
                "host_os_status": host.os_status,
                "host_role_progress": host.role_progress,
                "host_role_status": host.role_status,
                "host_messages": host.messages,
                "role_messages": role_messages,
                "host_id": host.id
            })

        LOG.info("get_data:host_status_list=%s" % host_status_list)
        return host_status_list


@csrf_exempt
def ClusterDelete(request):
    response = HttpResponse()
    data = json.loads(request.body)
    msg = ('Cluster delete request.body::::::: %s') % request.body
    LOG.info(msg)

    cluster_info = data["cluster_info"]
    try:
        api.daisy.cluster_delete(request,
                                 cluster_info["cluster_id"])
    except Exception:
        exceptions.handle(request, "Delete failed!")
        response.status_code = 500
        return response

    response.status_code = 200
    return response


@csrf_exempt
def update_badge(request, cluster_id):
    data = {"success_host_num": 0,
            "on_going_host_num": 0,
            "on_uninstalling_host_num": 0,
            "on_updating_host_num": 0,
            "undeploy_host_num": 0,
            "failed_host_num": 0}
    try:
        qp = {"cluster_id": cluster_id}
        host_list = api.daisy.host_list(request, filters=qp)
        for host in host_list:
            if hasattr(host, 'role_status'):
                if host.role_status == "active" and host.os_status == "active":
                    data["success_host_num"] += 1
                elif host.role_status == "installing" \
                        or host.os_status == "installing":
                    data["on_going_host_num"] += 1
                elif host.role_status == "uninstalling":
                    data["on_uninstalling_host_num"] += 1
                elif host.role_status == "updating" \
                        or host.os_status == "updating":
                    data["on_updating_host_num"] += 1
                elif host.os_status == "init":
                    data["undeploy_host_num"] += 1
                else:
                    data["failed_host_num"] += 1
            else:
                if host.os_status == "active":
                    data["success_host_num"] += 1
                else:
                    data["failed_host_num"] += 1
        response = HttpResponse(json.dumps(data),
                                content_type="application/json")
        response.status_code = 200
        return response
    except Exception as e:
        LOG.error("wmh dbg: e type = %s" % type(e))
        exceptions.handle(request, "update badge failed!")
        response = HttpResponse()
        response.status_code = 500
        return response


@csrf_exempt
def upgrade_cluster(request, cluster_id):
    try:
        api.daisy.upgrade_cluster(request, cluster_id)
        response = HttpResponse()
        response.status_code = 200
        return response
    except Exception as e:
        LOG.error("upgrade_cluster raise exceptions: %s" % e)
        response = HttpResponse()
        response.status_code = 200
        return response


def uninstall_version(request, cluster_id):
    try:
        api.daisy.uninstall_cluster(request, cluster_id)
        response = HttpResponse()
        response.status_code = 200
        wizard_cache.clean_cache(cluster_id)
        return response
    except Exception as e:
        LOG.error("uninstall_version raise exceptions: %s" % e)
        response = HttpResponse()
        response.status_code = 200
        return response


class GenerateHostTemplateForm(forms.SelfHandlingForm):
    name = forms.CharField(label=_("Name"), required=True)
    description = forms.CharField(widget=forms.widgets.Textarea(
                                  attrs={'rows': 4}),
                                  label=_("Description"),
                                  required=False)

    def clean(self):
        cleaned_data = super(GenerateHostTemplateForm, self).clean()
        return cleaned_data

    def handle(self, request, data):
        cluster_id = self.initial['cluster_id']
        host_id = self.initial['host_id']
        try:
            cluster = api.daisy.cluster_get(request, cluster_id)
            param = {
                "cluster_name": cluster.name,
                "host_template_name": data['name'],
                "host_id": host_id,
                "description": data["description"]
            }
            api.daisy.host_to_template(request, **param)
            message = _('Generate template: "%s"') % data['name']
            messages.success(request, message)
            return True
        except Exception:
            redirect = reverse('horizon:environment:cluster:overview',
                               args=[cluster_id])
            exceptions.handle(request,
                              _('Unable to generate template.'),
                              redirect=redirect)


class GenerateHostTemplateView(forms.ModalFormView):
    form_class = GenerateHostTemplateForm
    modal_header = _("Generate Host Template")
    submit_label = _("Generate Host Template")
    template_name = 'environment/cluster/host_template.html'
    submit_url = "horizon:environment:cluster:generate_host_template"
    page_title = _("Generate Host Template")

    def get_context_data(self, **kwargs):
        context = super(GenerateHostTemplateView, self).\
            get_context_data(**kwargs)
        cluster_id = self.kwargs["cluster_id"]
        host_id = self.kwargs["host_id"]
        context['submit_url'] = \
            reverse(self.submit_url, args=(cluster_id, host_id))
        return context

    def get_success_url(self):
        cluster_id = self.kwargs["cluster_id"]
        return reverse('horizon:environment:cluster:overview',
                       args=[cluster_id])

    def get_initial(self):
        cluster_id = self.kwargs["cluster_id"]
        host_id = self.kwargs["host_id"]
        return {'cluster_id': cluster_id,
                'host_id': host_id}
