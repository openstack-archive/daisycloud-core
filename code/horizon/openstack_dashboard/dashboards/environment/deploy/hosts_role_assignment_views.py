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
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy

from daisyclient.v1 import client as daisy_client

import json
from django import template
from horizon import messages
from horizon import exceptions
from horizon import forms
from horizon import tables

from openstack_dashboard import api

from openstack_dashboard.dashboards.environment.deploy import tables as deploy_tables
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
            api.daisy.host_update(request, obj_id, cluster=self.table.kwargs["cluster_id"], role=[])
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
            roles = [role for role in role_list if role.cluster_id == self.kwargs["cluster_id"]]
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
        wizard_cache.set_cache(context['cluster_id'], "hosts_role_assignment", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])
        context["current_cluster"] = self.get_current_cluster(context['clusters'], context["cluster_id"])

        return context


@csrf_exempt
def assign_host_role(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    roles = data["roles"]

    try:
        for host_id in hosts:
            api.daisy.host_update(request, host_id, cluster=cluster_id, role=roles)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("assign role to host failed!")
        return response

    response.status_code = 200
    return response

@csrf_exempt
def get_ha_role_info(request):
    request_data = json.loads(request.body)
    role_id = request_data["role_id"]
    try:
        role = api.daisy.role_get(request, role_id)
        role_info = {
            "role_id": role_id,
            "name": role.name,
            "vip": role.vip,
            "ntp_ip": role.ntp_server,
            "glance_lv_size": role.glance_lv_size,
            "db_lv_size": role.db_lv_size,
            'service_disk_array': [],
            'cinder_volume_array': []}
    except Exception:
        role_info = {
            "role_id": role_id,
            "vip": None,
            "ntp_ip": None,
            "glance_lv_size": None,
            "db_lv_size": None,
            'service_disk_array': [],
            'cinder_volume_array': []}

    try:
        service_disks = api.daisy.service_disk_list(request, **{'role_id': role_id})

        columns = ['ID', 'SERVICE','ROLE_ID','DISK_LOCATION','DATA_IPS','SIZE', 'LUN']
        service_disk_array = []
        for disk in service_disks:
            row = []
            for item in columns:
                field_name = item.lower().replace(' ', '_')
                data = getattr(disk, field_name, None)
                row.append(data)
            service_disk_array.append(row)
        
        dict_names = ['id', 'service','role_id','disk_location','data_ips','size', 'lun']
        for item in service_disk_array:
            if item[columns.index('ROLE_ID')] != role_id:
                continue;
            role_info['service_disk_array'].append(dict(zip(dict_names, item)))
    except Exception, e:
        role_info['service_disk_array'] = []

    try:
        cinder_volumes = api.daisy.cinder_volume_list(request, **{'role_id': role_id})

        columns = ["ID", "MANAGEMENT_IPS", "POOLS", "VOLUME_DRIVER", "VOLUME_TYPE", "BACKEND_INDEX", "USER_NAME", "USER_PWD", "ROLE_ID"]
        cinder_volume_array = []
        for volume in cinder_volumes:
            row = []
            for item in columns:
                field_name = item.lower().replace(' ', '_')
                data = getattr(volume, field_name, None)
                row.append(data)
            cinder_volume_array.append(row)
        
        dict_names = ['id', 'management_ips','pools','volume_driver','volume_type','backend_index', 'user_name', "user_pwd", "role_id"]
        for item in cinder_volume_array:
            if item[columns.index('ROLE_ID')] != role_id:
                continue;
            role_info['cinder_volume_array'].append(dict(zip(dict_names, item)))
    except Exception, e:
        role_info['cinder_volume_array'] = []

    return HttpResponse(json.dumps(role_info),
                        content_type="application/json")

@csrf_exempt
def get_role_info(request):
    request_data = json.loads(request.body)
    role_id = request_data["role_id"]
    try:
        role = api.daisy.role_get(request, role_id)
        role_info = {
            "role_id": role_id,
            "name": role.name,
            "vip": role.vip,
            "ntp_ip": role.ntp_server,
            "glance_lv_size": role.glance_lv_size,
            "db_lv_size": role.db_lv_size}
    except Exception, e:
        messages.error(request, e)
        role_info = {
            "role_id": role_id,
            "vip": None,
            "glance_lv_size": None,
            "db_lv_size": None}
    return HttpResponse(json.dumps(role_info),
                        content_type="application/json")

@csrf_exempt
def set_ha_role_info(request):
    response = HttpResponse()
    data = json.loads(request.body)
    role_param = {}
    msg = ('Role modify request.body::::::: %s') % request.body
    LOG.info(msg)

    role_id = data["role_id"]
    try:
        role_param["vip"] = data["vip"]
        role_param["ntp_server"] = data["ntp_ip"]
        role_param["glance_lv_size"] = data["glance_lv_size"]
        role_param["db_lv_size"] = data["db_lv_size"]
        api.daisy.role_update(request, role_id, **role_param)

        # glance
        if data["glance_service_id"] == "":
            glance_param = {
                'service': 'glance',
                'role_id': role_id,
                'data_ips': data["glance_data_ips"],
                'lun': data["glance_lun"],
                'disk_location': data["glance_disk_location"]
            }
            api.daisy.service_disk_add(request, **glance_param)
        else:
            glance_param = {
                'service': 'glance',
                'role_id': role_id,
                'data_ips': data["glance_data_ips"],
                'lun': data["glance_lun"],
                'disk_location': data["glance_disk_location"]
            }
            api.daisy.service_disk_update(request, data['glance_service_id'], **glance_param)

        # db
        if data["db_service_id"] == "":
            db_param = {
                'service': 'db',
                'role_id': role_id,
                'data_ips': data["db_data_ips"],
                'lun': data["db_lun"],
                'disk_location': data["db_disk_location"]
            }
            api.daisy.service_disk_add(request, **db_param)
        else:
            db_param = {
                'service': 'db',
                'role_id': role_id,
                'data_ips': data["db_data_ips"],
                'lun': data["db_lun"],
                'disk_location': data["db_disk_location"]
            }
            api.daisy.service_disk_update(request, data['db_service_id'], **db_param)

        # cinder
        # 1. get all cinder volumes and delete it
        cinder_volumes = api.daisy.cinder_volume_list(request, **{'role_id': role_id})
        columns = ["ID", "MANAGEMENT_IPS", "POOLS", "VOLUME_DRIVER", "VOLUME_TYPE", "BACKEND_INDEX", "USER_NAME", "USER_PWD", "ROLE_ID"]
        disk_array = []
        for volume in cinder_volumes:
            row = []
            for item in columns:
                field_name = item.lower().replace(' ', '_')
                row.append(getattr(volume, field_name, None))
            disk_array.append(row)
        for item in disk_array:
            if item[columns.index('ROLE_ID')] != role_id:
                continue
            api.daisy.cinder_volume_delete(request, item[columns.index('ID')])
        #2. Add new cinder volumes
        if len(data["cinder_volume_array"]) > 0:
            cinder_param = {
                    'role_id': role_id,
                    'disk_array': data["cinder_volume_array"]
            }
            api.daisy.cinder_volume_add(request, **cinder_param)
    except Exception, e:
        messages.error(request, e)
        LOG.info("update role info failed!, role_id=%s" % role_id)
        response.status_code = 500
        return response

    response.status_code = 200
    return response

@csrf_exempt
def set_role_info(request):
    response = HttpResponse()
    data = json.loads(request.body)
    role_id = data["role_id"]

    try:
        role_param = {
            "vip": data["vip"]
        }
        if data['name'] == 'CONTROLLER_HA':
            role_param["ntp_server"] = data["ntp_ip"]
            role_param["glance_lv_size"] = data["glance_lv_size"]
            role_param["db_lv_size"] = data["db_lv_size"]
        api.daisy.role_update(request, role_id, **role_param)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("update role info failed!")
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