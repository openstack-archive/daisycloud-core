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
# NOTE(jokke): simplified transition to py3, behaves like py2 xrange
from six.moves import range
import sqlalchemy
import sqlalchemy.orm as sa_orm
import sqlalchemy.sql as sa_sql
import types
import socket
import netaddr

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
        LOG.warn(_LW("Deadlock detected. Retrying..."))
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


def clear_db_env():
    """
    Unset global configuration variables for database.
    """
    global _FACADE
    _FACADE = None


def _check_mutate_authorization(context, image_ref):
    if not is_image_mutable(context, image_ref):
        LOG.warn(_LW("Attempted to modify image user did not own."))
        msg = _("You do not own this image")
        if image_ref.is_public:
            exc_class = exception.ForbiddenPublicImage
        else:
            exc_class = exception.Forbidden

        raise exc_class(msg)


def image_create(context, values):
    """Create an image from the values dictionary."""
    return _image_update(context, values, None, purge_props=False)


def image_update(context, image_id, values, purge_props=False,
                 from_state=None):
    """
    Set the given properties on an image and update it.

    :raises NotFound if image does not exist.
    """
    return _image_update(context, values, image_id, purge_props,
                         from_state=from_state)


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
def image_destroy(context, image_id):
    """Destroy the image or raise if it does not exist."""
    session = get_session()
    with session.begin():
        image_ref = _image_get(context, image_id, session=session)

        # Perform authorization check
        _check_mutate_authorization(context, image_ref)

        image_ref.delete(session=session)
        delete_time = image_ref.deleted_at

        _image_locations_delete_all(context, image_id, delete_time, session)

        _image_property_delete_all(context, image_id, delete_time, session)

        _image_member_delete_all(context, image_id, delete_time, session)

        _image_tag_delete_all(context, image_id, delete_time, session)

    return _normalize_locations(context, image_ref)

def _normalize_locations(context, image, force_show_deleted=False):
    """
    Generate suitable dictionary list for locations field of image.

    We don't need to set other data fields of location record which return
    from image query.
    """

    if image['status'] == 'deactivated' and not context.is_admin:
        # Locations are not returned for a deactivated image for non-admin user
        image['locations'] = []
        return image

    if force_show_deleted:
        locations = image['locations']
    else:
        locations = filter(lambda x: not x.deleted, image['locations'])
    image['locations'] = [{'id': loc['id'],
                           'url': loc['value'],
                           'metadata': loc['meta_data'],
                           'status': loc['status']}
                          for loc in locations]
    return image


def _normalize_tags(image):
    undeleted_tags = filter(lambda x: not x.deleted, image['tags'])
    image['tags'] = [tag['value'] for tag in undeleted_tags]
    return image


def image_get(context, image_id, session=None, force_show_deleted=False):
    image = _image_get(context, image_id, session=session,
                       force_show_deleted=force_show_deleted)
    image = _normalize_locations(context, image.to_dict(),
                                 force_show_deleted=force_show_deleted)
    return image


def _check_image_id(image_id):
    """
    check if the given image id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the image id
    length is longer than the defined length in database model.
    :param image_id: The id of the image we want to check
    :return: Raise NoFound exception if given image id is invalid
    """
    if (image_id and
       len(image_id) > models.Image.id.property.columns[0].type.length):
        raise exception.NotFound()


def _image_get(context, image_id, session=None, force_show_deleted=False):
    """Get an image or raise if it does not exist."""
    _check_image_id(image_id)
    session = session or get_session()

    try:
        query = session.query(models.Image).options(
            sa_orm.joinedload(models.Image.properties)).options(
                sa_orm.joinedload(
                    models.Image.locations)).filter_by(id=image_id)

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)

        image = query.one()

    except sa_orm.exc.NoResultFound:
        msg = "No image found with ID %s" % image_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    # Make sure they can look at it
    if not is_image_visible(context, image):
        msg = "Forbidding request, image %s not visible" % image_id
        LOG.debug(msg)
        raise exception.Forbidden(msg)

    return image

def _check_host_id(host_id):
    """
    check if the given host id is valid before executing operations. For
    now, we only check its length. The original purpose of this method is
    wrapping the different behaviors between MySql and DB2 when the host id
    length is longer than the defined length in database model.
    :param image_id: The id of the host we want to check
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

    sql_network_plane_cidr = "select networks.cidr from networks \
                              where networks.name='" + network_plane_name + \
                             "' and networks.cluster_id='" + cluster_id + \
                             "' and networks.deleted=0"
    query_network_plane_cidr = \
        session.execute(sql_network_plane_cidr).fetchone()
    network_cidr = query_network_plane_cidr.values().pop()
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
            if query_network_plane_tmp_info[2] == 'MANAGEMENT':
                roles_info_sql = "select roles.db_vip,roles.glance_vip,\
                                 roles.vip from roles where \
                                 roles.cluster_id='" + cluster_id + \
                                 "' and roles.deleted=0"
                roles_vip = session.execute(roles_info_sql).fetchall()
                available_ip_list.extend([vip for role_vip in
                                          roles_vip for vip in
                                          role_vip if vip])

    for network_id in equal_cidr_network_plane_id_list:
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
# merged_networks=[{'name':'MAGEMENT','ip':"10.43.177.2"},{'name':'DEPLOYMENT,STORAGE','ip':""}]
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
        networks_name = []
        networks_ip = ''
        for network in networks:
            networks_name.append(network['name'])
            if not networks_ip:
                networks_ip = network.get('ip')
        merged_networks.append({'name': ','.join(networks_name),
                                'ip': networks_ip})

    return merged_networks


def check_ip_exist_and_in_cidr_range(cluster_id, network_plane_name,
                                     network_plane_ip,
                                     occupied_network_ips, session):
    # equal_cidr_network_plane_id = []

    check_ip_if_valid = _checker_the_ip_or_hostname_valid(network_plane_ip)
    if not check_ip_if_valid:
        msg = "Error:The %s is not the right ip!" % network_plane_ip
        LOG.error(msg)
        raise exception.Forbidden(msg)

    sql_network_plane_cidr = \
        "select networks.cidr from networks \
        where networks.name='" + network_plane_name + \
        "' and networks.cluster_id='" + cluster_id + \
        "' and networks.deleted=0"
    query_network_plane_cidr = \
        session.execute(sql_network_plane_cidr).fetchone()
    network_cidr = query_network_plane_cidr.values().pop()

    check_ip_if_in_cidr = is_in_cidr_range(network_plane_ip, network_cidr)
    if not check_ip_if_in_cidr:
        msg = "Error:The ip %s is not in cidr %s range!" \
              % (network_plane_ip, network_cidr)
        raise exception.Forbidden(msg)

    available_ip_list = \
        get_ip_with_equal_cidr(cluster_id, network_plane_name, session)
    # allow different networks with same ip in the same interface
    if (network_plane_ip in available_ip_list or
       network_plane_ip in occupied_network_ips):
        msg = "Error:The IP %s already exist." % network_plane_ip
        LOG.error(msg)
        raise exception.Forbidden(msg)


def check_ip_ranges(ip_ranges_one,available_ip_list):
    ip_range = copy.deepcopy(ip_ranges_one.values())
    ip_ranges_end = ip_range.pop()
    ip_ranges_start = ip_range.pop()
    inter_num = ip_into_int(ip_ranges_start)
    ip_ranges_end_inter = ip_into_int(ip_ranges_end)
    while True:
        inter_tmp = inter_num
        ip_tmp = inter_into_ip(inter_tmp)
        if ip_tmp not in available_ip_list:
            if inter_tmp > ip_ranges_end_inter:
                msg = "warning:The IP address assigned \
                        by IP ranges is already insufficient."
                LOG.warn(msg)
                break
            else:
                return [True, ip_tmp]
        else:
            inter_num = inter_tmp + 1

    return [False, None]


def change_host_name(values, mangement_ip,host_ref):
    if mangement_ip and host_ref.os_status != "active":
        values['name'] = "host-" + mangement_ip.replace('.', '-')


def compare_same_cidr_ip(x, y):
    return eval(x[0].split('.').pop()) - eval(y[0].split('.').pop())


def according_to_cidr_distribution_ip(cluster_id, network_plane_name,
                                      session, exclude_ips=[]):
    ip_ranges_cidr = []
    distribution_ip = ""

    sql_network_plane_info = "select networks.id,networks.cidr,\
                             networks.network_type from networks \
                             where networks.name='" + network_plane_name + \
                             "' and networks.cluster_id='" + cluster_id + \
                             "' and networks.deleted=0"
    query_network_plane_info = \
        session.execute(sql_network_plane_info).fetchone()
    network_id = query_network_plane_info.values()[0]
    network_cidr = query_network_plane_info.values()[1]
    network_type = query_network_plane_info.values()[2]

    if network_type not in ['DATAPLANE','EXTERNAL']:
        available_ip_list = get_ip_with_equal_cidr(
            cluster_id, network_plane_name, session, exclude_ips)
        sql_ip_ranges = "select ip_ranges.start,end from \
                         ip_ranges where network_id='" + network_id + \
                        "' and ip_ranges.deleted=0"
        query_ip_ranges = session.execute(sql_ip_ranges).fetchall()
        query_ip_ranges = sorted(query_ip_ranges, cmp=compare_same_cidr_ip)
        if query_ip_ranges:
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
        else:
            ip_ranges_cidr = cidr_convert_ip_ranges(network_cidr)
            ip_min_inter = ip_into_int(ip_ranges_cidr[0])
            ip_max_inter = ip_into_int(ip_ranges_cidr[1])
            while True:
                distribution_ip = inter_into_ip(ip_min_inter + 1)
                if distribution_ip not in available_ip_list:
                    distribution_ip_inter = ip_into_int(distribution_ip)
                    if distribution_ip_inter < ip_max_inter:
                        break
                    else:
                        msg = "Error:The IP address assigned by \
                              CIDR is already insufficient."
                        LOG.error(msg)
                        raise exception.Forbidden(msg)
                else:
                    ip_min_inter = ip_min_inter + 1
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
    # assigned_networks_ip = []
    # management_ip = ""

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
            if values.has_key("os_version") and \
               utils.is_uuid_like(values['os_version']):
                host_ref.os_version_id = values['os_version']
            elif(values.has_key("os_version") and not
                 utils.is_uuid_like(values['os_version'])):
                host_ref.os_version_file = values['os_version']
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
                    host_interface_ref = models.HostInterface()
                    host_interface_ref.update(host_interfaces_values)
                    host_interface_ref.host_id = host_id
                    _update_values(host_interface_ref, host_interfaces_values)
                    host_interface_ref.save(session=session)

                    if values.has_key('cluster'):
                        if network.has_key('assigned_networks'):
                            occupied_network_ips = []
                            merged_assigned_networks = \
                                merge_networks_for_unifiers(
                                    values['cluster'],
                                    network['assigned_networks'])
                            for networks_plane in merged_assigned_networks:
                                network_plane_names = \
                                    networks_plane['name'].split(',')
                                network_plane_ip = networks_plane.get('ip')
                                if network_plane_ip:
                                    check_ip_exist_and_in_cidr_range(
                                        values['cluster'],
                                        network_plane_names[0],
                                        network_plane_ip,
                                        occupied_network_ips,
                                        session)
                                    occupied_network_ips.append(
                                        network_plane_ip)
                                else:
                                    network_plane_ip = \
                                        according_to_cidr_distribution_ip(
                                            values['cluster'],
                                            network_plane_names[0],
                                            session)

                                if 'MANAGEMENT' in network_plane_names:
                                    change_host_name(values, network_plane_ip,
                                                     host_ref)
                                    # management_ip = network_plane_ip
                                add_assigned_networks_data(
                                    context, network, values['cluster'],
                                    host_interface_ref, network_plane_names,
                                    network_plane_ip, session)

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
            if values.has_key("os_version") and \
               utils.is_uuid_like(values['os_version']):
                host_ref.os_version_id = values['os_version']
            elif(values.has_key("os_version") and not 
                 utils.is_uuid_like(values['os_version'])):
                host_ref.os_version_file = values['os_version']

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
                    host_interfaces_values['host_id'] = host_ref.id
                    host_interface_ref.update(host_interfaces_values)
                    _update_values(host_interface_ref, host_interfaces_values)
                    host_interface_ref.save(session=session)

                    if values.has_key('cluster'):
                        if network.has_key('assigned_networks'):
                            occupied_network_ips = []
                            merged_assigned_networks = \
                                merge_networks_for_unifiers(
                                    values['cluster'],
                                    network['assigned_networks'])
                            for networks_plane in merged_assigned_networks:
                                network_plane_names = \
                                    networks_plane['name'].split(',')
                                network_plane_ip = networks_plane.get('ip')
                                if network_plane_ip:
                                    check_ip_exist_and_in_cidr_range(
                                        values['cluster'],
                                        network_plane_names[0],
                                        network_plane_ip,
                                        occupied_network_ips,
                                        session)
                                    occupied_network_ips.append(
                                        network_plane_ip)
                                else:
                                    network_plane_ip = \
                                        according_to_cidr_distribution_ip(
                                            values['cluster'],
                                            network_plane_names[0],
                                            session)
                                if 'MANAGEMENT' in network_plane_names:
                                    change_host_name(values, network_plane_ip,
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
    return host_get(context, host_ref.id)


def _host_get(context, host_id, session=None, force_show_deleted=False):
    """Get an host or raise if it does not exist."""
    _check_host_id(host_id)
    session = session or get_session()

    try:
        query = session.query(models.Host).filter_by(id=host_id)

        # filter out deleted images if context disallows it
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

        # filter out deleted images if context disallows it
        if not force_show_deleted:
            query = query.filter_by(deleted=False)

        host_interface = query.all()

        for interface in host_interface:
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
                                              'ip': assignnetwork.ip}

                    assigned_networks_list.append(assigned_networks_info)
                    if query_network.network_type in ['DATAPLANE']:
                        openvswitch_type = assignnetwork.vswitch_type
            interface.assigned_networks = assigned_networks_list
            interface.vswitch_type = openvswitch_type

    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)

    return host_interface


def get_host_interface_mac(context, mac, session=None,
                           force_show_deleted=False):
    session = session or get_session()
    try:
        query = session.query(models.HostInterface).filter_by(
            mac=mac).filter_by(deleted=False)
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
        query = session.query(models.version).filter_by(id=version_id)

        # filter out deleted images if context disallows it
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
        delete_host_interface(context, host_id)
        host_ref.delete(session=session)

    return host_ref


def host_update(context, host_id, values):
    """
    Set the given properties on an image and update it.

    :raises NotFound if host does not exist.
    """
    return _host_update(context, values, host_id)


def discover_host_add(context, values):
    """Add an discover host from the values dictionary."""
    return _discover_host_update(context, values, None)


def discover_host_update(context, discover_host_id, values):
    """
    Set the given properties on an image and update it.

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

        # filter out deleted images if context disallows it
        if not force_show_deleted and not context.can_see_deleted:
            query = query.filter_by(deleted=False)
        discover_host = query.one()
        return discover_host
    except sa_orm.exc.NoResultFound:
        msg = "No host found with ID %s" % discover_host_id
        LOG.debug(msg)
        raise exception.NotFound(msg)


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
        # filter out deleted images if context disallows it
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
    :param image_id: The id of the project we want to check
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
                values['net_l23_provider'] = \
                    network_params.get('net_l23_provider', None)
                values['base_mac'] = network_params.get('base_mac', None)
                values['segmentation_type'] = \
                    network_params.get('segmentation_type', None)
                values['public_vip'] = network_params.get('public_vip', None)

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

            role_query = \
                session.query(models.Role).filter_by(
                    type="template", cluster_id=None).filter_by(
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
    :param image_id: The id of the component we want to check
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
    Set the given properties on an image and update it.

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
        # filter out deleted images if context disallows it
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
        # filter out deleted images if context disallows it
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
        # filter out deleted images if context disallows it
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
        # filter out deleted images if context disallows it
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
        # filter out deleted images if context disallows it
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
        # filter out deleted images if context disallows it
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
    :param image_id: The id of the service we want to check
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
    Set the given properties on an image and update it.

    :raises NotFound if service does not exist.
    """
    return _service_update(context, values, service_id)


def _service_get(context, service_id, session=None, force_show_deleted=False):
    """Get an service or raise if it does not exist."""
    _check_service_id(service_id)
    session = session or get_session()

    try:
        query = session.query(models.Service).filter_by(id=service_id).filter_by(deleted=False)
        # filter out deleted images if context disallows it
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
    :param image_id: The id of the role we want to check
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
    Set the given properties on an image and update it.

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
        # filter out deleted images if context disallows it
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
        # If uninstalling tecs, we reset the role_progress value to (100 - role_progress)
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
        # filter out deleted images if context disallows it
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
        # filter out deleted images if context disallows it
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
    :param image_id: The id of the role we want to check
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

def is_image_mutable(context, image):
    """Return True if the image is mutable in this context."""
    # Is admin == image mutable
    if context.is_admin:
        return True

    # No owner == image not mutable
    if image['owner'] is None or context.owner is None:
        return False

    # Image only mutable by its owner
    return image['owner'] == context.owner


def is_image_visible(context, image, status=None):
    """Return True if the image is visible in this context."""
    # Is admin == image visible
    if context.is_admin:
        return True

    # No owner == image visible
    if image['owner'] is None:
        return True

    # Image is_public == image visible
    if image['is_public']:
        return True

    # Perform tests based on whether we have an owner
    if context.owner is not None:
        if context.owner == image['owner']:
            return True

        # Figure out if this image is shared with that tenant
        members = image_member_find(context,
                                    image_id=image['id'],
                                    member=context.owner,
                                    status=status)
        if members:
            return True

    # Private image
    return False


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
        LOG.warn(_LW('Id not in sort_keys; is sort_keys unique?'))

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


def _make_conditions_from_filters(filters, is_public=None):
    # NOTE(venkatesh) make copy of the filters are to be altered in this
    # method.
    filters = filters.copy()

    image_conditions = []
    prop_conditions = []
    tag_conditions = []

    if is_public is not None:
        image_conditions.append(models.Image.is_public == is_public)

    if 'checksum' in filters:
        checksum = filters.pop('checksum')
        image_conditions.append(models.Image.checksum == checksum)

    if 'is_public' in filters:
        key = 'is_public'
        value = filters.pop('is_public')
        prop_filters = _make_image_property_condition(key=key, value=value)
        prop_conditions.append(prop_filters)

    for (k, v) in filters.pop('properties', {}).items():
        prop_filters = _make_image_property_condition(key=k, value=v)
        prop_conditions.append(prop_filters)

    if 'changes-since' in filters:
        # normalize timestamp to UTC, as sqlalchemy doesn't appear to
        # respect timezone offsets
        changes_since = timeutils.normalize_time(filters.pop('changes-since'))
        image_conditions.append(models.Image.updated_at > changes_since)

    if 'deleted' in filters:
        deleted_filter = filters.pop('deleted')
        image_conditions.append(models.Image.deleted == deleted_filter)
        # TODO(bcwaldon): handle this logic in registry server
        if not deleted_filter:
            image_statuses = [s for s in STATUSES if s != 'killed']
            image_conditions.append(models.Image.status.in_(image_statuses))

    if 'tags' in filters:
        tags = filters.pop('tags')
        for tag in tags:
            tag_filters = [models.ImageTag.deleted == False]
            tag_filters.extend([models.ImageTag.value == tag])
            tag_conditions.append(tag_filters)

    filters = dict([(k, v) for k, v in filters.items() if v is not None])

    for (k, v) in filters.items():
        key = k
        if k.endswith('_min') or k.endswith('_max'):
            key = key[0:-4]
            try:
                v = int(filters.pop(k))
            except ValueError:
                msg = _("Unable to filter on a range "
                        "with a non-numeric value.")
                raise exception.InvalidFilterRangeValue(msg)

            if k.endswith('_min'):
                image_conditions.append(getattr(models.Image, key) >= v)
            if k.endswith('_max'):
                image_conditions.append(getattr(models.Image, key) <= v)

    for (k, v) in filters.items():
        value = filters.pop(k)
        if hasattr(models.Image, k):
            image_conditions.append(getattr(models.Image, k) == value)
        else:
            prop_filters = _make_image_property_condition(key=k, value=value)
            prop_conditions.append(prop_filters)

    return image_conditions, prop_conditions, tag_conditions


def _make_image_property_condition(key, value):
    prop_filters = [models.ImageProperty.deleted == False]
    prop_filters.extend([models.ImageProperty.name == key])
    prop_filters.extend([models.ImageProperty.value == value])
    return prop_filters


def _select_images_query(context, image_conditions, admin_as_user,
                         member_status, visibility):
    session = get_session()

    img_conditional_clause = sa_sql.and_(*image_conditions)

    regular_user = (not context.is_admin) or admin_as_user

    query_member = session.query(models.Image).join(
        models.Image.members).filter(img_conditional_clause)
    if regular_user:
        member_filters = [models.ImageMember.deleted == False]
        if context.owner is not None:
            member_filters.extend([models.ImageMember.member == context.owner])
            if member_status != 'all':
                member_filters.extend([
                    models.ImageMember.status == member_status])
        query_member = query_member.filter(sa_sql.and_(*member_filters))

    # NOTE(venkatesh) if the 'visibility' is set to 'shared', we just
    # query the image members table. No union is required.
    if visibility is not None and visibility == 'shared':
        return query_member

    query_image = session.query(models.Image).filter(img_conditional_clause)
    if regular_user:
        query_image = query_image.filter(models.Image.is_public == True)
        query_image_owner = None
        if context.owner is not None:
            query_image_owner = session.query(models.Image).filter(
                models.Image.owner == context.owner).filter(
                    img_conditional_clause)
        if query_image_owner is not None:
            query = query_image.union(query_image_owner, query_member)
        else:
            query = query_image.union(query_member)
        return query
    else:
        # Admin user
        return query_image


def image_get_all(context, filters=None, marker=None, limit=None,
                  sort_key=None, sort_dir=None,
                  member_status='accepted', is_public=None,
                  admin_as_user=False, return_tag=False):
    """
    Get all images that match zero or more filters.

    :param filters: dict of filter keys and values. If a 'properties'
                    key is present, it is treated as a dict of key/value
                    filters on the image properties attribute
    :param marker: image id after which to start page
    :param limit: maximum number of images to return
    :param sort_key: list of image attributes by which results should be sorted
    :param sort_dir: directions in which results should be sorted (asc, desc)
    :param member_status: only return shared images that have this membership
                          status
    :param is_public: If true, return only public images. If false, return
                      only private and shared images.
    :param admin_as_user: For backwards compatibility. If true, then return to
                      an admin the equivalent set of images which it would see
                      if it was a regular user
    :param return_tag: To indicates whether image entry in result includes it
                       relevant tag entries. This could improve upper-layer
                       query performance, to prevent using separated calls
    """
    sort_key = ['created_at'] if not sort_key else sort_key

    default_sort_dir = 'desc'

    if not sort_dir:
        sort_dir = [default_sort_dir] * len(sort_key)
    elif len(sort_dir) == 1:
        default_sort_dir = sort_dir[0]
        sort_dir *= len(sort_key)

    filters = filters or {}

    visibility = filters.pop('visibility', None)
    showing_deleted = 'changes-since' in filters or filters.get('deleted',
                                                                False)

    img_cond, prop_cond, tag_cond = _make_conditions_from_filters(
        filters, is_public)

    query = _select_images_query(context,
                                 img_cond,
                                 admin_as_user,
                                 member_status,
                                 visibility)

    if visibility is not None:
        if visibility == 'publicAPI':
            query = query.filter(models.Image.is_public == True)
        elif visibility == 'dataplane':
            query = query.filter(models.Image.is_public == False)

    if prop_cond:
        for prop_condition in prop_cond:
            query = query.join(models.ImageProperty, aliased=True).filter(
                sa_sql.and_(*prop_condition))

    if tag_cond:
        for tag_condition in tag_cond:
            query = query.join(models.ImageTag, aliased=True).filter(
                sa_sql.and_(*tag_condition))

    marker_image = None
    if marker is not None:
        marker_image = _image_get(context,
                                  marker,
                                  force_show_deleted=showing_deleted)

    for key in ['created_at', 'id']:
        if key not in sort_key:
            sort_key.append(key)
            sort_dir.append(default_sort_dir)

    query = _paginate_query(query, models.Image, limit,
                            sort_key,
                            marker=marker_image,
                            sort_dir=None,
                            sort_dirs=sort_dir)

    query = query.options(sa_orm.joinedload(
        models.Image.properties)).options(
            sa_orm.joinedload(models.Image.locations))
    if return_tag:
        query = query.options(sa_orm.joinedload(models.Image.tags))

    images = []
    for image in query.all():
        image_dict = image.to_dict()
        image_dict = _normalize_locations(context, image_dict,
                                          force_show_deleted=showing_deleted)
        if return_tag:
            image_dict = _normalize_tags(image_dict)
        images.append(image_dict)
    return images
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
        sql = "select hosts.*  from hosts ,cluster_hosts where hosts.deleted=0 and hosts.status='in-cluster' and cluster_hosts.cluster_id ='"+cluster_id +"' and cluster_hosts.host_id=hosts.id and cluster_hosts.deleted=0"
        query = session.execute(sql).fetchall()
        hosts = []
        for host in query:
            host_dict = dict(host.items())
            hosts.append(host_dict)
        sql = "select hosts.*,cluster_hosts.cluster_id as cluster_id," \
            "host_roles.progress as role_progress,host_roles.status as role_status," \
            "host_roles.messages as role_messages from cluster_hosts ,hosts,roles,host_roles \
              where hosts.deleted=0 and cluster_hosts.cluster_id ='"+cluster_id +"' and cluster_hosts.deleted=0 \
              and roles.deleted=0 and roles.cluster_id='" + cluster_id+ "'\
              and cluster_hosts.host_id=hosts.id \
              and host_roles.role_id = roles.id \
              and host_roles.host_id = hosts.id and host_roles.deleted=0 group by hosts.id"
        query = session.execute(sql).fetchall()
        for host in query:
            host_dict = dict(host.items())
            hosts.append(host_dict)
        return hosts
    elif 'cluster_id' in filters and 'status' in filters:
        status = filters.pop('status')
        cluster_id = filters.pop('cluster_id')
        if status == 'in-cluster':
            sql = "select hosts.* from hosts ,cluster_hosts where hosts.deleted=0 and hosts.status='in-cluster' and cluster_hosts.cluster_id ='"+cluster_id +"' and cluster_hosts.host_id=hosts.id and cluster_hosts.deleted=0"
            query = session.execute(sql).fetchall()
            hosts = []
            for host in query:
                host_dict = dict(host.items())
                hosts.append(host_dict)
            return hosts
        if status == 'with-role':
            sql = "select hosts.*,cluster_hosts.cluster_id as cluster_id," \
            "host_roles.progress as role_progress,host_roles.status as role_status," \
            "host_roles.messages as role_messages from cluster_hosts ,hosts,roles,host_roles \
              where hosts.deleted=0 and cluster_hosts.cluster_id ='"+cluster_id +"' and cluster_hosts.deleted=0 \
              and roles.deleted=0 and roles.cluster_id='" + cluster_id+ "'\
              and cluster_hosts.host_id=hosts.id \
              and host_roles.role_id = roles.id \
              and host_roles.host_id = hosts.id and host_roles.deleted=0 group by hosts.id"
            query = session.execute(sql).fetchall()
            hosts = []
            for host in query:
                host_dict = dict(host.items())
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


def _image_get_disk_usage_by_owner(owner, session, image_id=None):
    query = session.query(models.Image)
    query = query.filter(models.Image.owner == owner)
    if image_id is not None:
        query = query.filter(models.Image.id != image_id)
    query = query.filter(models.Image.size > 0)
    query = query.filter(~models.Image.status.in_(['killed', 'deleted']))
    images = query.all()

    total = 0
    for i in images:
        locations = [l for l in i.locations if l['status'] != 'deleted']
        total += (i.size * len(locations))
    return total


def _validate_image(values):
    """
    Validates the incoming data and raises a Invalid exception
    if anything is out of order.

    :param values: Mapping of image metadata to check
    """

    status = values.get('status')
    if not status:
        msg = "Image status is required."
        raise exception.Invalid(msg)

    if status not in STATUSES:
        msg = "Invalid image status '%s' for image." % status
        raise exception.Invalid(msg)

    return values


def _update_values(image_ref, values):
    for k in values:
        if getattr(image_ref, k) != values[k]:
            setattr(image_ref, k, values[k])


@retry(retry_on_exception=_retry_on_deadlock, wait_fixed=500,
       stop_max_attempt_number=50)
@utils.no_4byte_params
def _image_update(context, values, image_id, purge_props=False,
                  from_state=None):
    """
    Used internally by image_create and image_update

    :param context: Request context
    :param values: A dict of attributes to set
    :param image_id: If None, create the image, otherwise, find and update it
    """

    # NOTE(jbresnah) values is altered in this so a copy is needed
    values = values.copy()

    session = get_session()
    with session.begin():

        # Remove the properties passed in the values mapping. We
        # handle properties separately from base image attributes,
        # and leaving properties in the values mapping will cause
        # a SQLAlchemy model error because SQLAlchemy expects the
        # properties attribute of an Image model to be a list and
        # not a dict.
        properties = values.pop('properties', {})

        location_data = values.pop('locations', None)

        new_status = values.get('status', None)
        if image_id:
            image_ref = _image_get(context, image_id, session=session)
            current = image_ref.status
            # Perform authorization check
            _check_mutate_authorization(context, image_ref)
        else:
            if values.get('size') is not None:
                values['size'] = int(values['size'])

            if 'min_ram' in values:
                values['min_ram'] = int(values['min_ram'] or 0)

            if 'min_disk' in values:
                values['min_disk'] = int(values['min_disk'] or 0)

            values['is_public'] = bool(values.get('is_public', False))
            values['protected'] = bool(values.get('protected', False))
            image_ref = models.Image()

        # Need to canonicalize ownership
        if 'owner' in values and not values['owner']:
            values['owner'] = None

        if image_id:
            # Don't drop created_at if we're passing it in...
            _drop_protected_attrs(models.Image, values)
            # NOTE(iccha-sethi): updated_at must be explicitly set in case
            #                   only ImageProperty table was modifited
            values['updated_at'] = timeutils.utcnow()

        if image_id:
            query = session.query(models.Image).filter_by(id=image_id)
            if from_state:
                query = query.filter_by(status=from_state)

            if new_status:
                _validate_image(values)

            # Validate fields for Images table. This is similar to what is done
            # for the query result update except that we need to do it prior
            # in this case.
            # TODO(dosaboy): replace this with a dict comprehension once py26
            #                support is deprecated.
            keys = values.keys()
            for k in keys:
                if k not in image_ref.to_dict():
                    del values[k]
            updated = query.update(values, synchronize_session='fetch')

            if not updated:
                msg = (_('cannot transition from %(current)s to '
                         '%(next)s in update (wanted '
                         'from_state=%(from)s)') %
                       {'current': current, 'next': new_status,
                        'from': from_state})
                raise exception.Conflict(msg)

            image_ref = _image_get(context, image_id, session=session)
        else:
            image_ref.update(values)
            # Validate the attributes before we go any further. From my
            # investigation, the @validates decorator does not validate
            # on new records, only on existing records, which is, well,
            # idiotic.
            values = _validate_image(image_ref.to_dict())
            _update_values(image_ref, values)

            try:
                image_ref.save(session=session)
            except db_exception.DBDuplicateEntry:
                raise exception.Duplicate("Image ID %s already exists!"
                                          % values['id'])

        _set_properties_for_image(context, image_ref, properties, purge_props,
                                  session)

        if location_data is not None:
            _image_locations_set(context, image_ref.id, location_data,
                                 session=session)

    return image_get(context, image_ref.id)

@utils.no_4byte_params
def image_location_add(context, image_id, location, session=None):
    deleted = location['status'] in ('deleted', 'pending_delete')
    delete_time = timeutils.utcnow() if deleted else None
    location_ref = models.ImageLocation(image_id=image_id,
                                        value=location['url'],
                                        meta_data=location['metadata'],
                                        status=location['status'],
                                        deleted=deleted,
                                        deleted_at=delete_time)
    session = session or get_session()
    location_ref.save(session=session)


@utils.no_4byte_params
def image_location_update(context, image_id, location, session=None):
    loc_id = location.get('id')
    if loc_id is None:
        msg = _("The location data has an invalid ID: %d") % loc_id
        raise exception.Invalid(msg)

    try:
        session = session or get_session()
        location_ref = session.query(models.ImageLocation).filter_by(
            id=loc_id).filter_by(image_id=image_id).one()

        deleted = location['status'] in ('deleted', 'pending_delete')
        updated_time = timeutils.utcnow()
        delete_time = updated_time if deleted else None

        location_ref.update({"value": location['url'],
                             "meta_data": location['metadata'],
                             "status": location['status'],
                             "deleted": deleted,
                             "updated_at": updated_time,
                             "deleted_at": delete_time})
        location_ref.save(session=session)
    except sa_orm.exc.NoResultFound:
        msg = (_("No location found with ID %(loc)s from image %(img)s") %
               dict(loc=loc_id, img=image_id))
        LOG.warn(msg)
        raise exception.NotFound(msg)


def image_location_delete(context, image_id, location_id, status,
                          delete_time=None, session=None):
    if status not in ('deleted', 'pending_delete'):
        msg = _("The status of deleted image location can only be set to "
                "'pending_delete' or 'deleted'")
        raise exception.Invalid(msg)

    try:
        session = session or get_session()
        location_ref = session.query(models.ImageLocation).filter_by(
            id=location_id).filter_by(image_id=image_id).one()

        delete_time = delete_time or timeutils.utcnow()

        location_ref.update({"deleted": True,
                             "status": status,
                             "updated_at": delete_time,
                             "deleted_at": delete_time})
        location_ref.save(session=session)
    except sa_orm.exc.NoResultFound:
        msg = (_("No location found with ID %(loc)s from image %(img)s") %
               dict(loc=location_id, img=image_id))
        LOG.warn(msg)
        raise exception.NotFound(msg)


def _image_locations_set(context, image_id, locations, session=None):
    # NOTE(zhiyan): 1. Remove records from DB for deleted locations
    session = session or get_session()
    query = session.query(models.ImageLocation).filter_by(
        image_id=image_id).filter_by(
            deleted=False).filter(~models.ImageLocation.id.in_(
                [loc['id']
                 for loc in locations
                 if loc.get('id')]))
    for loc_id in [loc_ref.id for loc_ref in query.all()]:
        image_location_delete(context, image_id, loc_id, 'deleted',
                              session=session)

    # NOTE(zhiyan): 2. Adding or update locations
    for loc in locations:
        if loc.get('id') is None:
            image_location_add(context, image_id, loc, session=session)
        else:
            image_location_update(context, image_id, loc, session=session)


def _image_locations_delete_all(context, image_id,
                                delete_time=None, session=None):
    """Delete all image locations for given image"""
    session = session or get_session()
    location_refs = session.query(models.ImageLocation).filter_by(
        image_id=image_id).filter_by(deleted=False).all()

    for loc_id in [loc_ref.id for loc_ref in location_refs]:
        image_location_delete(context, image_id, loc_id, 'deleted',
                              delete_time=delete_time, session=session)


@utils.no_4byte_params
def _set_properties_for_image(context, image_ref, properties,
                              purge_props=False, session=None):
    """
    Create or update a set of image_properties for a given image

    :param context: Request context
    :param image_ref: An Image object
    :param properties: A dict of properties to set
    :param session: A SQLAlchemy session to use (if present)
    """
    orig_properties = {}
    for prop_ref in image_ref.properties:
        orig_properties[prop_ref.name] = prop_ref

    for name, value in six.iteritems(properties):
        prop_values = {'image_id': image_ref.id,
                       'name': name,
                       'value': value}
        if name in orig_properties:
            prop_ref = orig_properties[name]
            _image_property_update(context, prop_ref, prop_values,
                                   session=session)
        else:
            image_property_create(context, prop_values, session=session)

    if purge_props:
        for key in orig_properties.keys():
            if key not in properties:
                prop_ref = orig_properties[key]
                image_property_delete(context, prop_ref.name,
                                      image_ref.id, session=session)


def _image_child_entry_delete_all(child_model_cls, image_id, delete_time=None,
                                  session=None):
    """Deletes all the child entries for the given image id.

    Deletes all the child entries of the given child entry ORM model class
    using the parent image's id.

    The child entry ORM model class can be one of the following:
    model.ImageLocation, model.ImageProperty, model.ImageMember and
    model.ImageTag.

    :param child_model_cls: the ORM model class.
    :param image_id: id of the image whose child entries are to be deleted.
    :param delete_time: datetime of deletion to be set.
                        If None, uses current datetime.
    :param session: A SQLAlchemy session to use (if present)

    :rtype: int
    :return: The number of child entries got soft-deleted.
    """
    session = session or get_session()

    query = session.query(child_model_cls).filter_by(
        image_id=image_id).filter_by(deleted=False)

    delete_time = delete_time or timeutils.utcnow()

    count = query.update({"deleted": True, "deleted_at": delete_time})
    return count


def image_property_create(context, values, session=None):
    """Create an ImageProperty object."""
    prop_ref = models.ImageProperty()
    prop = _image_property_update(context, prop_ref, values, session=session)
    return prop.to_dict()


def _image_property_update(context, prop_ref, values, session=None):
    """
    Used internally by image_property_create and image_property_update.
    """
    _drop_protected_attrs(models.ImageProperty, values)
    values["deleted"] = False
    prop_ref.update(values)
    prop_ref.save(session=session)
    return prop_ref


def image_property_delete(context, prop_ref, image_ref, session=None):
    """
    Used internally by image_property_create and image_property_update.
    """
    session = session or get_session()
    prop = session.query(models.ImageProperty).filter_by(image_id=image_ref,
                                                         name=prop_ref).one()
    prop.delete(session=session)
    return prop


def _image_property_delete_all(context, image_id, delete_time=None,
                               session=None):
    """Delete all image properties for given image"""
    props_updated_count = _image_child_entry_delete_all(models.ImageProperty,
                                                        image_id,
                                                        delete_time,
                                                        session)
    return props_updated_count


def image_member_create(context, values, session=None):
    """Create an ImageMember object."""
    memb_ref = models.ImageMember()
    _image_member_update(context, memb_ref, values, session=session)
    return _image_member_format(memb_ref)


def _image_member_format(member_ref):
    """Format a member ref for consumption outside of this module."""
    return {
        'id': member_ref['id'],
        'image_id': member_ref['image_id'],
        'member': member_ref['member'],
        'can_share': member_ref['can_share'],
        'status': member_ref['status'],
        'created_at': member_ref['created_at'],
        'updated_at': member_ref['updated_at']
    }


def image_member_update(context, memb_id, values):
    """Update an ImageMember object."""
    session = get_session()
    memb_ref = _image_member_get(context, memb_id, session)
    _image_member_update(context, memb_ref, values, session)
    return _image_member_format(memb_ref)


def _image_member_update(context, memb_ref, values, session=None):
    """Apply supplied dictionary of values to a Member object."""
    _drop_protected_attrs(models.ImageMember, values)
    values["deleted"] = False
    values.setdefault('can_share', False)
    memb_ref.update(values)
    memb_ref.save(session=session)
    return memb_ref


def image_member_delete(context, memb_id, session=None):
    """Delete an ImageMember object."""
    session = session or get_session()
    member_ref = _image_member_get(context, memb_id, session)
    _image_member_delete(context, member_ref, session)


def _image_member_delete(context, memb_ref, session):
    memb_ref.delete(session=session)


def _image_member_delete_all(context, image_id, delete_time=None,
                             session=None):
    """Delete all image members for given image"""
    members_updated_count = _image_child_entry_delete_all(models.ImageMember,
                                                          image_id,
                                                          delete_time,
                                                          session)
    return members_updated_count


def _image_member_get(context, memb_id, session):
    """Fetch an ImageMember entity by id."""
    query = session.query(models.ImageMember)
    query = query.filter_by(id=memb_id)
    return query.one()


def image_member_find(context, image_id=None, member=None, status=None):
    """Find all members that meet the given criteria

    :param image_id: identifier of image entity
    :param member: tenant to which membership has been granted
    """
    session = get_session()
    members = _image_member_find(context, session, image_id, member, status)
    return [_image_member_format(m) for m in members]


def _image_member_find(context, session, image_id=None,
                       member=None, status=None):
    query = session.query(models.ImageMember)
    query = query.filter_by(deleted=False)

    if not context.is_admin:
        query = query.join(models.Image)
        filters = [
            models.Image.owner == context.owner,
            models.ImageMember.member == context.owner,
        ]
        query = query.filter(sa_sql.or_(*filters))

    if image_id is not None:
        query = query.filter(models.ImageMember.image_id == image_id)
    if member is not None:
        query = query.filter(models.ImageMember.member == member)
    if status is not None:
        query = query.filter(models.ImageMember.status == status)

    return query.all()


def image_member_count(context, image_id):
    """Return the number of image members for this image

    :param image_id: identifier of image entity
    """
    session = get_session()

    if not image_id:
        msg = _("Image id is required.")
        raise exception.Invalid(msg)

    query = session.query(models.ImageMember)
    query = query.filter_by(deleted=False)
    query = query.filter(models.ImageMember.image_id == str(image_id))

    return query.count()


def image_tag_set_all(context, image_id, tags):
    # NOTE(kragniz): tag ordering should match exactly what was provided, so a
    # subsequent call to image_tag_get_all returns them in the correct order

    session = get_session()
    existing_tags = image_tag_get_all(context, image_id, session)

    tags_created = []
    for tag in tags:
        if tag not in tags_created and tag not in existing_tags:
            tags_created.append(tag)
            image_tag_create(context, image_id, tag, session)

    for tag in existing_tags:
        if tag not in tags:
            image_tag_delete(context, image_id, tag, session)


@utils.no_4byte_params
def image_tag_create(context, image_id, value, session=None):
    """Create an image tag."""
    session = session or get_session()
    tag_ref = models.ImageTag(image_id=image_id, value=value)
    tag_ref.save(session=session)
    return tag_ref['value']


def image_tag_delete(context, image_id, value, session=None):
    """Delete an image tag."""
    _check_image_id(image_id)
    session = session or get_session()
    query = session.query(models.ImageTag).filter_by(
        image_id=image_id).filter_by(
            value=value).filter_by(deleted=False)
    try:
        tag_ref = query.one()
    except sa_orm.exc.NoResultFound:
        raise exception.NotFound()

    tag_ref.delete(session=session)


def _image_tag_delete_all(context, image_id, delete_time=None, session=None):
    """Delete all image tags for given image"""
    tags_updated_count = _image_child_entry_delete_all(models.ImageTag,
                                                       image_id,
                                                       delete_time,
                                                       session)
    return tags_updated_count


def image_tag_get_all(context, image_id, session=None):
    """Get a list of tags for a specific image."""
    _check_image_id(image_id)
    session = session or get_session()
    tags = session.query(models.ImageTag.value).filter_by(
        image_id=image_id).filter_by(deleted=False).all()
    return [tag[0] for tag in tags]


def user_get_storage_usage(context, owner_id, image_id=None, session=None):
    _check_image_id(image_id)
    session = session or get_session()
    total_size = _image_get_disk_usage_by_owner(
        owner_id, session, image_id=image_id)
    return total_size


def _task_info_format(task_info_ref):
    """Format a task info ref for consumption outside of this module"""
    if task_info_ref is None:
        return {}
    return {
        'task_id': task_info_ref['task_id'],
        'input': task_info_ref['input'],
        'result': task_info_ref['result'],
        'message': task_info_ref['message'],
    }


def _task_info_create(context, task_id, values, session=None):
    """Create an TaskInfo object"""
    session = session or get_session()
    task_info_ref = models.TaskInfo()
    task_info_ref.task_id = task_id
    task_info_ref.update(values)
    task_info_ref.save(session=session)
    return _task_info_format(task_info_ref)


def _task_info_update(context, task_id, values, session=None):
    """Update an TaskInfo object"""
    session = session or get_session()
    task_info_ref = _task_info_get(context, task_id, session=session)
    if task_info_ref:
        task_info_ref.update(values)
        task_info_ref.save(session=session)
    return _task_info_format(task_info_ref)


def _task_info_get(context, task_id, session=None):
    """Fetch an TaskInfo entity by task_id"""
    session = session or get_session()
    query = session.query(models.TaskInfo)
    query = query.filter_by(task_id=task_id)
    try:
        task_info_ref = query.one()
    except sa_orm.exc.NoResultFound:
        msg = ("TaskInfo was not found for task with id %(task_id)s" %
               {'task_id': task_id})
        LOG.debug(msg)
        task_info_ref = None

    return task_info_ref


def task_create(context, values, session=None):
    """Create a task object"""

    values = values.copy()
    session = session or get_session()
    with session.begin():
        task_info_values = _pop_task_info_values(values)

        task_ref = models.Task()
        _task_update(context, task_ref, values, session=session)

        _task_info_create(context,
                          task_ref.id,
                          task_info_values,
                          session=session)

    return task_get(context, task_ref.id, session)


def _pop_task_info_values(values):
    task_info_values = {}
    for k, v in values.items():
        if k in ['input', 'result', 'message']:
            values.pop(k)
            task_info_values[k] = v

    return task_info_values


def task_update(context, task_id, values, session=None):
    """Update a task object"""

    session = session or get_session()

    with session.begin():
        task_info_values = _pop_task_info_values(values)

        task_ref = _task_get(context, task_id, session)
        _drop_protected_attrs(models.Task, values)

        values['updated_at'] = timeutils.utcnow()

        _task_update(context, task_ref, values, session)

        if task_info_values:
            _task_info_update(context,
                              task_id,
                              task_info_values,
                              session)

    return task_get(context, task_id, session)


def task_get(context, task_id, session=None, force_show_deleted=False):
    """Fetch a task entity by id"""
    task_ref = _task_get(context, task_id, session=session,
                         force_show_deleted=force_show_deleted)
    return _task_format(task_ref, task_ref.info)


def task_delete(context, task_id, session=None):
    """Delete a task"""
    session = session or get_session()
    task_ref = _task_get(context, task_id, session=session)
    task_ref.delete(session=session)
    return _task_format(task_ref, task_ref.info)


def task_get_all(context, filters=None, marker=None, limit=None,
                 sort_key='created_at', sort_dir='desc', admin_as_user=False):
    """
    Get all tasks that match zero or more filters.

    :param filters: dict of filter keys and values.
    :param marker: task id after which to start page
    :param limit: maximum number of tasks to return
    :param sort_key: task attribute by which results should be sorted
    :param sort_dir: direction in which results should be sorted (asc, desc)
    :param admin_as_user: For backwards compatibility. If true, then return to
                      an admin the equivalent set of tasks which it would see
                      if it were a regular user
    :return: tasks set
    """
    filters = filters or {}

    session = get_session()
    query = session.query(models.Task)

    if not (context.is_admin or admin_as_user) and context.owner is not None:
        query = query.filter(models.Task.owner == context.owner)

    showing_deleted = False

    if 'deleted' in filters:
        deleted_filter = filters.pop('deleted')
        query = query.filter_by(deleted=deleted_filter)
        showing_deleted = deleted_filter

    for (k, v) in filters.items():
        if v is not None:
            key = k
            if hasattr(models.Task, key):
                query = query.filter(getattr(models.Task, key) == v)

    marker_task = None
    if marker is not None:
        marker_task = _task_get(context, marker,
                                force_show_deleted=showing_deleted)

    sort_keys = ['created_at', 'id']
    if sort_key not in sort_keys:
        sort_keys.insert(0, sort_key)

    query = _paginate_query(query, models.Task, limit,
                            sort_keys,
                            marker=marker_task,
                            sort_dir=sort_dir)

    task_refs = query.all()

    tasks = []
    for task_ref in task_refs:
        tasks.append(_task_format(task_ref, task_info_ref=None))

    return tasks


def _is_task_visible(context, task):
    """Return True if the task is visible in this context."""
    # Is admin == task visible
    if context.is_admin:
        return True

    # No owner == task visible
    if task['owner'] is None:
        return True

    # Perform tests based on whether we have an owner
    if context.owner is not None:
        if context.owner == task['owner']:
            return True

    return False


def _task_get(context, task_id, session=None, force_show_deleted=False):
    """Fetch a task entity by id"""
    session = session or get_session()
    query = session.query(models.Task).options(
        sa_orm.joinedload(models.Task.info)
    ).filter_by(id=task_id)

    if not force_show_deleted and not context.can_see_deleted:
        query = query.filter_by(deleted=False)
    try:
        task_ref = query.one()
    except sa_orm.exc.NoResultFound:
        msg = "No task found with ID %s" % task_id
        LOG.debug(msg)
        raise exception.TaskNotFound(task_id=task_id)

    # Make sure the task is visible
    if not _is_task_visible(context, task_ref):
        msg = "Forbidding request, task %s is not visible" % task_id
        LOG.debug(msg)
        raise exception.Forbidden(msg)

    return task_ref


def _task_update(context, task_ref, values, session=None):
    """Apply supplied dictionary of values to a task object."""
    values["deleted"] = False
    task_ref.update(values)
    task_ref.save(session=session)
    return task_ref


def _task_format(task_ref, task_info_ref=None):
    """Format a task ref for consumption outside of this module"""
    task_dict = {
        'id': task_ref['id'],
        'type': task_ref['type'],
        'status': task_ref['status'],
        'owner': task_ref['owner'],
        'expires_at': task_ref['expires_at'],
        'created_at': task_ref['created_at'],
        'updated_at': task_ref['updated_at'],
        'deleted_at': task_ref['deleted_at'],
        'deleted': task_ref['deleted']
    }

    if task_info_ref:
        task_info_dict = {
            'input': task_info_ref['input'],
            'result': task_info_ref['result'],
            'message': task_info_ref['message'],
        }
        task_dict.update(task_info_dict)

    return task_dict


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
    :param image_id: The id of the config_file we want to check
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

        # filter out deleted images if context disallows it
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
    Set the given properties on an image and update it.

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
    :param image_id: The id of the config_set we want to check
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

        # filter out deleted images if context disallows it
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

        # filter out deleted images if context disallows it
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

        # filter out deleted images if context disallows it
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
    Set the given properties on an image and update it.

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
    :param image_id: The id of the config we want to check
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

        # filter out deleted images if context disallows it
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

        # filter out deleted images if context disallows it
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
    Set the given properties on an image and update it.

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
        sql_ip_ranges="select ip_ranges.start,end from ip_ranges where ip_ranges." \
                      "network_id='"+network_id+"' and ip_ranges.deleted=0 " \
                                                "order by ip_ranges.start"
        ip_ranges = session.execute(sql_ip_ranges).fetchall()
        ip_ranges_sorted = sorted(ip_ranges, cmp=compare_same_cidr_ip)
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
    :param image_id: The id of the project we want to check
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


def check_assigned_ip_in_ip_range(assigned_ip_list, ip_range_list):
    if not ip_range_list:
        return
    assigned_ips = copy.deepcopy(assigned_ip_list)
    ip_ranges = copy.deepcopy(ip_range_list)
    ip_list = [ip for ip in assigned_ips if ip]
    for ip in ip_list:
        flag = False
        for ip_range in ip_ranges:
            if is_in_ip_range(ip, ip_range):
                flag = True
                break
        if not flag:
            msg = "ip assigned by this ip range is being used by " \
                  "networkplane.Delete the network on host interfaces " \
                  "before changing ip range."
            LOG.error(msg)
            raise exception.Forbidden(msg)


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
                            msg = "ip %s being used is not in range of new cidr" \
                                  "%s" % (tmp_ip, values['cidr'])
                            LOG.error(msg)
                            raise exception.Forbidden(msg)

            network_ref = _network_get(context, network_id, session=session)
            if values.has_key("ip_ranges"):
                check_assigned_ip_in_ip_range(network_ip_list,
                                              eval(values['ip_ranges']))
                delete_network_ip_range(context,  network_id)
                for ip_range in list(eval(values['ip_ranges'])):
                    ip_range_ref = models.IpRange()
                    ip_range_ref['start'] = ip_range["start"]
                    ip_range_ref['end'] = ip_range["end"]
                    ip_range_ref.network_id = network_ref.id
                    ip_range_ref.save(session=session)
                del values['ip_ranges']
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
                        ip_ranges_values['network_id'] = network_ref.id
                        ip_range_ref = models.IpRange()
                        ip_range_ref.update(ip_ranges_values)
                        _update_values(ip_range_ref, ip_ranges_values)
                        ip_range_ref.save(session=session)
                    except db_exception.DBDuplicateEntry:
                        raise exception.Duplicate("ip rangge %s already exists!"
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
        # filter out deleted images if context disallows it
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
    :param image_id: The id of the project we want to check
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
        # filter out deleted images if context disallows it
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
    :param image_id: The id of the project we want to check
    :return: Raise NoFound exception if given project id is invalid
    """
    if (cinder_volume_id and
       len(cinder_volume_id) > models.CinderVolume.id.property.columns[0].type.length):
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
        # filter out deleted images if context disallows it
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

        # filter out deleted images if context disallows it
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

        # filter out deleted images if context disallows it
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
    query = session.query(models.HostInterface).filter_by(deleted=0)

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
        host_interface = host_interface.to_dict()
        host_interfaces.append(host_interface)
    return host_interfaces
