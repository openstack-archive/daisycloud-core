#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _

from horizon import messages
from horizon import exceptions

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.host import views as host_views

import logging
LOG = logging.getLogger(__name__)


def get_ha_role(request, cluster_id):
    ha_role = {}
    try:
        role_list = api.daisy.role_list(request)
        role_list = [role for role in role_list
                     if role.cluster_id == cluster_id and
                     role.name == "CONTROLLER_HA"]
        if not len(role_list):
            return None
        role_get = api.daisy.role_get(request, role_list[0].id)
        ha_role["public_vip"] = role_get.public_vip
        ha_role["service_disk_array"] = []
        ha_role["cinder_volume_array"] = []
        service_disks = \
            api.daisy.service_disk_list(request, **{'role_id': role_get.id})
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
            if item[columns.index('ROLE_ID')] != role_get.id:
                continue
            ha_role['service_disk_array'].append(dict(zip(dict_names, item)))

        cinder_volumes = \
            api.daisy.cinder_volume_list(request, **{'role_id': role_get.id})

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
            if item[columns.index('ROLE_ID')] != role_get.id:
                continue
            ha_role['cinder_volume_array'].\
                append(dict(zip(dict_names, item)))
    except Exception, e:
        LOG.info("get_ha_role failed!%s", e)
        messages.error(request, e)
        return None
    return ha_role


def host_role_tecs_rule(count_ha, count_lb, count_compute):
    if (count_ha > 0) and (count_ha != 2):
        message = _("Configure must have tow HA roles.")
        raise exceptions.ConfigurationError(message)
    elif (count_lb > 0) and (count_lb != 2):
        message = _("Configure must have tow LB roles.")
        raise exceptions.ConfigurationError(message)
    elif (count_ha > 0) and (count_lb == 0):
        message = _('Configure HA role, you must configure LB role.')
        raise exceptions.ConfigurationError(message)
    elif (count_lb > 0) and (count_ha == 0):
        message = _('Configure LB role, you must configure HA role.')
        raise exceptions.ConfigurationError(message)
    elif count_compute > 0 and (count_ha == 0 or count_lb == 0):
        message = _("Compute role must have the HA and LB roles.")
        raise exceptions.ConfigurationError(message)


def host_role_zenic_rule(count_zen_nfm, count_zen_ctl):
    if (count_zen_nfm > 0) and (count_zen_nfm != 2):
        message = _("Configure must have tow ZEN_NFM roles.")
        raise exceptions.ConfigurationError(message)
    elif (count_zen_nfm > 0) and (count_zen_ctl == 0):
        message = _("Configure ZEN_NFM role, "
                    "you must configure ZEN_CTL role.")
        raise exceptions.ConfigurationError(message)
    elif (count_zen_ctl > 0) and (count_zen_ctl < 2):
        message = _("Configure must have tow ZEN_NFM roles.")
        raise exceptions.ConfigurationError(message)


def host_role_openstack_rule(count_lb, count_compute):
    if count_lb == 0:
        message = _('Configure must have LB roles.')
        raise exceptions.ConfigurationError(message)
    elif count_compute == 0:
        message = _('Config must have computer roles.')
        raise exceptions.ConfigurationError(message)


def hosts_role_rule(rule_context):
    count_context = {
        "CONTROLLER_HA": {"count": 0},
        "CONTROLLER_LB": {"count": 0},
        "COMPUTER": {"count": 0},
        "ZEN_NFM": {"count": 0},
        "ZEN_CTL": {"count": 0}}
    for host in rule_context.get("hosts"):
        if not host.get("role", None):
            continue
        for role_name in count_context:
            if role_name in host.get("role"):
                count_context[role_name]["count"] += 1
    backends = rule_context.get("backends")
    backend = ""
    if backends is not None:
        backend = str(backends[0])
    try:
        ha_count = count_context["CONTROLLER_HA"]["count"]
        lb_count = count_context["CONTROLLER_LB"]["count"]
        compute_count = count_context["COMPUTER"]["count"]
        if backend == "tecs":
            host_role_tecs_rule(ha_count,
                                lb_count,
                                compute_count)
        if backend == "kolla":
            host_role_openstack_rule(lb_count,
                                     compute_count)
        if backend == "zenic":
            nfm_count = count_context["ZEN_NFM"]["count"]
            ctl_count = count_context["ZEN_CTL"]["count"]
            host_role_zenic_rule(nfm_count, ctl_count)
        # TO DO
        # if backend == "tecs+zenic":
        #     PASS
    except Exception as e:
        LOG.info("hosts_role_rule %s", e)
        raise


def has_net_plane(host, network_type, networks):

    def is_assigned_network_in_networks(name, in_network_type, in_networks):
        for in_network in in_networks:
            if (in_network.name == name) and \
                    (in_network.network_type == in_network_type):
                return True
        return False

    is_config = False
    count = 0
    for interface in host.get("interfaces"):
        for assigned_network in interface["assigned_networks"]:
            if is_assigned_network_in_networks(assigned_network["name"],
                                               network_type,
                                               networks):
                is_config = True
                count += 1
    return is_config, count


def is_config_share_disk(ha_role):
    for service_disk in ha_role["service_disk_array"]:
        if service_disk["disk_location"] == "share":
            return True
    if len(ha_role["cinder_volume_array"]) > 0:
        return True
    return False


def control_node_net_plane_rule(ha_role, host, networks):
    if ("CONTROLLER_HA" in host.get("role")) or \
            ("CONTROLLER_LB" in host.get("role")):
        # ha/lb must be config PUBLICAPI net plane
        if not has_net_plane(host, "PUBLICAPI", networks)[0]:
            message = _("Control nodes must be config PUBLICAPI net plane.")
            raise exceptions.ConfigurationError(message)
        # share disk, ha/lb must be config STORAGE net plane
        if is_config_share_disk(ha_role):
            if not has_net_plane(host, "STORAGE", networks)[0]:
                message = _("Configure share disk, control nodes "
                            "must be config STORAGE net plane.")
                raise exceptions.ConfigurationError(message)


def compute_node_net_plane_rule(ha_role, host, networks):
    if "COMPUTER" in host.get("role"):
        # compute must be config DATAPLANE net plane
        if not has_net_plane(host, "DATAPLANE", networks)[0]:
            message = _("Compute nodes must be config DATAPLANE net plane.")
            raise exceptions.ConfigurationError(message)
        if is_config_share_disk(ha_role):
            if not has_net_plane(host, "STORAGE", networks)[0]:
                message = _("Configure share disk, compute nodes "
                            "must be config STORAGE net plane.")
                raise exceptions.ConfigurationError(message)


def zenic_node_net_plane_rule(host, networks):
    if "ZEN_NFM" in host.get("role") or "ZEN_CTL" in host.get("role"):
        is_config, count = has_net_plane(host, "HEARTBEAT", networks)
        if not is_config or count != 1:
            message = _("ZEN_NFM/ZEN_CTL must be "
                        "config one HEARTBEAT net plane.")
            raise exceptions.ConfigurationError(message)


def is_config_dvs(host):
    for interface in host.get("interfaces"):
        if interface["vswitch_type"] == "dvs":
            return True
    return False


def segment_type_4_vswitch_type_rule(host, networks):

    def is_config_vxlan(in_networks):
        for in_network in in_networks:
            if (in_network.name == "physnet1") and \
                    (in_network.segmentation_type == "vxlan"):
                return True
        return False

    if is_config_vxlan(networks) and \
            has_net_plane(host, "DATAPLANE", networks)[0] and \
            not is_config_dvs(host):
        message = _("Configure vxlan must configure DVS.")
        raise exceptions.ConfigurationError(message)


def network_map_4_net_port_rule(host, networks):

    def is_linux_bond_port(in_interface):
        # mode map type to find linux bond port
        linux_bond_modes = ["active-backup", "balance-xor", "802.3ad"]
        if (in_interface["type"] == "bond") and \
                (in_interface["mode"] in linux_bond_modes):
            return True
        return False

    def is_config_dataplane(in_interface, in_networks):
        for assigned_network in in_interface['assigned_networks']:
            for in_network in in_networks:
                if (in_network.name == assigned_network["name"]) and \
                        (in_network.network_type == "DATAPLANE"):
                    return True
        return False

    for interface in host.get("interfaces"):
        if is_linux_bond_port(interface) and \
                is_config_dataplane(interface, networks):
            message = _("Linux bond port can not map DATAPLANE net plane.")
            raise exceptions.ConfigurationError(message)


def host_net_plane_rule(ha_role, host, networks):
    if not host.get("interfaces", None):
        return
    if not host.get("role", None):
        return
    # all host must be config MANAGEMENT net plane
    if not has_net_plane(host, "MANAGEMENT", networks)[0]:
        message = _("All hosts must be config MANAGEMENT net plane.")
        raise exceptions.ConfigurationError(message)
    if backend == "tecs":
        # control node net plane rule
        control_node_net_plane_rule(ha_role, host, networks)
        # compute node net plane rule
        compute_node_net_plane_rule(ha_role, host, networks)
    # zenic node net plane rule
    zenic_node_net_plane_rule(host, networks)
    # segment type vswitch type rule
    segment_type_4_vswitch_type_rule(host, networks)
    # net work map net port rule
    network_map_4_net_port_rule(host, networks)


def hosts_net_plane_rule(rule_context):
    try:
        for host in rule_context.get("hosts"):
            host_net_plane_rule(rule_context.get("ha_role"),
                                host,
                                rule_context.get("networks"),
                                rule_context.get("backends"))
    except Exception as e:
        LOG.info("hosts_net_plane_rule %s", e)
        raise


def host_config_rule(host):

    def get_huge_page_size(size):
        compose = size.strip().split("G")
        act_size = int(compose[0])
        return act_size

    if not host.get("role", None):
        return
    if not host.get("interfaces", None):
        return
    # if not host.get("os_version"):
    #    message = _("Host %s must be config os version.") % host.get("name")
    #    raise exceptions.ConfigurationError(message)
    if is_config_dvs(host) and "COMPUTER" in host.get("role"):
        if not host.get("hugepagesize") or not host.get("hugepages"):
            message = _("Configure DVS, host huge page size "
                        "must be large 10G.")
            raise exceptions.ConfigurationError(message)
        # huge page size must be large 10G
        huge_page_size = get_huge_page_size(host.get("hugepagesize"))
        total_size = huge_page_size * int(host.get("hugepages"))
        if total_size < 10:
            message = _("Configure DVS, "
                        "host huge page size must be large 10G.")
            raise exceptions.ConfigurationError(message)


def hosts_config_rule(rule_context):
    try:
        for host in rule_context.get("hosts"):
            host_config_rule(host)
    except Exception as e:
        LOG.info("host_config_rule %s", e)
        raise


@csrf_exempt
def get_rule_context(request, cluster_id):
    rule_context = {}
    try:
        host_get_list = []
        ha_role = get_ha_role(request, cluster_id)
        qp = {"cluster_id": cluster_id}
        host_list = api.daisy.host_list(request, filters=qp)
        for host in host_list:
            host_get = api.daisy.host_get(request, host.id)
            host_get_list.append(host_get.to_dict())
        network_list = api.daisy.network_list(request, cluster_id)
        backends = host_views.get_backend_type_by_role_list(request)
        rule_context.update({
            "backends": backends,
            "ha_role": ha_role,
            "hosts": host_get_list,
            "networks": network_list})
    except Exception, e:
        LOG.info("get_rule_context failed!%s", e)
        raise
    return rule_context


@csrf_exempt
def deploy_rule_func(request, cluster_id):
    rule_lib_funcs = [hosts_role_rule,
                      hosts_net_plane_rule,
                      hosts_config_rule]
    try:
        rule_context = get_rule_context(request, cluster_id)
        for rule_func in rule_lib_funcs:
            rule_func(rule_context)
    except Exception, e:
        LOG.info("deploy_rule_func failed!%s", e)
        raise


def ip_into_int(ip):
    """
    Switch ip string to decimalism integer..
    :param ip: ip string
    :return: decimalism integer
    """
    return reduce(lambda x, y: (x << 8) + y, map(int, ip.split('.')))


def inter_into_ip(num):
    inter_ip = lambda x: '.'.join(
        [str(x / (256 ** i) % 256) for i in range(3, -1, -1)])
    return inter_ip(num)


def is_ip_in_cidr(ip, cidr):
    str_ip_mask = cidr.split('/')[1]
    ip_addr = cidr.split('/')[0]
    ip_inst = ip_into_int(ip_addr)
    mask = ~(2 ** (32 - int(str_ip_mask)) - 1)
    ip_addr_min = ip_inst & (mask & 0xffffffff)
    ip_addr_max = ip_inst | (~mask & 0xffffffff)
    if (ip_into_int(ip) >= ip_addr_min) and (ip_into_int(ip) <= ip_addr_max):
        return True
    return False


def ha_float_ip_rule(ha, public_cidr, management_cidr):
    if not is_ip_in_cidr(ha["public_vip"], public_cidr):
        message = _("Public VIP must be on the same "
                    "network segment of PUBLICAPI net plane.")
        raise exceptions.ConfigurationError(message)
    ha_vip = ha.get("vip", None)
    if ha_vip and not is_ip_in_cidr(ha_vip, management_cidr):
        message = _("HA VIP must be on the same network segment "
                    "of MANAGEMENT net plane.")
        raise exceptions.ConfigurationError(message)
    glance_vip = ha.get("glance_vip", None)
    if glance_vip and not is_ip_in_cidr(glance_vip, management_cidr):
        message = _("Glance VIP must be on the same network "
                    "segment of MANAGEMENT net plane.")
        raise exceptions.ConfigurationError(message)
    if glance_vip == "" and ha["glance_disk_location"] != "share":
        message = _("Glance back-end is not share disk, "
                    "you need to configure glance float IP.")
        raise exceptions.ConfigurationError(message)
    db_vip = ha.get("db_vip", None)
    if db_vip and not is_ip_in_cidr(db_vip, management_cidr):
        message = _("DB VIP must be on the same network segment "
                    "of MANAGEMENT net plane.")
        raise exceptions.ConfigurationError(message)


def lb_float_ip_rule(lb, management_cidr):
    lb_vip = lb.get("vip", None)
    if lb_vip and not is_ip_in_cidr(lb_vip, management_cidr):
        message = _("LB VIP must be on the same network segment "
                    "of MANAGEMENT net plane.")
        raise exceptions.ConfigurationError(message)


def zenic_nfm_float_ip_rule(zenic_nfm, management_cidr):
    zenic_nfm_vip = zenic_nfm.get("vip", None)
    if zenic_nfm_vip and not is_ip_in_cidr(zenic_nfm_vip, management_cidr):
        message = _("ZENIC NFM VIP must be on the same network "
                    "segment of MANAGEMENT net plane.")
        raise exceptions.ConfigurationError(message)


def zenic_ctl_float_ip_rule(zenic_ctl, management_cidr):
    zenic_ctl_vip = zenic_ctl.get("vip", None)
    if zenic_ctl_vip and not is_ip_in_cidr(zenic_ctl_vip, management_cidr):
        message = _("ZENIC CTL VIP must be on the same network "
                    "segment of MANAGEMENT net plane.")
        raise exceptions.ConfigurationError(message)


def net_plane_4_role_rule(request, cluster_id, role_info, net_planes):

    def get_net_plane_cidr(nets, name):
        for net in nets:
            if net["name"] == name:
                return net["cidr"]
        return ""

    try:
        public_cidr = get_net_plane_cidr(net_planes, "PUBLICAPI")
        management_cidr = get_net_plane_cidr(net_planes, "MANAGEMENT")
        role_list = api.daisy.role_list(request)
        roles = [role for role in role_list
                 if role.cluster_id == cluster_id]
        for role in roles:
            if role.name == "CONTROLLER_HA":
                ha = role_info["ha"]
                ha_float_ip_rule(ha, public_cidr, management_cidr)
            elif role.name == "CONTROLLER_LB":
                lb = role_info["lb"]
                lb_float_ip_rule(lb, management_cidr)
            elif role.name == "ZENIC_NFM":
                zenic_nfm = role_info["zenic_nfm"]
                zenic_nfm_float_ip_rule(zenic_nfm, management_cidr)
            elif role.name == "ZENIC_CTL":
                zenic_ctl = role_info["zenic_ctl"]
                zenic_ctl_float_ip_rule(zenic_ctl, management_cidr)
    except Exception as e:
        LOG.info("net_plane_4_role_rule %s", e)
        raise


def net_port_4_net_map_rule(interfaces, net_ports):
    try:
        for interface in interfaces:
            if interface["name"] in net_ports \
                    and len(interface["assigned_networks"]) > 0:
                message = _("Has been mapped network port does not "
                            "support bond/unbond.")
                raise exceptions.ConfigurationError(message)
    except Exception as e:
        LOG.info("net_port_4_net_map_rule %s", e)
        raise
