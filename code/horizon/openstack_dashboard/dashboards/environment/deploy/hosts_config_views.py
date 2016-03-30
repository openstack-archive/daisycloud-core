#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
import os
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
import json
from django import template
from horizon import messages
from horizon import exceptions
from horizon import tables
from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy import actions
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

import logging
LOG = logging.getLogger(__name__)


class ToggleMappingAction(actions.OperateRegionAction):
    name = "toggle_mapping"
    verbose_name = _("Host Config")


class HostConfigFilterAction(tables.FilterAction):
    def filter(self, table, hosts, filter_string):
        pass


def get_host_role_url(host):
    template_name = 'environment/overview/host_roles.html'
    context = {
        "host_id": host["host_id"],
        "roles": host["roles"],
    }
    return template.loader.render_to_string(template_name, context)


class HostsTable(tables.DataTable):
    name = tables.Column("name",
                         verbose_name=_("Name"))
    roles = tables.Column(get_host_role_url,
                          verbose_name=_('Roles'))
    os_status = tables.Column("os_status",
                              verbose_name=_("OS Status"),
                              hidden=True)
    os_version_file = tables.Column("os_version_file",
                                    verbose_name=_('OS Version File'))
    root_disk = tables.Column("root_disk",
                              verbose_name=_('ROOT Disk'))
    root_lv_size = tables.Column("root_lv_size",
                                 verbose_name=_('ROOT LV Size(GB)'))
    ipmi_user = tables.Column("ipmi_user",
                              verbose_name=_('IPMI User'))
    cpu_number = tables.Column("cpu_number",
                               verbose_name=_('CPU Number'))
    isol_cpus = tables.Column("isol_cpus",
                              verbose_name=_('Isolation CPU'))
    memory_size = tables.Column("memory_size",
                                verbose_name=_('Memory Size'))
    huge_pages = tables.Column("huge_pages",
                               verbose_name=_('Huge Page Count'))
    huge_page_size = tables.Column("huge_page_size",
                                   verbose_name=_('Huge Page Size'))
    ipmi_passwd = tables.Column("ipmi_passwd",
                                verbose_name=_('IPMI Passwd'),
                                hidden=True)

    def get_object_id(self, datum):
        return datum["host_id"]

    class Meta(object):
        name = "hosts"
        verbose_name = _("Hosts")
        multi_select = True
        table_actions = (HostConfigFilterAction, ToggleMappingAction)


def get_version_path():
    return getattr(settings, 'DAISY_VER_PATH', "/var/lib/daisy/tecs/")


def get_version_files():
    ver_path = get_version_path()
    ver_files = []
    ver_file_format = ['.iso']
    items = os.listdir(ver_path)
    for item in items:
        full_path = os.path.join(ver_path, item)
        if os.path.isfile(full_path) \
                and os.path.splitext(full_path)[1] in ver_file_format:
            ver_files.append(item)
    return ver_files


class IndexView(tables.DataTableView):
    table_class = HostsTable
    template_name = 'environment/deploy/hosts_config.html'
    page_title = _("Host")

    def get_data(self):
        hosts_data = []
        try:
            cluster = api.daisy.cluster_get(self.request,
                                            self.kwargs["cluster_id"])
            if not hasattr(cluster, 'nodes'):
                return hosts_data
            for node in cluster.nodes:
                host_detail = api.daisy.host_get(self.request, node)
                host_info = {
                    "host_id": host_detail.id,
                    "name": host_detail.name,
                    "roles": None,
                    "ipmi_user": host_detail.ipmi_user,
                    "ipmi_passwd": host_detail.ipmi_passwd,
                    "os_status": host_detail.os_status,
                    "os_version_file": None,
                    "root_disk": host_detail.root_disk,
                    "root_lv_size": None,
                    "cpus": None,
                    "isol_cpus": host_detail.isolcpus,
                    "memory": None,
                    "huge_pages": host_detail.hugepages,
                    "huge_page_size": host_detail.hugepagesize}
                if host_detail.root_lv_size is not None:
                    host_info["root_lv_size"] = host_detail.root_lv_size / 1024
                if host_detail.os_version_file is not None:
                    host_info["os_version_file"] = \
                        host_detail.os_version_file.split("/")[-1]
                if hasattr(host_detail, "role"):
                    host_detail.role.sort()
                    host_info["roles"] = host_detail.role
                if hasattr(host_detail, "cpu"):
                    host_info["cpu_number"] = host_detail.cpu["total"]
                if hasattr(host_detail, "memory"):
                    host_info["memory_size"] = host_detail.memory["total"]

                hosts_data.append(host_info)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve host list.'))
        return hosts_data

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c.name
        return ""

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context["cluster_id"] = self.kwargs["cluster_id"]
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        wizard_cache.set_cache(context['cluster_id'], "hosts_config", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])
        context["current_cluster"] = \
            self.get_current_cluster(context['clusters'],
                                     context["cluster_id"])
        context['version_files'] = get_version_files()
        return context


@csrf_exempt
def set_host_config(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    param = data["param"]
    host_config = {
        "os_version": param["os_version_file"],
        "root_disk": param["root_disk"],
        "root_lv_size": param["root_lv_size"]
    }

    if param["ipmi_user"]:
        host_config["ipmi_user"] = param["ipmi_user"]
    if param["ipmi_passwd"]:
        host_config["ipmi_passwd"] = param["ipmi_passwd"]

    if "isol_cpus" in param.keys():
        host_config["isolcpus"] = param["isol_cpus"]
    if "huge_page_size" in param.keys() and "huge_pages" in param.keys():
        host_config["hugepagesize"] = param["huge_page_size"]
        host_config["hugepages"] = param["huge_pages"]
    try:
        for host in hosts:
            api.daisy.host_update(request, host["host_id"], **host_config)
            if "isolcpus" in host_config.keys():
                config_add = {
                    "cluster": cluster_id,
                    "role": "COMPUTER",
                    "config": [{
                        "file-name": "/etc/nova/nova.conf",
                        "section": "DEFAULT",
                        "key": "vcpu_pin_set",
                        "value": host_config["isolcpus"],
                        "description": ""
                    }]
                }
                LOG.info("config_add %s", config_add)
                api.daisy.config_add(request, **config_add)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("set host config failed!")
        return response

    response.status_code = 200
    return response
