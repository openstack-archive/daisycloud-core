#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
import json

from django.utils.translation import ugettext
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _

from horizon import tables
from horizon import exceptions

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.cluster import tables \
    as cluster_tables
from openstack_dashboard.dashboards.environment.cluster import role \
    as cluster_role
from openstack_dashboard.dashboards.environment.host \
    import views as host_views
from openstack_dashboard.dashboards.environment.deploy import wizard_cache
from openstack_dashboard.dashboards.environment.version import views \
    as version_views

import logging
LOG = logging.getLogger(__name__)


def get_script_path():
    return getattr(settings, 'DAISY_OS_PATH', "/var/lib/daisy/versionfile/os/")


def count_deploy_info(request, host_list):
    backends = get_backend_type_by_role_list(request)
    deploy_data = {
        "success_host_num": 0,
        "on_going_host_num": 0,
        "on_uninstalling_host_num": 0,
        "on_updating_host_num": 0,
        "undeploy_host_num": 0,
        "failed_host_num": 0,
        "hosts": []}
    for host in host_list:
        deploy_info = host_views.\
            get_backends_deploy_info(backends,
                                     host.os_status,
                                     getattr(host, "role_status", None),
                                     host.os_progress,
                                     host.messages,
                                     getattr(host, "role_progress", 0),
                                     getattr(host, "role_messages", " "))
        if deploy_info.get("count", None):
            deploy_data[deploy_info["count"]] += 1

        current_version = ""
        if getattr(host, "os_version_id", None):
            version = api.daisy.version_get(request,
                                            host.os_version_id)
            if version:
                current_version += version.name + ","
        if getattr(host, "tecs_version_id", None):
            version = api.daisy.version_get(request,
                                            host.tecs_version_id)
            if version:
                current_version += version.name + ","

        i18n_list = deploy_info.get("i18n", 'unknown').split(",")
        status_info = _(i18n_list[0])
        if len(i18n_list) > 1:
            status_info = "%s, %s" % (i18n_list[0], i18n_list[1])

        message = deploy_info.get("role_message", "")
        analyze_result = cluster_tables.analyze_role_msg(message)

        host = {
            "id": host.id,
            "progress": deploy_info.get("progress", None),
            "message": deploy_info.get("message", ""),
            "bar_type": deploy_info.get("bar_type", "progress-bar-info"),
            "os_status": host.os_status,
            "role_status": getattr(host, "role_status", None),
            "status": ugettext(deploy_info.get("i18n", 'unknown')),
            "current_version": current_version}

        deploy_data["hosts"].append(host)
    return deploy_data


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

    def get_context_data(self, **kwargs):
        context = super(ClusterView, self).get_context_data(**kwargs)
        backend_types = api.daisy.backend_types_get(self.request)
        backend_types_dict = backend_types.to_dict()
        context['clusters'] = self.get_clusters()
        context["pre_url"] = "/dashboard/environment/"
        context["cluster_id"] = self.kwargs["cluster_id"]
        context["current_cluster"] = \
            self.get_current_cluster(context['clusters'],
                                     context["cluster_id"])

        qp = {"cluster_id": context["cluster_id"]}
        host_list = api.daisy.host_list(self.request, filters=qp)
        backends = host_views.get_backend_type_by_role_list(self.request)
        context['target_systems'] = getattr(self.table, "target_systems", "")
        target_system_list = context['target_systems'].split("+")
        context["data"] = count_deploy_info(backends, host_list)
        context['tecs_version_list'] = \
            version_views.get_kolla_version_list(self.request)
        return context

    def get_backends(self):
        backends = host_views.get_backend_type_by_role_list(self.request)
        return backends

    def get_data(self):
        cluster_id = self.kwargs["cluster_id"]
        target_system_list = getattr(self.table, "target_systems", "").\
            split("+")

        qp = {"cluster_id": cluster_id}
        host_list = api.daisy.host_list(self.request, filters=qp)
        host_status_list = []

        host_manage_ip = ""
        role_messages = ""
        roles = None

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

            if hasattr(host_detail, "role"):
                roles = host_detail.role
                roles.sort()

            if not hasattr(host, 'role_progress'):
                host.role_progress = 0

            if not hasattr(host, 'role_status'):
                host.role_status = ""
            backends = host_views.get_backend_type_by_role_list(self.request)
           
            host.current_version = []
            if hasattr(host, 'os_version_id') and host.os_version_id:
                version = api.daisy.version_get(self.request,
                                                host.os_version_id)
                if version:
                    host.current_version.append(version.name)
            if hasattr(host, 'tecs_version_id') and host.tecs_version_id:
                version = api.daisy.version_get(self.request,
                                                host.tecs_version_id)
                if version:
                    host.current_version.append(version.name)
            for i in range(2 - len(host.current_version)):
                host.current_version.append("")

            host_status_list.append({
                "cluster_id": cluster_id,
                "host_name": host.name,
                "host_manager_ip": host_manage_ip,
                "host_current_version": host.current_version,
                "host_os_progress": host.os_progress,
                "host_os_status": host.os_status,
                "host_role_progress": host.role_progress,
                "host_role_status": host.role_status,
                "host_messages": host.messages,
                "role_messages": role_messages,
                "host_id": host.id,
                "backends": backends,
                "roles": cluster_role.get_roles_detail(self.request,
                                                       roles,
                                                       cluster_id)})
        return host_status_list


@csrf_exempt
def ClusterDelete(request):
    response = HttpResponse()
    data = json.loads(request.body)

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
def update_deploy_info(request, cluster_id):
    deploy_data = {}
    status_code = 200
    try:
        qp = {"cluster_id": cluster_id}
        host_list = api.daisy.host_list(request, filters=qp)
        backends = host_views.get_backend_type_by_role_list(request)
        deploy_data = count_deploy_info(backends, host_list)
    except Exception as e:
        status_code = 500
        LOG.error("update deploy info failed: %s" % e)
        messages.error(request, e)
    return HttpResponse(json.dumps(deploy_data),
                        content_type="application/json",
                        status=status_code)


@csrf_exempt
def upgrade_cluster(request, cluster_id):
    response = http.HttpResponse()

    data = json.loads(request.body)
    try:
        # Check version file exist or not
        version_views.check_version_file_exist(request,
                                               data["version_id"],
                                               "system")
        # Check host os/kolla install status
        error_host_names = check_all_tecs_install_status(request, cluster_id)
        if len(error_host_names) > 0:
            msg = _("TECS is in the process of execution, init or "
                    "install failed. %s") % error_host_names
            raise exceptions.WorkflowValidationError(msg)

        params = {"cluster_id": cluster_id,
                  "update_object": "kolla",
                  "version_id": data["version_id"]}
        LOG.info("KOLLA upgrade=%s", params)
        api.daisy.upgrade_cluster(request, **params)
        messages.success(request, _('KOLLA upgrade start'))
        response.status_code = 200
    except Exception as e:
        messages.error(request, _("Upgrade cluster failed! %s") % e)
        LOG.error("Upgrade cluster failed! %s" % e)
        response.status_code = 200

        return response


def check_all_tecs_install_status(request, cluster_id):
    error_host_names = []

    host_list = \
        api.daisy.host_list(request, filters={"cluster_id": cluster_id})
    for host in host_list:
        if host.os_status == "update-failed" or host.os_status == "active":
            if host.role_status != "uninstall-failed" \
                    and host.role_status != "update-failed" \
                    and host.role_status != "rollback-failed" \
                    and host.role_status != "active":
                error_host_names.append(host.name)
        else:
            error_host_names.append(host.name)

    return error_host_names

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
