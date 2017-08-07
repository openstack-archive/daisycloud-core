# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2010-2011 OpenStack Foundation
# Copyright 2012 Justin Santa Barbara
# Copyright 2013 IBM Corp.
# Copyright 2015 Mirantis, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


"""Defines interface for DB access."""

import threading
import uuid
import re
import copy
from oslo_config import cfg
from oslo_db import exception as db_exception
from oslo_db.sqlalchemy import session
from oslo_log import log as logging
from oslo_utils import timeutils
import osprofiler.sqlalchemy
from retrying import retry
import six
from operator import itemgetter
# NOTE(jokke): simplified transition to py3, behaves like py2 xrange
from six.moves import range
import sqlalchemy
import sqlalchemy.orm as sa_orm
import sqlalchemy.sql as sa_sql
import types
import socket
import netaddr
import copy
import json

from daisy.common import exception
from daisy.common import utils
from daisy.db.sqlalchemy import models
from daisy import i18n

BASE = models.BASE
sa_logger = None
LOG = logging.getLogger(__name__)
_ = i18n._
_LI = i18n._LI
_LW = i18n._LW


STATUSES = ['active', 'saving', 'queued', 'killed', 'pending_delete',
            'deleted', 'deactivated']

CONF = cfg.CONF
CONF.import_group("profiler", "daisy.common.wsgi")

_FACADE = None
_LOCK = threading.Lock()


def _retry_on_deadlock(exc):
    """Decorator to retry a DB API call if Deadlock was received."""

    if isinstance(exc, db_exception.DBDeadlock):
        LOG.warning(_LW("Deadlock detected. Retrying..."))
        return True
    return False


def _create_facade_lazily():
    global _LOCK, _FACADE
    if _FACADE is None:
        with _LOCK:
            if _FACADE is None:
                _FACADE = session.EngineFacade.from_config(CONF)

                if CONF.profiler.enabled and CONF.profiler.trace_sqlalchemy:
                    osprofiler.sqlalchemy.add_tracing(sqlalchemy,
                                                      _FACADE.get_engine(),
                                                      "db")
    return _FACADE


def get_engine():
    facade = _create_facade_lazily()
    return facade.get_engine()


def get_session(autocommit=True, expire_on_commit=False):
    facade = _create_facade_lazily()
    return facade.get_session(autocommit=autocommit,
                              expire_on_commit=expire_on_commit)


def _check_host_id(host_id):
    """
    check if the given host id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the host id
    length is longer than the defined length in database model.
    :param host_id: The id of the host we want to check
    :return: Raise NoFound exception if given host id is invalid
    """
    if (host_id and
       len(host_id) > models.Host.id.property.columns[0].type.length):
        raise exception.NotFound()

def _checker_the_ip_or_hostname_valid(ip_str):
    try:
        socket.gethostbyname_ex(ip_str)
        return True
    except Exception:
        if netaddr.IPAddress(ip_str).version == 6:
            return True
        else:
            return False


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


def is_in_cidr_range(ip, network):
    """
    Check ip is in range
    :param ip: Ip will be checked, like:192.168.1.2.
    :param network: Ip range,like:192.168.0.0/24.
    :return: If ip in range,return True,else return False.
    """
    network = network.split('/')
    mask = ~(2**(32 - int(network[1])) - 1)
    return (ip_into_int(ip) & mask) == (ip_into_int(network[0]) & mask)


def is_in_ip_range(ip, ip_range):
    """
    Check ip is in ip range
    :param ip: Ip will be checked, like:192.168.1.2.
    :param network: Ip range,like:
    {u'start': u'192.168.1.20', u'end': u'192.168.1.21'}.
    :return: If ip in range,return True,else return False.
    """
    if ip_range.get('start') and ip_range.get('end'):
        integer_start_ip = ip_into_int(ip_range['start'])
        integer_end_ip = ip_into_int(ip_range['end'])
        ip_int = ip_into_int(ip)
        return True if integer_start_ip <= ip_int <= integer_end_ip else False


def cidr_convert_ip_ranges(cidr):
    str_ip_mask = cidr.split('/')[1]
    ip_addr = cidr.split('/')[0]
    ip_inst = ip_into_int(ip_addr)
    mask = ~(2**(32 - int(str_ip_mask)) - 1)
    ip_addr_min = inter_into_ip(ip_inst & (mask & 0xffffffff))
    ip_addr_max = inter_into_ip(ip_inst | (~mask & 0xffffffff))
    if ip_addr_min.split('.')[3] == '0':
        ip_addr_min = ip_addr_min.split('.')[0] + '.' + \
            ip_addr_min.split('.')[1] + '.' + ip_addr_min.split('.')[2] + '.1'
    return [ip_addr_min, ip_addr_max]

def get_ip_with_equal_cidr(cluster_id,network_plane_name,session, exclude_ips=[]):
    equal_cidr_network_plane_id_list = []
    available_ip_list = copy.deepcopy(exclude_ips)

    sql_network_plane_cidr = "select networks.cidr,network_type,id from networks \
                              where networks.name='" + network_plane_name + \
                             "' and networks.cluster_id='" + cluster_id + \
                             "' and networks.deleted=0"
    query_network_plane_cidr = \
        session.execute(sql_network_plane_cidr).fetchone()
    LOG.info('query_network_plane_cidr: %s' % query_network_plane_cidr.values())
    network_cidr = query_network_plane_cidr.values()[0]
    network_type = query_network_plane_cidr.values()[1]
    tmp_netword_id = query_network_plane_cidr.values()[2]
    if network_type == 'DATAPLANE':
        return get_used_ip_in_dataplan_net(tmp_netword_id, session)
    if not network_cidr:
        msg = "Error:The CIDR is blank of %s!" % network_plane_name
        LOG.error(msg)
        raise exception.Forbidden(msg)
    str_network_cidr = ','.join(cidr_convert_ip_ranges(network_cidr))

    sql_all_network_plane_info = "select networks.id,networks.cidr,\
                                 networks.name from networks where \
                                 networks.cluster_id='" + cluster_id + \
                                 "' and networks.deleted=0"
    query_all_network_plane_info = \
        session.execute(sql_all_network_plane_info).fetchall()
    for network_plane_tmp in query_all_network_plane_info:
        query_network_plane_tmp_info = network_plane_tmp.values()
        cidr = query_network_plane_tmp_info[1]
        if not cidr:
            continue
        ip_ranges_cidr = cidr_convert_ip_ranges(cidr)
        str_query_network_plane_cidr = ','.join(ip_ranges_cidr)
        if str_network_cidr == str_query_network_plane_cidr:
            equal_cidr_network_plane_id_list.append(
                query_network_plane_tmp_info[0])
            if query_network_plane_tmp_info[2] == 'MANAGEMENT' or \
                    query_network_plane_tmp_info[2] == 'PUBLICAPI':
                roles_info_sql = "select roles.db_vip,roles.glance_vip,\
                                 roles.vip, roles.provider_public_vip,\
                                 roles.public_vip from roles where \
                                 roles.cluster_id='" + cluster_id + \
                                 "' and roles.deleted=0"
                roles_vip = session.execute(roles_info_sql).fetchall()
                available_ip_list.extend([vip for role_vip in
                                          roles_vip for vip in
                                          role_vip.values() if vip])
            if query_network_plane_tmp_info[2] == 'OUTBAND':
                roles_info_sql = "select roles.outband_vip from roles where " +\
                            "roles.cluster_id='" + cluster_id + \
                            "' and roles.deleted=0"
                outband_vip = session.execute(roles_info_sql).fetchall()
                available_ip_list.extend([vip for role_vip in
                                          outband_vip for vip in
                                          role_vip.values() if vip])

    for network_id in equal_cidr_network_plane_id_list:
        sql_ip = "select assigned_networks.ip from assigned_networks \
                 where assigned_networks.deleted=0 and \
                 assigned_networks.network_id='" + network_id + \
                 "' order by assigned_networks.ip"
        query_ip_list = session.execute(sql_ip).fetchall()
        for tmp_ip in query_ip_list:
            ip_pop = tmp_ip.values().pop()
            available_ip_list.append(ip_pop)
    LOG.info('available_ip_list: %s ' % available_ip_list)
    return list(set(available_ip_list))

def get_used_ip_in_dataplan_net(network_id, session):
    available_ip_list = []
    sql_ip = "select assigned_networks.ip from assigned_networks \
             where assigned_networks.deleted=0 and \
             assigned_networks.network_id='" + network_id + \
             "' order by assigned_networks.ip"
    query_ip_list = session.execute(sql_ip).fetchall()
    for tmp_ip in query_ip_list:
        ip_pop = tmp_ip.values().pop()
        available_ip_list.append(ip_pop)
    return list(set(available_ip_list))


# for example:
# merged_by_cidr_vlan['(10,23)'] = [management_network_plane]
# merged_by_cidr_vlan['(9,24)'] = [
# deployment_network_plane,storage_network_plane]
# merged_networks=[{'name':'MAGEMENT','ip':"10.43.177.2"},
#                  {'name':'DEPLOYMENT,STORAGE','ip':""}]
def merge_networks_for_unifiers(cluster_id, assigned_networks):
    merged_by_cidr_vlan = {}
    session = get_session()
    for network_plane in assigned_networks:
        network_plane_name = network_plane['name']
        # network_plane_ip = network_plane.get('ip')
        sql_network_plane_info = "select networks.vlan_id,networks.cidr \
                                 from networks where networks.name='" + \
                                 network_plane_name + \
                                 "' and networks.cluster_id='" + \
                                 cluster_id + "' and networks.deleted=0"
        query_network_plane_info = \
            session.execute(sql_network_plane_info).fetchone()
        vlan_id = query_network_plane_info.values()[0]
        if not vlan_id:
            vlan_id = ''
        cidr = query_network_plane_info.values()[1]

        if cidr:
            cidr_split = cidr.split('/')
            mask = ~(2**(32 - int(cidr_split[1])) - 1)
            ip_validvalue = ip_into_int(cidr_split[0]) & mask
            ip_str = inter_into_ip(ip_validvalue)
            cidr = ip_str + '/' + cidr_split[1]

        index = (vlan_id, cidr)
        if merged_by_cidr_vlan.has_key(index):
            merged_by_cidr_vlan[index].append(network_plane)
        else:
            merged_by_cidr_vlan[index] = [network_plane]

    merged_networks = []
    for networks in merged_by_cidr_vlan.values():
        same_networks = []
        for network in networks:
            is_network_merged = False
            for merged_network in same_networks:
                if (network.get('ip', None) ==
                        merged_network.get('ip', None)):
                    is_network_merged = True
                    merged_network['name'] = \
                        merged_network['name'] + ',' + network['name']
            if not is_network_merged:
                same_networks.append({'name': network['name'],
                                        'ip': network.get('ip', None)})
        merged_networks += same_networks
    return merged_networks


def check_ip_exist(cluster_id, network_plane_name,
                   network_plane_ip,
                   session):
    check_ip_if_valid = _checker_the_ip_or_hostname_valid(network_plane_ip)
    if not check_ip_if_valid:
        msg = "Error:The %s is not the right ip!" % network_plane_ip
        LOG.error(msg)
        raise exception.Forbidden(msg)

    available_ip_list = \
        get_ip_with_equal_cidr(cluster_id, network_plane_name, session)
    # allow different networks with same ip in the same interface
    if network_plane_ip in available_ip_list:
        msg = "Error:The IP %s already exist." % network_plane_ip
        LOG.error(msg)
        raise exception.Forbidden(msg)


def check_ip_ranges(ip_ranges_one,available_ip_list):
    # ip_range = copy.deepcopy(ip_ranges_one.values())
    ip_ranges_end = ip_ranges_one[1]
    ip_ranges_start = ip_ranges_one[0]
    ip_range_gw = ip_ranges_one[3]
    if ip_range_gw:
        available_ip_list.append(ip_range_gw)
    inter_num = ip_into_int(ip_ranges_start)
    ip_ranges_end_inter = ip_into_int(ip_ranges_end)
    while True:
        inter_tmp = inter_num
        ip_tmp = inter_into_ip(inter_tmp)
        if ip_tmp not in available_ip_list:
            if inter_tmp > ip_ranges_end_inter:
                msg = "warning:The IP address assigned \
                        by IP ranges is already insufficient."
                LOG.warning(msg)
                break
            else:
                return [True, ip_tmp]
        else:
            inter_num = inter_tmp + 1

    return [False, None]


def change_host_name(context, values, mangement_ip, host_ref):

    def is_host_name_exist(in_hosts, origin_name, origin_id):
        for host in in_hosts:
            if (host.get("name", "") == origin_name) and\
                    (host.get("id", "") != origin_id):
                return True
        return False

    # The host name has been assigned and no redistribution is required.
    if getattr(host_ref, "name", None):
        return
    if mangement_ip and host_ref.os_status != "active":
        host_name = "host-" + mangement_ip.replace('.', '-')
        hosts = host_get_all(context)
        if is_host_name_exist(hosts, host_name, getattr(host_ref, "id")):
            raise exception.Duplicate("Host name %s already exists!"
                                          % host_name)
        values['name'] = host_name


def compare_same_cidr_ip(x, y):
    return eval(x[0].split('.').pop()) - eval(y[0].split('.').pop())

def sort_ip_ranges_with_cidr(ip_ranges, net_cidr=None):
    '''
    ip_ranges=[(start,end,cidr,gateway),
            ('12.18.1.5', '12.18.1.6', '12.18.1.1/24', '12.18.1.5'),
            ('12.18.1.15', '12.18.1.16', '12.18.1.1/24', '12.18.1.5'),
            ('13.18.1.5', '13.18.1.5', '13.18.1.1/24', '13.18.1.5'),
            ('2.1.1.12', '2.1.1.12', '2.1.1.1/24', '2.1.1.1'),
            ('2.1.1.17', '2.1.1.32', '2.1.1.1/24', '2.1.1.1'),
            ('9.18.1.1', '9.18.1.2', '9.18.1.1/24', '9.18.1.1'),
            ('', '', '9.8.1.1/24', '9.8.1.1'),
            ('9.18.1.1', '9.18.1.2', '', ''),]
    '''
    tmp_ip_ranges = copy.deepcopy(ip_ranges)
    convert_ip_ranges=[]
    for ip_range in tmp_ip_ranges:
        if ip_range[0]:
            int_start_ip = ip_into_int(ip_range[0])
        else:
            int_start_ip = 0
        cidr = ip_range[2]
        if cidr and cidr != 'None':
            cidr_ip = cidr.split('/')[0]
            int_cidr_ip = ip_into_int(cidr_ip)
        elif net_cidr and is_in_cidr_range(ip_range[0], net_cidr):
            cidr_ip = net_cidr.split('/')[0]
            int_cidr_ip = ip_into_int(cidr_ip)
        else:
            int_cidr_ip = 0
        convert_ip_ranges.append((int_cidr_ip, int_start_ip, ip_range))
    convert_ip_ranges = sorted(convert_ip_ranges, key=itemgetter(0,1))
    LOG.info('convert_ip_ranges: %s' % convert_ip_ranges)
    sorted_ip_ranges = [ip_range[2] for ip_range in convert_ip_ranges]
    LOG.info('sort_ip_ranges_with_cidr ip ranges: %s' % sorted_ip_ranges)
    return sorted_ip_ranges


def according_to_cidr_distribution_ip(cluster_id, network_plane_name,
                                      session, exclude_ips=[]):
    ip_ranges_cidr = []
    distribution_ip = ""

    sql_network_plane_info = "select networks.id,cidr,network_type,\
                             segmentation_type,gateway from networks \
                             where networks.name='" + network_plane_name + \
                             "' and networks.cluster_id='" + cluster_id + \
                             "' and networks.deleted=0"
    query_network_plane_info = \
        session.execute(sql_network_plane_info).fetchone()
    network_id = query_network_plane_info.values()[0]
    network_cidr = query_network_plane_info.values()[1]
    network_type = query_network_plane_info.values()[2]
    segmentation_type = query_network_plane_info.values()[3]
    network_gw = query_network_plane_info.values()[4]
    if network_type not in ['EXTERNAL']:
        if network_type == 'DATAPLANE' and segmentation_type == 'vlan':
            return distribution_ip
        available_ip_list = get_ip_with_equal_cidr(
            cluster_id, network_plane_name, session, exclude_ips)
        sql_ip_ranges = "select ip_ranges.start,end,cidr,gateway from \
                         ip_ranges where network_id='" + network_id + \
                        "' and ip_ranges.deleted=0"
        query_ip_ranges = session.execute(sql_ip_ranges).fetchall()
        LOG.info('query_ip_ranges: %s ' % query_ip_ranges)

        used_cidrs = []
        all_full_ip_ranges = []
        if query_ip_ranges:
            for ip_range in query_ip_ranges:
                tmp_full_ip_ranges = []
                if ip_range[0] and not ip_range[2]:
                    # with start_ip, without ip_range_cidr
                    if is_in_cidr_range(ip_range[0], network_cidr):
                        tmp_full_ip_ranges = \
                            [ip_range[0], ip_range[1], network_cidr, '']
                        used_cidrs.append(network_cidr)
                    else:
                        msg = 'Ip range: %s maybe invalid data.' % ip_range 
                        LOG.error(msg)
                elif ip_range[0] and ip_range[2]:
                    # with start_ip and ip_range_cidr
                    tmp_full_ip_ranges = \
                        [ip_range[0], ip_range[1], ip_range[2], ip_range[3]]
                    used_cidrs.append(ip_range[2])
                elif not ip_range[0] and ip_range[2]:
                    # without start_ip, with ip_range_cidr
                    tmp_cidr_ranges = cidr_convert_ip_ranges(ip_range[2])
                    tmp_full_ip_ranges = [tmp_cidr_ranges[0],
                        tmp_cidr_ranges[1], ip_range[2], ip_range[3]]
                    used_cidrs.append(ip_range[2])
                all_full_ip_ranges.append(tmp_full_ip_ranges)
        if network_cidr and network_cidr not in used_cidrs:
            tmp_gw = ''
            if network_type == 'DATAPLANE':
                tmp_gw = network_gw
            tmp_cidr_ranges = cidr_convert_ip_ranges(network_cidr)
            tmp_full_ip_ranges = [tmp_cidr_ranges[0], tmp_cidr_ranges[1],
                                    network_cidr, tmp_gw]
            used_cidrs.append(network_cidr)
            all_full_ip_ranges.append(tmp_full_ip_ranges)
        LOG.info("network_type: %s, all_full_ip_ranges: %s" % (network_type,
                                                        all_full_ip_ranges))
        query_ip_ranges = \
            sort_ip_ranges_with_cidr(all_full_ip_ranges, network_cidr)

        for ip_ranges_one in query_ip_ranges:
            check_ip_exist_list = \
                check_ip_ranges(ip_ranges_one, available_ip_list)
            if check_ip_exist_list[0]:
                distribution_ip = check_ip_exist_list[1]
                return distribution_ip
        msg = "Error:The IP address assigned by \
              ip ranges is already insufficient."
        LOG.error(msg)
        raise exception.Forbidden(msg)
    return distribution_ip


def add_assigned_networks_data(context, network, cluster_id,
                               host_interface_ref, network_plane_names,
                               network_plane_ip, session):
    for network_plane_name in network_plane_names:
        sql_network_plane_id = "select networks.id,networks.network_type \
                                from networks where networks.name='" + \
                               network_plane_name + \
                               "' and networks.cluster_id='" + \
                               cluster_id + "' and networks.deleted=0"
        query_network_plane_id = \
            session.execute(sql_network_plane_id).fetchone()
        network_id = query_network_plane_id.values()[0]
        network_type = query_network_plane_id.values()[1]

        assigned_network = dict()
        assigned_network['ip'] = network_plane_ip
        assigned_networks_ref = models.AssignedNetworks()
        assigned_network['network_id'] = network_id
        if host_interface_ref.type == 'bond':
            assigned_network['mac'] = ''
        else:
            assigned_network['mac'] = network['mac']
        assigned_network['interface_id'] = host_interface_ref.id
        if network_type == 'VXLAN' or network_type == 'DATAPLANE':
            assigned_network['vswitch_type'] = network.get('vswitch_type',
                                                           'ovs')
        assigned_networks_ref.update(assigned_network)
        _update_values(assigned_networks_ref, assigned_network)
        assigned_networks_ref.save(session=session)


def assign_float_ip(context, cluster_id, role_id, network_name, session):
    assigned_ips = []
    vip = {}
    query = session.query(models.Role).filter_by(id=role_id).\
        filter_by(deleted=False)
    query_role = query.one()
    if query_role.name == 'CONTROLLER_HA':
        if not query_role.vip:
            vip['vip'] = according_to_cidr_distribution_ip(
                cluster_id, network_name, session, assigned_ips)
            assigned_ips.append(vip['vip'])

            sql_cluster_info = "select clusters.public_vip from clusters \
                                where id='" + cluster_id +\
                               "' and clusters.deleted=0"
            query_cluster_info = session.execute(sql_cluster_info).fetchone()
            cluster_public_vip = query_cluster_info.values().pop()
            if not cluster_public_vip:
                cluster_values = dict()
                cluster_ref = _cluster_get(context, cluster_id,
                                           session=session)
                cluster_values['public_vip'] = vip['vip']
                cluster_ref.update(cluster_values)
                _update_values(cluster_ref, cluster_values)
                cluster_ref.save(session=session)
        if not query_role.glance_vip:
            vip['glance_vip'] = according_to_cidr_distribution_ip(
                cluster_id, network_name, session, assigned_ips)
            assigned_ips.append(vip['glance_vip'])

        if not query_role.db_vip:
            vip['db_vip'] = according_to_cidr_distribution_ip(
                cluster_id, network_name, session, assigned_ips)
            assigned_ips.append(vip['db_vip'])
    elif query_role.name == 'CONTROLLER_LB':
        if not query_role.vip:
            vip['vip'] = according_to_cidr_distribution_ip(
                cluster_id, network_name, session)
    if vip:
        query.update(vip, synchronize_session='fetch')


def _according_interface_to_add_network_alias(context,
                                              interface_assigned_networks,
                                              values):
    network_cidrs = []
    session = get_session()
    network_query = \
        session.query(models.Network).filter_by(
            deleted=False).filter_by(cluster_id=values['cluster']).all()
    for network_info in network_query:
        for network_name in interface_assigned_networks:
            if network_name == network_info['name']:
                network_cidrs.append(network_info['cidr'])
    if len(set(network_cidrs)) == 1 and len(network_cidrs) > 1:
        for sub_network_query in network_query:
            if sub_network_query.name in interface_assigned_networks:
                alias_name = '_'.join(interface_assigned_networks)
                query_network = \
                    session.query(models.Network).filter_by(
                        deleted=False).filter_by(id=sub_network_query.id)
                query_network.update({"alias": alias_name})


def _modify_os_version(os_version, host_ref):
    if utils.is_uuid_like(os_version):
        host_ref.os_version_id =os_version
        host_ref.os_version_file = None
    else:
        host_ref.os_version_file = os_version
        host_ref.os_version_id = None
    return host_ref


def _delete_host_fields(host_ref, values):
    delete_fields = ['config_set_id',
                     'vcpu_pin_set',
                     'dvs_high_cpuset',
                     'pci_high_cpuset',
                     'os_cpus',
                     'dvs_cpus',
                     'dvs_config_type',
                     'dvsc_cpus',
                     'dvsp_cpus',
                     'dvsv_cpus',
                     'dvsblank_cpus',
                     'flow_mode',
                     'virtio_queue_size',
                     'dvs_config_desc']
    for field in delete_fields:
        values[field] = None

    if values.has_key('os_status'):
        if values['os_status'] == 'init':
            values['isolcpus'] = None
    else:
        if host_ref.os_status == 'init':
            values['isolcpus'] = None


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _host_update(context, values, host_id):
    """
    Used internally by host_add and host_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param host_id: If None, create the host, otherwise, find and update it
    """
    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()
    role_values = dict()
    host_interfaces_values = dict()
    host_cluster_values = dict()
    delete_config_set_id = None

    session = get_session()
    with session.begin():
        if host_id:
            host_ref = _host_get(context, host_id, session=session)
        else:
            host_ref = models.Host()
        cluster_host_ref = models.ClusterHost()
        if host_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Host, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()
            host_cluster_values['updated_at'] = timeutils.utcnow()

        if host_id:
            if values.has_key("os_version"):
                host_ref = _modify_os_version(values["os_version"], host_ref)
            if values.has_key('cluster'):
                delete_host_cluster(context, host_id, session)
                host_cluster_values['host_id'] = host_id
                host_cluster_values['cluster_id'] = values['cluster']
                if host_ref.status == 'init':
                    values['status'] = "in-cluster"
                cluster_host_ref.update(host_cluster_values)
                _update_values(cluster_host_ref, host_cluster_values)
                cluster_host_ref.save(session=session)

            if values.has_key('role'):
                if values['role']:
                    delete_host_role(context, host_id, session)
                    for role_info in values['role']:
                        host_role_ref = models.HostRole()
                        role_values['host_id'] = host_ref.id
                        role_values['role_id'] = role_info
                        host_role_ref.update(role_values)
                        _update_values(host_role_ref, role_values)
                        host_role_ref.save(session=session)
                        if values.get('cluster'):
                            assign_float_ip(context, values['cluster'],
                                            role_info, 'MANAGEMENT', session)
                    values['status'] = "with-role"
                else:
                    delete_host_role(context, host_id, session)
                    if (values.has_key('cluster') or
                        host_ref.status == 'with-role' or
                       host_ref.status == 'in-cluster'):
                        values['status'] = "in-cluster"
                    else:
                        values['status'] = "init"
            if values.has_key('interfaces'):
                host_interfaces = \
                    get_host_interface(context, host_id, None, session)
                if host_interfaces:
                    for host_interface_info in host_interfaces:
                        delete_assigned_networks(
                            context, host_interface_info.id, session)
                    delete_host_interface(context, host_id, session)
                if isinstance(values['interfaces'], list):
                    orig_keys = values['interfaces']
                else:
                    orig_keys = list(eval(values['interfaces']))
                for host_interface_info in orig_keys:
                    if (host_interface_info.has_key('assigned_networks') and
                       host_interface_info['assigned_networks']):
                        _according_interface_to_add_network_alias(
                            context, host_interface_info[
                                'assigned_networks'], values)
                for network in orig_keys:
                    host_interfaces_values = network.copy()
                    if len(network.get('name', '')) > 15:
                        msg = 'The length of interface name:%s \
                                is larger than 15.' % network['name']
                        LOG.error(msg)
                        raise exception.Forbidden(msg)
                    if network.has_key('slaves'):
                        if len(network['slaves']) == 1:
                            host_interfaces_values['slave1'] = \
                                network['slaves'][0]
                        elif len(network['slaves']) == 2:
                            host_interfaces_values['slave1'] = \
                                network['slaves'][0]
                            host_interfaces_values['slave2'] = \
                                network['slaves'][1]
                        del host_interfaces_values['slaves']

                    if host_interfaces_values.has_key('assigned_networks'):
                        del host_interfaces_values['assigned_networks']
                    if host_interfaces_values.has_key('is_deployment'):
                        if host_interfaces_values[
                                'is_deployment'] == "True" or\
                           host_interfaces_values['is_deployment'] == True or\
                           host_interfaces_values['is_deployment'] == "true":
                            host_interfaces_values['is_deployment'] = 1
                        else:
                            host_interfaces_values['is_deployment'] = 0
                    if host_interfaces_values.has_key('id'):
                        del host_interfaces_values['id']
                    if host_interfaces_values.get('vf'):
                        host_interfaces_values['is_support_vf'] = True
                    host_interface_ref = models.HostInterface()
                    host_interface_ref.update(host_interfaces_values)
                    host_interface_ref.host_id = host_id
                    _update_values(host_interface_ref, host_interfaces_values)
                    host_interface_ref.save(session=session)
                    if host_interfaces_values.get('vf'):
                        _update_host_interface_vf_info(context,
                                                       host_id,
                                                       host_interface_ref.id,
                                                       host_interfaces_values.get('vf'),
                                                       session)

                    if values.has_key('cluster'):
                        if network.has_key('assigned_networks'):
                            merged_assigned_networks = \
                                merge_networks_for_unifiers(
                                    values['cluster'],
                                    network['assigned_networks'])
                            for networks_plane in merged_assigned_networks:
                                network_plane_names = \
                                    networks_plane['name'].split(',')
                                network_plane_ip = networks_plane.get('ip')
                                if network_plane_ip:
                                    check_ip_exist(
                                        values['cluster'],
                                        network_plane_names[0],
                                        network_plane_ip,
                                        session)
                                else:
                                    network_plane_ip = \
                                        according_to_cidr_distribution_ip(
                                            values['cluster'],
                                            network_plane_names[0],
                                            session)

                                if 'MANAGEMENT' in network_plane_names:
                                    change_host_name(context, values,
                                                     network_plane_ip,
                                                     host_ref)
                                    # management_ip = network_plane_ip
                                add_assigned_networks_data(
                                    context, network, values['cluster'],
                                    host_interface_ref, network_plane_names,
                                    network_plane_ip, session)

            if (host_ref.status == 'with-role' and
                    (values.get('status', None) == 'init' or
                     values.get('status', None) == 'in-cluster')):
                delete_config_set_id = host_ref.config_set_id
                _delete_host_fields(host_ref, values)

            query = session.query(models.Host).filter_by(id=host_id)
            keys = values.keys()
            for k in keys:
                if k not in host_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update host_id %(host_id)s failed') %
                       {'host_id': host_id})
                raise exception.Conflict(msg)
            host_ref = _host_get(context, host_id, session=session)
        else:
            if values.has_key('cluster'):
                values['status'] = "in-cluster"
            if values.has_key('role'):
                values['status'] = "with-role"
            host_ref.update(values)
            _update_values(host_ref, values)
            try:
                host_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

            if values.has_key('cluster'):
                host_cluster_values['host_id'] = host_ref.id
                host_cluster_values['cluster_id'] = values['cluster']
                cluster_host_ref.update(host_cluster_values)
                _update_values(cluster_host_ref, host_cluster_values)
                cluster_host_ref.save(session=session)

            if values.has_key('role'):
                for role_info in values['role']:
                    host_role_ref = models.HostRole()
                    role_values['host_id'] = host_ref.id
                    role_values['role_id'] = role_info
                    host_role_ref.update(role_values)
                    _update_values(host_role_ref, role_values)
                    host_role_ref.save(session=session)
                    if values.get('cluster'):
                        assign_float_ip(
                            context, values['cluster'], role_info,
                            'MANAGEMENT', session)
            if values.has_key("os_version"):
                host_ref = _modify_os_version(values["os_version"], host_ref)

            if values.has_key('interfaces'):
                orig_keys = list(eval(values['interfaces']))
                for network in orig_keys:
                    host_interface_ref = models.HostInterface()
                    host_interfaces_values = network.copy()
                    if network.has_key('slaves'):
                        if len(network['slaves']) == 1:
                            host_interfaces_values['slave1'] = \
                                network['slaves'][0]
                        elif len(network['slaves']) == 2:
                            host_interfaces_values['slave1'] = \
                                network['slaves'][0]
                            host_interfaces_values['slave2'] = \
                                network['slaves'][1]

                    if host_interfaces_values.has_key('is_deployment'):
                        if host_interfaces_values['is_deployment'] == \
                            "True" or\
                           host_interfaces_values['is_deployment'] == True or \
                           host_interfaces_values['is_deployment'] == "true":
                            host_interfaces_values['is_deployment'] = 1
                        else:
                            host_interfaces_values['is_deployment'] = 0
                    if host_interfaces_values.get('vf'):
                        host_interfaces_values['is_support_vf'] = True
                    host_interfaces_values['host_id'] = host_ref.id
                    host_interface_ref.update(host_interfaces_values)
                    _update_values(host_interface_ref, host_interfaces_values)
                    host_interface_ref.save(session=session)
                    if host_interfaces_values.get('vf'):
                        _update_host_interface_vf_info(context,
                                                       host_ref.id,
                                                       host_interface_ref.id,
                                                       host_interfaces_values.get('vf'),
                                                       session)


                    if values.has_key('cluster'):
                        if network.has_key('assigned_networks'):
                            merged_assigned_networks = \
                                merge_networks_for_unifiers(
                                    values['cluster'],
                                    network['assigned_networks'])
                            for networks_plane in merged_assigned_networks:
                                network_plane_names = \
                                    networks_plane['name'].split(',')
                                network_plane_ip = networks_plane.get('ip')
                                if network_plane_ip:
                                    check_ip_exist(
                                        values['cluster'],
                                        network_plane_names[0],
                                        network_plane_ip,
                                        session)
                                else:
                                    network_plane_ip = \
                                        according_to_cidr_distribution_ip(
                                            values['cluster'],
                                            network_plane_names[0],
                                            session)
                                if 'MANAGEMENT' in network_plane_names:
                                    change_host_name(context, values,
                                                     network_plane_ip,
                                                     host_ref)
                                    # management_ip = network_plane_ip
                                add_assigned_networks_data(
                                    context, network, values['cluster'],
                                    host_interface_ref, network_plane_names,
                                    network_plane_ip, session)

            query = session.query(models.Host).filter_by(id=host_ref.id)
            if values.has_key('cluster'):
                del values['cluster']
            if values.has_key('interfaces'):
                del values['interfaces']
            if values.has_key('role'):
                del values['role']
            if values.has_key('os_version'):
                del values['os_version']
            updated = query.update(values, synchronize_session='fetch')

    if delete_config_set_id:
        # delete config set data after the host data is saved to db
        config_set_destroy(context, delete_config_set_id)
    return host_get(context, host_ref.id)


def _host_get(context, host_id, session=None, force_show_deleted=False):
    """Get an host or raise if it does not exist."""
    _check_host_id(host_id)
    session = session or get_session()

    try:
        query = session.query(models.Host).filter_by(id=host_id)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        host = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return host


def host_get(context, host_id, session=None, force_show_deleted=False):
    host = _host_get(context, host_id, session=session,
                     force_show_deleted=force_show_deleted)
    return host


def get_host_interface(context, host_id, mac=None, session=None,
                       force_show_deleted=False):
    session = session or get_session()
    try:
        query = session.query(models.HostInterface).filter_by(host_id=host_id)
        if mac:
            query = query.filter_by(mac=mac)

        # filter out deleted items if context disallows it
        if not force_show_deleted:
            query = query.filter_by(deleted=False)

        host_interface = query.all()
        pf_host_interface = []
        for interface in host_interface:
            if not interface.is_vf:
                pf_host_interface.append(interface)
                assigned_networks_list = []
                openvswitch_type = ''
                assignnetwork_query = \
                    session.query(models.AssignedNetworks).filter_by(
                        interface_id=interface.id).filter_by(deleted=False)
                assignnetwork_list = assignnetwork_query.all()
                for assignnetwork in assignnetwork_list:
                    query_network = \
                        session.query(models.Network).filter_by(
                            id=assignnetwork.network_id).filter_by(
                            deleted=False).first()
                    if query_network:
                        assigned_networks_info = {'name': query_network.name,
                                                  'ip': assignnetwork.ip,
                                                  'type': query_network.network_type}

                        assigned_networks_list.append(assigned_networks_info)
                        if query_network.network_type in ['DATAPLANE']:
                            openvswitch_type = assignnetwork.vswitch_type
                interface.assigned_networks = assigned_networks_list
                interface.vswitch_type = openvswitch_type

                if interface.is_support_vf:
                    vf_infos = [inter.to_dict() for inter in host_interface if inter.parent_id==interface.id]
                    interface.vf = sorted(vf_infos, key=lambda x: x["vf_index"])

    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return pf_host_interface


def get_host_interface_mac(context, mac, session=None,
                           force_show_deleted=False):
    session = session or get_session()
    try:
        query = session.query(models.HostInterface).filter_by(
            mac=mac).filter_by(deleted=False).filter_by(is_vf=False)
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        host_interface = query.all()
        for interface in host_interface:
            list = []
            assignnetwork_query = \
                session.query(models.AssignedNetworks).filter_by(
                    interface_id=interface.id).filter_by(deleted=False)
            assignnetwork_list = assignnetwork_query.all()
            for assignnetwork in assignnetwork_list:
                query_network_name = \
                    session.query(models.Network).filter_by(
                        id=assignnetwork.network_id).filter_by(
                        deleted=False).one()
                list.append(query_network_name.name)
            interface.assigned_networks = list

    except sa_orm.exc.NoResultFound:
        msg = "No mac found with %s" % mac
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return host_interface


def get_assigned_network(context, interface_id, network_id,
                         session=None, force_show_deleted=False):
    session = session or get_session()
    try:
        query = \
            session.query(models.AssignedNetworks).filter_by(
                interface_id=interface_id).filter_by(
                network_id=network_id).filter_by(deleted=False)
        host_assigned_network = query.one()
    except sa_orm.exc.NoResultFound:
        msg = "No assigned_network found with interface %s and \
                network %s" % (interface_id, network_id)
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return host_assigned_network


def delete_host_role(context, host_id, session=None):
    session = session or get_session()
    try:
        query = session.query(models.HostRole).filter_by(
            host_id=host_id).filter_by(deleted=False)
        host_roles = query.all()
        for host_role in host_roles:
            host_role.delete(session=session)
    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def delete_host_cluster(context, host_id, session=None):
    session = session or get_session()
    try:
        query = session.query(models.ClusterHost).filter_by(
            host_id=host_id).filter_by(deleted=False)
        host_clusters = query.all()
        for host_cluster in host_clusters:
            host_cluster.delete(session=session)
    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def delete_host_interface(context, host_id, session=None):
    session = session or get_session()
    try:
        query = session.query(models.HostInterface).filter_by(
            host_id=host_id).filter_by(deleted=False)
        host_interface = query.all()
        for interface in host_interface:
            interface.delete(session=session)
    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def _get_assigned_networks_by_network_id(context, network_id, session=None,
                                         force_show_deleted=False):
    session = session or get_session()
    try:
        query = session.query(models.AssignedNetworks).filter_by(
            network_id=network_id).filter_by(deleted=False)
        assigned_networks = query.all()
    except sa_orm.exc.NoResultFound:
        msg = "No network found with ID %s" % network_id
        LOG.debug(msg)
        raise exception.NotFound(msg)
    return assigned_networks


def get_assigned_networks(context, interface_id, session=None,
                          force_show_deleted=False):
    session = session or get_session()
    try:
        query = session.query(models.AssignedNetworks).filter_by(
            interface_id=interface_id).filter_by(deleted=False)
        assigned_networks = query.all()
    except sa_orm.exc.NoResultFound:
        msg = "No interface found with ID %s" % interface_id
        LOG.debug(msg)
        raise exception.NotFound(msg)
    return assigned_networks


def delete_assigned_networks(context, interface_id, session=None,
                             force_show_deleted=False):
    session = session or get_session()
    try:
        query = session.query(models.AssignedNetworks).filter_by(
            interface_id=interface_id).filter_by(deleted=False)
        assigned_networks = query.all()
        for assigned_network in assigned_networks:
            assigned_network.delete(session=session)

    except sa_orm.exc.NoResultFound:
        msg = "No interface found with ID %s" % interface_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def get_os_version(context, version_id, session=None,
                   force_show_deleted=False):
    session = session or get_session()
    try:
        query = session.query(models.Version).filter_by(id=version_id)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        os_version = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No version found with ID %s" % version_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return os_version


def host_add(context, values):
    """Add an host from the values dictionary."""
    return _host_update(context, values, None)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def host_destroy(context, host_id):
    """Destroy the host or raise if it does not exist."""
    session = get_session()
    with session.begin():
        host_ref = _host_get(context, host_id, session=session)
        host_interfaces = get_host_interface(context, host_id, None, session)
        if host_interfaces:
            for host_interface_info in host_interfaces:
                delete_assigned_networks(context, host_interface_info.id)
        delete_host_interface(context, host_id, session=session)
        host_ref.delete(session=session)

        discover_hosts = discover_host_get_by_host_id(context,
                                                      host_id,
                                                      session=session)
        for discover_host in discover_hosts:
            discover_host_ref = _discover_host_get(context,
                                                   discover_host['id'],
                                                   session=session)
            discover_host_ref.delete(session=session)
    return host_ref


def host_update(context, host_id, values):
    """
    Set the given properties on an host and update it.

    :raises NotFound if host does not exist.
    """
    return _host_update(context, values, host_id)


def discover_host_add(context, values):
    """Add an discover host from the values dictionary."""
    return _discover_host_update(context, values, None)


def discover_host_update(context, discover_host_id, values):
    """
    Set the given properties on an discover host and update it.

    :raises NotFound if host does not exist.
    """
    return _discover_host_update(context, values, discover_host_id)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _discover_host_update(context, values, discover_host_id):
    """
    Used internally by discover_host_add and discover_host_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param discover_host_id: If None, create the discover host,
    otherwise, find and update it
    """
    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()
    session = get_session()
    with session.begin():
        if discover_host_id:
            discover_host_ref = \
                _discover_host_get(context, discover_host_id, session=session)

        else:
            discover_host_ref = models.DiscoverHost()

        if discover_host_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.DiscoverHost, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if discover_host_id:
            if values.get('id', None): del values['id']
            discover_host_ref.update(values)
            _update_values(discover_host_ref, values)
            try:
                discover_host_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])
        else:
            discover_host_ref.update(values)
            _update_values(discover_host_ref, values)
            try:
                discover_host_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

    return discover_host_get(context, discover_host_ref.id)


def _discover_host_get(context, discover_host_id, session=None,
                       force_show_deleted=False):
    """Get an host or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.DiscoverHost).filter_by(id=discover_host_id)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        discover_host = query.one()
        return discover_host
    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % discover_host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def discover_host_get_by_host_id(context, host_id, session=None,
                                 force_show_deleted=False):

    session = session or get_session()
    discover_hosts = []
    query = session.query(models.DiscoverHost).filter_by(host_id=host_id)
    if not force_show_deleted and not context.can_see_deleted:
        query = query.filter_by(deleted=False)
    for discover_host in query.all():
        discover_host_dict = discover_host.to_dict()
        discover_hosts.append(discover_host_dict)

    return discover_hosts


def discover_host_get(context, discover_host_id, session=None,
                      force_show_deleted=False):
    discover_host = _discover_host_get(context, discover_host_id,
                                       session=session,
                                       force_show_deleted=force_show_deleted)
    return discover_host


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def discover_host_destroy(context, host_id):
    """Destroy the discover host or raise if it does not exist."""
    session = get_session()
    with session.begin():
        host_ref = _discover_host_get(context, host_id, session=session)
        host_ref.delete(session=session)
    return host_ref


def discover_host_get_all(context, filters=None, marker=None, limit=None,
                          sort_key=None, sort_dir=None):

    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_discover_host = None
    if marker is not None:
        marker_discover_host =\
            _discover_host_get(context,
                               marker,
                               force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    discover_hosts = []

    if 'cluster_id' in filters:
        cluster_id = filters.pop('cluster_id')
        sql = "select discover_hosts.*  from discover_hosts where \
              discover_hosts.deleted=0 and discover_hosts.cluster_id ='" + \
              cluster_id + "'"
        query = session.execute(sql).fetchall()
        for host in query:
            host_dict = dict(host.items())
            discover_hosts.append(host_dict)
        return discover_hosts

    query = session.query(models.DiscoverHost).filter_by(
        deleted=showing_deleted)
    query = _paginate_query(query, models.DiscoverHost, limit,
                            sort_key,
                            marker=marker_discover_host,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    for discover_host in query.all():
        discover_host = discover_host.to_dict()
        discover_hosts.append(discover_host)
    return discover_hosts


def get_discover_host_detail(context, discover_host_id, session=None,
                             force_show_deleted=False):
    '''
    '''
    session = session or get_session()
    try:
        query = session.query(models.DiscoverHost).filter_by(
            id=discover_host_id, deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        discover_host = query.one()
    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % discover_host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return discover_host


def _check_cluster_id(cluster_id):
    """
    check if the given project id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the project id
    length is longer than the defined length in database model.
    :param cluster_id: The id of the project we want to check
    :return: Raise NoFound exception if given project id is invalid
    """
    if (cluster_id and
       len(cluster_id) > models.Cluster.id.property.columns[0].type.length):
        raise exception.NotFound()


def delete_cluster_host(context, cluster_id, session=None):
    session = session or get_session()
    try:
        query = session.query(models.ClusterHost).filter_by(
            cluster_id=cluster_id).filter_by(deleted=False)
        cluster_host = query.all()
        for host in cluster_host:
            host.delete(session=session)
    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % cluster_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _cluster_update(context, values, cluster_id):
    """
    Used internally by cluster_add and project_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param cluster_id: If None, create the project,
        otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    if not values:
        raise exception.Invalid()

    values = values.copy()
    hosts_values = dict()
    interfaces_values = dict()

    session = get_session()
    with session.begin():
        if cluster_id:
            project_ref = _cluster_get(context, cluster_id, session=session)
        else:
            project_ref = models.Cluster()
            # host_ref = models.Host()

        # parse the range params
        if values.has_key('networking_parameters'):
            network_params = eval(values['networking_parameters'])
            if network_params:
                if network_params.has_key('gre_id_range') and \
                   len(network_params['gre_id_range']) > 1:
                    values['gre_id_start'] = network_params['gre_id_range'][0]
                    values['gre_id_end'] = network_params['gre_id_range'][1]
                if network_params.has_key('vlan_range') and \
                   len(network_params['vlan_range']) > 1:
                    values['vlan_start'] = network_params['vlan_range'][0]
                    values['vlan_end'] = network_params['vlan_range'][1]
                if network_params.has_key('vni_range') and \
                   len(network_params['vni_range']) > 1:
                    values['vni_start'] = network_params['vni_range'][0]
                    values['vni_end'] = network_params['vni_range'][1]
                if network_params.has_key('net_l23_provider'):
                    values['net_l23_provider'] = \
                        network_params.get('net_l23_provider', None)
                if network_params.has_key('base_mac'):
                    values['base_mac'] = network_params.get('base_mac', None)
                if network_params.has_key('segmentation_type'):
                    values['segmentation_type'] = \
                        network_params.get('segmentation_type', None)
                if network_params.has_key('public_vip'):
                    values['public_vip'] = \
                        network_params.get('public_vip', None)

        # save host info
        if values.has_key('nodes'):
            for host_id in eval(values['nodes']):
                host = host_get(context, host_id, session=None,
                                force_show_deleted=False)
                host.status = "in-cluster"
                host.save(session=session)

        if cluster_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Cluster, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if cluster_id:

            for cluster in session.query(models.Cluster).filter_by(
                    deleted=False).all():
                if cluster['id'] == cluster_id:
                    continue
                if cluster['name'] == values.get('name', None):
                    msg = "cluster name is repeated!"
                    LOG.debug(msg)
                    raise exception.Invalid(msg)
            if values.has_key('nodes'):
                delete_cluster_host(context, cluster_id, session)
                for host_id in eval(values['nodes']):
                    cluster_host_ref = models.ClusterHost()
                    hosts_values['cluster_id'] = project_ref.id
                    hosts_values['host_id'] = host_id
                    _update_values(cluster_host_ref, hosts_values)
                    cluster_host_ref.save(session=session)

            if values.has_key('networks'):
                for interface_id in eval(values['networks']):
                    query = \
                        session.query(models.Network).filter_by(
                            id=interface_id)
                    interfaces_values['cluster_id'] = project_ref.id
                    interfaces_values['updated_at'] = timeutils.utcnow()
                    updated = query.update(interfaces_values,
                                           synchronize_session='fetch')

            # update ----------------------------------------------------------
            # deal with logic_network
            if values.has_key('logic_networks'):
                query = session.query(models.Cluster).filter_by(id=cluster_id)
                if not query:
                    raise exception.NotFound(
                        "Cluster not found,id=%s" % cluster_id)
                    # insert data to logic_network tables

                logic_networks = eval(values['logic_networks'])
                if logic_networks:
                    _cluster_add_logic_network(
                        logic_networks=logic_networks,
                        cluster_id=project_ref.id,
                        session=session,
                        status="update")
                # ---start--delete all logic_networks
                # if values['logic_networks'] == []---
                else:
                    logic_networks_query = session.query(models.LogicNetwork).\
                        filter_by(cluster_id=cluster_id, deleted=0)
                    if logic_networks_query:
                        logic_networks_query.update(
                            {"deleted": True, "deleted_at": timeutils.utcnow()}
                        )
                # ------------------------end----------------------------------------------

            # deal routers
            if values.has_key('routers'):
                routers = eval(values['routers'])
                if routers:
                    _cluster_add_routers(
                        routers=routers,
                        cluster_id=project_ref.id,
                        session=session,
                        status="update"
                    )
                # ----delete all routers if values['routers'] == []---
                else:
                    router_ref = \
                        session.query(models.Router).filter_by(
                            cluster_id=cluster_id, deleted=False)
                    if router_ref:
                        router_ref.update(
                            {"deleted": True, "deleted_at": timeutils.utcnow()}
                        )
                # ------------------------end--------------------------------
            # update ----------------------------------------------------------

            query = session.query(models.Cluster).filter_by(id=cluster_id)

            # Validate fields for projects table.
            # This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in project_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update cluster_id %(cluster_id)s failed') %
                       {'cluster_id': cluster_id})
                raise exception.Conflict(msg)

            project_ref = _cluster_get(context, cluster_id, session=session)
        else:
            for cluster in session.query(models.Cluster).filter_by(
                    deleted=False).all():
                if cluster['name'] == values['name']:
                    msg = "cluster name is repeated!"
                    LOG.debug(msg)
                    raise exception.Forbidden(msg)
            project_ref.update(values)
            _update_values(project_ref, values)
            try:
                project_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("cluster ID %s already exists!"
                                          % values['id'])
            if values.has_key('nodes'):
                for host_id in eval(values['nodes']):
                    cluster_host_ref = models.ClusterHost()
                    hosts_values['cluster_id'] = project_ref.id
                    hosts_values['host_id'] = host_id
                    _update_values(cluster_host_ref, hosts_values)
                    cluster_host_ref.save(session=session)

            if values.has_key('networks'):
                for interface_id in eval(values['networks']):
                    query = session.query(models.Network).filter_by(
                        id=interface_id)
                    interfaces_values['cluster_id'] = project_ref.id
                    interfaces_values['updated_at'] = timeutils.utcnow()
                    updated = query.update(interfaces_values,
                                           synchronize_session='fetch')

            network_query = \
                session.query(models.Network).filter_by(
                    type="template").filter_by(deleted=False).all()
            for sub_network_query in network_query:
                network_ref = models.Network()
                network_ref.cluster_id = project_ref.id
                network_ref.name = sub_network_query.name
                network_ref.description = sub_network_query.description
                network_ref.cidr = sub_network_query.cidr
                network_ref.network_type = sub_network_query.network_type
                network_ref.ml2_type = sub_network_query.ml2_type
                network_ref.capability = sub_network_query.capability
                network_ref.save(session=session)

            # add -------------------------------------------------------------
            # deal logic_network infos
            if values.has_key('logic_networks'):
                # insert data to logic_network tables
                logic_networks = eval(values['logic_networks'])
                if logic_networks:
                    _cluster_add_logic_network(
                        logic_networks=logic_networks,
                        cluster_id=project_ref.id,
                        session=session,
                        status="add")

            # deal routers
            if values.has_key('routers'):
                routers = eval(values['routers'])
                if routers:
                    _cluster_add_routers(
                        routers=routers,
                        cluster_id=project_ref.id,
                        session=session,
                        status="add"
                    )
            # add ------------------------------------------------------------
            target_systems = values['target_systems'].split("+")
            role_query = []
            for target_system in target_systems:
                role_query = role_query + \
                             session.query(models.Role).filter_by(
                                 type="template", cluster_id=None,
                                 deployment_backend=target_system).filter_by(
                                 deleted=False).all()
            for sub_role_query in role_query:
                role_ref = models.Role()
                role_ref.cluster_id = project_ref.id
                role_ref.name = sub_role_query.name
                role_ref.description = sub_role_query.description
                role_ref.status = sub_role_query.status
                role_ref.type = "default"
                role_ref.deployment_backend = sub_role_query.deployment_backend
                role_ref.role_type = sub_role_query.role_type
                configset_ref = models.ConfigSet()
                configset_ref.name = project_ref.name + role_ref.name
                configset_ref.description = project_ref.name + role_ref.name
                configset_ref.save(session=session)
                role_ref.config_set_id = configset_ref.id
                role_ref.save(session=session)
                service_role_query = \
                    session.query(models.ServiceRole).filter_by(
                        role_id=sub_role_query.id).filter_by(
                        deleted=False).all()
                for sub_service_role_query in service_role_query:
                    service_role_ref = models.ServiceRole()
                    service_role_ref.role_id = role_ref.id
                    service_role_ref.service_id = \
                        sub_service_role_query.service_id
                    service_role_ref.save(session=session)

    return _cluster_get(context, project_ref.id)


def _cluster_add_routers(**params):
    session = params['session'] or get_session()
    if 0 == cmp(params['status'], "update"):
        router_ref = \
            session.query(models.Router).filter_by(
                cluster_id=params['cluster_id'])
        if router_ref.all():
            router_ref.update(
                {"deleted": True, "deleted_at": timeutils.utcnow()}
            )

    logic_networks_query_all = []
    logic_networks_query = \
        session.query(models.LogicNetwork).\
        filter_by(cluster_id=params['cluster_id'], deleted=0)
    if logic_networks_query:
        logic_networks_query_all = logic_networks_query.all()

    for router in params['routers']:
        # inser data to router tables
        router_values = {}
        router_ref = models.Router()
        router_values['name'] = router.get('name', None)
        router_values['description'] = router.get('description', None)
        router_values['cluster_id'] = params['cluster_id']
        external_name = router.get('external_logic_network', None)
        if external_name:
            logic_network_query = \
                session.query(models.LogicNetwork).filter_by(
                    name=external_name).filter_by(deleted=False).first()
            if logic_network_query:
                router_values['external_logic_network'] = external_name

        _update_values(router_ref, router_values)
        router_ref.save(session)
        # submit logic_network info to affair

        for internal_subnet_name in router.get('subnets', None):
            for logic_netwrok in logic_networks_query_all:
                subnet_query = \
                    session.query(models.Subnet).filter_by(
                        name=internal_subnet_name,
                        deleted=False,
                        logic_network_id=logic_netwrok.id)
                if subnet_query.first():
                    subnet_query.update(
                        {"router_id": router_ref.id,
                         "updated_at": timeutils.utcnow()}
                    )


def _cluster_add_logic_network(**params):
    session = params['session']or get_session()
    logic_networks_query_all = []
    if "update" == params['status']:
        logic_networks_query = session.query(models.LogicNetwork).\
            filter_by(cluster_id=params['cluster_id'], deleted=0)
        if logic_networks_query:
            logic_networks_query_all = logic_networks_query.all()
            logic_networks_query.update(
                {"deleted": True, "deleted_at": timeutils.utcnow()}
            )

    for logic_network in params['logic_networks']:
        # insert data to subnet table
        logic_network_values = {}
        logic_network_values['name'] = logic_network.get('name', None)
        logic_network_values['type'] = logic_network.get('type', None)
        logic_network_values['segmentation_type'] = \
            logic_network.get('segmentation_type', None)
        logic_network_values['segmentation_id'] = \
            logic_network.get('segmentation_id', None)
        logic_network_values['shared'] = logic_network.get('shared', None)
        if logic_network.get('physnet_name', None):
            query_list = session.query(models.Network).\
                filter_by(cluster_id=params['cluster_id']).filter_by(
                    deleted=False).all()
            if (query_list and [valid_physnet
                for valid_physnet in query_list
                if logic_network['physnet_name'] ==
                valid_physnet.name]) or \
                    logic_network.get('segmentation_type', None) == "flat":
                logic_network_values['physnet_name'] = \
                    logic_network['physnet_name']
        logic_network_values['cluster_id'] = params['cluster_id']

        logic_network_ref = models.LogicNetwork()
        _update_values(logic_network_ref, logic_network_values)
        logic_network_ref.save(session)
        # submit logic_network info to affair

        if logic_network.get('subnets', None):
            _cluster_add_subnet(
                subnets=logic_network['subnets'],
                logic_networks_query_all=logic_networks_query_all,
                logic_network_id=logic_network_ref.id,
                session=session,
                status=params['status'])


def _cluster_add_subnet(**params):
    session = params['session'] or get_session()
    subnets_query_all = []
    if "update" == params['status']:
        for logic_network_query in params['logic_networks_query_all']:
            subnet_query = session.query(models.Subnet).\
                filter_by(logic_network_id=logic_network_query.id, deleted=0)
            if subnet_query:
                subnets_query_all += subnet_query.all()
                subnet_query.update({
                    "deleted": True, "deleted_at": timeutils.utcnow()}
                )

    for subnet in params['subnets']:
        subnet_values = {}
        subnet_values['cidr'] = subnet.get('cidr', None)
        subnet_values['gateway'] = subnet.get('gateway', None)
        subnet_values['name'] = subnet.get('name', None)
        subnet_values['logic_network_id'] = params['logic_network_id']

        subnet_ref = models.Subnet()
        _update_values(subnet_ref, subnet_values)
        subnet_ref.save(session)

        if subnet.get('floating_ranges', None):
            _cluster_add_floating_range(
                values=subnet['floating_ranges'],
                subnets_query_all=subnets_query_all,
                subnet_id=subnet_ref.id,
                session=session,
                status=params['status'])

        if subnet.get('dns_nameservers', None):
            _cluster_add_dns_nameservers(
                values=subnet['dns_nameservers'],
                subnets_query_all=subnets_query_all,
                subnet_id=subnet_ref.id,
                session=session,
                status=params['status'])


def _cluster_add_floating_range(**params):
    session = params['session'] or get_session()
    floating_range_values = dict()
    if params['status'] == "update":
        for subnet_query in params['subnets_query_all']:
            query = session.query(models.FloatIpRange).\
                filter_by(subnet_id=subnet_query.id).filter_by(deleted=False)
            if query.first() is not None:
                floating_range_values['updated_at'] = timeutils.utcnow()
                query.delete(synchronize_session='fetch')

    if params['values']:
        for floating_range in params['values']:
            float_ip_range_ref = models.FloatIpRange()
            if len(floating_range) > 1:
                floating_range_values['start'] = floating_range[0]
                floating_range_values['end'] = floating_range[1]
            floating_range_values['subnet_id'] = params['subnet_id']
            float_ip_range_ref.update(floating_range_values)
            _update_values(float_ip_range_ref, floating_range_values)
            float_ip_range_ref.save(session=session)


def _cluster_add_dns_nameservers(**params):
    session = params['session'] or get_session()
    dns_nameservers_values = dict()
    if params['status'] == "update":
        for subnet_query in params['subnets_query_all']:
            query = session.query(models.DnsNameservers).\
                filter_by(subnet_id=subnet_query.id).filter_by(deleted=False)
            if query.first() is not None:
                dns_nameservers_values['updated_at'] = timeutils.utcnow()
                query.delete(synchronize_session='fetch')

    if params['values']:
        for dns_nameservers in params['values']:
            dns_Nameservers_ref = models.DnsNameservers()
            dns_nameservers_values['dns'] = dns_nameservers
            dns_nameservers_values['subnet_id'] = params['subnet_id']
            session.query(models.DnsNameservers).filter_by(
                subnet_id=params['subnet_id']).filter_by(deleted=False)
            dns_Nameservers_ref.update(dns_nameservers_values)
            _update_values(dns_Nameservers_ref, dns_nameservers_values)
            dns_Nameservers_ref.save(session=session)


def _check_component_id(component_id):
    """
    check if the given component id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between
    MySql and DB2 when the component id
    length is longer than the defined length in database model.
    :param component_id: The id of the component we want to check
    :return: Raise NoFound exception if given component id is invalid
    """
    if (component_id and
       len(component_id) >
       models.Component.id.property.columns[0].type.length):
        raise exception.NotFound()


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _component_update(context, values, component_id):
    """
    Used internally by component_add and component_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param component_id: If None, create the component,
    otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()

    session = get_session()
    with session.begin():
        if component_id:
            component_ref = _component_get(context, component_id,
                                           session=session)
        else:
            component_ref = models.Component()
            # if host_ref.id is None:
            #    host_ref.id = str(uuid.uuid4())
        if component_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Component, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if component_id:
            query = session.query(models.Component).filter_by(
                id=component_id).filter_by(deleted=False)

            # Validate fields for components table.
            # This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in component_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update component_id %(component_id)s failed') %
                       {'component_id': component_id})
                raise exception.Conflict(msg)

            component_ref = _component_get(context, component_id,
                                           session=session)
        else:
            # print "1 host_ref.id:%s" % host_ref.id
            # print host_ref.created_at
            # print values
            # values["id"] = host_ref.id
            component_ref.update(values)
            # Validate the attributes before we go any further. From my
            # investigation, the @validates decorator does not validate
            # on new records, only on existing records, which is, well,
            # idiotic.
            _update_values(component_ref, values)
            # print "2 host_ref.id:%s" % host_ref.id
            # print host_ref.created_at
            # print values
            try:
                component_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("component ID %s already exists!"
                                          % values['id'])

    return component_get(context, component_ref.id)


def component_update(context, component_id, values):
    """
    Set the given properties on an component and update it.

    :raises NotFound if component does not exist.
    """
    return _component_update(context, values, component_id)


def _cluster_get(context, cluster_id, session=None, force_show_deleted=False):
    """Get an project or raise if it does not exist."""
    _check_cluster_id(cluster_id)
    session = session or get_session()

    try:
        query = session.query(models.Cluster).filter_by(
            id=cluster_id).filter_by(
            deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted:
            query = query.filter_by(deleted=False)

        project = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No cluster found with ID %s" % cluster_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return project


def get_logic_network(context, cluster_id, session=None,
                      force_show_deleted=False):
    """Get an logic network or raise if it does not exist."""
    session = session or get_session()
    try:
        query = session.query(models.LogicNetwork).filter_by(
            cluster_id=cluster_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        logic_networks = query.all()

    except sa_orm.exc.NoResultFound:
        msg = "No logic network found with cluster ID %s" % cluster_id
        LOG.debug(msg)
        raise exception.NotFound(msg)
    for logic_network in list(logic_networks):
        # subnet_list = []
        subnet = _get_subnet(context, logic_network['id'], None, session)
        # subnet_list.append(subnet)
        logic_network['subnets'] = subnet

    return logic_networks


def _get_subnet(context, logic_network_id=None, router_id=None,
                session=None, force_show_deleted=False):
    """Get an subnet or raise if it does not exist."""
    session = session or get_session()
    try:
        if logic_network_id and router_id is None:
            query = \
                session.query(models.Subnet).filter_by(
                    logic_network_id=logic_network_id).filter_by(
                    deleted=False)
        elif logic_network_id is None and router_id is not None:
            query = session.query(models.Subnet).filter_by(router_id=router_id)
            query = query.filter_by(deleted=False)
            return query.all()
        else:
            query = session.query(models.Subnet)

        if not force_show_deleted:
            query = query.filter_by(deleted=False)

        subnets = query.all()

    except sa_orm.exc.NoResultFound:
        msg = ("No Float Ip Range found with "
               "logic_network_id %s and router_id  %s"
               % (logic_network_id, router_id))
        LOG.debug(msg)
        raise exception.NotFound(msg)

    ip_into_int = lambda ip: reduce(lambda x, y: (x << 8) + y, map(int, ip.split('.')))
    int_to_ip = lambda x: '.'.join([str(x / (256 **i) % 256) for i in range(3, -1, -1)])
    for subnet in subnets:
        dns_nameservers = _dns_nameservers_get(context, subnet['id'], session)
        subnet['dns_nameservers'] = \
            [dns_server['dns'] for dns_server in
                dns_nameservers] if dns_nameservers else []
        subnet['dns_nameservers'].sort()

        float_ip_range = _float_ip_range_get(context, subnet['id'], session)
        if float_ip_range and len(float_ip_range) > 1:
            int_ip_range = \
                [[ip_into_int(float_ip[0]), ip_into_int(float_ip[1])] for
                    float_ip in float_ip_range]
            int_ip_range = sorted(int_ip_range, key=lambda x: x[0])
            float_ip_range = \
                [[int_to_ip(int_ip[0]), int_to_ip(int_ip[1])] for
                    int_ip in int_ip_range]
        subnet['floating_ranges'] = float_ip_range if float_ip_range else []

    return subnets


def _float_ip_range_get(context, subnet_id, session=None,
                        force_show_deleted=False):
    """Get an project or raise if it does not exist."""
    session = session or get_session()

    try:
        query = \
            session.query(models.FloatIpRange).filter_by(
                subnet_id=subnet_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        floatIpRange = query.all()

        float_ip_ranges_list = []
        for float_ip_range in list(floatIpRange):
            float_ip_range_list = []
            float_ip_range_list.append(float_ip_range.start)
            float_ip_range_list.append(float_ip_range.end)
            float_ip_ranges_list.append(float_ip_range_list)

    except sa_orm.exc.NoResultFound:
        msg = "float ip range no found with subnet ID %s" % subnet_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return float_ip_ranges_list


def _dns_nameservers_get(context, subnet_id, session=None,
                         force_show_deleted=False):
    """Get an nameservers or raise if it does not exist."""
    session = session or get_session()

    try:
        query = session.query(models.DnsNameservers).filter_by(
            subnet_id=subnet_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        dns_nameservers = query.all()

    except sa_orm.exc.NoResultFound:
        msg = "No dns nameservers found with subnet ID %s" % subnet_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return dns_nameservers


def router_get(context, cluster_id, session=None,
               force_show_deleted=False):
    """Get an routers or raise if it does not exist."""
    session = session or get_session()
    try:
        query = session.query(models.Router).filter_by(
            cluster_id=cluster_id).filter_by(deleted=False)
        if not force_show_deleted:
            query = query.filter_by(deleted=False)

        routers = query.all()
        routers_list = []
        for router in routers:
            subnets = []
            router_id = router['id']
            subnets = _get_subnet(context, None, router_id, session)
            router['subnets'] = [subnet.name for subnet in subnets]
            routers_list.append(router)

    except sa_orm.exc.NoResultFound:
        msg = "No routers found with cluster ID %s" % cluster_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return routers_list


def cluster_get(context, cluster_id, session=None,
                force_show_deleted=False):
    Cluster = _cluster_get(context, cluster_id, session=session,
                           force_show_deleted=force_show_deleted)
    return Cluster


def cluster_add(context, values):
    """Add an cluster from the values dictionary."""
    return _cluster_update(context, values, None)


def cluster_update(context, cluster_id, values):
    """
    Set the given properties on an cluster and update it.

    :raises NotFound if cluster does not exist.
    """
    return _cluster_update(context, values, cluster_id)


def get_cluster_host(context, cluster_id, session=None,
                     force_show_deleted=False):
    _check_cluster_id(cluster_id)
    session = session or get_session()
    try:
        query = session.query(models.ClusterHost).filter_by(
            cluster_id=cluster_id, deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        cluster_hosts = query.all()
        cluster_hosts_id = [item.host_id for item in cluster_hosts]

    except sa_orm.exc.NoResultFound:
        msg = "No cluster found with ID %s" % cluster_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return cluster_hosts_id


def _component_get(context, component_id, session=None,
                   force_show_deleted=False):
    """Get an component or raise if it does not exist."""
    _check_component_id(component_id)
    session = session or get_session()

    try:
        query = session.query(models.Component).filter_by(
            id=component_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        component = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No component found with ID %s" % component_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return component


def component_get(context, component_id, session=None,
                  force_show_deleted=False):
    component = _component_get(context, component_id, session=session,
                               force_show_deleted=force_show_deleted)
    return component


def component_add(context, values):
    """Add an component from the values dictionary."""
    return _component_update(context, values, None)


def _component_services_get(context, component_id, session=None):
    """Get an service or raise if it does not exist."""
    _check_component_id(component_id)
    session = session or get_session()
    try:
        query = session.query(models.Service).filter_by(
            component_id=component_id).filter_by(deleted=False)
        services = query.all()
    except sa_orm.exc.NoResultFound:
        msg = "No component found with ID %s" % component_id
        LOG.debug(msg)
        raise exception.NotFound(msg)
    return services


def _services_used_in_cluster(context, services_id, session=None):
    session = session or get_session()
    services_used = set()
    for service_id in services_id:
        _check_service_id(service_id)
        try:
            query = session.query(models.ServiceRole).filter_by(
                service_id=service_id).filter_by(deleted=False)
            service_roles = query.all()
            for service_role in service_roles:
                role_ref = _role_get(context, service_role.role_id,
                                     session=session)
                if role_ref.type != 'template':
                    services_used.add(service_id)
        except sa_orm.exc.NoResultFound:
            msg = "No service role found with ID %s" % service_id
            LOG.debug(msg)
            raise exception.NotFound(msg)
    return services_used


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def component_destroy(context, component_id):
    """Destroy the component or raise if it does not exist."""
    session = get_session()

    services = _component_services_get(context, component_id, session)
    services_id = [service.id for service in services]

    services_used = _services_used_in_cluster(context, services_id, session)
    if services_used:
        msg = "Services '%s' of component '%s' is using in cluster" % (
              ','.join(services_used), component_id)
        raise exception.DeleteConstrainted(msg)

    for service_id in services_id:
        _service_destroy(context, service_id)

    with session.begin():
        component_ref = _component_get(context, component_id, session=session)
        component_ref.delete(session=session)

    return component_ref


def _check_service_id(service_id):
    """
    check if the given service id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the service id
    length is longer than the defined length in database model.
    :param service_id: The id of the service we want to check
    :return: Raise NoFound exception if given service id is invalid
    """
    if (service_id and
       len(service_id) > models.Service.id.property.columns[0].type.length):
        raise exception.NotFound()


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _service_update(context, values, service_id):
    """
    Used internally by service_add and service_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param service_id: If None, create the service,
    otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()

    session = get_session()
    with session.begin():
        if service_id:
            service_ref = _service_get(context, service_id, session=session)
        else:
            service_ref = models.Service()
            # if host_ref.id is None:
            #    host_ref.id = str(uuid.uuid4())
        if service_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Service, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if service_id:
            query = session.query(models.Service).filter_by(
                id=service_id).filter_by(deleted=False)

            # Validate fields for services table.
            # This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in service_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update service_id %(service_id)s failed') %
                       {'service_id': service_id})
                raise exception.Conflict(msg)

            service_ref = _service_get(context, service_id, session=session)
        else:
            # print "1 host_ref.id:%s" % host_ref.id
            # print host_ref.created_at
            # print values
            # values["id"] = host_ref.id
            service_ref.update(values)
            # Validate the attributes before we go any further. From my
            # investigation, the @validates decorator does not validate
            # on new records, only on existing records, which is, well,
            # idiotic.
            _update_values(service_ref, values)
            # print "2 host_ref.id:%s" % host_ref.id
            # print host_ref.created_at
            # print values
            try:
                service_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("service ID %s already exists!"
                                          % values['id'])

    return service_get(context, service_ref.id)


def service_update(context, service_id, values):
    """
    Set the given properties on an service and update it.

    :raises NotFound if service does not exist.
    """
    return _service_update(context, values, service_id)


def _service_get(context, service_id, session=None, force_show_deleted=False):
    """Get an service or raise if it does not exist."""
    _check_service_id(service_id)
    session = session or get_session()

    try:
        query = session.query(models.Service).filter_by(id=service_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        service = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No service found with ID %s" % service_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return service


def service_get(context, service_id, session=None, force_show_deleted=False):
    service = _service_get(context, service_id, session=session,
                           force_show_deleted=force_show_deleted)
    return service


def service_add(context, values):
    """Add an service from the values dictionary."""
    return _service_update(context, values, None)


def _delete_service_role(context, service_id, session=None):
    _check_service_id(service_id)
    session = session or get_session()
    try:
        query = session.query(models.ServiceRole).filter_by(
            service_id=service_id).filter_by(deleted=False)
        service_roles = query.all()
        for service_role in service_roles:
            service_role.delete(session=session)
    except sa_orm.exc.NoResultFound:
        msg = "No service role found with ID %s" % service_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def _service_destroy(context, service_id):
    """Destroy the service or raise if it does not exist."""
    session = get_session()
    _delete_service_role(context, service_id, session)
    with session.begin():
        service_ref = _service_get(context, service_id, session=session)
        service_ref.delete(session=session)
    return service_ref


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def service_destroy(context, service_id):
    """Destroy the service or raise if it does not exist."""
    session = get_session()

    services_used = _services_used_in_cluster(context, [service_id], session)
    if services_used:
        msg = "The service %s usd in cluster" % ','.join(services_used)
        raise exception.DeleteConstrainted(msg)

    return _service_destroy(context, service_id)


def service_get_all(context, filters=None, marker=None, limit=None,
                    sort_key=None, sort_dir=None):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_service = None
    if marker is not None:
        marker_service =\
            _service_get(context,
                         marker,
                         force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    query = session.query(models.Service).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.Service, limit,
                            sort_key,
                            marker=marker_service,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    services = []
    for service in query.all():
        service_dict = service.to_dict()
        services.append(service_dict)
    return services


def _role_host_member_get(context, session, member_id=None, host_id=None):
    """
    Fetch an HostRole entity by id.
    """
    query = session.query(models.HostRole)

    if host_id is not None and member_id is not None:
        query = query.filter(models.HostRole.role_id == member_id).filter(
            models.HostRole.host_id == host_id).filter(
            models.HostRole.deleted == 0)
    elif member_id is not None and host_id is None:
        query = query.filter(models.HostRole.role_id == member_id).filter(
            models.HostRole.deleted == 0)
    elif host_id is not None and member_id is None:
        query = query.filter(models.HostRole.host_id == host_id).filter(
            models.HostRole.deleted == 0)
    return query.all()


def role_host_member_get(context, member_id=None, host_id=None):
    session = get_session()
    nodes_ref = _role_host_member_get(context, session, member_id, host_id)
    return nodes_ref


def _set_host_status(context, host_id, status):
    session = get_session()
    host_ref = _host_get(context, host_id, session=session)
    host_ref.status = status
    host_ref.save(session=session)


def role_host_member_delete(context, member_id=None, host_id=None):
    """Delete an HostRole object."""
    session = get_session()
    nodes_ref = _role_host_member_get(context, session, member_id, host_id)
    hosts_id = set()
    for node_ref in nodes_ref:
        hosts_id.add(node_ref.host_id)
        node_ref.delete(session=session)
    for host_id in hosts_id:
        nodes_ref = _role_host_member_get(context, session, host_id=host_id)
        if not nodes_ref:
            _set_host_status(context, host_id, "in-cluster")


def _role_service_member_get(context, session, member_id):
    """Fetch an ServiceRole entity by id."""
    query = session.query(models.ServiceRole)
    query = query.filter(models.ServiceRole.role_id == member_id).filter(
        models.ServiceRole.deleted == 0)

    return query.all()


def role_service_member_delete(context, member_id):
    """Delete an ServiceRole object."""
    session = get_session()
    services_ref = _role_service_member_get(context, session, member_id)
    for service_ref in services_ref:
        if service_ref.role_id == member_id:
            service_ref.delete(session=session)


def _check_role_id(role_id):

    """
    check if the given role id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the role id
    length is longer than the defined length in database model.
    :param role_id: The id of the role we want to check
    :return: Raise NoFound exception if given role id is invalid
    """
    if (role_id and
       len(role_id) > models.Role.id.property.columns[0].type.length):
        raise exception.NotFound()


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _role_update(context, values, role_id):
    """
    Used internally by role_add and role_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param role_id: If None, create the role, otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()

    hosts_values = dict()
    services_values = dict()
    host_cluster_values = dict()
    session = get_session()
    with session.begin():
        if role_id:
            role_ref = _role_get(context, role_id, session=session)
        else:
            role_ref = models.Role()

            # if host_ref.id is None:
            #    host_ref.id = str(uuid.uuid4())
        if role_id:
            # Don't drop created_at if we're passing it in...
            if values.has_key('nodes'):
                orig_hosts = list(eval(values['nodes']))
                nodes_ref = _role_host_member_get(context, session, role_id)
                if nodes_ref:
                    for host_id in orig_hosts:
                        _set_host_status(context, host_id, "with-role")
                        host_flag = 0
                        for node_ref in nodes_ref:
                            if node_ref.host_id == host_id:
                                host_flag = 1
                                break

                        if host_flag == 0:
                            # host without this role, add role to this host,
                            # should add host to cluster at the same time
                            role_host_ref = models.HostRole()
                            hosts_values['role_id'] = role_id
                            hosts_values['host_id'] = host_id
                            _update_values(role_host_ref, hosts_values)
                            role_host_ref.save(session=session)
                            cluster_id = None
                            if values.has_key('cluster_id'):
                                cluster_id = values['cluster_id']
                            else:
                                role_def_tmp = \
                                    session.query(models.Role).filter_by(
                                        id=role_id, deleted=False).one()
                                if role_def_tmp:
                                    cluster_id = role_def_tmp.cluster_id
                            if cluster_id:
                                cluster_hosts_id = \
                                    get_cluster_host(context, cluster_id,
                                                     session=None,
                                                     force_show_deleted=False)
                                # check this host existed in the cluster or not
                                if host_id not in cluster_hosts_id:
                                    cluster_host_ref = models.ClusterHost()
                                    host_cluster_values['updated_at'] = \
                                        timeutils.utcnow()
                                    host_cluster_values['host_id'] = host_id
                                    host_cluster_values['cluster_id'] = \
                                        cluster_id
                                    cluster_host_ref.update(
                                        host_cluster_values)
                                    _update_values(
                                        cluster_host_ref, host_cluster_values)
                                    cluster_host_ref.save(session=session)
                else:   # new host
                    for host_id in orig_hosts:
                        _set_host_status(context, host_id, "with-role")
                        role_host_ref = models.HostRole()
                        hosts_values['role_id'] = role_id
                        hosts_values['host_id'] = host_id
                        _update_values(role_host_ref, hosts_values)
                        role_host_ref.save(session=session)
                        cluster_id = None
                        if values.has_key('cluster_id'):
                            cluster_id = values['cluster_id']
                        else:
                            role_def_tmp = \
                                session.query(models.Role).filter_by(
                                    id=role_id, deleted=False).one()
                            if role_def_tmp:
                                cluster_id = role_def_tmp.cluster_id
                        if cluster_id:
                            cluster_hosts_id = \
                                get_cluster_host(context, cluster_id,
                                                 session=None,
                                                 force_show_deleted=False)
                            if host_id not in cluster_hosts_id:
                                cluster_host_ref = models.ClusterHost()
                                host_cluster_values['updated_at'] =\
                                    timeutils.utcnow()
                                host_cluster_values['host_id'] = host_id
                                host_cluster_values['cluster_id'] = cluster_id
                                cluster_host_ref.update(host_cluster_values)
                                _update_values(cluster_host_ref,
                                               host_cluster_values)
                                cluster_host_ref.save(session=session)

            if values.has_key('services'):
                orig_services = list(eval(values['services']))
                services_ref = \
                    _role_service_member_get(context, session, role_id)

                if services_ref:
                    for service_id in orig_services:
                        service_flag = 0
                        for service_ref in services_ref:
                            if service_ref.service_id == service_id:
                                service_flag = 1
                                break

                        if service_flag == 0:
                            role_service_ref = models.ServiceRole()
                            services_values['role_id'] = role_id
                            services_values['service_id'] = service_id
                            _update_values(role_service_ref, services_values)
                            role_service_ref.save(session=session)
                else:
                    for service_id in orig_services:
                        role_service_ref = models.ServiceRole()
                        services_values['role_id'] = role_id
                        services_values['service_id'] = service_id
                        _update_values(role_service_ref, services_values)
                        role_service_ref.save(session=session)

            _drop_protected_attrs(models.Role, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if role_id:
            query = \
                session.query(models.Role).filter_by(
                    id=role_id).filter_by(deleted=False)

            # Validate fields for roles table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in role_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update role_id %(role_id)s failed') %
                       {'role_id': role_id})
                raise exception.Conflict(msg)

            role_ref = _role_get(context, role_id, session=session)
        else:
            # print "1 host_ref.id:%s" % host_ref.id
            # print host_ref.created_at
            # print values
            # values["id"] = host_ref.id
            role_ref.update(values)
            # Validate the attributes before we go any further. From my
            # investigation, the @validates decorator does not validate
            # on new records, only on existing records, which is, well,
            # idiotic.
            _update_values(role_ref, values)
            # print "2 host_ref.id:%s" % host_ref.id
            # print host_ref.created_at
            # print values
            try:
                role_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("role ID %s already exists!"
                                          % values['id'])

            if values.has_key('nodes'):
                orig_hosts = list(eval(values['nodes']))
                cluster_id = None
                if values.has_key('cluster_id') and values['cluster_id']:
                    cluster_id = values['cluster_id']

                    for host_id in orig_hosts:
                        _set_host_status(context, host_id, "with-role")
                        role_host_ref = models.HostRole()
                        hosts_values['role_id'] = role_ref.id
                        hosts_values['host_id'] = host_id
                        _update_values(role_host_ref, hosts_values)
                        role_host_ref.save(session=session)

                        cluster_hosts_id = \
                            get_cluster_host(context, cluster_id,
                                             session=None,
                                             force_show_deleted=False)
                        if host_id not in cluster_hosts_id:
                            # add new record in cluster_host
                            cluster_host_ref = models.ClusterHost()
                            host_cluster_values['updated_at'] = \
                                timeutils.utcnow()
                            host_cluster_values['host_id'] = host_id
                            host_cluster_values['cluster_id'] = cluster_id
                            cluster_host_ref.update(host_cluster_values)
                            _update_values(cluster_host_ref,
                                           host_cluster_values)
                            cluster_host_ref.save(session=session)

            if values.has_key('services'):
                orig_services = list(eval(values['services']))
                for service_id in orig_services:
                    role_service_ref = models.ServiceRole()
                    services_values['role_id'] = role_ref.id
                    services_values['service_id'] = service_id
                    _update_values(role_service_ref, services_values)
                    role_service_ref.save(session=session)

    return role_get(context, role_ref.id)


def role_update(context, role_id, values):
    """
    Set the given properties on an role and update it.

    :raises NotFound if role does not exist.
    """
    return _role_update(context, values, role_id)


def _role_get(context, role_id, session=None, force_show_deleted=False):
    """Get an role or raise if it does not exist."""
    _check_role_id(role_id)
    session = session or get_session()

    try:
        query = \
            session.query(models.Role).filter_by(
                id=role_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        role = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No role found with ID %s" % role_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return role


def role_get(context, role_id, session=None, force_show_deleted=False):
    role = _role_get(context, role_id, session=session,
                     force_show_deleted=force_show_deleted)
    return role


def role_add(context, values):
    """Add an role from the values dictionary."""
    return _role_update(context, values, None)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def role_destroy(context, role_id):
    """Destroy the role or raise if it does not exist."""
    session = get_session()
    with session.begin():
        delete_service_disks_by_role(role_id, session)
        delete_cinder_volumes_by_role(role_id, session)

        role_ref = _role_get(context, role_id, session=session)
        role_ref.delete(session=session)
        role_host_member_delete(context, role_id)
        role_service_member_delete(context, role_id)

    return role_ref

def role_get_all(context, filters=None, marker=None, limit=None,
                sort_key=None, sort_dir=None):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_role = None
    if marker is not None:
        marker_role = _role_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    if 'cluster_id' in filters:
        query=session.query(models.Role).filter_by(cluster_id=filters.pop('cluster_id')).filter_by(deleted=False)
    else:
        query = session.query(models.Role).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.Role, limit,
                            sort_key,
                            marker=marker_role,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    roles = []
    for role in query.all():
        role_dict = role.to_dict()
        # If uninstalling backend, we reset the role_progress value to (100 - role_progress)
        # for showing data on client. Because role_progress will reduce from 100 to 0 and
        #  role_status will be set to 'init', when uninstalling is finished.
        #  So that installing could be started at next time.
        status = role_dict.get('status', None)
        progress = role_dict.get('progress', None)
        if status in ["uninstalling", "uninstall-failed"] and type(progress) is types.LongType:
            role_dict['progress'] = 100 - progress
            role_dict["status"] = status
        roles.append(role_dict)
    return roles

def role_services_get(context, role_id, session=None, force_show_deleted=False):
    """Get an role or raise if it does not exist."""
    _check_role_id(role_id)
    session = session or get_session()

    try:
        query = session.query(models.ServiceRole).filter_by(role_id=role_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

    except sa_orm.exc.NoResultFound:
        msg = "No role found with ID %s" % role_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    roles = []
    for role in query.all():
        role_dict = role.to_dict()
        roles.append(role_dict)
    return roles

def get_host_roles(context, role_id, session=None, force_show_deleted=False):
    """Get an role or raise if it does not exist."""
    _check_role_id(role_id)
    session = session or get_session()

    try:
        query = session.query(models.HostRole).filter_by(role_id=role_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

    except sa_orm.exc.NoResultFound:
        msg = "No role found with ID %s" % role_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    roles = []
    for role in query.all():
        role_dict = role.to_dict()
        roles.append(role_dict)
    return roles

def role_host_destroy(context, role_id):
    """Destroy the role or raise if it does not exist."""
    session = get_session()
    with session.begin():
        role_ref = _role_get(context, role_id, session=session)
        role_host_member_delete(context,role_id)
    return role_ref

def delete_service_disks_by_role(role_id, session=None):
    if session is None:
        session = get_session()
    service_disks_query = session.query(models.ServiceDisk).filter_by(
        role_id=role_id).filter_by(deleted=False)
    delete_time = timeutils.utcnow()
    service_disks_query.update({"deleted": True, "deleted_at": delete_time})


def delete_cinder_volumes_by_role(role_id, session=None):
    if session is None:
        session = get_session()
    cinder_volumes_query = session.query(models.CinderVolume).filter_by(
        role_id=role_id).filter_by(deleted=False)
    delete_time = timeutils.utcnow()
    cinder_volumes_query.update({"deleted": True, "deleted_at": delete_time})


def delete_optical_switchs_by_role(role_id, session=None):
    if session is None:
        session = get_session()
    optical_switchs_query = session.query(models.OpticalSwitch).filter_by(
        role_id=role_id).filter_by(deleted=False)
    delete_time = timeutils.utcnow()
    optical_switchs_query.update({"deleted": True,
                                  "deleted_at": delete_time})


def role_host_update(context, role_host_id, values):
    """Update the host_roles or raise if it does not exist."""
    _check_role_host_id(role_host_id)
    session = get_session()
    with session.begin():
        query = session.query(models.HostRole).filter_by(id=role_host_id)
        updated = query.update(values, synchronize_session='fetch')
        if not updated:
            msg = (_('update role_host_id %(role_host_id)s failed') %
                   {'role_host_id': role_host_id})
            raise exception.Conflict(msg)
        return

def _check_role_host_id(role_host_id):
    """
    check if the given role id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the role id
    length is longer than the defined length in database model.
    :param role_host_id: The id of the role we want to check
    :return: Raise NoFound exception if given role id is invalid
    """
    if (role_host_id and
       len(role_host_id) > models.HostRole.id.property.columns[0].type.length):
        raise exception.NotFound()

def cluster_update(context, cluster_id, values):
    """
    Set the given properties on an cluster and update it.

    :raises NotFound if cluster does not exist.
    """
    return _cluster_update(context, values, cluster_id)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def cluster_destroy(context, cluster_id):
    """Destroy the project or raise if it does not exist."""
    session = get_session()
    with session.begin():
        project_ref = _cluster_get(context, cluster_id, session=session)
        project_ref.delete(session=session)

        logicnetwork_query = session.query(models.LogicNetwork).filter_by(
        cluster_id=cluster_id).filter_by(deleted=False)
        delete_time = timeutils.utcnow()
        for logicnetwork_info in logicnetwork_query.all():
            query_subnet=session.query(models.Subnet).filter_by(logic_network_id=logicnetwork_info.id).filter_by(deleted=False)
            for subnet_info in query_subnet.all():
                query_float_ip_range=session.query(models.FloatIpRange).filter_by(
                subnet_id=subnet_info.id).filter_by(deleted=False)
                query_float_ip_range.update({"deleted": True, "deleted_at": delete_time})

                query_dns_nameservers=session.query(models.DnsNameservers).filter_by(
                subnet_id=subnet_info.id).filter_by(deleted=False)
                query_dns_nameservers.update({"deleted": True, "deleted_at": delete_time})
            query_subnet.update({"deleted": True, "deleted_at": delete_time})
        logicnetwork_query.update({"deleted": True, "deleted_at": delete_time})

        router_query = session.query(models.Router).filter_by(
        cluster_id=cluster_id).filter_by(deleted=False)
        router_query.update({"deleted": True, "deleted_at": delete_time})

        role_query = session.query(models.Role).filter_by(
        cluster_id=cluster_id).filter_by(deleted=False)
        for role_info in role_query.all():
            query_config_set_id=session.query(models.ConfigSet).filter_by(id=role_info.config_set_id).filter_by(deleted=False)
            for config_set_id_info in query_config_set_id.all():
                config_set_item=session.query(models.ConfigSetItem).filter_by(
                config_set_id=config_set_id_info.id).filter_by(deleted=False)
                config_set_item.update({"deleted": True, "deleted_at": delete_time})
            query_config_set_id.update({"deleted": True, "deleted_at": delete_time})

            query_host_role=session.query(models.HostRole).filter_by(role_id=role_info.id).filter_by(deleted=False)
            query_host_role.update({"deleted": True, "deleted_at": delete_time})

            query_service_role=session.query(models.ServiceRole).filter_by(role_id=role_info.id).filter_by(deleted=False)
            query_service_role.update({"deleted": True, "deleted_at": delete_time})
            delete_service_disks_by_role(role_info.id, session)
            delete_cinder_volumes_by_role(role_info.id, session)
            delete_optical_switchs_by_role(role_info.id, session)
        role_query.update({"deleted": True, "deleted_at": delete_time})

        network_query = session.query(models.Network).filter_by(
        cluster_id=cluster_id).filter_by(deleted=False)
        for network_info in network_query.all():
            query_assigned_network=session.query(models.AssignedNetworks).filter_by(
            network_id=network_info.id).filter_by(deleted=False)
            query_assigned_network.update({"deleted": True, "deleted_at": delete_time})

            query_ip_range=session.query(models.IpRange).filter_by(
            network_id=network_info.id).filter_by(deleted=False)
            query_ip_range.update({"deleted": True, "deleted_at": delete_time})
        network_query.update({"deleted": True, "deleted_at": delete_time})

        cluster_host_query = session.query(models.ClusterHost).filter_by(cluster_id=cluster_id).filter_by(deleted=False)
        cluster_hosts = cluster_host_query.all()
        for cluster_host in cluster_hosts:  #delete host role which all the roles belong to this cluster
            delete_host_role(context, cluster_host.host_id, session=session)
            host_ref = _host_get(context, cluster_host.host_id, session=session)
            host_ref.update({'status': 'init'})
        delete_cluster_host(context, cluster_id, session=session)

    return project_ref


def _paginate_query(query, model, limit, sort_keys, marker=None,
                    sort_dir=None, sort_dirs=None):
    """Returns a query with sorting / pagination criteria added.

    Pagination works by requiring a unique sort_key, specified by sort_keys.
    (If sort_keys is not unique, then we risk looping through values.)
    We use the last row in the previous page as the 'marker' for pagination.
    So we must return values that follow the passed marker in the order.
    With a single-valued sort_key, this would be easy: sort_key > X.
    With a compound-values sort_key, (k1, k2, k3) we must do this to repeat
    the lexicographical ordering:
    (k1 > X1) or (k1 == X1 && k2 > X2) or (k1 == X1 && k2 == X2 && k3 > X3)

    We also have to cope with different sort_directions.

    Typically, the id of the last row is used as the client-facing pagination
    marker, then the actual marker object must be fetched from the db and
    passed in to us as marker.

    :param query: the query object to which we should add paging/sorting
    :param model: the ORM model class
    :param limit: maximum number of items to return
    :param sort_keys: array of attributes by which results should be sorted
    :param marker: the last item of the previous page; we returns the next
                    results after this value.
    :param sort_dir: direction in which results should be sorted (asc, desc)
    :param sort_dirs: per-column array of sort_dirs, corresponding to sort_keys

    :rtype: sqlalchemy.orm.query.Query
    :return: The query with sorting/pagination added.
    """

    if 'id' not in sort_keys:
        # TODO(justinsb): If this ever gives a false-positive, check
        # the actual primary key, rather than assuming its id
        LOG.warning(_LW('Id not in sort_keys; is sort_keys unique?'))

    assert(not (sort_dir and sort_dirs))

    # Default the sort direction to ascending
    if sort_dirs is None and sort_dir is None:
        sort_dir = 'asc'

    # Ensure a per-column sort direction
    if sort_dirs is None:
        sort_dirs = [sort_dir for _sort_key in sort_keys]

    assert(len(sort_dirs) == len(sort_keys))

    # Add sorting
    for current_sort_key, current_sort_dir in zip(sort_keys, sort_dirs):
        sort_dir_func = {
            'asc': sqlalchemy.asc,
            'desc': sqlalchemy.desc,
        }[current_sort_dir]

        try:
            sort_key_attr = getattr(model, current_sort_key)
        except AttributeError:
            raise exception.InvalidSortKey()
        query = query.order_by(sort_dir_func(sort_key_attr))

    default = ''  # Default to an empty string if NULL

    # Add pagination
    if marker is not None:
        marker_values = []
        for sort_key in sort_keys:
            v = getattr(marker, sort_key)
            if v is None:
                v = default
            marker_values.append(v)

        # Build up an array of sort criteria as in the docstring
        criteria_list = []
        for i in range(len(sort_keys)):
            crit_attrs = []
            for j in range(i):
                model_attr = getattr(model, sort_keys[j])
                default = None if isinstance(
                    model_attr.property.columns[0].type,
                    sqlalchemy.DateTime) else ''
                attr = sa_sql.expression.case([(model_attr != None,
                                              model_attr), ],
                                              else_=default)
                crit_attrs.append((attr == marker_values[j]))

            model_attr = getattr(model, sort_keys[i])
            default = None if isinstance(model_attr.property.columns[0].type,
                                         sqlalchemy.DateTime) else ''
            attr = sa_sql.expression.case([(model_attr != None,
                                          model_attr), ],
                                          else_=default)
            if sort_dirs[i] == 'desc':
                crit_attrs.append((attr < marker_values[i]))
            elif sort_dirs[i] == 'asc':
                crit_attrs.append((attr > marker_values[i]))
            else:
                raise ValueError(_("Unknown sort direction, "
                                   "must be 'desc' or 'asc'"))

            criteria = sa_sql.and_(*crit_attrs)
            criteria_list.append(criteria)

        f = sa_sql.or_(*criteria_list)
        query = query.filter(f)

    if limit is not None:
        query = query.limit(limit)

    return query


def host_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)

    marker_host = None
    if marker is not None:
        marker_host = _host_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)
    session = get_session()
    if 'status' in filters and 'cluster_id' not in filters:
        status = filters.pop('status')
        query = session.query(models.Host).filter_by(deleted=showing_deleted).filter_by(status=status)
    elif 'cluster_id' in filters and 'status' not in filters:
        cluster_id = filters.pop('cluster_id')
        hosts = []
        query = session.query(models.Host)
        query = query.filter(models.Host.status=="in-cluster")
        query = query.filter(models.Host.deleted==0)
        query = query.filter(models.ClusterHost.cluster_id==cluster_id)
        query = query.filter(models.ClusterHost.host_id==models.Host.id)
        query = query.filter(models.ClusterHost.deleted==0)        
        for host in query.all():
            host_dict = host.to_dict()
            hosts.append(host_dict)

        query = session.query(models.Host, 
            models.ClusterHost.cluster_id.label("cluster_id"), 
            models.HostRole.progress.label("role_progress"),
            models.HostRole.status.label("role_status"),
            models.HostRole.messages.label("role_messages"))
        query = query.filter(models.Host.deleted==0)
        query = query.filter(models.ClusterHost.cluster_id==cluster_id)
        query = query.filter(models.ClusterHost.host_id==models.Host.id)
        query = query.filter(models.ClusterHost.deleted==0)
        query = query.filter(models.HostRole.host_id==models.Host.id)
        query = query.filter(models.HostRole.role_id==models.Role.id)
        query = query.filter(models.HostRole.deleted==0)
        query = query.filter(models.Role.cluster_id==cluster_id)
        query = query.filter(models.Role.deleted==0)
        query = query.group_by(models.Host.id)
        for host, cluster_id, role_progress, role_status, role_messages in query.all():
            host_dict = host.to_dict()
            host_dict["cluster_id"] = cluster_id
            host_dict["role_progress"] = role_progress
            host_dict["role_status"] = role_status
            host_dict["role_messages"] = role_messages
            hosts.append(host_dict)
        return hosts
    elif 'cluster_id' in filters and 'status' in filters:
        status = filters.pop('status')
        cluster_id = filters.pop('cluster_id')
        if status == 'in-cluster':
            hosts = []
            query = session.query(models.Host)
            query = query.filter(models.Host.status=="in-cluster")
            query = query.filter(models.Host.deleted==0)
            query = query.filter(models.ClusterHost.cluster_id==cluster_id)
            query = query.filter(models.ClusterHost.host_id==models.Host.id)
            query = query.filter(models.ClusterHost.deleted==0)
            for host in query.all():
                host_dict = host.to_dict()
                hosts.append(host_dict)
            return hosts
        if status == 'with-role':
            hosts = []
            query = session.query(models.Host,
                models.ClusterHost.cluster_id.label("cluster_id"),
                models.HostRole.progress.label("role_progress"),
                models.HostRole.status.label("role_status"),
                models.HostRole.messages.label("role_messages"))
            query = query.filter(models.Host.deleted==0)
            query = query.filter(models.ClusterHost.cluster_id==cluster_id)
            query = query.filter(models.ClusterHost.host_id==models.Host.id)
            query = query.filter(models.ClusterHost.deleted==0)
            query = query.filter(models.HostRole.host_id==models.Host.id)
            query = query.filter(models.HostRole.role_id==models.Role.id)
            query = query.filter(models.HostRole.deleted==0)
            query = query.filter(models.Role.cluster_id==cluster_id)
            query = query.filter(models.Role.deleted==0)
            query = query.group_by(models.Host.id)
            for host, cluster_id, role_progress, role_status, role_messages in query.all():
                host_dict = host.to_dict()
                host_dict["cluster_id"] = cluster_id
                host_dict["role_progress"] = role_progress
                host_dict["role_status"] = role_status
                host_dict["role_messages"] = role_messages
                hosts.append(host_dict)
            return hosts
    elif 'name' in filters:
        name = filters.pop('name')
        query = session.query(models.Host).filter_by(deleted=showing_deleted).filter_by(name=name)
    else:
        query = session.query(models.Host).filter_by(deleted=showing_deleted)

        query = _paginate_query(query, models.Host, limit,
                            sort_key,
                            marker=marker_host,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    hosts = []
    for host in query.all():
        host_dict = host.to_dict()
        hosts.append(host_dict)
    return hosts

def _drop_protected_attrs(model_class, values):
    """
    Removed protected attributes from values dictionary using the models
    __protected_attributes__ field.
    """
    for attr in model_class.__protected_attributes__:
        if attr in values:
            del values[attr]


def _update_values(ref, values):
    for k in values:
        if getattr(ref, k) != values[k]:
            setattr(ref, k, values[k])


def _project_host_member_format(member_ref):
    """Format a member ref for consumption outside of this module."""
    return {
        'id': member_ref['id'],
        'cluster_id': member_ref['cluster_id'],
        'host_id': member_ref['host_id'],
        'created_at': member_ref['created_at'],
        'updated_at': member_ref['updated_at']
    }

def _cluster_host_member_get(context, session, member_id):
    """Fetch an ClusterHost entity by id."""
    query = session.query(models.ClusterHost)
    query = query.filter(models.ClusterHost.id == member_id).filter_by(deleted=False)
    return query.one()

def _cluster_host_member_update(context, memb_ref, values, session=None):
    """Apply supplied dictionary of values to a Member object."""
    _drop_protected_attrs(models.ClusterHost, values)
    if values.has_key('node'):
        host = host_get(context, values['node'], session=None, force_show_deleted=False)
        host.status = "in-cluster"
        host.save(session=session)
    values["deleted"] = False
    memb_ref.update(values)
    memb_ref.save(session=session)
    return memb_ref

def cluster_host_member_update(context, values, member_id):
    """Update an ClusterHost object."""
    session = get_session()
    memb_ref = _cluster_host_member_get(context, session, member_id)
    _cluster_host_member_update(context, memb_ref, values, session)
    return _project_host_member_format(memb_ref)

def cluster_host_member_create(context, values, session=None):
    """Create an ClusterHost object."""
    memb_ref = models.ClusterHost()
    _cluster_host_member_update(context, memb_ref, values, session=session)
    return _project_host_member_format(memb_ref)

def _cluster_host_member_find(context, session, cluster_id=None, host_id=None):
    query = session.query(models.ClusterHost)
    query = query.filter_by(deleted=False)

    if cluster_id is not None:
        query = query.filter(models.ClusterHost.cluster_id == cluster_id and models.ClusterHost.deleted == "0")
    if host_id is not None:
        query = query.filter(models.ClusterHost.host_id == host_id and models.ClusterHost.deleted == "0")

    return query.all()


def _cluster_host_member_delete(context, memb_ref, session):
    memb_ref.delete(session=session)

def cluster_host_member_delete(context, member_id):
    """Delete an ClusterHost object."""
    session = get_session()
    member_ref = _cluster_host_member_get(context, session, member_id)
    host_info=host_get(context, member_ref['host_id'], session)
    host_info['status']="init"
    host_update(context,member_ref['host_id'],dict(host_info))
    _cluster_host_member_delete(context, member_ref, session)
    delete_host_role(context, member_ref['host_id'], session)
    host_interfaces = get_host_interface(context, member_ref['host_id'], None, session)
    for host_interface_info in host_interfaces:
        delete_assigned_networks(context, host_interface_info.id, session)


def cluster_host_member_find(context, cluster_id=None, host_id=None):
    """Find all members that meet the given criteria

    :param cluster_id: identifier of project entity
    :param host_id: host identifier
    """
    session = get_session()
    members = _cluster_host_member_find(context, session, cluster_id, host_id)
    return [_project_host_member_format(m) for m in members]

def cluster_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_cluster = None
    if marker is not None:
        marker_cluster = _cluster_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    if 'name' in filters:
        name = filters.pop('name')
        query = session.query(models.Cluster).filter_by(deleted=False).filter_by(name=name)
    elif 'auto_scale' in filters:
        auto_scale = filters.pop('auto_scale')
        query = session.query(models.Cluster).filter_by(deleted=False).filter_by(auto_scale=auto_scale)
    else:
        query = session.query(models.Cluster).filter_by(deleted=False)

        query = _paginate_query(query, models.Cluster, limit,
                            sort_key,
                            marker=marker_cluster,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    clusters = []
    for cluster in query.all():
        cluster_dict = cluster.to_dict()
        clusters.append(cluster_dict)
    return clusters

def component_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_component = None
    if marker is not None:
        marker_component = _component_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    query = session.query(models.Component).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.Component, limit,
                            sort_key,
                            marker=marker_component,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    components = []
    for component in query.all():
        component_dict = component.to_dict()
        components.append(component_dict)
    return components

def _check_config_file_id(config_file_id):
    """
    check if the given config_file id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the config_file id
    length is longer than the defined length in database model.
    :param config_file_id: The id of the config_file we want to check
    :return: Raise NoFound exception if given config_file id is invalid
    """
    if (config_file_id and
       len(config_file_id) > models.ConfigFile.id.property.columns[0].type.length):
        raise exception.NotFound()

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _config_file_update(context, values, config_file_id):
    """
    Used internally by config_file_add and config_file_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param config_file_id: If None, create the config_file, otherwise, find and update it
    """
    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()

    session = get_session()
    with session.begin():
        if config_file_id:
            config_file_ref = _config_file_get(context, config_file_id, session=session)
        else:
            config_file_ref = models.ConfigFile()
            #if config_file_ref.id is None:
            #    config_file_ref.id = str(uuid.uuid4())
        if config_file_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.ConfigFile, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if config_file_id:
            query = session.query(models.ConfigFile).filter_by(id=config_file_id).filter_by(deleted=False)

            # Validate fields for Config_files table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in config_file_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update config_file_id %(config_file_id)s failed') %
                       {'config_file_id': config_file_id})
                raise exception.Conflict(msg)

            config_file_ref = _config_file_get(context, config_file_id, session=session)
        else:
            config_file_ref.update(values)
            _update_values(config_file_ref, values)
            try:
                config_file_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Config_file ID %s already exists!"
                                          % values['id'])

    return config_file_get(context, config_file_ref.id)

def _config_file_get(context, config_file_id, session=None, force_show_deleted=False):
    """Get an config_file or raise if it does not exist."""
    _check_config_file_id(config_file_id)
    session = session or get_session()

    try:
        query = session.query(models.ConfigFile).filter_by(id=config_file_id).filter_by(deleted=False)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        config_file = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No config_file found with ID %s" % config_file_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return config_file

def config_file_get(context, config_file_id, session=None, force_show_deleted=False):
    config_file = _config_file_get(context, config_file_id, session=session,
                       force_show_deleted=force_show_deleted)
    return config_file

def config_file_add(context, values):
    """Add an config_file from the values dictionary."""
    return _config_file_update(context, values, None)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def config_file_destroy(context, config_file_id):
    """Destroy the config_file or raise if it does not exist."""
    session = get_session()
    configs = _config_get_by_config_file_id(context, config_file_id, session=session)
    for config in configs:
        config_items = _config_item_set_get_by_config_id(context, config.id, session=session)
        if config_items:
            msg = "config file '%s' is using" % (config_file_id)
            raise exception.DeleteConstrainted(msg)
    for config in configs:
        config_destroy(context, config.id)

    with session.begin():
        config_file_ref = _config_file_get(context, config_file_id, session=session)
        config_file_ref.delete(session=session)

    return config_file_ref

def config_file_update(context, config_file_id, values):
    """
    Set the given properties on an config_file and update it.

    :raises NotFound if config_file does not exist.
    """
    return _config_file_update(context, values, config_file_id)

def config_file_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all config_files that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the config_file properties attribute
    :param marker: config_file id after which to start page
    :param limit: maximum number of config_files to return
    :param sort_key: list of config_file attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)

    marker_config_file = None
    if marker is not None:
        marker_config_file = _config_file_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    query = session.query(models.ConfigFile).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.ConfigFile, limit,
                            sort_key,
                            marker=marker_config_file,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    config_files = []
    for config_file in query.all():
        config_file_dict = config_file.to_dict()
        config_files.append(config_file_dict)
    return config_files

def _check_config_set_id(config_set_id):
    """
    check if the given config_set id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the config_set id
    length is longer than the defined length in database model.
    :param config_set_id: The id of the config_set we want to check
    :return: Raise NoFound exception if given config_set id is invalid
    """
    if (config_set_id and
        len(config_set_id) > models.ConfigSet.id.property.columns[0].type.length):
        raise exception.NotFound()

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _config_set_update(context, values, config_set_id=None):
    """
    Used internally by config_set_add and config_set_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param config_set_id: If None, create the config_set, otherwise, find and update it
    """
    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()

    session = get_session()
    with session.begin():
        if config_set_id:
            config_set_ref = _config_set_get(context, config_set_id, session=session)
        else:
            config_set_ref = models.ConfigSet()
            #if config_set_ref.id is None:
            #    config_set_ref.id = str(uuid.uuid4())
        if config_set_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.ConfigSet, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if config_set_id:
            query = session.query(models.ConfigSet).filter_by(id=config_set_id).filter_by(deleted=False)

            # Validate fields for config_sets table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in config_set_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update config_file_id %(config_set_id)s failed') %
                       {'config_set_id': config_set_id})
                raise exception.Conflict(msg)

            config_set_ref = _config_set_get(context, config_set_id, session=session)
        else:
            config_set_ref.update(values)
            _update_values(config_set_ref, values)
            try:
                config_set_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Config_set ID %s already exists!"
                                          % values['id'])

    return config_set_get(context, config_set_ref.id)


def _config_set_get(context, config_set_id, session=None, force_show_deleted=False):
    """Get an config_set or raise if it does not exist."""
    _check_config_set_id(config_set_id)
    session = session or get_session()

    try:
        query = session.query(models.ConfigSet).filter_by(id=config_set_id).filter_by(deleted=False)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        config_set = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No config_set found with ID %s" % config_set_id
        LOG.info(msg)
        raise exception.NotFound(msg)

    return config_set

def config_set_get(context, config_set_id, session=None, force_show_deleted=False):
    config_set = _config_set_get(context, config_set_id, session=session,
                       force_show_deleted=force_show_deleted)
    return config_set

def config_set_add(context, values):
    """Add an config_set from the values dictionary."""
    return _config_set_update(context, values)

def _config_item_set_get_by_config_id(context, config_id, session=None, force_show_deleted=False):
    """Get an config_set or raise if it does not exist."""
    _check_config_id(config_id)
    session = session or get_session()

    try:
        query = session.query(models.ConfigSetItem).filter_by(config_id=config_id).filter_by(deleted=False)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        config_items = query.all()

    except sa_orm.exc.NoResultFound:
        msg = "No config_set found with ID %s" % config_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return config_items

def _config_item_get_by_config_set_id(context, config_set_id, session=None, force_show_deleted=False):
    """Get an config or raise if it does not exist."""
    _check_config_set_id(config_set_id)
    session = session or get_session()

    try:
        query = session.query(models.ConfigSetItem).filter_by(config_set_id=config_set_id).filter_by(deleted=False)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        config_items = query.all()

    except sa_orm.exc.NoResultFound:
        msg = "No config_item found with ID %s" % config_set_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return config_items

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def config_set_destroy(context, config_set_id):
    """Destroy the config_set or raise if it does not exist."""
    session = get_session()
    with session.begin():
        config_set_ref = _config_set_get(context,
                                         config_set_id,
                                         session=session)
        query_role = session.query(models.Host).filter_by(\
                     config_set_id=config_set_id).filter_by(deleted=False)
        if query_role.all():
            msg = "config_set %s is being used by other host"\
                    % config_set_id
            raise exception.Forbidden(msg)
        query_role = session.query(models.Role).filter_by(\
                     config_set_id=config_set_id).filter_by(deleted=False)
        if query_role.all():
            msg = "config_set %s is being used by other role"\
                    % config_set_id
            raise exception.Forbidden(msg)

        config_set_ref.delete(session=session)

        config_item_refs =\
            _config_item_get_by_config_set_id(context,
                                              config_set_id,
                                              session=session)
        for config_item_ref in config_item_refs:
            config_id = config_item_ref.config_id
            config_item_ref.delete(session=session)
            if not _config_item_set_get_by_config_id(context,
                                                     config_id,
                                                     session=session):
                config_ref = _config_get(context,
                                         config_id,
                                         session=session)
                config_ref.delete(session=session)

    return config_set_ref

def config_set_update(context, config_set_id, values):
    """
    Set the given properties on an config_set and update it.

    :raises NotFound if config_set does not exist.
    """
    return _config_set_update(context, values, config_set_id)

def config_set_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all config_sets that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the config_set properties attribute
    :param marker: config_set id after which to start page
    :param limit: maximum number of config_sets to return
    :param sort_key: list of config_set attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)

    marker_config_set = None
    if marker is not None:
        marker_config_set = _config_set_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    query = session.query(models.ConfigSet).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.ConfigSet, limit,
                            sort_key,
                            marker=marker_config_set,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    config_sets = []
    for config_set in query.all():
        config_set_dict = config_set.to_dict()
        config_sets.append(config_set_dict)
    return config_sets

def _check_config_id(config_id):
    """
    check if the given config id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the config id
    length is longer than the defined length in database model.
    :param config_id: The id of the config we want to check
    :return: Raise NoFound exception if given config id is invalid
    """
    if (config_id and
        len(config_id) > models.Config.id.property.columns[0].type.length):
        raise exception.NotFound()

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _config_update(context, values, config_id):
    """
    Used internally by config_add and config_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param config_id: If None, create the config, otherwise, find and update it
    """
    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()

    config_item_values=dict()

    session = get_session()

    with session.begin():
        if config_id:
            config_ref = _config_get(context, config_id, session=session)
        else:
            config_ref = models.Config()
            config_item_ref = models.ConfigSetItem()
            #if config_ref.id is None:
            #    config_ref.id = str(uuid.uuid4())
        if config_id:
            if values.has_key('config_set_id'):
                config_item_values['config_set_id'] = str(values['config_set_id'])

            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Config, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if config_id:
            query = session.query(models.Config).filter_by(id=config_id).filter_by(deleted=False)

            # Validate fields for configs table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in config_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')



            if config_item_values.has_key('config_set_id'):
                session = get_session()
                _drop_protected_attrs(models.ConfigSetItem, config_item_values)
                query = session.query(models.ConfigSetItem).filter_by(config_id=config_id).filter_by(deleted=False)
                query.update(config_item_values, synchronize_session='fetch')

            if not updated:
                msg = (_('update config_id %(config_id)s failed') %
                       {'config_id': config_id})
                raise exception.Conflict(msg)

            config_ref = _config_get(context, config_id, session=session)

        else:
            config_ref.update(values)

            _update_values(config_ref, values)
            try:

                config_ref.save(session=session)

            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Config ID %s already exists!"
                                          % values['id'])

            if values.has_key('config_set_id'):
                config_item_values['config_id'] = config_ref.id
                config_item_values['config_set_id'] = str(values['config_set_id'])
                _update_values(config_item_ref, config_item_values)
                config_item_ref.save(session=session)

    return config_get(context, config_ref.id)

def _config_get(context, config_id, session=None, force_show_deleted=False):
    """Get an config or raise if it does not exist."""
    _check_config_id(config_id)
    session = session or get_session()

    try:
        query = session.query(models.Config).filter_by(id=config_id).filter_by(deleted=False)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        config = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No config found with ID %s" % config_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return config

def _config_get_by_config_file_id(context, config_file_id, session=None, force_show_deleted=False):
    """Get an config or raise if it does not exist."""
    _check_config_file_id(config_file_id)
    session = session or get_session()

    try:
        query = session.query(models.Config).filter_by(config_file_id=config_file_id).filter_by(deleted=False)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        configs = query.all()

    except sa_orm.exc.NoResultFound:
        msg = "No config found with ID %s" % config_file_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return configs

def _config_item_get_by_config_id(config_id, session=None):
    """Get an config or raise if it does not exist."""
    _check_config_id(config_id)
    try:
        query = session.query(models.ConfigSetItem).filter_by(config_id=config_id).filter_by(deleted=False)
        config_items = query.all()

    except sa_orm.exc.NoResultFound:
        msg = "No config found with ID %s" % config_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return config_items

def config_get(context, config_id, session=None, force_show_deleted=False):
    config = _config_get(context, config_id, session=session,
                       force_show_deleted=force_show_deleted)
    return config

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def update_config_by_role_hosts(context, values):
    if not values:
        LOG.error("<<<FUN:update_config_by_role_hosts, config_set datas is NULL.>>>")

    session = get_session()
    with session.begin():
        for value in values:
            if not value.get('config', None):
                continue
            configs = value['config']

            for config in configs:
                if not config.get('id', None):
                    continue

                id = config['id']
                config['updated_at'] = timeutils.utcnow()
                config_ref =_config_get(context, id, session)
                if not config_ref:
                    continue

                config_ref.update(config)
                _update_values(config_ref, config)

    return  {'configs':values}

def config_add(context, values):
    """Add an config from the values dictionary."""
    return _config_update(context, values, None)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def config_destroy(context, config_id):
    """Destroy the config or raise if it does not exist."""
    session = get_session()
    with session.begin():
        config_ref = _config_get(context, config_id, session=session)
        # config_file_id=config_ref.config_file_id
        config_item_refs = _config_item_get_by_config_id(config_id, session=session)
        for config_item_ref in config_item_refs:
            config_item_ref.delete(session=session)
        config_ref.delete(session=session)

        return config_ref

def config_update(context, config_id, values):
    """
    Set the given properties on an config and update it.

    :raises NotFound if config does not exist.
    """
    return _config_update(context, values, config_id)

def config_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all configs that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the config properties attribute
    :param marker: config id after which to start page
    :param limit: maximum number of configs to return
    :param sort_key: list of config attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)

    marker_config = None
    if marker is not None:
        marker_config = _config_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    query = session.query(models.Config).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.Config, limit,
                            sort_key,
                            marker=marker_config,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    configs = []
    for config in query.all():
        config_dict = config.to_dict()
        configs.append(config_dict)
    return configs

def network_get(context, network_id, session=None, force_show_deleted=False):
    Network = _network_get(context, network_id, session=session,
                       force_show_deleted=force_show_deleted)
    return Network

def network_add(context, values):
    """Add an cluster from the values dictionary."""
    return _network_update(context, values, None)

def network_update(context, network_id, values):
    """
    Set the given properties on an cluster and update it.

    :raises NotFound if cluster does not exist.
    """
    return _network_update(context, values, network_id)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def network_destroy(context,  network_id):
    """Destroy the project or raise if it does not exist."""
    session = get_session()
    with session.begin():
        network_ref = _network_get(context, network_id, session=session)
        assign_networks = _get_assigned_networks_by_network_id(context, network_id, session=session)
        if assign_networks:
            msg = "network %s is in used, it couldn't be deleted" % network_id
            raise exception.DeleteConstrainted(msg)
        else:
            network_ref.delete(session=session)

    return network_ref

def get_assigned_networks_by_network_id(context, network_id,
                                        session=None, force_show_deleted=False):
    # get the assign networks by network id
    assign_networks = \
        _get_assigned_networks_by_network_id(context, network_id, session=session)
    return assign_networks

def delete_network_ip_range(context,  network_id):
    session = get_session()
    with session.begin():
        querry= session.query(models.IpRange).filter_by(network_id=network_id).filter_by(deleted=0)
        ip_ranges=querry.all()
        for ip_range in ip_ranges:
            ip_range.delete(session=session)

def get_network_ip_range(context,  network_id):
    session = get_session()
    with session.begin():
        sql_ip_ranges="select ip_ranges.start,end,cidr,gateway from ip_ranges \
            where ip_ranges.network_id='"+network_id+"' and \
            ip_ranges.deleted=0;"
        ip_ranges = session.execute(sql_ip_ranges).fetchall()
        #ip_ranges_sorted = sorted(ip_ranges, cmp=compare_same_cidr_ip)
        ip_ranges_sorted=sort_ip_ranges_with_cidr(ip_ranges)
    return ip_ranges_sorted
def network_get_all(context, cluster_id=None, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    if 'cluster_id' in filters:
        cluster_id = filters['cluster_id']

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)

    marker_network = None
    if marker is not None:
        marker_network = _network_get(context, marker, cluster_id,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    if 0 == cmp(cluster_id, "template"):
        query = session.query(models.Network).filter_by(type="template").filter_by(deleted=False).all()
        return [phynet_name.name for phynet_name in query]
    elif cluster_id is not None and filters.get('type'):
        query = session.query(models.Network).\
            filter_by(cluster_id=cluster_id).\
            filter_by(type=filters['type']).\
            filter_by(deleted=showing_deleted)
    elif cluster_id is not None:
        query = session.query(models.Network).\
            filter_by(cluster_id=cluster_id).\
            filter_by(deleted=showing_deleted)
    elif filters.get('type'):
        query = session.query(models.Network).\
            filter_by(type=filters['type']).\
            filter_by(deleted=showing_deleted)
    else:
        query = session.query(models.Network). \
            filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.Network, limit,
                             sort_key,
                             marker=marker_network,
                             sort_dir=None,
                             sort_dirs=sort_dir)
    query = query.all()
    networks = []
    for network in query:
        ip_range_list=[]
        ip_ranges=get_network_ip_range(context,  network['id'])
        if ip_ranges:
            for ip_range in ip_ranges:
                ip_range_dict={}
                ip_range_dict['start']=str(ip_range['start'])
                ip_range_dict['end']=str(ip_range['end'])
                if 'cidr' in ip_range:
                    ip_range_dict['cidr']=str(ip_range['cidr'])
                if 'gateway' in ip_range:
                    ip_range_dict['gateway']=str(ip_range['gateway'])
                ip_range_list.append(ip_range_dict)
        network['ip_ranges']=ip_range_list
        network_dict = network.to_dict()
        networks.append(network_dict)
    return networks

def _check_network_id(network_id):
    """
    check if the given project id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the project id
    length is longer than the defined length in database model.
    :param network_id: The id of the project we want to check
    :return: Raise NoFound exception if given project id is invalid
    """
    if (network_id and
       len(network_id) > models.Network.id.property.columns[0].type.length):
        raise exception.NotFound()

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def update_phyname_of_network(context, network_phyname_set):
    """
    Update phynet_name segment in network table.
    :param context: data for context
    :param network_phyname_set: Like {'network_id':pyhnet_name}
    :return:
    """
    if not context or not network_phyname_set:
        raise exception.Invalid("Fun:update_phyname_of_network, input params invalid.")

    session = get_session()
    with session.begin():
        for k,v in network_phyname_set.items():
            query = session.query(models.Network). \
                filter_by(id = k). \
                filter_by(name = v[0]).filter_by(deleted=False)

            if query and query.first():
                query.update(
                    {'updated_at' : timeutils.utcnow(), 'physnet_name' :"physnet_"+v[1]}
                )


def check_assigned_ip_in_ip_range(assigned_ip_list, ip_range_list,
                                  ssh_host_ip):
    if not ip_range_list:
        return
    assigned_ips = copy.deepcopy(assigned_ip_list)
    ip_ranges = copy.deepcopy(ip_range_list)
    ip_list = [ip for ip in assigned_ips if ip]
    for ip in ip_list:
        flag = False
        if ip in ssh_host_ip:
            continue
        for ip_range in ip_ranges:
            if is_in_ip_range(ip, ip_range):
                flag = True
                break
        if not flag:
            msg = "'%s' not in new range '%s'" % (ip, ip_ranges)
            LOG.error(msg)
            raise exception.Forbidden(msg)


def get_ip_of_ssh_discover_host(session):
    host_filter = [models.HostInterface.deleted == 0,
                   models.DiscoverHost.deleted == 0,
                   models.HostInterface.ip == models.DiscoverHost.ip]
    query = session.query(models.HostInterface, models.DiscoverHost).\
        filter(sa_sql.and_(*host_filter))

    ssh_host_ip_list = []
    for item in query.all():
        ip_query_sql = "select ip from host_interfaces where host_interfaces." \
                       "host_id='%s' and is_vf=0" % item.HostInterface.host_id
        ip_query_result = session.execute(ip_query_sql).fetchall()
        ip_query_list = [item[0] for item in ip_query_result if item[0]]
        ssh_host_ip_list.extend(ip_query_list)
    return set(ssh_host_ip_list)


def _get_role_float_ip(session, cluster_id):
    roles = session.query(models.Role).filter_by(cluster_id=cluster_id).\
        filter_by(deleted=False)
    float_ip_lists = [[role.vip, role.db_vip, role.glance_vip]
                      for role in roles if role.name == 'CONTROLLER_HA' or
                      role.name == 'CONTROLLER_LB']
    return [ip for float_ip_list in float_ip_lists
            for ip in float_ip_list if ip]


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _network_update(context, values, network_id):
    """
    Used internally by network_add and project_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param network_id: If None, create the network, otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()
    ip_ranges_values = dict()
    session = get_session()
    role_vip_list = []
    with session.begin():
        if network_id:
            network_ref = _network_get(context, network_id, session=session)
        else:
            network_ref = models.Network()

        if network_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Network, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if network_id:
            query = session.query(models.Network).filter_by(id=network_id).filter_by(deleted=False)
            sql_ip="select assigned_networks.ip from assigned_networks where assigned_networks.deleted=0 and assigned_networks.network_id='"+network_id+"' order by assigned_networks.ip"
            query_ip_list = session.execute(sql_ip).fetchall()
            network_ip_list = [tmp_ip.values().pop() for tmp_ip in query_ip_list]
            if values.get('name') == 'MANAGEMENT'and query.one().cluster_id:
                role_vip_list = _get_role_float_ip(session, query.one().cluster_id)
            assign_ip_list = list(set(network_ip_list + role_vip_list))
            # Validate fields for projects table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            if values.has_key("cidr") and values['cidr'] != [u''] and values['cidr'] !='':
                sql_cidr="select networks.cidr from networks where networks.id='"+network_id +"'"
                query_cidr = session.execute(sql_cidr).fetchone()
                network_tmp=query_cidr.values()
                network_cidr=network_tmp.pop()
                if network_cidr and network_cidr != values['cidr']:
                    #sql_ip="select host_interfaces.ip from host_interfaces, assigned_networks where host_interfaces.deleted=0 and host_interfaces.id=assigned_networks.interface_id and assigned_networks.deleted=0 and assigned_networks.network_id='"+network_id+"'"
                    for tmp_ip in assign_ip_list:
                        if tmp_ip and not is_in_cidr_range(tmp_ip, values['cidr']):
                            msg = "ip %s being used is not in range of new cidr " \
                                  "%s" % (tmp_ip, values['cidr'])
                            LOG.error(msg)
                            raise exception.Forbidden(msg)

            network_ref = _network_get(context, network_id, session=session)
            if values.get("ip_ranges"):
                if not isinstance(values['ip_ranges'], list):
                    ip_ranges = eval(values['ip_ranges'])
                else:
                    ip_ranges = values['ip_ranges']
                old_ip_ranges = get_network_ip_range(context,  network_id)
                # new_ip_ranges = [tuple(ran.values()) for ran in
                #                  ip_ranges]
                new_ip_ranges = []
                for ip_range in ip_ranges:
                    tmp_start = ip_range.get('start', None)
                    tmp_end = ip_range.get('end', None)
                    tmp_cidr = ip_range.get('cidr', None)
                    tmp_gw = ip_range.get('gateway', None)
                    new_ip_ranges.append(
                        (tmp_start, tmp_end, tmp_cidr, tmp_gw))
                if new_ip_ranges != old_ip_ranges:
                    ssh_host_ip = get_ip_of_ssh_discover_host(session)
                    check_assigned_ip_in_ip_range(network_ip_list,
                                                  ip_ranges,
                                                  ssh_host_ip)
                    delete_network_ip_range(context,  network_id)
                    for ip_range in new_ip_ranges:
                        ip_range_ref = models.IpRange()
                        ip_range_ref['start'] = ip_range[0]
                        ip_range_ref['end'] = ip_range[1]
                        ip_range_ref['cidr'] = ip_range[2]
                        ip_range_ref['gateway'] = ip_range[3]
                        ip_range_ref.network_id = network_ref.id
                        ip_range_ref.save(session=session)
                    del values['ip_ranges']
                else:
                    values.pop('ip_ranges')
            keys = values.keys()
            for k in keys:
                if k not in network_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update network_id %(network_id)s failed') %
                       {'network_id': network_id})
                raise exception.Conflict(msg)
        else:

            network_ref.update(values)
            _update_values(network_ref, values)
            try:
                network_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("network ID %s already exists!"
                                          % values['id'])
            if values.has_key("ip_ranges"):
                for ip_range in list(eval(values['ip_ranges'])):
                    try:
                        ip_ranges_values['start'] = ip_range["start"]
                        ip_ranges_values['end'] = ip_range["end"]
                        if ip_range.get('cidr'):
                            ip_ranges_values['cidr'] = ip_range['cidr']
                        if ip_range.get('gateway'):
                            ip_ranges_values['gateway'] = ip_range['gateway']
                        ip_ranges_values['network_id'] = network_ref.id
                        ip_range_ref = models.IpRange()
                        ip_range_ref.update(ip_ranges_values)
                        _update_values(ip_range_ref, ip_ranges_values)
                        ip_range_ref.save(session=session)
                    except db_exception.DBDuplicateEntry:
                        raise exception.Duplicate("ip range %s already exists!"
                                          % values['ip_ranges'])

    return _network_get(context, network_ref.id)

def _network_get(context, network_id=None, cluster_id=None, session=None, force_show_deleted=False):
    """Get an network or raise if it does not exist."""
    if network_id is not None:
        _check_network_id(network_id)
    session = session or get_session()

    try:
        if network_id is not None:
            query = session.query(models.Network).filter_by(id=network_id).filter_by(deleted=False)
        #if cluster_id is not None:
            #query = session.query(models.Network).filter_by(cluster_id=cluster_id).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        networks = query.one()

        ip_range_list=[]
        ip_ranges=get_network_ip_range(context,  networks['id'])
        if ip_ranges:
            for ip_range in ip_ranges:
                ip_range_dict={}
                ip_range_dict['start']=str(ip_range['start'])
                ip_range_dict['end']=str(ip_range['end'])
                if 'cidr' in ip_range:
                    ip_range_dict['cidr']=str(ip_range['cidr'])
                if 'gateway' in ip_range:
                    ip_range_dict['gateway']=str(ip_range['gateway'])
                ip_range_list.append(ip_range_dict)
        networks['ip_ranges']=ip_range_list


    except sa_orm.exc.NoResultFound:
        msg = "No network found with ID %s" % network_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return networks

def update_config(session,config_flag,config_set_id,query_set_item_list,config_interface_info):
    for config_set_item in query_set_item_list.all():
        query_config_info= session.query(models.Config).filter_by(id=config_set_item.config_id).filter_by(deleted=False)
        query_config_file_info= session.query(models.ConfigFile).filter_by(id=query_config_info.one().config_file_id).filter_by(deleted=False)
        if query_config_file_info.one().name == config_interface_info['file-name']\
            and config_interface_info['section'] == query_config_info.one().section and config_interface_info['key'] == query_config_info.one().key:
            config_info = copy.deepcopy(config_interface_info)
            del config_info['file-name']
            config_info['config_version']=query_config_info.one().config_version+1
            query_config_info.one().update(config_info)
            config_flag=1
            return config_flag
        else:
            continue
    return config_flag

def add_config(session,config_interface_info,config_set_id,config_file_id):
    config_set_value=dict()
    add_config = models.Config()
    config_info = copy.deepcopy(config_interface_info)
    del config_info['file-name']
    config_info['config_file_id']=config_file_id
    config_info['config_version']=1
    config_info['running_version']=0
    add_config.update(config_info)
    _update_values(add_config,config_info)
    add_config.save(session=session)

    add_config_setitem=models.ConfigSetItem()
    config_set_value['config_set_id']=config_set_id
    config_set_value['config_id']=add_config.id
    config_set_value.update(config_set_value)
    _update_values(add_config_setitem,config_set_value)
    add_config_setitem.save(session=session)

def add_config_and_file(session,config_interface_info,config_set_id):
    query_config_file=session.query(models.ConfigFile).filter_by(name=config_interface_info['file-name']).filter_by(deleted=False)
    if query_config_file.all():
        config_file_id=query_config_file.one().id
    else:
        config_file_value = dict()
        add_config_file = models.ConfigFile()
        config_file_value['name']=config_interface_info['file-name']
        config_file_value.update(config_file_value)
        _update_values(add_config_file,config_file_value)
        add_config_file.save(session=session)
        config_file_id=add_config_file.id

    add_config(session,config_interface_info,config_set_id,config_file_id)

def config_interface(context, config_interface):
    config_flag=0
    config_info_list=[]
    config_interface = config_interface.copy()

    if isinstance(config_interface['config'], list):
        config_items = config_interface['config']
    else:
        config_items = eval(config_interface['config'])

    session = get_session()
    with session.begin():
        if config_interface.get('role',None) and config_interface.get('cluster',None):
            query_role_info=session.query(models.Role).filter_by(\
                name=config_interface['role']).filter_by(\
                cluster_id=config_interface['cluster']).filter_by(\
                deleted=False)
            if query_role_info.one().config_set_id:
                config_set_id=query_role_info.one().config_set_id
            else:
                msg = "No config_set_id found with Role Name %s" % config_interface.role_name
                LOG.error(msg)
                raise exception.NotFound(msg)
        elif config_interface.get('host_id',None):
            query_host_ref = _host_get(context,
                                       config_interface['host_id'],
                                       session=session)
            if query_host_ref.config_set_id:
                config_set_id=query_host_ref.config_set_id
            else:
                #create config_set and get id
                config_set_value = {'name':config_interface['host_id'],
                              'description':'config set for host %s'\
                                            %config_interface['host_id']}
                config_set = _config_set_update(context, config_set_value)
                config_set_id = config_set['id']
                #add config_set_id to host
                host_meta = {'config_set_id':config_set_id}
                _host_update(context,
                             host_meta,
                             config_interface['host_id'])
        elif config_interface.get('config_set',None):
             config_set_id=config_interface.get('config_set',None)
        else:
            msg = "no way to add config"
            LOG.error(msg)
            raise exception.NotFound(msg)

        try:
            for config_interface_info in config_items:
                query_set_item_list=session.query(models.ConfigSetItem).filter_by(config_set_id=config_set_id).filter_by(deleted=False)
                if query_set_item_list.all():
                    config_exist=update_config(session,config_flag,config_set_id,query_set_item_list,config_interface_info)
                    if not config_exist:
                        query_config_file=session.query(models.ConfigFile).filter_by(name=config_interface_info['file-name']).filter_by(deleted=False)
                        if query_config_file.all():
                            add_config(session,config_interface_info,config_set_id,query_config_file.one().id)
                        else:
                            add_config_and_file(session,config_interface_info,config_set_id)
                else:
                    add_config_and_file(session,config_interface_info,config_set_id)

        except sa_orm.exc.NoResultFound:
            msg = "No config_set found with ID %s" % config_set_id
            LOG.error(msg)
            raise exception.NotFound(msg)

    for config_interface_info in config_items:
        query_config_set_item_list=session.query(models.ConfigSetItem).filter_by(config_set_id=config_set_id).filter_by(deleted=False)
        if query_config_set_item_list.all():
            for config_set_item in query_config_set_item_list.all():
                query_config_info= session.query(models.Config).filter_by(id=config_set_item.config_id).filter_by(deleted=False)
                query_config_file= session.query(models.ConfigFile).filter_by(id=query_config_info.one().config_file_id).filter_by(deleted=False)
                if query_config_file.one().name == config_interface_info['file-name'] and config_interface_info['section'] == query_config_info.one().section \
                    and config_interface_info['key'] == query_config_info.one().key:
                        config_info={}
                        config_info['id']=query_config_info.one().id
                        config_info['file-name']=config_interface_info['file-name']
                        config_info['section']=query_config_info.one().section
                        config_info['key']=query_config_info.one().key
                        config_info['value']=query_config_info.one().value
                        config_info['description']=query_config_info.one().description
                        config_info['config_version']=query_config_info.one().config_version
                        config_info['running_version']=query_config_info.one().running_version
                        config_info_list.append(config_info)

    return_config_info={'cluster':config_interface.get('cluster',None),
                        'role':config_interface.get('role',None),
                        'config':config_info_list}
    return return_config_info

def _check_service_disk_id(service_disk_id):
    """
    check if the given project id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the project id
    length is longer than the defined length in database model.
    :param service_disk_id: The id of the project we want to check
    :return: Raise NoFound exception if given project id is invalid
    """
    if (service_disk_id and
       len(service_disk_id) > models.ServiceDisk.id.property.columns[0].type.length):
        raise exception.NotFound()

def _service_disk_get(context, service_disk_id=None, role_id=None, marker=None, session=None, force_show_deleted=False):
    """Get an service_disk or raise if it does not exist."""
    if service_disk_id is not None:
        _check_service_disk_id(service_disk_id)
    session = session or get_session()

    try:
        if service_disk_id is not None:
            query = session.query(models.ServiceDisk).filter_by(id=service_disk_id).filter_by(deleted=False)
        elif role_id is not None:
            query = session.query(models.ServiceDisk).filter_by(role_id=role_id).filter_by(deleted=False)
        else:
            query = session.query(models.ServiceDisk).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        if service_disk_id is not None:
            service_disk = query.one()
        else:
            service_disk = query.all()
    except sa_orm.exc.NoResultFound:
        msg = "No service_disk found with ID %s" % service_disk_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return service_disk

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _service_disk_update(context, values, service_disk_id):
    """
    Used internally by service_disk_add and project_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param service_disk_id: If None, create the service_disk, otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()
    session = get_session()
    with session.begin():
        if service_disk_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.ServiceDisk, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()
            # Validate fields for projects table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            query = session.query(models.ServiceDisk).filter_by(id=service_disk_id).filter_by(deleted=False)
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update service_disk_id %(service_disk_id)s failed') %
                       {'service_disk_id': service_disk_id})
                raise exception.Conflict(msg)
        else:
            service_disk_ref = models.ServiceDisk()
            service_disk_ref.update(values)
            _update_values(service_disk_ref, values)
            try:
                service_disk_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("service_disk ID %s already exists!"
                                          % values['id'])

            service_disk_id = service_disk_ref.id
    return _service_disk_get(context, service_disk_id)

def service_disk_add(context, values):
    """Add an cluster from the values dictionary."""
    return _service_disk_update(context, values, None)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def service_disk_destroy(context, service_disk_id):
    """Destroy the service_disk or raise if it does not exist."""
    session = get_session()
    with session.begin():
        service_disk_ref = _service_disk_get(context, service_disk_id, session=session)
        service_disk_ref.delete(session=session)
    return service_disk_ref

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def service_disk_update(context, service_disk_id, values):
    """
    Set the given properties on an cluster and update it.

    :raises NotFound if cluster does not exist.
    """
    return _service_disk_update(context, values, service_disk_id)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)

def service_disk_detail (context, service_disk_id):
    service_disk_ref = _service_disk_get(context, service_disk_id)
    return service_disk_ref

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def service_disk_list(context, filters=None, **param):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    # sort_key = ['created_at'] if not sort_key else sort_key

    # default_sort_dir = 'desc'

    # if not sort_dir:
        # sort_dir = [default_sort_dir] * len(sort_key)
    # elif len(sort_dir) == 1:
        # default_sort_dir = sort_dir[0]
        # sort_dir *= len(sort_key)

    filters = filters or {}
    # showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                               # False)

    role_id = None
    if 'role_id' in filters:
        role_id=filters.pop('role_id')

    service_disk_ref = _service_disk_get(context, role_id=role_id)
    return service_disk_ref

def _check_cinder_volume_id(cinder_volume_id):
    """
    check if the given project id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the project id
    length is longer than the defined length in database model.
    :param cinder_volume_id: The id of the project we want to check
    :return: Raise NoFound exception if given project id is invalid
    """
    if (cinder_volume_id and
       len(cinder_volume_id) > models.CinderVolume.id.property.columns[0].type.length):
        raise exception.NotFound()


def _check_optical_switch_id(optical_switch_id):
    if (optical_switch_id and
       len(optical_switch_id) > models.OpticalSwitch.id.property.columns[0].type.length):
        raise exception.NotFound()


def _cinder_volume_get(context, cinder_volume_id=None, role_id=None, marker=None, session=None, force_show_deleted=False):
    """Get an cinder_volume or raise if it does not exist."""
    if cinder_volume_id is not None:
        _check_cinder_volume_id(cinder_volume_id)
    session = session or get_session()

    try:
        if cinder_volume_id is not None:
            query = session.query(models.CinderVolume).filter_by(id=cinder_volume_id).filter_by(deleted=False)
        elif role_id is not None:
            query = session.query(models.CinderVolume).filter_by(role_id=role_id).filter_by(deleted=False)
        else:
            query = session.query(models.CinderVolume).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        if cinder_volume_id is not None:
            cinder_volume = query.one()
        else:
            cinder_volume = query.all()
    except sa_orm.exc.NoResultFound:
        msg = "No cinder_volume found with ID %s" % cinder_volume_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return cinder_volume


def _optical_switch_get(context, optical_switch_id=None,
                        role_id=None, marker=None, session=None,
                        force_show_deleted=False):
    """Get an optical switch or raise if it does not exist."""
    if optical_switch_id is not None:
        _check_optical_switch_id(optical_switch_id)
    session = session or get_session()

    try:
        if optical_switch_id is not None:
            query = session.query(models.OpticalSwitch).\
                filter_by(id=optical_switch_id).filter_by(deleted=False)
        elif role_id is not None:
            query = session.query(models.OpticalSwitch).\
                filter_by(role_id=role_id).filter_by(deleted=False)
        else:
            query = session.query(models.OpticalSwitch).\
                filter_by(deleted=False)
        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        if optical_switch_id is not None:
            optical_switch = query.one()
        else:
            optical_switch = query.all()
    except sa_orm.exc.NoResultFound:
        msg = "No optical switch found with ID %s" % optical_switch_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return optical_switch


def _cinder_volume_update(context, values, cinder_volume_id):
    """
    Used internally by cinder_volume_add and project_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param cinder_volume_id: If None, create the cinder_volume, otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()
    session = get_session()
    with session.begin():
        if cinder_volume_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.CinderVolume, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()
            # Validate fields for projects table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            query = session.query(models.CinderVolume).filter_by(id=cinder_volume_id).filter_by(deleted=False)
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update cinder_volume_id %(cinder_volume_id)s failed') %
                       {'cinder_volume_id': cinder_volume_id})
                raise exception.Conflict(msg)
        else:
            cinder_volume_ref = models.CinderVolume()
            cinder_volume_ref.update(values)
            _update_values(cinder_volume_ref, values)
            try:
                cinder_volume_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("cinder_volume ID %s already exists!"
                                          % values['id'])

            cinder_volume_id = cinder_volume_ref.id
    return _cinder_volume_get(context, cinder_volume_id)


def _optical_switch_update(context, values, optical_switch_id):
    """
    Used internally by optical_switch_add and project_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param optical_switch_id: If None, create the optical switch, otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()
    session = get_session()
    with session.begin():
        if optical_switch_id:
            _drop_protected_attrs(models.OpticalSwitch, values)
            values['updated_at'] = timeutils.utcnow()
            # TODO(dosaboy): replace this with a dict comprehension once py26
            query = session.query(models.OpticalSwitch).\
                filter_by(id=optical_switch_id).filter_by(deleted=False)
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update optical_switch_id '
                         '%(optical_switch_id)s failed') %
                       {'optical_switch_id': optical_switch_id})
                raise exception.Conflict(msg)
        else:
            optical_switch_ref = models.OpticalSwitch()
            optical_switch_ref.update(values)
            _update_values(optical_switch_ref, values)
            try:
                optical_switch_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("optical_switch ID %s "
                                          "already exists!" % values['id'])

            optical_switch_id = optical_switch_ref.id
    return _optical_switch_get(context, optical_switch_id)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def cinder_volume_add(context, values):
    """Add an cluster from the values dictionary."""
    return _cinder_volume_update(context, values, None)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def cinder_volume_destroy(context, cinder_volume_id):
    """Destroy the service_disk or raise if it does not exist."""
    session = get_session()
    with session.begin():
        cinder_volume_ref = _cinder_volume_get(context, cinder_volume_id, session=session)
        cinder_volume_ref.delete(session=session)
    return cinder_volume_ref

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def cinder_volume_update(context, cinder_volume_id, values):
    """
    Set the given properties on an cluster and update it.

    :raises NotFound if cluster does not exist.
    """
    return _cinder_volume_update(context, values, cinder_volume_id)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def cinder_volume_detail(context, cinder_volume_id):
    cinder_volume_ref = _cinder_volume_get(context, cinder_volume_id)
    return cinder_volume_ref

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def cinder_volume_list(context, filters=None, **param):
    """
    Get all hosts that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    filters = filters or {}
    # showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                               # False)
    role_id = None
    if 'role_id' in filters:
        role_id=filters.pop('role_id')

    cinder_volume_ref = _cinder_volume_get(context, role_id=role_id)
    return cinder_volume_ref


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def optical_switch_add(context, values):
    """Add an cluster from the values dictionary."""
    return _optical_switch_update(context, values, None)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def optical_switch_list(context, filters=None, **param):
    filters = filters or {}
    role_id = None
    if 'role_id' in filters:
        role_id = filters.pop('role_id')
    optical_switch_ref = _optical_switch_get(context, role_id=role_id)
    return optical_switch_ref


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def optical_switch_detail(context, optical_switch_id):
    optical_switch_ref = _optical_switch_get(context, optical_switch_id)
    return optical_switch_ref


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def optical_switch_update(context, optical_switch_id, values):
    return _optical_switch_update(context, values, optical_switch_id)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def optical_switch_destroy(context, optical_switch_id):
    """Destroy the optical_switch or raise if it does not exist."""
    session = get_session()
    with session.begin():
        optical_switch_ref = _optical_switch_get(context,
                                                 optical_switch_id,
                                                 session=session)
        optical_switch_ref.delete(session=session)
    return optical_switch_ref


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def hwm_add(context, values):
    """add hwm to daisy."""
    return _hwm_update(context, values, None)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def hwm_update(context, hwm_id, values):
    """update cluster template to daisy."""
    return _hwm_update(context, values, hwm_id)


def _hwm_update(context, values, hwm_id):
    """update or add hwm to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if hwm_id:
            hwm_ref = _hwm_get(context, hwm_id, session=session)
        else:
            hwm_ref = models.Hwm()

        if hwm_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Hwm, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if hwm_id:
            if values.get('id', None): del values['id']
            hwm_ref.update(values)
            _update_values(hwm_ref, values)
            try:
                hwm_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])
        else:
            hwm_ref.update(values)
            _update_values(hwm_ref, values)
            try:
                hwm_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

    return hwm_get(context, hwm_ref.id)


def hwm_destroy(context, hwm_id, session=None, force_show_deleted=False):
    session = session or get_session()
    with session.begin():
        hwm_ref = _hwm_get(context, hwm_id, session=session)
        hwm_ref.delete(session=session)
        return hwm_ref


def _hwm_get(context, hwm_id, session=None, force_show_deleted=False):
    """Get an hwm or raise if it does not exist."""
    session = session or get_session()
    try:
        query = session.query(models.Hwm).filter_by(id=hwm_id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        hwm = query.one()
        return hwm
    except sa_orm.exc.NoResultFound:
        msg = "No hwm found with ID %s" % hwm_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def hwm_get(context, hwm_id, session=None, force_show_deleted=False):
    hwm = _hwm_get(context, hwm_id, session=session,
                       force_show_deleted=force_show_deleted)
    return hwm


def hwm_get_all(context, filters=None, marker=None, limit=None, sort_key=None,
                sort_dir=None):
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}
    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_hwm = None
    if marker is not None:
        marker_hwm = _hwm_get(context, marker,
                              force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    query = session.query(models.Hwm).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.Hwm, limit, sort_key,
                            marker=marker_hwm,
                            sort_dir=None,
                            sort_dirs=sort_dir)
    hwms = []
    for hwm in query.all():
        hwm = hwm.to_dict()
        hwms.append(hwm)
    return hwms

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def template_add(context, values):
    """add cluster template to daisy."""
    return _template_update(context, values, None)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def template_update(context, template_id, values):
    """update cluster template to daisy."""
    return _template_update(context, values, template_id)

def _template_update(context, values, template_id):
    """update or add cluster template to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if template_id:
            template_ref = _template_get(context, template_id, session=session)
        else:
            template_ref = models.Template()

        if template_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Template, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if template_id:
            if values.get('id', None): del values['id']
            template_ref.update(values)
            _update_values(template_ref, values)
            try:
                template_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])
        else:
            template_ref.update(values)
            _update_values(template_ref, values)
            try:
                template_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

    return template_get(context, template_ref.id)

def _template_get(context, template_id, session=None, force_show_deleted=False):
    """Get an host or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.Template).filter_by(id=template_id)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        template = query.one()
        return template
    except sa_orm.exc.NoResultFound:
        msg = "No template found with ID %s" % template_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def template_get(context, template_id, session=None, force_show_deleted=False):
    template = _template_get(context, template_id, session=session,
                       force_show_deleted=force_show_deleted)
    return template

def template_destroy(context, template_id, session=None, force_show_deleted=False):
    session = session or get_session()
    with session.begin():
        template_ref = _template_get(context, template_id, session=session)
        template_ref.delete(session=session)
        return template_ref

def template_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_template = None
    if marker is not None:
        marker_template = _template_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    query = session.query(models.Template).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.Template, limit,
                            sort_key,
                            marker=marker_template,
                            sort_dir=None,
                            sort_dirs=sort_dir)
    if 'name' in filters:
        name = filters.pop('name')
        query = session.query(models.Template).filter_by(deleted=False).filter_by(name=name)
    if 'type' in filters:
        type = filters.pop('type')
        query = session.query(models.Template).filter_by(deleted=False).filter_by(type=type)
    templates = []
    for template in query.all():
        template = template.to_dict()
        templates.append(template)
    return templates

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def host_template_add(context, values):
    """add host template to daisy."""
    return _host_template_update(context, values, None)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def host_template_update(context, template_id, values):
    """update host template to daisy."""
    return _host_template_update(context, values, template_id)

def _host_template_update(context, values, template_id):
    """update or add cluster template to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if template_id:
            template_ref = _host_template_get(context, template_id, session=session)
        else:
            template_ref = models.HostTemplate()

        if template_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.HostTemplate, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if template_id:
            if values.get('id', None): del values['id']
            template_ref.update(values)
            _update_values(template_ref, values)
            try:
                template_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])
        else:
            template_ref.update(values)
            _update_values(template_ref, values)
            try:
                template_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

    return host_template_get(context, template_ref.id)

def _host_template_get(context, template_id, session=None, force_show_deleted=False):
    """Get an host or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.HostTemplate).filter_by(id=template_id)

        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        template = query.one()
        return template
    except sa_orm.exc.NoResultFound:
        msg = "No host_template found with ID %s" % template_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def host_template_get(context, template_id, session=None, force_show_deleted=False):
    template = _host_template_get(context, template_id, session=session,
                       force_show_deleted=force_show_deleted)
    return template

def host_template_destroy(context, template_id, session=None, force_show_deleted=False):
    session = session or get_session()
    with session.begin():
        template_ref = _host_template_get(context, template_id, session=session)
        template_ref.delete(session=session)
        return template_ref

def host_template_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_template = None
    if marker is not None:
        marker_template = _host_template_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()

    query = session.query(models.HostTemplate).filter_by(deleted=showing_deleted)

    query = _paginate_query(query, models.HostTemplate, limit,
                            sort_key,
                            marker=marker_template,
                            sort_dir=None,
                            sort_dirs=sort_dir)
    if 'cluster_name' in filters:
        cluster_name = filters.pop('cluster_name')
        query = session.query(models.HostTemplate).filter_by(deleted=False).filter_by(cluster_name=cluster_name)
    if 'name' in filters:
        name = filters.pop('name')
        query = session.query(models.HostTemplate).filter_by(deleted=False).filter_by(name=name)
    templates = []
    for template in query.all():
        template = template.to_dict()
        templates.append(template)
    return templates

def host_interfaces_get_all(context, filters=None):
    filters = filters or {}
    session = get_session()
    query = session.query(models.HostInterface).filter_by(deleted=0).filter_by(is_vf=False)

    if 'host_id' in filters:
        host_id = filters.pop('host_id')
        query = query.filter_by(id=host_id)
    if 'ip' in filters:
        ip = filters.pop('ip')
        query = query.filter_by(ip=ip)
    if 'mac' in filters:
        mac = filters.pop('mac')
        query = query.filter_by(mac=mac)
    if 'pci' in filters:
        pci = filters.pop('pci')
        query = query.filter_by(pci=pci)
    host_interfaces = []
    for host_interface in query.all():
        if host_interface.is_support_vf:
            host_interface.vf = _get_host_interface_vf_info(context,host_interface.id,session)
        host_interface = host_interface.to_dict()
        host_interfaces.append(host_interface)
    return host_interfaces

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def version_add(context, values):
    """add version to daisy."""
    return _version_update(context, values, None)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def version_update(context, version_id, values):
    """update version  to daisy."""
    return _version_update(context, values, version_id)

def _version_update(context, values, version_id):
    """update or add version to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if version_id:
            version_ref = _version_get(context, version_id, session=session)
        else:
            version_ref = models.Version()

        if version_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Version, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if version_id:
            if values.get('id', None): del values['id']
            version_ref.update(values)
            _update_values(version_ref, values)
            try:
                version_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])
        else:
            version_ref.update(values)
            _update_values(version_ref, values)
            try:
                version_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

    return version_get(context, version_ref.id)

def _version_get(context, version_id, session=None, force_show_deleted=False):
    """Get an host or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.Version).filter_by(id=version_id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        version = query.one()
        return version
    except sa_orm.exc.NoResultFound:
        msg = "No version found with ID %s" % version_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def version_get(context, version_id, session=None, force_show_deleted=False):
    version = _version_get(context, version_id, session=session,
                       force_show_deleted=force_show_deleted)
    return version


def version_destroy(context, version_id, session=None,
                    force_show_deleted=False):
    session = session or get_session()
    with session.begin():
        version_ref = _version_get(context, version_id, session=session)
        version_ref.delete(session=session)
        return version_ref


def version_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all versions that match zero or more filters.
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_version = None
    if marker is not None:
        marker_version = _version_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    if 'name' in filters:
        name = filters.pop('name')
        query = session.query(models.Version).filter_by(deleted=False).\
            filter_by(name=name)
    elif 'type' in filters:
        type = filters.pop('type')
        query = session.query(models.Version).filter_by(deleted=False).\
            filter_by(type=type)
    elif 'version' in filters:
        version = filters.pop('version')
        query = session.query(models.Version).filter_by(deleted=False).\
            filter_by(version=version)
    elif 'status' in filters:
        status = filters.pop('status')
        query = session.query(models.Version).filter_by(deleted=False).\
            filter_by(status=status)
    else:
        query = session.query(models.Version).filter_by(deleted=False)

    query = _paginate_query(query, models.Version, limit,
                        sort_key,
                        marker=marker_version,
                        sort_dir=None,
                        sort_dirs=sort_dir)

    versions = []
    for version in query.all():
        version_dict = version.to_dict()
        version_sql = "select * from hosts,clusters where (" \
                      "(hosts.os_version_id ='" + version_dict['id'] +\
                      "' or hosts.version_patch_id ='" + \
                      version_dict['id'] +"' or hosts.tecs_version_id ='"\
                      + version_dict['id'] +"' or hosts.tecs_patch_id ='"\
                      + version_dict['id'] +"') and hosts.deleted=0) or " \
                                            "(clusters.tecs_version_id='"\
                      + version_dict['id'] +"' and clusters.deleted=0)"
        hosts_number = session.execute(version_sql).fetchone()
        if hosts_number:
            version_dict['status'] = "used"
        else:
            version_dict['status'] = "unused"
        versions.append(version_dict)
    return versions


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def version_patch_add(context, values):
    """add version to daisy."""
    return _version_patch_update(context, values, None)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def version_patch_update(context, version_patch_id, values):
    """update version  to daisy."""
    return _version_patch_update(context, values, version_patch_id)

def _version_patch_update(context, values, version_patch_id):
    """update or add version patch to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if version_patch_id:
            version_patch_ref = _version_patch_get(context, version_patch_id,
                                                   session=session)
        else:
            version_patch_ref = models.VersionPatch()

        if version_patch_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.VersionPatch, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if version_patch_id:
            if values.get('id', None): del values['id']
            version_patch_ref.update(values)
            _update_values(version_patch_ref, values)
            try:
                version_patch_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("version patch ID %s already exists!"
                                          % values['id'])
        else:
            version_patch_ref.update(values)
            _update_values(version_patch_ref, values)
            try:
                version_patch_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("version patch ID %s already exists!"
                                          % values['id'])

    return version_patch_get(context, version_patch_ref.id)

@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def add_host_patch_history(context, values):
    """add version to daisy."""
    return _host_patch_history_update(context, values, None)

def _host_patch_history_update(context, values, patch_history_id):
    """update or add patch history to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if patch_history_id:
            patch_history_ref = _patch_history_get(context, patch_history_id,
                                                   session=session)
        else:
            patch_history_ref = models.HostPatchHistory()

        if patch_history_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.HostPatchHistory, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if patch_history_id:
            if values.get('id', None): del values['id']
            patch_history_ref.update(values)
            _update_values(patch_history_ref, values)
            try:
                patch_history_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("version patch ID %s already exists!"
                                          % values['id'])
        else:
            patch_history_ref.update(values)
            _update_values(patch_history_ref, values)
            try:
                patch_history_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("version patch ID %s already exists!"
                                          % values['id'])
    return patch_history_get(context, patch_history_ref.id)

def _patch_history_get(context, id, session=None,
                       force_show_deleted=False):
    """Get an patch history or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.HostPatchHistory).filter_by(
            id=id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        patch_history = query.one()
        return patch_history
    except sa_orm.exc.NoResultFound:
        msg = "No patch history patch found with ID %s" % id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def patch_history_get(context, id, session=None,
                      force_show_deleted=False):
    patch_history = _patch_history_get(context, id,
                                       session=session,
                                       force_show_deleted=force_show_deleted)
    return patch_history

def list_host_patch_history(context, filters=None, marker=None, limit=None,
                            sort_key=None, sort_dir=None):
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = False
    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    query = session.query(models.HostPatchHistory).filter_by(deleted=showing_deleted)
    if 'host_id' in filters and 'version_id' in filters:
        host_id = filters.pop('host_id')
        version_id = filters.pop('version_id')
        query = session.query(models.HostPatchHistory).\
            filter_by(deleted=False).filter_by(host_id=host_id).\
            filter_by(version_id=version_id)
    if 'host_id' in filters:
        host_id = filters.pop('host_id')
        query = session.query(models.HostPatchHistory).\
            filter_by(deleted=False).filter_by(host_id=host_id)
    if 'type' in filters:
        type = filters.pop('type')
        query = session.query(models.HostPatchHistory).\
            filter_by(deleted=False).filter_by(type=type)
    patchs = []
    for patch_history in query.all():
        patch = patch_history.to_dict()
        version_ref = _version_get(context, patch['version_id'])
        if version_ref:
            patch['version_name'] = version_ref.name
        patchs.append(patch)
    return patchs

def _version_patch_get(context, version_patch_id, session=None,
                       force_show_deleted=False):
    """Get an version patch or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.VersionPatch).filter_by(
            id=version_patch_id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        version = query.one()
        return version
    except sa_orm.exc.NoResultFound:
        msg = "No version patch found with ID %s" % version_patch_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def version_patch_get(context, version_patch_id, session=None,
                      force_show_deleted=False):
    version_patch = _version_patch_get(context, version_patch_id,
                                       session=session,
                                       force_show_deleted=force_show_deleted)
    return version_patch


def version_patch_destroy(context, version_patch_id, session=None,
                          force_show_deleted=False):
    session = session or get_session()
    with session.begin():
        version_patch_ref = _version_patch_get(context, version_patch_id,
                                               session=session)
        version_patch_ref.delete(session=session)
        return version_patch_ref


def version_patch_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None):
    """
    Get all version patchs that match zero or more filters.
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_version = None
    if marker is not None:
        marker_version = _version_patch_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id', 'version_id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)
    session = get_session()
    if 'name' in filters:
        name = filters.pop('name')
        query = session.query(models.VersionPatch).filter_by(deleted=False).\
            filter_by(name=name)
    elif 'type' in filters:
        type = filters.pop('type')
        query = session.query(models.VersionPatch).filter_by(deleted=False).\
            filter_by(type=type)
    elif 'version_id' in filters:
        version_id = filters.pop('version_id')
        query = session.query(models.VersionPatch).filter_by(deleted=False).\
            filter_by(version_id=version_id)
    else:
        query = session.query(models.VersionPatch).filter_by(deleted=False)

    query = _paginate_query(query, models.VersionPatch, limit,
                        sort_key,
                        marker=marker_version,
                        sort_dir=None,
                        sort_dirs=sort_dir)

    version_patchs = []
    for version_patch in query.all():
        version_dict = version_patch.to_dict()
        version_sql = "select * from hosts, host_patch_history where" \
                      " (hosts.version_patch_id ='" + version_dict['id'] +\
                      "' and hosts.deleted=0) or (hosts.id =" \
                      "host_patch_history.host_id and " \
                      "host_patch_history.patch_name='" + \
                      version_dict['name'] +"' and hosts.deleted=0 and " \
                                            "host_patch_history.deleted=0)"
        hosts_number = session.execute(version_sql).fetchone()
        if hosts_number:
            version_dict['status'] = "used"
        else:
            version_dict['status'] = "unused"
        version_patchs.append(version_dict)
    return version_patchs


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def template_config_import(context, values):
    def clear_template_config(session):
        table_classes = [models.ConfigService,
                         models.TemplateService,
                         models.TemplateConfig]
        for table_class in table_classes:
            session.query(table_class).delete()

    def import_template_config_service(session, config_id, service_id):
        config_service = {
            "config_id": config_id,
            "service_id": service_id}
        template_config_service_ref = models.ConfigService()
        template_config_service_ref.update(config_service)
        _update_values(template_config_service_ref, config_service)
        try:
            template_config_service_ref.save(session=session)
        except db_exception.DBDuplicateEntry:
            raise exception.Duplicate("Node %s already exists!"
                                      % config_service)

    def import_template_service(session, config_id, services):
        for service_name in services:
            template_service = {
                "service_name": service_name,
                "force_type": services[service_name].get("force_type")
            }
            template_service_ref = models.TemplateService()
            template_service_ref.update(template_service)
            _update_values(template_service_ref, template_service)
            try:
                template_service_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % template_service)
            import_template_config_service(session, config_id,
                                           template_service_ref.id)

    """import template function to daisy."""
    template = values.copy()
    template_configs = json.loads(template.get('template', None))
    session = get_session()
    with session.begin():
        clear_template_config(session)
        for config_id in template_configs:
            template_config_ref = models.TemplateConfig()
            template_config = template_configs[config_id]
            template_config.update({"id": config_id})
            if template_config.get("suggested_range"):
                template_config["suggested_range"] = json.dumps(
                    template_config["suggested_range"])
            else:
                template_config["suggested_range"] = None
            template_config_ref.update(template_config)
            _update_values(template_config_ref, template_config)
            try:
                template_config_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % config_id)
            service = template_configs[config_id].get("service", [])
            import_template_service(session, config_id, service)
    return values


def _template_config_update(context, values, template_config_id):
    """update or add template config to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if template_config_id:
            template_config_ref = _template_config_get(
                context, template_config_id, session=session)
        else:
            template_config_ref = models.TemplateConfig()

        if template_config_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.TemplateConfig, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if template_config_id:
            if values.get('id', None):
                del values['id']
            template_config_ref.update(values)
            _update_values(template_config_ref, values)
            try:
                template_config_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])
        else:
            template_config_ref.update(values)
            _update_values(template_config_ref, values)
            try:
                template_config_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

    return template_config_get(context, template_config_ref.id)


def _template_config_get(context, template_config_id, session=None,
                         force_show_deleted=False):
    """Get an host or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.TemplateConfig).\
            filter_by(id=template_config_id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        template_config = query.one()
        return template_config
    except sa_orm.exc.NoResultFound:
        msg = "No template config found with ID %s" % template_config_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def template_config_get(context, template_config_id, session=None,
                        force_show_deleted=False):
    session = get_session()
    try:
        config = session.query(models.TemplateConfig).filter_by(
            id=template_config_id).filter_by(deleted=False).one()
    except sa_orm.exc.NoResultFound:
        msg = "No template config found with ID %s" % template_config_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    try:
        template_func = session.query(models.TemplateFuncConfigs).filter_by(
            config_id=config.id).filter_by(deleted=False).one()
    except sa_orm.exc.NoResultFound:
        msg = "No template func found with config ID %s" % template_config_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    template_config_meta = config.to_dict()
    filters = [
        models.TemplateConfig.id == template_config_id,
        models.TemplateConfig.id == models.ConfigService.config_id,
        models.ConfigService.service_id == models.TemplateService.id]
    query = session.query(models.TemplateConfig, models.ConfigService,
                          models.TemplateService).filter(sa_sql.and_(*filters))

    template_services = []
    for item in query.all():
        if item.TemplateService not in template_services:
            template_services.append(item.TemplateService)

    service_meta = [service.to_dict() for service in template_services]
    template_config_meta.update({'services': service_meta})
    template_config_meta.update({'template_func_id': template_func.id})
    return template_config_meta


def template_config_get_all(context, filters=None, marker=None, limit=None,
                            sort_key=None, sort_dir=None):
    """
    Get all template_configs that match zero or more filters.
    """
    sort_key = ['created_at'] if not sort_key else sort_key
    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}
    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_template_config = None
    if marker is not None:
        marker_template_config = _template_config_get(
            context, marker, force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    query = session.query(models.TemplateConfig).filter_by(deleted=False)

    query = _paginate_query(query, models.TemplateConfig, limit,
                            sort_key,
                            marker=marker_template_config,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    template_configs = []
    for template_config in query.all():
        template_config_dict = template_config.to_dict()
        template_configs.append(template_config_dict)
    if 'func_id' in filters:
        func_id = filters.pop('func_id')
        query = session.query(models.TemplateFuncConfigs).\
            filter_by(deleted=False).filter_by(func_id=func_id)
        config_ids = []
        for template_func_config in query.all():
            template_func_config_dict = template_func_config.to_dict()
            config_ids.append(template_func_config_dict["config_id"])

        template_configs = [template_config
                            for template_config in template_configs
                            if template_config["id"] in config_ids]
    return template_configs


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def template_func_import(context, values):
    def clear_template_func(session):
        table_classes = [models.TemplateFuncConfigs, models.TemplateFunc]
        for table_class in table_classes:
            session.query(table_class).delete()

    def import_template_func_configs(session, func_id, configs):
        for config_id in configs:
            func_config = {
                "func_id": func_id,
                "config_id": config_id
            }
            template_func_config_ref = models.TemplateFuncConfigs()
            template_func_config_ref.update(func_config)
            _update_values(template_func_config_ref, func_config)
            try:
                template_func_config_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node %s already exists!"
                                          % func_config)

    """import template function to daisy."""
    template = values.copy()
    template_funcs = json.loads(template.get('template', None))
    session = get_session()
    with session.begin():
        clear_template_func(session)
        for func_id in template_funcs:
            template_func = template_funcs[func_id]
            template_func.update({"id": func_id})
            template_func_ref = models.TemplateFunc()
            template_func_ref.update(template_func)
            _update_values(template_func_ref, template_func)
            try:
                template_func_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % func_id)
            configs = template_funcs[func_id].get("config", [])
            import_template_func_configs(session, func_id, configs)
    return values


def _template_func_update(context, values, template_func_id):
    """update or add template function to daisy."""
    values = values.copy()
    session = get_session()
    with session.begin():
        if template_func_id:
            template_func_ref = _template_func_get(context, template_func_id, session=session)
        else:
            template_func_ref = models.TemplateFunc()

        if template_func_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.TemplateFunc, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if template_func_id:
            if values.get('id', None): del values['id']
            template_func_ref.update(values)
            _update_values(template_func_ref, values)
            try:
                template_func_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])
        else:
            template_func_ref.update(values)
            _update_values(template_func_ref, values)
            try:
                template_func_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Node ID %s already exists!"
                                          % values['id'])

    return template_func_get(context, template_func_ref.id)


def _template_func_get(context, template_func_id, session=None, force_show_deleted=False):
    """Get an host or raise if it does not exist."""
    session = session or get_session()
    try:
        query = session.query(models.TemplateFunc).filter_by(id=template_func_id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        template_func = query.one()
        return template_func
    except sa_orm.exc.NoResultFound:
        msg = "No template function found with ID %s" % template_func_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def template_func_get(context, template_func_id, filters=None, marker=None,
                      limit=None, sort_key=None, sort_dir=None):
    session = get_session()
    try:
        template_func = session.query(models.TemplateFunc).\
            filter_by(id=template_func_id).filter_by(deleted=False).one()
    except sa_orm.exc.NoResultFound:
        msg = "No template function found with ID %s" % template_func_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    template_func_metadata = template_func.to_dict()

    service_filter = [
        models.TemplateFunc.deleted == 0,
        models.TemplateFuncConfigs.deleted == 0,
        models.TemplateConfig.deleted == 0,
        models.ConfigService.deleted == 0,
        models.TemplateFuncConfigs.func_id == template_func_id,
        models.TemplateFuncConfigs.config_id ==
        models.TemplateConfig.id,
        models.TemplateConfig.id == models.ConfigService.config_id,
        models.ConfigService.service_id == models.TemplateService.id]
    query = session.query(models.TemplateFunc, models.TemplateFuncConfigs,
                          models.TemplateConfig, models.ConfigService,
                          models.TemplateService).\
        filter(sa_sql.and_(*service_filter))
    config_services = {}
    service_names = set()
    for item in query.all():
        if item.TemplateConfig not in config_services:
            config_services.update({item.TemplateConfig: set()})
        config_services[item.TemplateConfig].add(
            item.TemplateService.service_name)
        service_names.add(item.TemplateService.service_name)

    if 'cluster_id' in filters:
        service_hosts = {}
        host_filter = [
            models.Service.deleted == 0,
            models.ServiceRole.deleted == 0,
            models.Role.deleted == 0,
            models.HostRole.deleted == 0,
            models.Service.id == models.ServiceRole.service_id,
            models.ServiceRole.role_id == models.Role.id,
            models.Role.cluster_id == filters['cluster_id'],
            models.Role.id == models.HostRole.role_id,
            models.HostRole.status == 'active',
            models.Service.name.in_(service_names)]
        query = session.query(models.Service, models.ServiceRole,
                              models.Role, models.HostRole).\
            filter(sa_sql.and_(*host_filter))

        for item in query.all():
            if item.Service.name not in service_hosts:
                service_hosts.update({item.Service.name: set()})
            service_hosts[item.Service.name].add(item.HostRole.host_id)

        host_configs_dict = {}
        for config, services in config_services.items():
            for service in services:
                for host in service_hosts.get(service, []):
                    if host not in host_configs_dict:
                        host_configs_dict.update({host: set()})
                    host_configs_dict[host].add(config)

        host_configs_list = []
        for host_id, configs in host_configs_dict.items():
            host_config = {'host_id': host_id}
            config_list = [config.to_dict() for config in configs]
            host_config.update({'configs': config_list})
            host_configs_list.append(host_config)
        template_func_metadata.update({'template_configs': host_configs_list})
    else:
        configs_list = [config.to_dict() for config in config_services]
        template_func_metadata.update({'template_configs': configs_list})
    return template_func_metadata


def template_func_get_all(context, filters=None, marker=None, limit=None,
                          sort_key=None, sort_dir=None):
    """
    Get all template_func_configs that match zero or more filters.
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_template_func = None
    if marker is not None:
        marker_template_func = _template_func_get(
            context, marker, force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    query = session.query(models.TemplateFunc).filter_by(deleted=False)

    query = _paginate_query(query, models.TemplateFunc, limit,
                            sort_key,
                            marker=marker_template_func,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    template_funcs = []
    for template_func in query.all():
        template_func_dict = template_func.to_dict()
        template_funcs.append(template_func_dict)
    return template_funcs


def _template_service_get(context, template_service_id, session=None,
                          force_show_deleted=False):
    """Get an host or raise if it does not exist."""

    session = session or get_session()
    try:
        query = session.query(models.TemplateService).\
            filter_by(id=template_service_id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        template_service = query.one()
        return template_service
    except sa_orm.exc.NoResultFound:
        msg = "No template function found with ID %s" % template_service_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


def template_service_get(context, template_service_id, session=None,
                         force_show_deleted=False):
    template_service = _template_service_get(
        context, template_service_id, session=session,
        force_show_deleted=force_show_deleted)
    return template_service


def template_service_get_all(context, filters=None, marker=None, limit=None,
                             sort_key=None, sort_dir=None):
    """
    Get all template_service_configs that match zero or more filters.
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)
    marker_template_service = None
    if marker is not None:
        marker_template_service = _template_service_get(
            context, marker, force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    session = get_session()
    query = session.query(models.TemplateService).filter_by(deleted=False)

    query = _paginate_query(query, models.TemplateService, limit,
                            sort_key,
                            marker=marker_template_service,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    template_services = []
    for template_service in query.all():
        template_service_dict = template_service.to_dict()
        template_services.append(template_service_dict)

    if 'config_id' in filters:
        config_id = filters.pop('config_id')
        query = session.query(models.ConfigService).\
            filter_by(deleted=False).filter_by(config_id=config_id)
        service_ids = []
        for config_service in query.all():
            config_service_dict = config_service.to_dict()
            service_ids.append(config_service_dict["service_id"])
        template_services = [template_service
                             for template_service in template_services
                             if template_service["id"] in service_ids]
    return template_services


def _get_host_interface_vf_info(context, pf_interface_id, session = None):
    session = session or get_session()
    query = session.query(models.HostInterface).filter_by(deleted = False)
    if pf_interface_id:
        query = query.filter_by(parent_id = pf_interface_id)
    else:
        msg = "Physical interface ID is NULL"
        LOG.error(msg)
        raise exception.NotFound(msg)
    query = _paginate_query(query, models.HostInterface, None,
                            ['vf_index'],sort_dir = 'asc')
    vf_infos = []
    for vf_info in query.all():
        vf_dict = vf_info.to_dict()
        vf_infos.append(vf_dict)
    return vf_infos

def _update_host_interface_vf_info(context, host_id, pf_interface_id, vf_values, session):
    if vf_values and session:
        if not isinstance(vf_values, list):
            vf_values = list(eval(vf_values))
        for vm_info in vf_values:
            if 'slaves' in vm_info:
                slaves = vm_info.get('slaves', "")
                slaves = slaves.split()
                if len(slaves) == 1:
                    vm_info['slave1'] = slaves[0]
                elif len(slaves) == 2:
                    vm_info['slave1'] = slaves[0]
                    vm_info['slave2'] = slaves[1]
                del vm_info['slaves']
            if vm_info.has_key('index'):
                vm_info['vf_index'] = vm_info['index']
            if vm_info.has_key('id'):
                del vm_info['id']
            vm_info['is_vf'] = True
            vm_info['parent_id'] = pf_interface_id
            vm_info['host_id'] = host_id
            host_interface_ref = models.HostInterface()
            host_interface_ref.update(vm_info)
            _update_values(host_interface_ref, vm_info)
            host_interface_ref.save(session = session)


def _check_neutron_backend_id(neutron_backend_id):
    """
    check if the given project id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the project id
    length is longer than the defined length in database model.
    :param neutron_backend_id: The id of the project we want to check
    :return: Raise NoFound exception if given project id is invalid
    """
    if (neutron_backend_id and
       len(neutron_backend_id) > models.NeutronBackend.id.property.columns[0].type.length):
        raise exception.NotFound()


def _neutron_backend_get(context, neutron_backend_id=None, role_id=None,
                         marker=None, session=None, force_show_deleted=False):
    """Get an neutron_backend or raise if it does not exist."""
    if neutron_backend_id is not None:
        _check_neutron_backend_id(neutron_backend_id)
    session = session or get_session()

    try:
        if neutron_backend_id is not None:
            query = session.query(models.NeutronBackend).filter_by(id=neutron_backend_id).filter_by(deleted=False)
        elif role_id is not None:
            query = session.query(models.NeutronBackend).filter_by(role_id=role_id).filter_by(deleted=False)
        else:
            query = session.query(models.NeutronBackend).filter_by(deleted=False)
        # filter out deleted items if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        if neutron_backend_id is not None:
            neutron_backend = query.one()
        else:
            neutron_backend = query.all()
    except sa_orm.exc.NoResultFound:
        msg = "No neutron_backend found with ID %s" % neutron_backend_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return neutron_backend


def _neutron_backend_update(context, values, neutron_backend_id):
    """
    Used internally by neutron_backend_add and project_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param neutron_backend_id: If None, create the neutron_backend, otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()
    session = get_session()
    with session.begin():
        if neutron_backend_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.NeutronBackend, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()
            # Validate fields for projects table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            query = session.query(models.NeutronBackend).filter_by(id=neutron_backend_id).filter_by(deleted=False)
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('update neutron_backend_id %(neutron_backend_id)s failed') %
                       {'neutron_backend_id': neutron_backend_id})
                raise exception.Conflict(msg)
        else:
            neutron_backend_ref = models.NeutronBackend()
            neutron_backend_ref.update(values)
            _update_values(neutron_backend_ref, values)
            try:
                neutron_backend_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("neutron_backend ID %s already exists!"
                                          % values['id'])

            neutron_backend_id = neutron_backend_ref.id
    return _neutron_backend_get(context, neutron_backend_id)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def neutron_backend_add(context, values):
    """Add a neutron backend from the values dictionary."""
    return _neutron_backend_update(context, values, None)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def neutron_backend_destroy(context, neutron_backend_id):
    """Destroy the neutron_backend or raise if it does not exist."""
    session = get_session()
    with session.begin():
        neutron_backend_ref = _neutron_backend_get(context,
                                                   neutron_backend_id,
                                                   session=session)
        neutron_backend_ref.delete(session=session)
    return neutron_backend_ref


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def neutron_backend_update(context, neutron_backend_id, values):
    """
    Set the given properties on an cluster and update it.

    :raises NotFound if cluster does not exist.
    """
    return _neutron_backend_update(context, values, neutron_backend_id)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def neutron_backend_detail(context, neutron_backend_id):
    neutron_backend_ref = _neutron_backend_get(context, neutron_backend_id)
    return neutron_backend_ref


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def neutron_backend_list(context, filters=None, **param):
    """
    Get all neutron_backends that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the host properties attribute
    :param marker: host id after which to start page
    :param limit: maximum number of hosts to return
    :param sort_key: list of host attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    """
    filters = filters or {}

    role_id = None
    if 'role_id' in filters:
        role_id = filters.pop('role_id')

    neutron_backend_ref = _neutron_backend_get(context, role_id=role_id)
    return neutron_backend_ref

