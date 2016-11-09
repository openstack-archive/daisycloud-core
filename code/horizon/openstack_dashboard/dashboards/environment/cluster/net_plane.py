#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _
import json
from horizon import messages
from horizon import exceptions
from openstack_dashboard import api

LOG = logging.getLogger(__name__)


@csrf_exempt
def add_net_plane(request, cluster_id):
    status_code = 200
    data = json.loads(request.body)
    net_plane_params = {
        "PUBLICAPI": ["cidr", "gateway", "ip_ranges", "vlan_id",
                      "capability", "description"],
        "MANAGEMENT": ["cidr", "gateway", "ip_ranges", "vlan_id",
                       "capability", "description"],
        "DATAPLANE": ["segmentation_type", "vlan_start", "vlan_end",
                      "capability", "description"],
        "STORAGE": ["cidr", "gateway", "ip_ranges", "vlan_id",
                    "capability", "description"],
        "HEARTBEAT": ["cidr", "vlan_id", "ip_ranges", "capability",
                      "description"]}
    try:
        net_plane = {
            "name": data["name"],
            "network_type": data["network_type"],
            "description": data["description"],
            "cluster_id": cluster_id,
            "type": "custom"}
        for param in net_plane_params[data["network_type"]]:
            net_plane[param] = data[param]
            if net_plane[param] == "":
                net_plane[param] = None
        new_net_plane = api.daisy.net_plane_add(request, **net_plane)
        data["id"] = new_net_plane.id
    except Exception as e:
        LOG.info("add_net_plane failed:%s", e)
        messages.error(request, e)
        status_code = 500
    return HttpResponse(json.dumps(data),
                        content_type="application/json",
                        status=status_code)


@csrf_exempt
def set_net_plane(request, cluster_id, nets):
    net_plane_params = {
        "PUBLICAPI": ["cidr", "gateway", "ip_ranges", "vlan_id",
                      "capability", "description"],
        "MANAGEMENT": ["cidr", "gateway", "ip_ranges", "vlan_id",
                       "capability", "description"],
        "DATAPLANE": ["segmentation_type", "vni_start", "vni_end",
                      "cidr", "gateway", "ip_ranges", "vlan_start",
                      "capability", "vlan_end", "description"],
        "STORAGE": ["cidr", "gateway", "ip_ranges", "vlan_id",
                    "capability", "description"],
        "HEARTBEAT": ["cidr", "vlan_id", "ip_ranges", "capability",
                      "description"]}
    for net in nets:
        net_params = {
            "name": net["name"],
            "cluster_id": cluster_id, }
        network_type = net["network_type"]
        for param in net_plane_params[network_type]:
            if param in net:
                net_params[param] = net[param]
        LOG.info("set_net_plane %s", net_params)
        api.daisy.network_update(request, net["id"], **net_params)


@csrf_exempt
def sort_net_planes(net_planes):
    ret_net_planes = []
    sort_list = ["MANAGEMENT", "PUBLICAPI", "DATAPLANE","EXTERNAL",
                 "STORAGE", "VXLAN", "HEARTBEAT"]
    for sort in sort_list:
        for net_plane in net_planes:
            if net_plane["network_type"] == sort:
                ret_net_planes.append(net_plane)
                break
    return ret_net_planes


@csrf_exempt
def get_default_net_plane():
    networks = [
        {"network_type": "MANAGEMENT",
         "net_planes": [{"name": "MANAGEMENT", }]},
        {"network_type": "DATAPLANE",
         "net_planes": [{"name": "physnet1", }]},
        {"network_type": "PUBLICAPI",
         "net_planes": [{"name": "PUBLICAPI", }]},
        {"network_type": "STORAGE",
         "net_planes": [{"name": "STORAGE", }]}, 
        {"network_type": "EXTERNAL",
         "net_planes": [{"name": "EXTERNAL", }]},]
    for net in networks:
        for net_plane in net["net_planes"]:
            net_plane.update({"cidr": "192.168.1.1/24",
                              "vlan_start": "1",
                              "vlan_end": "4094",
                              "vlan_id": "",
                              "capability": "high",
                              "segmentation_type": "vlan",
                              "vni_start": None,
                              "vni_end": None})
    return sort_net_planes(networks)


@csrf_exempt
def add_net_plane_for_add_cluster(request, cluster_id, in_net_planes):
    net_plane_params = {
        "PUBLICAPI": ["cidr", "gateway", "ip_ranges", "vlan_id",
                      "capability", "description"],
        "MANAGEMENT": ["cidr", "gateway", "ip_ranges",
                       "capability", "vlan_id", "description"],
        "DATAPLANE": ["segmentation_type", "vni_start", "vni_end",
                      "cidr", "gateway", "ip_ranges", "vlan_start",
                      "capability", "vlan_end", "description"],
        "STORAGE": ["cidr", "gateway", "ip_ranges",
                    "capability", "vlan_id", "description"],
        "HEARTBEAT": ["cidr", "vlan_id", "ip_ranges", "capability",
                      "description"],
        "EXTERNAL": ["cidr", "gateway", "ip_ranges", "vlan_id",
                      "capability", "description"]}

    def get_id_by_name(nets, name):
        for n in nets:
            if n.name == name:
                return n.id
        return None

    try:
        network_list = api.daisy.network_list(request, cluster_id)
        for in_net_plane in in_net_planes:
            net_id = get_id_by_name(network_list, in_net_plane["name"])
            if net_id:
                net_params = {
                    "name": in_net_plane["name"],
                    "cluster_id": cluster_id}
                network_type = in_net_plane["network_type"]
                for param in net_plane_params[network_type]:
                    if param in in_net_plane:
                        net_params[param] = in_net_plane[param]
                api.daisy.network_update(request, net_id, **net_params)
            else:
                net_plane = {
                    "name": in_net_plane["name"],
                    "network_type": in_net_plane["network_type"],
                    "description": in_net_plane["description"],
                    "cluster_id": cluster_id,
                    "type": "custom"}

                for param in net_plane_params[in_net_plane["network_type"]]:
                    if param in in_net_plane:
                        net_plane[param] = in_net_plane[param]
                        if net_plane[param] == "":
                            net_plane[param] = None
                api.daisy.net_plane_add(request, **net_plane)
    except Exception as e:
        LOG.error('add_net_plane_for_add_cluster failed: e=%s' % e)
        raise


@csrf_exempt
def delete_net_plane(request, cluster_id):
    data = json.loads(request.body)
    net_plane_info = {
        "name": data["name"]
    }
    response = HttpResponse(json.dumps(net_plane_info),
                            content_type="application/json")
    try:
        api.daisy.netplane_delete(request, data["id"])
    except Exception as e:
        LOG.info("delete_net_plane:%s", e)
        messages.error(request, e)
        response.status_code = 500
        return response
    response.status_code = 200
    return response


@csrf_exempt
def get_net_plane_list(request, cluster_id):
    ret_net_planes = []
    filter_net_planes = ["DEPLOYMENT", "EXTERNAL"]
    try:
        network_list = api.daisy.network_list(request, cluster_id)
        show_net_planes = [net.__dict__ for net in network_list
                           if net.name not in filter_net_planes]
        for show_net_plane in show_net_planes:
            network_types = [ret_net_plane["network_type"]
                             for ret_net_plane in ret_net_planes]
            if show_net_plane["network_type"] not in network_types:
                ret_net_planes.append(
                    {"network_type": show_net_plane["network_type"],
                     "net_planes": [show_net_plane, ]})
            else:
                for ret_net_plane in ret_net_planes:
                    if ret_net_plane["network_type"] == \
                            show_net_plane["network_type"]:
                        ret_net_plane["net_planes"].append(show_net_plane)
    except Exception as e:
        LOG.info("get_net_plane_list! %s" % e)
        exceptions.handle(request,
                          _('Unable to retrieve net plane list.'))
    return sort_net_planes(ret_net_planes)
