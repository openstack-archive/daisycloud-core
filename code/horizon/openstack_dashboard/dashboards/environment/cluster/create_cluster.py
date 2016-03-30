#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
import json

from django.http import HttpResponse

from horizon import messages
from horizon import views

from openstack_dashboard import api

import logging
LOG = logging.getLogger(__name__)


def is_zenic_role(roles):
    for role in roles:
        if "ZENIC_" in role:
            return True
    return False


class CreateView(views.HorizonTemplateView):
    template_name = "environment/cluster/create_cluster.html"

    def get_context_data(self, **kwargs):
        context = super(CreateView, self).get_context_data(**kwargs)
        networks = [{"name": "DEPLOYMENT", "network_type": "DEPLOYMENT"},
                    {"name": "EXTERNAL", "network_type": "EXTERNAL"},
                    {"name": "MANAGEMENT", "network_type": "MANAGEMENT"},
                    {"name": "PRIVATE", "network_type": "PRIVATE"},
                    {"name": "PUBLIC", "network_type": "PUBLIC"},
                    {"name": "STORAGE", "network_type": "STORAGE"},
                    {"name": "VXLAN", "network_type": "VXLAN"}, ]

        networks.sort(key=lambda x: x['name'])

        for net in networks:
            net.update({"cidr": "192.168.1.1/24",
                        "vlan_start": "1",
                        "vlan_end": "4094",
                        "vlan_id": "1"})

        context["network"] = {"networks": networks}

        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists

        role_list = api.daisy.role_list(self.request)
        roles = [role.name for role in role_list if role.type == "template"]
        context["has_zenic"] = is_zenic_role(roles)

        return context


def create_submit(request):
    data = json.loads(request.body)
    msg = ('Create cluster request.body::::::: %s') % request.body
    LOG.info(msg)

    cluster_new = []
    status_code = 200
    cluster = data["cluster_info"]
    try:
        cluster_created = api.daisy.cluster_add(
            request,
            name=cluster["cluster_name"],
            description=cluster["description"],
            networking_parameters=cluster["networking_parameters"],
            use_dns=cluster["use_dns"])
        cluster_new.append({
            "id": cluster_created.id
        })

        role_list = api.daisy.role_list(request)
        roles = [role for role in role_list
                 if role.cluster_id == cluster_created.id]
        for role in roles:
            if role.name == "CONTROLLER_HA":
                if not set_ha_role(request, role.id, data["role_info"]["ha"]):
                    status_code = 500

            if role.name == "CONTROLLER_LB":
                if not set_lb_role(request, role.id, data["role_info"]["lb"]):
                    status_code = 500

            if role.name == "ZENIC_NFM":
                if not set_zenic_nfm_role(request, role.id, data["role_info"]["zenic_nfm"]):
                    status_code = 500
        
            if role.name == "ZENIC_CTL":
                if not set_zenic_ctl_role(request, role.id, data["role_info"]["zenic_ctl"]):
                    status_code = 500

        if not set_netplane(request,
                            cluster_created.id,
                            data["netplane_info"]):
            status_code = 500
            messages.error(request, 'Set Netplane Information Failed!')

        if status_code == 500:
            api.daisy.cluster_delete(request, cluster_created.id)

    except Exception as e:
        status_code = 500
        messages.error(request, 'Create Cluster Failed: %s' % e)

    return HttpResponse(json.dumps(cluster_new),
                        content_type="application/json",
                        status=status_code)


def set_ha_role(request, role_id, data):
    try:
        role_param = {}
        role_param["vip"] = data["vip"]
        role_param["glance_vip"] = data["glance_vip"]
        role_param["db_vip"] = data["db_vip"]
        role_param["public_vip"] = data["public_vip"]
        role_param["ntp_server"] = data["ntp_ip"]
        role_param["glance_lv_size"] = data["glance_lv_size"]
        role_param["db_lv_size"] = data["db_lv_size"]
        api.daisy.role_update(request, role_id, **role_param)

        # glance
        glance_param = {
            'service': 'glance',
            'role_id': role_id,
            'data_ips': data["glance_data_ips"],
            'lun': data["glance_lun"],
            'disk_location': data["glance_disk_location"]
        }
        api.daisy.service_disk_add(request, **glance_param)

        # db
        db_param = {
            'service': 'db',
            'role_id': role_id,
            'data_ips': data["db_data_ips"],
            'lun': data["db_lun"],
            'disk_location': data["db_disk_location"]
        }
        api.daisy.service_disk_add(request, **db_param)

        # mongodb
        LOG.info("WMH DBG: mongodb settings")
        mongodb_param = {
            'service': 'mongodb',
            'role_id': role_id,
            'data_ips': data["mongodb_data_ips"],
            'lun': data["mongodb_lun"],
            'disk_location': data["mongodb_disk_location"],
            'size': data["mongodb_lv_size"]
        }
        api.daisy.service_disk_add(request, **mongodb_param)

        # Add new cinder volumes
        if len(data["cinder_volume_array"]) > 0:
            cinder_param = \
                {'role_id': role_id,
                 'disk_array': data["cinder_volume_array"]}
            api.daisy.cinder_volume_add(request, **cinder_param)

    except Exception as e:
        LOG.info("update ha role info failed! %s" % e)
        messages.error(request, 'Set HA Role Information Failed!')
        return False

    return True


def set_lb_role(request, role_id, data):
    try:
        role_param = {
            "vip": data["vip"]
        }

        api.daisy.role_update(request, role_id, **role_param)

    except Exception as e:
        LOG.info("update lb role info failed! %s" % e)
        messages.error(request, 'Set LB Role Information Failed!')
        return False

    return True


def set_zenic_nfm_role(request, role_id, data):
    try:
        role_param = {
            "vip": data["vip"],
            "mongodb_vip": data["mongodb_vip"]
        }
        api.daisy.role_update(request, role_id, **role_param)

    except Exception as e:
        LOG.info("update zenic nfm role info failed! %s" % e)
        messages.error(request, 'Set ZENIC NFM Role Information Failed!')
        return False

    return True


def set_zenic_ctl_role(request, role_id, data):
    try:
        role_param = {
            "vip": data["vip"]
        }

        api.daisy.role_update(request, role_id, **role_param)

    except Exception as e:
        LOG.info("update zenic role info failed! %s" % e)
        messages.error(request, 'Set ZENIC Role Information Failed!')
        return False

    return True

def set_netplane(request, cluster_id, nets):
    netplane_param = \
        {"PUBLIC": ["cidr", "gateway", "ip_ranges", "vlan_id", "description"],
         "DEPLOYMENT": ["cidr", "gateway", "ip_ranges",
                        "vlan_id", "description"],
         "MANAGEMENT": ["cidr", "gateway", "ip_ranges",
                        "vlan_id", "description"],
         "PRIVATE": ["vlan_start", "vlan_end", "description"],
         "STORAGE": ["cidr", "gateway", "ip_ranges",
                     "vlan_id", "description"],
         "EXTERNAL": ["cidr", "gateway", "ip_ranges", "vlan_start",
                      "vlan_end", "description"],
         "VXLAN": ["cidr", "gateway", "ip_ranges", "description"], }

    def get_id_by_name(nets, name):
        for n in nets:
            if n.name == name:
                return n.id
        return None

    try:
        networks = api.daisy.network_list(request, cluster_id)
        for net in nets:
            net_id = get_id_by_name(networks, net["name"])
            if net_id:
                net_params = {
                    "name": net["name"],
                    "cluster_id": cluster_id}
                network_type = net["network_type"]
                for param in netplane_param[network_type]:
                    net_params[param] = net[param]

                api.daisy.network_update(request, net_id, **net_params)

            else:
                net_plane = {
                    "name": net["name"],
                    "network_type": net["network_type"],
                    "description": net["description"],
                    "cluster_id": cluster_id}

                for param in netplane_param[net["network_type"]]:
                    net_plane[param] = net[param]

                    if net_plane[param] == "":
                        net_plane[param] = None

                api.daisy.net_plane_add(request, **net_plane)
    except Exception as e:
        LOG.error('wmh dbg: e=%s' % e)
        return False

    return True
