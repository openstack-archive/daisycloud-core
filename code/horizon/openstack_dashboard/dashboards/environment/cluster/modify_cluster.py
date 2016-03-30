#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _

import json

from horizon import messages
from horizon import views
from horizon import exceptions

from openstack_dashboard import api

import logging
LOG = logging.getLogger(__name__)


def is_zenic_role(roles):
    for role in roles:
        if "ZENIC_" in role["name"]:
            return True
    return False


class ModifyView(views.HorizonTemplateView):
    template_name = "environment/cluster/modify_cluster.html"

    def get_clusters(self):
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]

        return cluster_lists

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

    def get_context_data(self, **kwargs):
        context = super(ModifyView, self).get_context_data(**kwargs)

        networks = \
            api.daisy.network_list(self.request, self.kwargs["cluster_id"])
        networks_list = [net.__dict__ for net in networks]
        networks_list.sort(key=lambda x: x['name'])
        context["network"] = {"networks": networks_list}
        context['cluster_id'] = self.kwargs['cluster_id']
        context['clusters'] = self.get_clusters()
        context["roles"] = self.get_roles_data()
        context["has_zenic"] = is_zenic_role(context["roles"])
        return context

    def get_success_url(self):
        return "/dashboard/environment/"


@csrf_exempt
def GetCluster(request):
    data = json.loads(request.body)

    filter = data["cluster_info"]
    cluster_info = api.daisy.cluster_get(request, filter["cluster_id"])

    ret_cluster_list = []
    ret_cluster_list.append({
        "id": cluster_info.id,
        "name": cluster_info.name,
        "base_mac": cluster_info.networking_parameters["base_mac"],
        "segmentation_type":
            cluster_info.networking_parameters["segmentation_type"],
        "gre_id_start": cluster_info.networking_parameters["gre_id_range"][0],
        "gre_id_end": cluster_info.networking_parameters["gre_id_range"][1],
        "vni_start": cluster_info.networking_parameters["vni_range"][0],
        "vni_end": cluster_info.networking_parameters["vni_range"][1],
        "auto_scale": cluster_info.auto_scale,
        "use_dns": cluster_info.use_dns,
        "description": cluster_info.description})

    return HttpResponse(json.dumps(ret_cluster_list),
                        content_type="application/json")


@csrf_exempt
def GetClusters(request):
    clusters = api.daisy.cluster_list(request)
    cluster_lists = [c for c in clusters]

    ret_cluster_list = []
    for cluster in cluster_lists:
        ret_cluster_list.append({
            "id": cluster.id,
            "name": cluster.name,
            "auto_scale": cluster.auto_scale})

    return HttpResponse(json.dumps(ret_cluster_list),
                        content_type="application/json")


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
            "glance_vip": role.glance_vip,
            "db_vip": role.db_vip,
            "public_vip": role.public_vip,
            "ntp_ip": role.ntp_server,
            "glance_lv_size": role.glance_lv_size,
            "db_lv_size": role.db_lv_size,
            'service_disk_array': [],
            'cinder_volume_array': []}
    except Exception:
        role_info = {
            "role_id": role_id,
            "vip": None,
            "glance_vip": None,
            "db_vip": None,
            "public_vip": None,
            "ntp_ip": None,
            "glance_lv_size": None,
            "db_lv_size": None,
            'service_disk_array': [],
            'cinder_volume_array': []}
    try:
        service_disks = \
            api.daisy.service_disk_list(request, **{'role_id': role_id})

        columns = ['ID', 'SERVICE', 'ROLE_ID', 'DISK_LOCATION', 'DATA_IPS',
                   'SIZE', 'LUN']
        service_disk_array = []
        for disk in service_disks:
            row = []
            for item in columns:
                field_name = item.lower().replace(' ', '_')
                data = getattr(disk, field_name, None)
                row.append(data)
            service_disk_array.append(row)
        dict_names = ['id', 'service', 'role_id', 'disk_location',
                      'data_ips', 'size', 'lun']
        for item in service_disk_array:
            if item[columns.index('ROLE_ID')] != role_id:
                continue
            role_info['service_disk_array'].append(dict(zip(dict_names, item)))
    except Exception:
        role_info['service_disk_array'] = []

    try:
        cinder_volumes = \
            api.daisy.cinder_volume_list(request, **{'role_id': role_id})

        columns = ["ID", "MANAGEMENT_IPS", "DATA_IPS", "POOLS", "VOLUME_DRIVER",
                   "VOLUME_TYPE", "BACKEND_INDEX", "USER_NAME",
                   "USER_PWD", "ROLE_ID"]
        cinder_volume_array = []
        for volume in cinder_volumes:
            row = []
            for item in columns:
                field_name = item.lower().replace(' ', '_')
                data = getattr(volume, field_name, None)
                row.append(data)
            cinder_volume_array.append(row)

        dict_names = ['id', 'management_ips', 'data_ips', 'pools', 'volume_driver',
                      'volume_type', 'backend_index', 'user_name',
                      'user_pwd', 'role_id']
        for item in cinder_volume_array:
            if item[columns.index('ROLE_ID')] != role_id:
                continue
            role_info['cinder_volume_array'].\
                append(dict(zip(dict_names, item)))
    except Exception:
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
            "mongodb_vip": role.mongodb_vip}
    except Exception, e:
        messages.error(request, e)
        role_info = {
            "role_id": role_id,
            "vip": None,
            "mongodb_vip": None}
    return HttpResponse(json.dumps(role_info),
                        content_type="application/json")


@csrf_exempt
def set_ha_role_info(request):
    response = HttpResponse()
    data = json.loads(request.body)
    role_param = {}
    msg = ('HA role modify request.body::::::: %s') % request.body
    LOG.info(msg)

    role_id = data["role_id"]
    try:
        role_param["vip"] = data["vip"]
        role_param["glance_vip"] = data["glance_vip"]
        role_param["db_vip"] = data["db_vip"]
        role_param["public_vip"] = data["public_vip"]
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
            api.daisy.service_disk_update(request,
                                          data['glance_service_id'],
                                          **glance_param)

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
            api.daisy.service_disk_update(request,
                                          data['db_service_id'],
                                          **db_param)


        # mongodb
        if data["mongodb_service_id"] == "":
            mongodb_param = {
                'service': 'mongodb',
                'role_id': role_id,
                'data_ips': data["mongodb_data_ips"],
                'lun': data["mongodb_lun"],
                'disk_location': data["mongodb_disk_location"],
                'size': data['mongodb_lv_size']
            }
            api.daisy.service_disk_add(request, **mongodb_param)
        else:
            mongodb_param = {
                'service': 'mongodb',
                'role_id': role_id,
                'data_ips': data["mongodb_data_ips"],
                'lun': data["mongodb_lun"],
                'disk_location': data["mongodb_disk_location"],
                'size': data['mongodb_lv_size']
            }
            api.daisy.service_disk_update(request,
                                          data['mongodb_service_id'],
                                          **mongodb_param)

        # cinder
        # 1. get all cinder volumes and delete it
        cinder_volumes = \
            api.daisy.cinder_volume_list(request, **{'role_id': role_id})
        columns = ["ID", "MANAGEMENT_IPS", "DATA_IPS", "POOLS", "VOLUME_DRIVER",
                   "VOLUME_TYPE", "BACKEND_INDEX", "USER_NAME",
                   "USER_PWD", "ROLE_ID"]
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
        # 2. Add new cinder volumes
        if len(data["cinder_volume_array"]) > 0:
            cinder_param = \
                {'role_id': role_id,
                 'disk_array': data["cinder_volume_array"]}
            api.daisy.cinder_volume_add(request, **cinder_param)
    except Exception, e:
        messages.error(request, e)
        LOG.info("update ha role info failed!, role_id=%s" % role_id)
        response.status_code = 500
        return response

    response.status_code = 200
    return response


@csrf_exempt
def set_role_info(request):
    response = HttpResponse()
    data = json.loads(request.body)
    msg = ('Role modify request.body::::::: %s') % request.body
    LOG.info(msg)
    role_id = data["role_id"]

    try:
        role_param = {
            "vip": data["vip"]
        }
        if "mongodb_vip" in data.keys():
            role_param["mongodb_vip"] = data["mongodb_vip"]
        api.daisy.role_update(request, role_id, **role_param)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("update role info failed!")
        return response

    response.status_code = 200
    return response


@csrf_exempt
def ModifyCluster(request):
    data = json.loads(request.body)
    msg = ('Cluster modify request.body::::::: %s') % request.body
    LOG.info(msg)

    cluster_info = data["cluster_info"]
    response = HttpResponse()
    try:
        if cluster_info["other"] == 1:
            api.daisy.cluster_update(request,
                                     cluster_info["id"],
                                     name=cluster_info["name"],
                                     auto_scale=cluster_info["auto_scale"])
        else:
            api.daisy.cluster_update(
                request,
                cluster_info["id"],
                name=cluster_info["name"],
                networking_parameters=cluster_info["networking_parameters"],
                auto_scale=cluster_info["auto_scale"],
                use_dns=cluster_info["use_dns"],
                description=cluster_info["description"])
    except Exception as e:
        messages.error(request, e)
        exceptions.handle(request, "Cluster modify failed!(%s)" % e)
        response.status_code = 500
        return response

    response.status_code = 200
    return response
