#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _
import json
from django import template
from horizon import messages
from horizon import exceptions
from openstack_dashboard import api

LOG = logging.getLogger(__name__)


@csrf_exempt
def set_ha_role_for_new_cluster(request, role_id, data):
    try:
        role_param = {
            "public_vip": data["public_vip"],
            "ntp_server": data["ntp_ip"],
            "glance_lv_size": data["glance_lv_size"],
            "db_lv_size": data["db_lv_size"]}
        if data.get("vip", None):
            role_param["vip"] = data["vip"]
        if data.get("glance_vip", None):
            role_param["glance_vip"] = data["glance_vip"]
        if data.get("db_vip", None):
            role_param["db_vip"] = data["db_vip"]
        api.daisy.role_update(request, role_id, **role_param)

        # glance
        glance_param = {
            'service': 'glance',
            'role_id': role_id,
            'protocol_type': data["glance_protocol_type"],
            'data_ips': data["glance_data_ips"],
            'lun': data["glance_lun"],
            'disk_location': data["glance_disk_location"]
        }
        api.daisy.service_disk_add(request, **glance_param)

        # db
        if data["db_disk_location"] == "local" or\
           data["db_disk_location"] == "share":
            db_param = {
                'service': 'db',
                'role_id': role_id,
                'protocol_type': data["db_protocol_type"],
                'data_ips': data["db_data_ips"],
                'lun': data["db_lun"],
                'disk_location': data["db_disk_location"]
            }
            api.daisy.service_disk_add(request, **db_param)
        else:
            db_param = {
                'service': 'db',
                'role_id': role_id,
                'protocol_type': data["db1_protocol_type"],
                'data_ips': data["db1_data_ips"],
                'lun': data["db1_lun"],
                'disk_location': data["db_disk_location"]
            }
            api.daisy.service_disk_add(request, **db_param)
            db_param = {
                'service': 'db',
                'role_id': role_id,
                'protocol_type': data["db2_protocol_type"],
                'data_ips': data["db2_data_ips"],
                'lun': data["db2_lun"],
                'disk_location': data["db_disk_location"]
            }
            api.daisy.service_disk_add(request, **db_param)

        # mongodb
        LOG.info("WMH DBG: mongodb settings")
        mongodb_param = {
            'service': 'mongodb',
            'role_id': role_id,
            'protocol_type': data["mongodb_protocol_type"],
            'data_ips': data["mongodb_data_ips"],
            'lun': data["mongodb_lun"],
            'disk_location': data["mongodb_disk_location"],
            'size': data["mongodb_lv_size"]
        }
        api.daisy.service_disk_add(request, **mongodb_param)

        # dbbackup
        LOG.info("WMH DBG: dbbackup settings")
        dbbackup_param = {
            'service': 'db_backup',
            'role_id': role_id,
            'protocol_type': data["dbbackup_protocol_type"],
            'data_ips': data["dbbackup_data_ips"],
            'lun': data["dbbackup_lun"],
            'disk_location': data["dbbackup_disk_location"],
            'size': data["dbbackup_lv_size"]
        }
        api.daisy.service_disk_add(request, **dbbackup_param)

        # Add new cinder volumes
        if len(data["cinder_volume_array"]) > 0:
            cinder_param = \
                {'role_id': role_id,
                 'disk_array': data["cinder_volume_array"]}
            api.daisy.cinder_volume_add(request, **cinder_param)

    except Exception as e:
        LOG.info("update ha role info failed! %s" % e)
        raise


@csrf_exempt
def set_ha_role_info_for_modify_cluster(request, data):
    role_param = {}
    role_id = data["role_id"]
    try:
        role_param["public_vip"] = data["public_vip"]
        role_param["ntp_server"] = data["ntp_ip"]
        role_param["glance_lv_size"] = data["glance_lv_size"]
        role_param["db_lv_size"] = data["db_lv_size"]
        if data.get("vip", None):
            role_param["vip"] = data["vip"]
        if data.get("glance_vip", None):
            role_param["glance_vip"] = data["glance_vip"]
        if data.get("db_vip", None):
            role_param["db_vip"] = data["db_vip"]
        api.daisy.role_update(request, role_id, **role_param)

        # glance
        if data["glance_service_id"] == "":
            glance_param = {
                'service': 'glance',
                'role_id': role_id,
                'protocol_type': data["glance_protocol_type"],
                'data_ips': data["glance_data_ips"],
                'lun': data["glance_lun"],
                'disk_location': data["glance_disk_location"]
            }
            api.daisy.service_disk_add(request, **glance_param)
        else:
            glance_param = {
                'service': 'glance',
                'role_id': role_id,
                'protocol_type': data["glance_protocol_type"],
                'data_ips': data["glance_data_ips"],
                'lun': data["glance_lun"],
                'disk_location': data["glance_disk_location"]
            }
            api.daisy.service_disk_update(request,
                                          data['glance_service_id'],
                                          **glance_param)

        # db
        if data["db_disk_location"] == "local" or\
           data["db_disk_location"] == "share":
            db_param = {
                'service': 'db',
                'role_id': role_id,
                'protocol_type': data["db_protocol_type"],
                'data_ips': data["db_data_ips"],
                'lun': data["db_lun"],
                'disk_location': data["db_disk_location"]
            }
            if data["db_service_id"] == "":
                api.daisy.service_disk_add(request, **db_param)
            else:
                api.daisy.service_disk_update(request,
                                              data['db_service_id'],
                                              **db_param)
        else:
            db1_param = {
                'service': 'db',
                'role_id': role_id,
                'protocol_type': data["db1_protocol_type"],
                'data_ips': data["db1_data_ips"],
                'lun': data["db1_lun"],
                'disk_location': "share_cluster"
            }
            db2_param = {
                'service': 'db',
                'role_id': role_id,
                'protocol_type': data["db2_protocol_type"],
                'data_ips': data["db2_data_ips"],
                'lun': data["db2_lun"],
                'disk_location': "share_cluster"
            }

            if data["db1_service_id"] == "" and data["db2_service_id"] == "":
                api.daisy.service_disk_add(request, **db1_param)
                api.daisy.service_disk_add(request, **db2_param)

            else:
                api.daisy.service_disk_update(request,
                                              data['db1_service_id'],
                                              **db1_param)
                api.daisy.service_disk_update(request,
                                              data['db2_service_id'],
                                              **db2_param)
        # mongodb
        if data["mongodb_service_id"] == "":
            mongodb_param = {
                'service': 'mongodb',
                'role_id': role_id,
                'protocol_type': data["mongodb_protocol_type"],
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
                'protocol_type': data["mongodb_protocol_type"],
                'data_ips': data["mongodb_data_ips"],
                'lun': data["mongodb_lun"],
                'disk_location': data["mongodb_disk_location"],
                'size': data['mongodb_lv_size']
            }
            api.daisy.service_disk_update(request,
                                          data['mongodb_service_id'],
                                          **mongodb_param)
        # dbbackup
        if data["dbbackup_service_id"] == "":
            dbbackup_param = {
                'service': 'db_backup',
                'role_id': role_id,
                'protocol_type': data["dbbackup_protocol_type"],
                'data_ips': data["dbbackup_data_ips"],
                'lun': data["dbbackup_lun"],
                'disk_location': data["dbbackup_disk_location"],
                'size': data['dbbackup_lv_size']
            }
            api.daisy.service_disk_add(request, **dbbackup_param)
        else:
            dbbackup_param = {
                'service': 'db_backup',
                'role_id': role_id,
                'protocol_type': data["dbbackup_protocol_type"],
                'data_ips': data["dbbackup_data_ips"],
                'lun': data["dbbackup_lun"],
                'disk_location': data["dbbackup_disk_location"],
                'size': data['dbbackup_lv_size']
            }
            api.daisy.service_disk_update(request,
                                          data['dbbackup_service_id'],
                                          **dbbackup_param)
        # cinder
        # 1. get all cinder volumes and delete it
        cinder_volumes = \
            api.daisy.cinder_volume_list(request, **{'role_id': role_id})
        columns = ["ID", "MANAGEMENT_IPS", "DATA_IPS", "POOLS",
                   "VOLUME_DRIVER", "VOLUME_TYPE", "BACKEND_INDEX",
                   "USER_NAME", "USER_PWD", "ROLE_ID"]
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
    except Exception as e:
        LOG.info("update ha role info failed!, %s" % e)
        raise


@csrf_exempt
def set_computer_role_info(request, role_id, data):
    try:
        role_param = {"nova_lv_size": data.get("nova_lv_size")}
        api.daisy.role_update(request, role_id, **role_param)
    except Exception as e:
        LOG.info("update computer role info failed! %s" % e)
        raise


@csrf_exempt
def set_role_info(request, role_id, data):
    try:
        role_param = {}
        if data.get("vip", None):
            role_param["vip"] = data["vip"]

        if "mongodb_vip" in data.keys():
            role_param["mongodb_vip"] = data["mongodb_vip"]
        api.daisy.role_update(request, role_id, **role_param)
    except Exception as e:
        LOG.info("update lb role info failed! %s" % e)
        raise


def sort_roles(roles):
    ret_roles = []
    sort_list = ["CONTROLLER_HA", "CONTROLLER_LB", "COMPUTER",
                 "ZENIC_NFM", "ZENIC_CTL"]
    for sort in sort_list:
        for role in roles:
            if role.get("name", "") == sort:
                ret_roles.append(role)
                break
    return ret_roles


@csrf_exempt
def get_role_list(request, cluster_id):
    roles_data = []
    try:
        role_list = api.daisy.role_list(request)
        roles = [role for role in role_list
                 if role.cluster_id == cluster_id]
        for role in roles:
            roles_data.append({
                "id": role.id,
                "name": role.name})
        roles_data = sort_roles(roles_data)
    except Exception as e:
        LOG.info("get_role_list! %s" % e)
        exceptions.handle(request,
                          _('Unable to retrieve role list.'))
    return roles_data


@csrf_exempt
def get_ha_role_info(request):
    request_data = json.loads(request.body)
    role_id = request_data["role_id"]
    status_code = 200
    role_info = {}
    try:
        role = api.daisy.role_get(request, role_id)
        role_info["role_id"] = role_id
        role_info["name"] = role.name
        role_info["vip"] = role.vip
        role_info["glance_vip"] = role.glance_vip
        role_info["db_vip"] = role.db_vip
        role_info["public_vip"] = role.public_vip
        role_info["ntp_ip"] = role.ntp_server
        role_info["glance_lv_size"] = role.glance_lv_size
        role_info["db_lv_size"] = role.db_lv_size
        role_info["service_disk_array"] = []
        role_info["cinder_volume_array"] = []

        service_disks = \
            api.daisy.service_disk_list(request, **{'role_id': role_id})

        columns = ['ID', 'SERVICE', 'ROLE_ID', 'DISK_LOCATION', 'DATA_IPS',
                   'SIZE', 'LUN', 'PROTOCOL_TYPE']
        service_disk_array = []
        for disk in service_disks:
            row = []
            for item in columns:
                field_name = item.lower().replace(' ', '_')
                data = getattr(disk, field_name, None)
                row.append(data)
            service_disk_array.append(row)
        dict_names = ['id', 'service', 'role_id', 'disk_location',
                      'data_ips', 'size', 'lun', 'protocol_type']
        for item in service_disk_array:
            if item[columns.index('ROLE_ID')] != role_id:
                continue
            role_info['service_disk_array'].append(dict(zip(dict_names, item)))

        cinder_volumes = \
            api.daisy.cinder_volume_list(request, **{'role_id': role_id})

        columns = ["ID", "MANAGEMENT_IPS", "DATA_IPS", "POOLS",
                   "VOLUME_DRIVER", "VOLUME_TYPE", "BACKEND_INDEX",
                   "USER_NAME", "USER_PWD", "ROLE_ID"]
        cinder_volume_array = []
        for volume in cinder_volumes:
            row = []
            for item in columns:
                field_name = item.lower().replace(' ', '_')
                data = getattr(volume, field_name, None)
                row.append(data)
            cinder_volume_array.append(row)

        dict_names = ['id', 'management_ips', 'data_ips', 'pools',
                      'volume_driver', 'volume_type', 'backend_index',
                      'user_name', 'user_pwd', 'role_id']
        for item in cinder_volume_array:
            if item[columns.index('ROLE_ID')] != role_id:
                continue
            role_info['cinder_volume_array'].\
                append(dict(zip(dict_names, item)))
    except Exception as e:
        status_code = 500
        messages.error(request, e)
        LOG.error("get_ha_role_info failed!%s", e)
    return HttpResponse(json.dumps(role_info),
                        content_type="application/json",
                        status=status_code)


@csrf_exempt
def get_computer_role_info(request):
    request_data = json.loads(request.body)
    role_id = request_data["role_id"]
    status_code = 200
    role_info = {}
    try:
        role = api.daisy.role_get(request, role_id)
        role_info["role_id"] = role_id
        role_info["name"] = role.name
        role_info["nova_lv_size"] = role.nova_lv_size
    except Exception, e:
        status_code = 500
        messages.error(request, e)
        LOG.error("get_computer_role_info failed!%s", e)
    return HttpResponse(json.dumps(role_info),
                        content_type="application/json",
                        status=status_code)


@csrf_exempt
def get_role_info(request):
    request_data = json.loads(request.body)
    role_id = request_data["role_id"]
    status_code = 200
    role_info = {}
    try:
        role = api.daisy.role_get(request, role_id)
        role_info["role_id"] = role_id
        role_info["name"] = role.name
        role_info["vip"] = role.vip
        role_info["mongodb_vip"] = role.mongodb_vip
    except Exception, e:
        status_code = 500
        messages.error(request, e)
        LOG.error("get_role_info failed!%s", e)
    return HttpResponse(json.dumps(role_info),
                        content_type="application/json",
                        status=status_code)


@csrf_exempt
def get_roles_detail(request, in_role_list, cluster_id):
    ret_role_list = []
    try:
        if in_role_list is not None:
            role_list = api.daisy.role_list(request)
            roles = [role for role in role_list
                     if role.cluster_id == cluster_id and
                     role.name in in_role_list]
            for role in roles:
                roles_detail = api.daisy.role_get(request, role.id)
                ret_role_list.append(roles_detail)
    except Exception as e:
        LOG.info("get_roles_detail! %s" % e)
        messages.error(request, 'Get Role Information Failed!')
    return ret_role_list


@csrf_exempt
def get_role_html_detail(host):
    template_name = 'environment/cluster/role_detail.html'
    context = {
        "host_id": host["host_id"],
        "roles": host["roles"],
        "show_vip_role_list": ["CONTROLLER_HA", "CONTROLLER_LB"]
    }
    return template.loader.render_to_string(template_name, context)
