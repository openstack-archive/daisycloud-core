# Copyright 2012 OpenStack Foundation.
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

import re

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import units

from daisy.common import exception
from daisy.common import wsgi
from daisy import i18n

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
CONF = cfg.CONF

_CACHED_THREAD_POOL = {}


def size_checked_iter(response, image_meta, expected_size, image_iter,
                      notifier):
    image_id = image_meta['id']
    bytes_written = 0

    def notify_image_sent_hook(env):
        image_send_notification(bytes_written, expected_size,
                                image_meta, response.request, notifier)

    # Add hook to process after response is fully sent
    if 'eventlet.posthooks' in response.request.environ:
        response.request.environ['eventlet.posthooks'].append(
            (notify_image_sent_hook, (), {}))

    try:
        for chunk in image_iter:
            yield chunk
            bytes_written += len(chunk)
    except Exception as err:
        with excutils.save_and_reraise_exception():
            msg = (_LE("An error occurred reading from backend storage for "
                       "image %(image_id)s: %(err)s") % {'image_id': image_id,
                                                         'err': err})
            LOG.error(msg)

    if expected_size != bytes_written:
        msg = (_LE("Backend storage for image %(image_id)s "
                   "disconnected after writing only %(bytes_written)d "
                   "bytes") % {'image_id': image_id,
                               'bytes_written': bytes_written})
        LOG.error(msg)
        raise exception.DaisyException(_("Corrupt image download for "
                                         "image %(image_id)s") %
                                       {'image_id': image_id})


def image_send_notification(bytes_written, expected_size, image_meta, request,
                            notifier):
    """Send an image.send message to the notifier."""
    try:
        context = request.context
        payload = {
            'bytes_sent': bytes_written,
            'image_id': image_meta['id'],
            'owner_id': image_meta['owner'],
            'receiver_tenant_id': context.tenant,
            'receiver_user_id': context.user,
            'destination_ip': request.remote_addr,
        }
        if bytes_written != expected_size:
            notify = notifier.error
        else:
            notify = notifier.info

        notify('image.send', payload)

    except Exception as err:
        msg = (_LE("An error occurred during image.send"
                   " notification: %(err)s") % {'err': err})
        LOG.error(msg)


def get_remaining_quota(context, db_api, image_id=None):
    """Method called to see if the user is allowed to store an image.

    Checks if it is allowed based on the given size in glance based on their
    quota and current usage.

    :param context:
    :param db_api:  The db_api in use for this configuration
    :param image_id: The image that will be replaced with this new data size
    :return: The number of bytes the user has remaining under their quota.
             None means infinity
    """

    # NOTE(jbresnah) in the future this value will come from a call to
    # keystone.
    users_quota = CONF.user_storage_quota

    # set quota must have a number optionally followed by B, KB, MB,
    # GB or TB without any spaces in between
    pattern = re.compile('^(\d+)((K|M|G|T)?B)?$')
    match = pattern.match(users_quota)

    if not match:
        LOG.error(_LE("Invalid value for option user_storage_quota: "
                      "%(users_quota)s")
                  % {'users_quota': users_quota})
        raise exception.InvalidOptionValue(option='user_storage_quota',
                                           value=users_quota)

    quota_value, quota_unit = (match.groups())[0:2]
    # fall back to Bytes if user specified anything other than
    # permitted values
    quota_unit = quota_unit or "B"
    factor = getattr(units, quota_unit.replace('B', 'i'), 1)
    users_quota = int(quota_value) * factor

    if users_quota <= 0:
        return

    usage = db_api.user_get_storage_usage(context,
                                          context.owner,
                                          image_id=image_id)
    return users_quota - usage


def check_quota(context, image_size, db_api, image_id=None):
    """Method called to see if the user is allowed to store an image.

    Checks if it is allowed based on the given size in glance based on their
    quota and current usage.

    :param context:
    :param image_size:  The size of the image we hope to store
    :param db_api:  The db_api in use for this configuration
    :param image_id: The image that will be replaced with this new data size
    :return:
    """

    remaining = get_remaining_quota(context, db_api, image_id=image_id)

    if remaining is None:
        return

    user = getattr(context, 'user', '<unknown>')

    if image_size is None:
        # NOTE(jbresnah) When the image size is None it means that it is
        # not known.  In this case the only time we will raise an
        # exception is when there is no room left at all, thus we know
        # it will not fit
        if remaining <= 0:
            LOG.warn(_LW("User %(user)s attempted to upload an image of"
                         " unknown size that will exceed the quota."
                         " %(remaining)d bytes remaining.")
                     % {'user': user, 'remaining': remaining})
            raise exception.StorageQuotaFull(image_size=image_size,
                                             remaining=remaining)
        return

    if image_size > remaining:
        LOG.warn(_LW("User %(user)s attempted to upload an image of size"
                     " %(size)d that will exceed the quota. %(remaining)d"
                     " bytes remaining.")
                 % {'user': user, 'size': image_size, 'remaining': remaining})
        raise exception.StorageQuotaFull(image_size=image_size,
                                         remaining=remaining)

    return remaining


def memoize(lock_name):
    def memoizer_wrapper(func):
        @lockutils.synchronized(lock_name)
        def memoizer(lock_name):
            if lock_name not in _CACHED_THREAD_POOL:
                _CACHED_THREAD_POOL[lock_name] = func()

            return _CACHED_THREAD_POOL[lock_name]

        return memoizer(lock_name)

    return memoizer_wrapper


def get_thread_pool(lock_name, size=1024):
    """Initializes eventlet thread pool.

    If thread pool is present in cache, then returns it from cache
    else create new pool, stores it in cache and return newly created
    pool.

    @param lock_name:  Name of the lock.
    @param size: Size of eventlet pool.

    @return: eventlet pool
    """
    @memoize(lock_name)
    def _get_thread_pool():
        return wsgi.get_asynchronous_eventlet_pool(size=size)

    return _get_thread_pool


def get_pxe_mac(host_detail):
    pxe_macs = [interface['mac'] for interface in host_detail['interfaces']
                if interface['is_deployment']]
    return pxe_macs


def get_host_network_ip(req, host_detail, cluster_networks, network_name):
    interface_network_ip = ''
    host_interface = get_host_interface_by_network(host_detail, network_name)
    if host_interface:
        network = _get_cluster_network(cluster_networks, network_name)
        assigned_network = daisy_cmn.get_assigned_network(req,
                                                          host_interface['id'],
                                                          network['id'])
        interface_network_ip = assigned_network['ip']

    if not interface_network_ip and 'MANAGEMENT' == network_name:
        msg = "%s network ip of host %s can't be empty" % (
            network_name, host_detail['id'])
        raise exception.InvalidNetworkConfig(msg)
    return interface_network_ip


def get_service_disk_list(req, params):
    try:
        service_disks = registry.list_service_disk_metadata(
            req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return service_disks


def sort_interfaces_by_pci(networks, host_detail):
    """
    Sort interfaces by pci segment, if interface type is bond,
    user the pci of first memeber nic.This function is fix bug for
    the name length of ovs virtual port, because if the name length large than
    15 characters, the port will create failed.
    :param interfaces: interfaces info of the host
    :return:
    """
    interfaces = eval(host_detail.get('interfaces', None)) \
        if isinstance(host_detail, unicode) else \
        host_detail.get('interfaces', None)
    if not interfaces:
        LOG.info("This host has no interfaces info.")
        return host_detail

    tmp_interfaces = copy.deepcopy(interfaces)

    slaves_name_list = []
    for interface in tmp_interfaces:
        if interface.get('type', None) == "bond" and\
                interface.get('slave1', None) and\
                interface.get('slave2', None):
            slaves_name_list.append(interface['slave1'])
            slaves_name_list.append(interface['slave2'])

    for interface in interfaces:
        if interface.get('name') not in slaves_name_list:
            vlan_id_len_list = [len(network['vlan_id'])
                                for assigned_network in interface.get(
                                    'assigned_networks', [])
                                for network in networks
                                if assigned_network.get('name') ==
                                network.get('name') and network.get('vlan_id')]
            max_vlan_id_len = max(vlan_id_len_list) if vlan_id_len_list else 0
            interface_name_len = len(interface['name'])
            redundant_bit = interface_name_len + max_vlan_id_len - 14
            interface['name'] = interface['name'][
                redundant_bit:] if redundant_bit > 0 else interface['name']
    return host_detail


def run_scrip(script, ip=None, password=None, msg=None):
    try:
        _run_scrip(script, ip, password)
    except:
        msg1 = 'Error occurred during running scripts.'
        message = msg1 + msg if msg else msg1
        LOG.error(message)
        raise HTTPForbidden(explanation=message)
    else:
        LOG.info('Running scripts successfully!')


def get_ctl_ha_nodes_min_mac(req, cluster_id):
    '''
    ctl_ha_nodes_min_mac = {'host_name1':'min_mac1', ...}
    '''
    ctl_ha_nodes_min_mac = {}
    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    cluster_networks =\
        daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
            continue
        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
        for role_host in role_hosts:
            # host has installed tecs are exclusive
            if (role_host['status'] == TECS_STATE['ACTIVE'] or
                    role_host['status'] == TECS_STATE['UPDATING'] or
                    role_host['status'] == TECS_STATE['UPDATE_FAILED']):
                continue
            host_detail = daisy_cmn.get_host_detail(req,
                                                    role_host['host_id'])
            host_name = host_detail['name']
            if role['name'] == "CONTROLLER_HA":
                min_mac = utils.get_host_min_mac(host_detail['interfaces'])
                ctl_ha_nodes_min_mac[host_name] = min_mac
    return ctl_ha_nodes_min_mac
