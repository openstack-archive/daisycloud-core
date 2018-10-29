# Copyright 2012 OpenStack Foundation
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

from __future__ import print_function

import copy
import functools
import pprint
import os
import json

from oslo_utils import encodeutils
from oslo_utils import strutils

from daisyclient.common import utils
from daisyclient import exc
import daisyclient.v1.hosts
import daisyclient.v1.clusters
import daisyclient.v1.cluster_hosts
import daisyclient.v1.template
import daisyclient.v1.components
import daisyclient.v1.services
import daisyclient.v1.roles
import daisyclient.v1.config_files
import daisyclient.v1.config_sets
import daisyclient.v1.networks
import daisyclient.v1.configs
import daisyclient.v1.uninstall
import daisyclient.v1.update
import daisyclient.v1.disk_array
import daisyclient.v1.template
from daisyclient.v1 import param_helper
import daisyclient.v1.backup_restore
import daisyclient.v1.versions
import daisyclient.v1.version_patchs
import daisyclient.v1.deploy_server
from daisy.common import utils as daisy_utils

_bool_strict = functools.partial(strutils.bool_from_string, strict=True)


def _daisy_show(daisy, max_column_width=80):
    info = copy.deepcopy(daisy._info)
    exclusive_field = ('deleted', 'deleted_at')
    for field in exclusive_field:
        if field in info:
            info.pop(field)
    utils.print_dict(info, max_column_width=max_column_width)


@utils.arg('name', metavar='<NAME>',
           help='node name to be added.')
@utils.arg('description', metavar='<DESCRIPTION>',
           help='node description to be added.')
@utils.arg('discover_mode', metavar='<DISCOVER_MODE>',
           help='node discover mode(PXE/SSH) to be added.')
@utils.arg('--resource-type', metavar='<RESOURCE_TYPE>',
           help='node resource type to be added, supported type are \
                 "baremetal", "server" and "docker".\
                 "baremetal" is traditional physical server ,\
                 "server" is virtual machine and \
                 "docker" is container created by docker.')
@utils.arg('--dmi-uuid', metavar='<DMI_UUID>',
           help='node dmi uuid to be added.')
@utils.arg('--ipmi-user', metavar='<IPMI_USER>',
           help='ipmi user name to be added.')
@utils.arg('--ipmi-passwd', metavar='<IPMI_PASSWD>',
           help='ipmi user of password to be added.')
@utils.arg('--ipmi-addr', metavar='<IPMI_ADDR>',
           help='ipmi ip to be added.')
@utils.arg('--role', metavar='<ROLE>', nargs='+',
           help='name of node role to be added.')
# @utils.arg('--status', metavar='<STATUS>',
#           help='node status to be added.')
@utils.arg('--cluster', metavar='<CLUSTER>',
           help='id of cluster that the node will be added.')
@utils.arg('--os-version', metavar='<OS_VERSION>',
           help='os version of the host.')
@utils.arg('--os-status', metavar='<OS_STATUS>',
           help='os status of the host.')
@utils.arg('--interfaces', metavar='<type=ether,name=eth5,'
                                   'mac=4C:AC:0A:AA:9C:EF,ip=ip_addr,'
                                   'netmask=netmask,gateway=gateway,'
                                   'is_deployment=False,'
                                   'assigned_networks=networkname1:'
                                   'ip1_networkname2:ip2_networkname3:'
                                   'ip3,pci=pci,mode=mode,'
                                   'slaves=eth0_eth1,vswitch_type=ovs>',
           nargs='+',
           help='node network interface detail, \
                 ip must be given if assigned_networks is empty,\
                 and cluster must be given if assigned_networks is not empty.')
@utils.arg('--vcpu-pin-set', metavar='<VCPU_PIN_SET>',
           help='Set the vcpu pin.')
@utils.arg('--dvs-high-cpuset', metavar='<DVS_HIGH_CPUSET>',
           help='Set the dvs high cpu cores.')
@utils.arg('--pci-high-cpuset', metavar='<PCI_HIGH_CPUSET>',
           help='Set the pci high cpu cores.')
@utils.arg('--os-cpus', metavar='<OS_CPUS>',
           help='Set the os cpu cores.')
@utils.arg('--dvs-cpus', metavar='<DVS_CPUS>',
           help='Set the dvs cpu cores.')
@utils.arg('--config-set-id', metavar='<CONFIG_SET_ID>',
           help='Set host config set id.')
def do_host_add(gc, args):
    """Add a host."""
    if args.cluster:
        cluster = utils.find_resource(gc.clusters, args.cluster)
        if cluster and cluster.deleted:
            msg = "No cluster with an ID of '%s' exists." % cluster.id
            raise exc.CommandError(msg)
    # if args.role:
        # role = utils.find_resource(gc.roles, args.role)
        # if role and role.deleted:
            # msg = "No role with an ID of '%s' exists." % role.id
            # raise exc.CommandError(msg)
    interface_list = []
    if args.interfaces:
        for interface in args.interfaces:
            interface_info = {"pci": "", "mode": "", "gateway": "",
                              "type": "", "name": "", "mac": "", "ip": "",
                              "netmask": "", "assigned_networks": "",
                              "slaves": "", "is_deployment": "",
                              "vswitch_type": "", "bond_type": ""}
            for kv_str in interface.split(","):
                try:
                    k, v = kv_str.split("=", 1)
                except ValueError:
                    raise exc.CommandError("interface error")

                if k in interface_info:
                    interface_info[k] = v
                    if k == "assigned_networks":
                        networks_list_obj = interface_info[
                            'assigned_networks'].split("_")
                        networks_list = []
                        for network in networks_list_obj:
                            network_dict = {}
                            name, ip = network.split(":", 1)
                            network_dict = {'name': name, 'ip': ip}
                            networks_list.append(network_dict)
                        interface_info['assigned_networks'] = networks_list
                    if k == "slaves":
                        slaves_list = interface_info['slaves'].split("_", 1)
                        interface_info['slaves'] = slaves_list
            interface_list.append(interface_info)
        args.interfaces = interface_list

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.hosts.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    host = gc.hosts.add(**fields)

    _daisy_show(host)


@utils.arg('hosts', metavar='<HOST>', nargs='+',
           help='ID of host(s) to delete.')
def do_host_delete(gc, args):
    """Delete specified host(s)."""

    for args_host in args.hosts:
        host = utils.find_resource(gc.hosts, args_host)
        if host and host.deleted:
            msg = "No host with an ID of '%s' exists." % host.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting host delete for %s ...' %
                      encodeutils.safe_decode(args_host), end=' ')
            gc.hosts.delete(host)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete host %s' % (e, args_host))


@utils.arg('host', metavar='<HOST>', help='ID of host to modify.')
@utils.arg('--name', metavar='<NAME>',
           help='Name of host.')
@utils.arg('--resource-type', metavar='<RESOURCE_TYPE>',
           help='node resource type to be added, \
                 supported type are "baremetal", "server" and "docker".\
                 "baremetal" is traditional physical server ,\
                 "server" is virtual machine and \
                 "docker" is container created by docker.')
@utils.arg('--dmi-uuid', metavar='<DMI_UUID>',
           help='node dmi uuid for the host.')
@utils.arg('--ipmi-user', metavar='<IPMI_USER>',
           help='ipmi user name for the host.')
@utils.arg('--ipmi-passwd', metavar='<IPMI_PASSWD>',
           help='ipmi user of password for the host.')
@utils.arg('--ipmi-addr', metavar='<IPMI_ADDR>',
           help='ipmi ip for the host.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of host.')
@utils.arg('--root-disk', metavar='<ROOT_DISK>',
           help='the disk used to install OS.')
@utils.arg('--root-lv-size', metavar='<ROOT_LV_SIZE>',
           help='the size of root_lv(M).')
@utils.arg('--swap-lv-size', metavar='<SWAP_LV_SIZE>',
           help='the size of swap_lv(M).')
@utils.arg('--root-pwd', metavar='<ROOT_PWD>',
           help='the password of os.')
@utils.arg('--isolcpus', metavar='<ISOLCPUS>',
           help='the cpus to be isolated.')
@utils.arg('--cluster', metavar='<CLUSTER>',
           help='id of cluster that the node will be added.')
@utils.arg('--os-version', metavar='<OS_VERSION>',
           help='os version for the host.')
@utils.arg('--os-status', metavar='<OS_STATUS>',
           help='os status for the host.')
# s@utils.arg('--status', metavar='<STATUS>',
#           help='node status for the host.')
@utils.arg('--role', metavar='<ROLE>', nargs='+',
           help='name of node role for the host.')
@utils.arg('--interfaces', metavar='<type=ether,name=eth5,'
                                   'mac=4C:AC:0A:AA:9C:EF,'
                                   'ip=ip_addr,netmask=netmask,'
                                   'gateway=gateway,is_deployment=False,'
                                   'assigned_networks=networkname1:'
                                   'ip1_networkname2:'
                                   'ip2_networkname3:ip3,'
                                   'pci=pci,mode=mode,slaves=eth0_eth1,'
                                   'vswitch_type=ovs>',
           nargs='+',
           help='node network interface detail,\
                 ip must be given if assigned_networks is empty,\
                 and cluster must be given if assigned_networks is not empty.')
@utils.arg('--hugepagesize', metavar='<HUGEPAGESIZE>',
           help='size of hugepage.')
@utils.arg('--hugepages', metavar='<HUGEPAGES>',
           help='number of hugepages.')
@utils.arg('--vcpu-pin-set', metavar='<VCPU_PIN_SET>',
           help='Set the vcpu pin.')
@utils.arg('--dvs-high-cpuset', metavar='<DVS_HIGH_CPUSET>',
           help='Set the dvs high cpu cores.')
@utils.arg('--pci-high-cpuset', metavar='<PCI_HIGH_CPUSET>',
           help='Set the pci high cpu cores.')
@utils.arg('--os-cpus', metavar='<OS_CPUS>',
           help='Set the os cpu cores.')
@utils.arg('--dvs-cpus', metavar='<DVS_CPUS>',
           help='Set the dvs cpu cores.')
@utils.arg('--config-set-id', metavar='<CONFIG_SET_ID>',
           help='Update host config set id.')
def do_host_update(gc, args):
    """Update a specific host."""
    # Filter out None values
    if args.cluster:
        cluster = utils.find_resource(gc.clusters, args.cluster)
        if cluster and cluster.deleted:
            msg = "No cluster with an ID of '%s' exists." % cluster.id
            raise exc.CommandError(msg)
    interface_list = []
    if args.interfaces:
        for interfaces in args.interfaces:
            interface_info = {"pci": "", "mode": "", "gateway": "",
                              "type": "", "name": "", "mac": "", "ip": "",
                              "netmask": "", "mode": "",
                              "assigned_networks": "", "slaves": "",
                              "is_deployment": "", "vswitch_type": "",
                              "bond_type": ""}
            for kv_str in interfaces.split(","):
                try:
                    k, v = kv_str.split("=", 1)
                except ValueError:
                    raise exc.CommandError("interface error")
                if k in interface_info:
                    interface_info[k] = v
                    if k == "assigned_networks":
                        networks_list_obj = interface_info[
                            'assigned_networks'].split("_")
                        networks_list = []
                        for network in networks_list_obj:
                            network_dict = {}
                            name, ip = network.split(":", 1)
                            network_dict = {'name': name, 'ip': ip}
                            networks_list.append(network_dict)
                        interface_info['assigned_networks'] = networks_list
                    if k == "slaves":
                        slaves_list = interface_info['slaves'].split("_", 1)
                        interface_info['slaves'] = slaves_list
            interface_list.append(interface_info)
        args.interfaces = interface_list
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    host_arg = fields.pop('host')
    host = utils.find_resource(gc.hosts, host_arg)

    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.hosts.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))

    host = gc.hosts.update(host, **fields)
    _daisy_show(host)


@utils.arg('--name', metavar='<NAME>',
           help='Filter hosts to those that have this name.')
@utils.arg('--status', metavar='<STATUS>',
           help='Filter hosts status.')
@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='Filter by cluster_id.')
@utils.arg('--page-size', metavar='<SIZE>', default=None, type=int,
           help='Number of hosts to request in each paginated request.')
@utils.arg('--sort-key', default='name',
           choices=daisyclient.v1.hosts.SORT_KEY_VALUES,
           help='Sort host list by specified field.')
@utils.arg('--sort-dir', default='asc',
           choices=daisyclient.v1.hosts.SORT_DIR_VALUES,
           help='Sort host list in specified direction.')
def do_host_list(gc, args):
    """List hosts you can access."""
    filter_keys = ['name', 'status', 'cluster_id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])

    kwargs = {'filters': filters}
    if args.page_size is not None:
        kwargs['page_size'] = args.page_size

    kwargs['sort_key'] = args.sort_key
    kwargs['sort_dir'] = args.sort_dir

    hosts = gc.hosts.list(**kwargs)

    columns = ['ID', 'Name', 'Description', 'Resource_type',
               'Status', 'Os_progress', 'Os_status', 'Discover_state',
               'Tecs_version_id', 'Messages', 'role']
#    if filters.has_key('cluster_id'):
    if 'cluster_id' in filters:
        role_columns = ['Role_progress', 'Role_status', 'Role_messages']
        columns += role_columns

    utils.print_list(hosts, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter host to those that have this id.')
def do_host_detail(gc, args):
    """List host you can access."""
    host = utils.find_resource(gc.hosts, args.id)
    _daisy_show(host)

# @utils.arg('name', metavar='<NAME>',
#            help='Cluster name to be added.')
# @utils.arg('--nodes', metavar='<NODES>',nargs='+',
#            help='id of cluster nodes to be added.')
# @utils.arg('description', metavar='<DESCRIPTION>',
#            help='Cluster description to be added.')
# @utils.arg('--networks', metavar='<NETWORKS>',nargs='+',
#            help='id of cluster networks.')
# @utils.arg('--floating_ranges', metavar='<FLOATING_RANGES>',nargs='+',
#            help='Cluster floating ranges:"172.16.0.130","172.16.0.254"')
# @utils.arg('--dns_nameservers', metavar='<DNS_NAMESERVERS>',nargs='+',
#            help='Cluster dns nameservers:"8.8.4.4" "8.8.8.8" ')
# @utils.arg('--net_l23_provider', metavar='<NET_123_PROVIDER>',
#            help='Cluster net_l23_provider.')
# @utils.arg('--base_mac', metavar='<BASE_MAC>',
#            help='Cluster base_mac.')
# @utils.arg('--internal_gateway', metavar='<INTERNAL_GATEWAY>',
#            help='Cluster internal gateway.')
# @utils.arg('--internal_cidr', metavar='<INTERNAL_CIDR>',
#            help='Cluster internal_cidr.')
# @utils.arg('--external_cidr', metavar='<EXTERNAL_CIDR>',
#            help='Cluster external cidr.')
# @utils.arg('--gre_id_range', metavar='<GRE_ID_RANGE>',nargs='+',
#            help='Cluster gre_id_range. 2 65535')
# @utils.arg('--vlan_range', metavar='<VLAN_RANGE>',nargs='+',
#            help='Cluster vlan_range.1000 1030')
# @utils.arg('--vni_range', metavar='<VNI_RANGE>',nargs='+',
#            help='Cluster vNI range.1000 1030')
# @utils.arg('--segmentation_type', metavar='<SEGMENTATION_TYPE>',
#            help='Cluster segmentation_type.')
# @utils.arg('--public_vip', metavar='<PUBLIC_VIP>',
#            help='Cluster public vip.')


@utils.arg('ip', metavar='<IP>',
           help='ip of the host will be discovered.')
@utils.arg('passwd', metavar='<PASSWD>',
           help='passwd of the host.')
@utils.arg('--user', metavar='<USER>',
           help='user name of the host.')
@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='id of cluster that the node will be added.')
def do_discover_host_add(gc, args):
    """Add a discover host."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.hosts.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    host = gc.hosts.add_discover_host(**fields)
    _daisy_show(host)


@utils.arg('id', metavar='<ID>', nargs='+',
           help='ID of discover host(s) to delete.')
def do_discover_host_delete(gc, args):
    """Delete specified host(s)."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    hosts = fields.get('id', None)
    for args_host in hosts:
        host = args_host
        try:
            if args.verbose:
                print('Requesting host delete for %s ...' %
                      encodeutils.safe_decode(args_host), end=' ')
            gc.hosts.delete_discover_host(host)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete host %s' % (e, args_host))


@utils.arg('--ip', metavar='<IP>',
           help='Filter hosts to those that have this ip.')
@utils.arg('--user', metavar='<USER>',
           help='Filter by user.')
@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='Filter by cluster_id.')
def do_discover_host_list(gc, args):
    """List hosts you can access."""

    filter_keys = ['ip', 'user', 'cluster_id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    kwargs = {'filters': filters}
    discover_hosts = gc.hosts.list_discover_host(**kwargs)
    columns = ['Id', 'Ip', 'User', 'Passwd', 'Status', 'Message',
               'Host_id', 'Cluster_id']
    utils.print_list(discover_hosts, columns)


@utils.arg('id', metavar='<ID>',
           help='id of the host.')
@utils.arg('--ip', metavar='<IP>',
           help='ip of the host.')
@utils.arg('--passwd', metavar='<PASSWD>',
           help='passwd of the host.')
@utils.arg('--user', metavar='<USER>',
           help='user name of the host.')
@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='id of cluster that the node will be added.')
def do_discover_host_update(gc, args):
    """Add a discover host."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    host = fields.get('id', None)
    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.hosts.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    host = gc.hosts.update_discover_host(host, **fields)
    _daisy_show(host)


@utils.arg('id', metavar='<ID>',
           help='ID of discover host.')
def do_discover_host_detail(gc, args):
    """get host detail infomation."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    host_id = fields.get('id', None)
    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.hosts.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    discover_host = gc.hosts.get_discover_host_detail(host_id, **fields)
    _daisy_show(discover_host)


@utils.arg('params_file_path', metavar='<PARAMS_FILE_PATH>',
           help="""Template file path.
                   Run \"daisy params-helper params_file_path\" for \
                   the template content.
                   Then save the output to a template file.\
                   Just use this path.""")
def do_cluster_add(gc, args):
    """Add a cluster."""
    fields = None
    if not args.params_file_path:
        if args.nodes:
            for arg_node in args.nodes:
                host = utils.find_resource(gc.hosts, arg_node)
                if host and host.deleted:
                    msg = "No host with an ID of '%s' exists." % host.id
                    raise exc.CommandError(msg)
        if args.networks:
            for arg_network in args.networks:
                network = utils.find_resource(gc.networks, arg_network)
                if network and network.deleted:
                    msg = "No network with an ID of '%s' exists." % network.id
                    raise exc.CommandError(msg)
        range_list = []
        if args.floating_ranges:
            for floating_ranges in args.floating_ranges:
                float_ip_list = floating_ranges.split(",")
                range_list.append(float_ip_list)
        args.floating_ranges = range_list
        fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

        # Filter out values we can't use
        CREATE_PARAMS = daisyclient.v1.clusters.CREATE_PARAMS
        fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    else:
        fields = param_helper._read_template_file(args)

    cluster = gc.clusters.add(**fields)
    _daisy_show(cluster)


@utils.arg('cluster', metavar='<CLUSTER>', help='ID of cluster to modify.')
# @utils.arg('--name', metavar='<NAME>',
#            help='Name of host.')
# @utils.arg('--description', metavar='<DESCRIPTION>',
#            help='Description of host.')
# @utils.arg('--nodes', metavar='<NODES>',nargs='+',
#            help='id of cluster nodes to be updated.')
# @utils.arg('--networks', metavar='<NETWORKS>',nargs='+',
#            help='id of update networks.')
# @utils.arg('--floating_ranges', metavar='<FLOATING_RANGES>',nargs='+',
#            help='Cluster floating ranges:"172.16.0.130","172.16.0.254"')
# @utils.arg('--dns_nameservers', metavar='<DNS_NAMESERVERS>',nargs='+',
#            help='Cluster dns nameservers:"8.8.4.4" "8.8.8.8" ')
# @utils.arg('--net_l23_provider', metavar='<NET_123_PROVIDER>',
#            help='Cluster net_l23_provider.')
# @utils.arg('--base_mac', metavar='<BASE_MAC>',
#            help='Cluster base_mac.')
# @utils.arg('--internal_gateway', metavar='<INTERNAL_GATEWAY>',
#            help='Cluster internal gateway.')
# @utils.arg('--internal_cidr', metavar='<INTERNAL_CIDR>',
#            help='Cluster internal_cidr.')
# @utils.arg('--external_cidr', metavar='<EXTERNAL_CIDR>',
#            help='Cluster external cidr.')
# @utils.arg('--gre_id_range', metavar='<GRE_ID_RANGE>',nargs='+',
#            help='Cluster gre_id_range. 2 65535')
# @utils.arg('--vlan_range', metavar='<VLAN_RANGE>',nargs='+',
#            help='Cluster vlan_range:1000 1030')
# @utils.arg('--vni_range', metavar='<VNI_RANGE>',nargs='+',
#            help='Cluster vNI range:1000 1030')
# @utils.arg('--segmentation_type', metavar='<SEGMENTATION_TYPE>',
#            help='Cluster segmentation_type.')
# @utils.arg('--public_vip', metavar='<PUBLIC_VIP>',
#            help='Cluster public vip.')
@utils.arg('params_file_path', metavar='<PARAMS_FILE_PATH>',
           help="""Template file path.
                   Run \"daisy params-helper params_file_path\" for \
                   the template content.
                   Then save the output to a template file.\
                   Just use this path.""")
def do_cluster_update(gc, args):
    """Update a specific cluster."""
    # Filter out None values
    fields = None
    cluster = None
    if not args.params_file_path:
        if args.nodes:
            for arg_node in args.nodes:
                host = utils.find_resource(gc.hosts, arg_node)
                if host and host.deleted:
                    msg = "No host with an ID of '%s' exists." % host.id
                    raise exc.CommandError(msg)
        if args.networks:
            for arg_network in args.networks:
                network = utils.find_resource(gc.networks, arg_network)
                if network and network.deleted:
                    msg = "No network with an ID of '%s' exists." % network.id
                    raise exc.CommandError(msg)
        range_list = []
        if args.floating_ranges:
            for floating_ranges in args.floating_ranges:
                float_ip_list = floating_ranges.split(",")
                range_list.append(float_ip_list)
        args.floating_ranges = range_list
        fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

        cluster_arg = fields.pop('cluster')

        cluster = utils.find_resource(gc.clusters, cluster_arg)

        # Filter out values we can't use
        UPDATE_PARAMS = daisyclient.v1.clusters.UPDATE_PARAMS
        fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))
    else:
        cluster_arg = args.cluster
        cluster = utils.find_resource(gc.clusters, cluster_arg)
        fields = param_helper._read_template_file(args)

    cluster = gc.clusters.update(cluster, **fields)
    _daisy_show(cluster)


@utils.arg('subcommand_param', nargs='+',
           metavar='<SUBCOMMAND_PARAM>',
           help='Subcommand param, [\'params_file_path\', \'test\'].')
def do_params_helper(gc, args):
    """ Params helper for some subcommand. """
    PARAMS = ('params_file_path', 'test')
    valid_params_list = \
        [param for param in args.subcommand_param if param in PARAMS]

    for valid_param in valid_params_list:
        if 0 == cmp(valid_param, u"params_file_path"):
            print("------------------------------------------")
            print("Cluster \'name\' and \'description\' segment must "
                  "be supportted.Template:")
            pprint.pprint(param_helper.CLUSTER_ADD_PARAMS_FILE)
            print("------------------------------------------")
        elif 0 == cmp(valid_param, u"test"):
            print("------------------------------------------")
            print("test")
            print("------------------------------------------")


@utils.arg('clusters', metavar='<CLUSTER>', nargs='+',
           help=' ID of cluster(s) to delete.')
def do_cluster_delete(gc, args):
    """Delete specified cluster(s)."""

    for args_cluster in args.clusters:
        cluster = utils.find_resource(gc.clusters, args_cluster)
        if cluster and cluster.deleted:
            msg = "No cluster with an ID of '%s' exists." % cluster.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting cluster delete for %s ...' %
                      encodeutils.safe_decode(args_cluster), end=' ')
            gc.clusters.delete(cluster)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete cluster %s' % (e, args_cluster))


@utils.arg('--name', metavar='<NAME>',
           help='Filter clusters to those that have this name.')
@utils.arg('--auto-scale', metavar='<AUTO_SCAELE>',
           help='auto-scale:1 or 0.')
@utils.arg('--page-size', metavar='<SIZE>', default=None, type=int,
           help='Number of clusters to request in each paginated request.')
@utils.arg('--sort-key', default='name',
           choices=daisyclient.v1.clusters.SORT_KEY_VALUES,
           help='Sort cluster list by specified field.')
@utils.arg('--sort-dir', default='asc',
           choices=daisyclient.v1.clusters.SORT_DIR_VALUES,
           help='Sort cluster list in specified direction.')
def do_cluster_list(gc, args):
    """List clusters you can access."""
    filter_keys = ['name', 'auto_scale']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])

    kwargs = {'filters': filters}
    if args.page_size is not None:
        kwargs['page_size'] = args.page_size

    kwargs['sort_key'] = args.sort_key
    kwargs['sort_dir'] = args.sort_dir

    clusters = gc.clusters.list(**kwargs)

    columns = ['ID', 'Name', 'Description', 'Nodes', 'Networks',
               'Auto_scale', 'Use_dns', 'Status']
    utils.print_list(clusters, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter cluster to those that have this id.')
def do_cluster_detail(gc, args):
    """List cluster you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        cluster = utils.find_resource(gc.clusters, fields.pop('id'))
        _daisy_show(cluster)
    else:
        cluster = gc.clusters.list(**kwargs)
        columns = ['ID', 'Name', 'Description', 'Nodes',
                   'Networks', 'Auto_scale', 'Use_dns']
        utils.print_list(cluster, columns)

# @utils.arg('cluster', metavar='<CLUSTER_ID>',
#           help='Filter results by an cluster ID.')
# def do_cluster_host_list(gc, args):
#    """Show cluster host membership by cluster or host."""
#   if not args.cluster:
#       utils.exit('Unable to list all members. Specify cluster-id')
#   if args.cluster:
#       kwargs = {'cluster': args.cluster}
#
#   members = gc.cluster_hosts.list(**kwargs)
#   columns = ['Cluster_ID', 'Host_ID']
#   utils.print_list(members, columns)


@utils.arg('cluster', metavar='<CLUSTER>',
           help='Project from which to remove member.')
@utils.arg('node', metavar='<NODE>',
           help='id of host to remove as member.')
def do_cluster_host_del(gc, args):
    """Remove a host from cluster."""
# cluster_id = utils.find_resource(gc.clusters, args.cluster).id
# host_id = utils.find_resource(gc.hosts, args.node).id
    cluster_id = args.cluster
    host_id = args.node
    gc.cluster_hosts.delete(cluster_id, host_id)


@utils.arg('name', metavar='<NAME>',
           help='Component name to be added.')
@utils.arg('description', metavar='<DESCRIPTION>',
           help='Component description to be added.')
def do_component_add(gc, args):
    """Add a component."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.components.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    component = gc.components.add(**fields)

    _daisy_show(component)


@utils.arg('components', metavar='<COMPONENT>', nargs='+',
           help='ID of component(s) to delete.')
def do_component_delete(gc, args):
    """Delete specified component(s)."""

    for args_component in args.components:
        component = utils.find_resource(gc.components, args_component)
        if component and component.deleted:
            msg = "No component with an ID of '%s' exists." % component.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting component delete for %s ...' %
                      encodeutils.safe_decode(args_component), end=' ')
            gc.components.delete(component)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete component %s' % (e, args_component))


@utils.arg('--id', metavar='<ID>',
           help='Filter components to those that have this name.')
def do_component_list(gc, args):
    """List components you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        component = utils.find_resource(gc.components, fields.pop('id'))
        _daisy_show(component)
    else:
        components = gc.components.list(**kwargs)
        columns = ['ID', 'Name', 'Description']
        utils.print_list(components, columns)


@utils.arg('component', metavar='<COMPONENT>',
           help='ID of component to modify.')
@utils.arg('--name', metavar='<NAME>',
           help='Name of component.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of component.')
def do_component_update(gc, args):
    """Update a specific component."""
    # Filter out None values
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    component_arg = fields.pop('component')
    component = utils.find_resource(gc.components, component_arg)

    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.components.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))

    component = gc.components.update(component, **fields)
    _daisy_show(component)


@utils.arg('name', metavar='<NAME>',
           help='Service name to be added.')
@utils.arg('description', metavar='<DESCRIPTION>',
           help='Service description to be added.')
@utils.arg('--component-id', metavar='<COMPONENT_ID>',
           help='Services that belong to the component of the ID.')
@utils.arg('--backup-type', metavar='<BACKUP_TYPE>',
           help='The backup-type mybe lb or ha.')
def do_service_add(gc, args):
    """Add a service."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.services.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    service = gc.services.add(**fields)

    _daisy_show(service)


@utils.arg('services', metavar='<SERVICE>', nargs='+',
           help='ID of service(s) to delete.')
def do_service_delete(gc, args):
    """Delete specified service(s)."""

    for args_service in args.services:
        service = utils.find_resource(gc.services, args_service)
        if service and service.deleted:
            msg = "No service with an ID of '%s' exists." % service.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting service delete for %s ...' %
                      encodeutils.safe_decode(args_service), end=' ')
            gc.services.delete(service)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete service %s' % (e, args_service))


@utils.arg('--id', metavar='<ID>',
           help='Filter services to those that have this name.')
def do_service_list(gc, args):
    """List services you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        service = utils.find_resource(gc.services, fields.pop('id'))
        _daisy_show(service)
    else:
        services = gc.services.list(**kwargs)
        columns = ['ID', 'Name', 'Description', 'Component_ID', 'Backup_Type']
        utils.print_list(services, columns)


@utils.arg('service', metavar='<SERVICE>', help='ID of service to modify.')
@utils.arg('--name', metavar='<NAME>',
           help='Name of service.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of service.')
@utils.arg('--component-id', metavar='<COMPONENT_ID>',
           help='Services that belong to the component of the ID.')
@utils.arg('--backup-type', metavar='<BACKUP_TYPE>',
           help='The backup-type mybe lb or ha.')
def do_service_update(gc, args):
    """Update a specific service."""
    # Filter out None values
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    service_arg = fields.pop('service')
    service = utils.find_resource(gc.services, service_arg)

    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.services.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))

    service = gc.services.update(service, **fields)
    _daisy_show(service)


@utils.arg('name', metavar='<NAME>',
           help='Role name to be added.')
@utils.arg('description', metavar='<DESCRIPTION>',
           help='Role description to be added.')
# @utils.arg('--progress', metavar='<PROGRESS>',
#           help='The role of the progress.')
@utils.arg('--config-set-id', metavar='<CONFIG_SET_ID>',
           help='Roles that belong to the config-set of the ID.')
@utils.arg('--nodes', metavar='<NODES>', nargs='+',
           help='Roles that belong to the host of the id,\
           host id can be more than one')
@utils.arg('--services', metavar='<SERVICES>', nargs='+',
           help='Roles that belong to the service of the id, \
           service id can be more than one')
# @utils.arg('--status', metavar='<STATUS>',
#           help='The role of the status.')
@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='Roles that belong to cluster of id.')
@utils.arg('--type', metavar='<TYPE>',
           help='The value should be template or  custom.')
@utils.arg('--vip', metavar='<VIP>',
           help='float ip.')
@utils.arg('--db-vip', metavar='<DB_VIP>',
           help='float ip of db.')
@utils.arg('--glance-vip', metavar='<GLANCE_VIP>',
           help='float ip of glance.')
@utils.arg('--public-vip', metavar='<PUBLIC_VIP>',
           help='float ip of public.')
@utils.arg('--mongodb-vip', metavar='<MONGODB_VIP>',
           help='float ip of mongodb.')
@utils.arg('--glance-lv-size', metavar='<GLANCE_LV_SIZE>',
           help='the size of logic volume disk for storaging image,\
            and the unit is M.')
@utils.arg('--docker-vg-size', metavar='<DOCKER_VG_SIZE>',
           help='the size of docker_vg(M).')
@utils.arg('--deployment-backend', metavar='<deployment_backend>',
           help="deployment backend, supported bacends are \
           'tecs' and 'zenic' now.")
@utils.arg('--db-lv-size', metavar='<DB_LV_SIZE>',
           help='the size of database disk(M).')
@utils.arg('--nova-lv-size', metavar='<NOVA_LV_SIZE>',
           help='the size of logic volume disk for nova, and the unit is MB.')
@utils.arg('--disk-location', metavar='<DISK_LOCATION>',
           help='where disks used by backends from, default is "local". \
                 "local" means disks come from local host, \
                 "share" means disks come from share storage devices')
@utils.arg('--role-type', metavar='<ROLE_TYPE>',
           help='type of role')
def do_role_add(gc, args):
    """Add a role."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.roles.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    role = gc.roles.add(**fields)

    _daisy_show(role)


@utils.arg('roles', metavar='<ROLE>', nargs='+',
           help='ID of role(s) to delete.')
def do_role_delete(gc, args):
    """Delete specified role(s)."""

    for args_role in args.roles:
        role = utils.find_resource(gc.roles, args_role)
        if role and role.deleted:
            msg = "No role with an ID of '%s' exists." % role.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting role delete for %s ...' %
                      encodeutils.safe_decode(args_role), end=' ')
            gc.roles.delete(role)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete role %s' % (e, args_role))


@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='Roles that belong to cluster.')
def do_role_list(gc, args):
    """List roles you can access."""
    filter_keys = ['cluster_id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    # fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}

    roles = gc.roles.list(**kwargs)
    columns = ['ID', 'Name', 'Description', 'Status', 'Progress',
               'Config_Set_ID', 'CLUSTER_ID', 'TYPE', 'VIP',
               'Deployment_Backend']
    utils.print_list(roles, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter roles to those that have this name.')
def do_role_detail(gc, args):
    """List roles you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        role = utils.find_resource(gc.roles, fields.pop('id'))
        _daisy_show(role)
    else:
        roles = gc.roles.list(**kwargs)
        columns = ['ID', 'Name', 'Description', 'Status',
                   'Progress', 'Config_Set_ID', 'CLUSTER_ID', 'TYPE', 'VIP']
        utils.print_list(roles, columns)


@utils.arg('--neutron-backend', metavar='<zenic_ip=1.1.1.1,'
                                        'sdn_controller_type=ZENIC,'
                                        'zenic_port=8181,'
                                        'zenic_user_password=ossdbg1,'
                                        'neutron_agent_type=SDN_Agent,'
                                        'zenic_user_name=root,'
                                        'enable_l2_or_l3=l3>',
           help='neutron-backend of sdn_type')
@utils.arg('role', metavar='<ROLE>', help='ID of role to modify.')
@utils.arg('--name', metavar='<NAME>',
           help='Name of role.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of role.')
@utils.arg('--config-set-id', metavar='<CONFIG_SET_ID>',
           help='Roles that belong to the config-set of the ID.')
@utils.arg('--nodes', metavar='<NODES>', nargs='+',
           help='Roles that belong to the host of the id,\
           host id can be more than one')
@utils.arg('--services', metavar='<SERVICES>', nargs='+',
           help='Roles that belong to the service of the id, \
           service id can be more than one')
# @utils.arg('--status', metavar='<STATUS>',
#           help='The role of the status.')
# @utils.arg('--progress', metavar='<PROGRESS>',
#           help='The role of the progress.')
@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='Roles that belong to cluster of id.')
@utils.arg('--type', metavar='<TYPE>',
           help='The value should be template or  custom.')
@utils.arg('--vip', metavar='<VIP>',
           help='float ip.')
@utils.arg('--glance-lv-size', metavar='<GLANCE_LV_SIZE>',
           help='the size of logic volume disk for storaging image,\
            and the unit is M.')
@utils.arg('--deployment-backend', metavar='<deployment_backend>',
           help="deployment backend,\
            supported bacends are 'tecs' and 'zenic' now.")
@utils.arg('--db-lv-size', metavar='<DB_LV_SIZE>',
           help='the size of database disk(M).')
@utils.arg('--nova-lv-size', metavar='<NOVA_LV_SIZE>',
           help='the size of logic volume disk for nova, and the unit is MB.')
@utils.arg('--docker-vg-size', metavar='<DOCKER_VG_SIZE>',
           help='the size of docker_vg(M).')
@utils.arg('--disk-location', metavar='<DISK_LOCATION>',
           help='where disks used by backends from, default is "local". \
                 "local" means disks come from local host, \
                 "share" means disks come from share storage devices')
@utils.arg('--ntp-server', metavar='<NTP_SERVER>',
           help='ip of ntp server')
@utils.arg('--role-type', metavar='<ROLE_TYPE>',
           help='type of role')
@utils.arg('--db-vip', metavar='<DB_VIP>',
           help='float ip of db')
@utils.arg('--glance-vip', metavar='<GLANCE_VIP>',
           help='float ip of glance')
@utils.arg('--public-vip', metavar='<PUBLIC_VIP>',
           help='float ip of public.')
@utils.arg('--mongodb-vip', metavar='<MONGODB_VIP>',
           help='float ip of mongodb')
def do_role_update(gc, args):
    """Update a specific role."""
    # Filter out None values
    neutron_backend_array_list = []
    neutron_backend_info = {'zenic_ip': '',
                            'sdn_controller_type': '',
                            'zenic_port': '',
                            'zenic_user_password': '',
                            'neutron_agent_type': '',
                            'zenic_user_name': '',
                            'enable_l2_or_l3': ''}
    if args.neutron_backend:
        neutron_backend_data = args.neutron_backend.split(",")
        for neutron_backend in neutron_backend_data:
            key, value = neutron_backend.split("=", 1)
            if key in neutron_backend_info:
                neutron_backend_info[key] = value
        neutron_backend_array_list.append(neutron_backend_info)
    args.neutron_backends_array = neutron_backend_array_list
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    role_arg = fields.pop('role')
    role = utils.find_resource(gc.roles, role_arg)

    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.roles.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))

    role = gc.roles.update(role, **fields)
    _daisy_show(role)


@utils.arg('name', metavar='<NAME>',
           help='config_file name to be added.')
@utils.arg('description', metavar='<DESCRIPTION>',
           help='config_file description to be added.')
def do_config_file_add(gc, args):
    """Add a config_file."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.config_files.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    config_file = gc.config_files.add(**fields)

    _daisy_show(config_file)


@utils.arg('config_files', metavar='<CONFIG_FILE>', nargs='+',
           help='ID of config_file(s) to delete.')
def do_config_file_delete(gc, args):
    """Delete specified config_file(s)."""

    for args_config_file in args.config_files:
        config_file = utils.find_resource(gc.config_files, args_config_file)
        if config_file and config_file.deleted:
            msg = "No config_file with an ID of '%s' exists." % config_file.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting config_file delete for %s ...' %
                      encodeutils.safe_decode(args_config_file), end=' ')
            gc.config_files.delete(config_file)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete config_file %s' %
                  (e, args_config_file))


@utils.arg('config_file', metavar='<CONFIG_FILE>',
           help='ID of config_file to modify.')
@utils.arg('--name', metavar='<NAME>',
           help='Name of config_file.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of config_file.')
def do_config_file_update(gc, args):
    """Update a specific config_file."""
    # Filter out None values
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    config_file_arg = fields.pop('config_file')
    config_file = utils.find_resource(gc.config_files, config_file_arg)

    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.config_files.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))

    config_file = gc.config_files.update(config_file, **fields)
    _daisy_show(config_file)


def do_config_file_list(gc, args):
    """List config_files you can access."""
    filter_keys = ''
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        config_file = utils.find_resource(gc.config_files, fields.pop('id'))
        _daisy_show(config_file)
    else:
        config_files = gc.config_files.list(**kwargs)
        columns = ['ID', 'Name', 'Description']
        utils.print_list(config_files, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter config_file to those that have this id.')
def do_config_file_detail(gc, args):
    """List config_files you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        config_file = utils.find_resource(gc.config_files, fields.pop('id'))
        _daisy_show(config_file)
    else:
        config_files = gc.config_files.list(**kwargs)
        columns = ['ID', 'Name', 'Description']
        utils.print_list(config_files, columns)


@utils.arg('name', metavar='<NAME>',
           help='config_set name to be added.')
@utils.arg('description', metavar='<DESCRIPTION>',
           help='config_set description to be added.')
def do_config_set_add(gc, args):
    """Add a config_set."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.config_sets.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    config_set = gc.config_sets.add(**fields)

    _daisy_show(config_set)


@utils.arg('config_sets', metavar='<CONFIG_SET>', nargs='+',
           help='ID of config_set(s) to delete.')
def do_config_set_delete(gc, args):
    """Delete specified config_set(s)."""

    for args_config_set in args.config_sets:
        config_set = utils.find_resource(gc.config_sets, args_config_set)
        if config_set and config_set.deleted:
            msg = "No config_set with an ID of '%s' exists." % config_set.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting config_set delete for %s ...' %
                      encodeutils.safe_decode(args_config_set), end=' ')
            gc.config_sets.delete(config_set)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete config_set %s' % (e, args_config_set))


@utils.arg('config_set', metavar='<CONFIG_SET>',
           help=' ID of config_set to modify.')
@utils.arg('--name', metavar='<NAME>',
           help='Name of config_set.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of config_set.')
def do_config_set_update(gc, args):
    """Update a specific config_set."""
    # Filter out None values
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    config_set_arg = fields.pop('config_set')
    config_set = utils.find_resource(gc.config_sets, config_set_arg)

    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.config_sets.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))

    config_set = gc.config_sets.update(config_set, **fields)
    _daisy_show(config_set)


def do_config_set_list(gc, args):
    """List config_sets you can access."""
    filter_keys = ''
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        config_set = utils.find_resource(gc.config_sets, fields.pop('id'))
        _daisy_show(config_set)
    else:
        config_sets = gc.config_sets.list(**kwargs)
        columns = ['ID', 'Name', 'Description']
        utils.print_list(config_sets, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter components to those that have this name.')
def do_config_set_detail(gc, args):
    """List config_sets you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        config_set = utils.find_resource(gc.config_sets, fields.pop('id'))
        _daisy_show(config_set)
    else:
        config_sets = gc.config_sets.list(**kwargs)
        columns = ['ID', 'Name', 'Description']
        utils.print_list(config_sets, columns)


@utils.arg('config', metavar='<CONFIG>', nargs='+',
           help='ID of config(s) to delete.')
def do_config_delete(gc, args):
    """Delete specified config(s)."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.configs.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))
    gc.configs.delete(**fields)


def do_config_list(gc, args):
    """List configs you can access."""
    filter_keys = ''
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        config = utils.find_resource(gc.configs, fields.pop('id'))
        _daisy_show(config)
    else:
        configs = gc.configs.list(**kwargs)
        columns = ['ID', 'Section', 'Key', 'Value', 'Description',
                   'Config_file_id', 'Config_version', 'Running_version']
        utils.print_list(configs, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter configs to those that have this id.')
def do_config_detail(gc, args):
    """List configs you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        config = utils.find_resource(gc.configs, fields.pop('id'))
        _daisy_show(config)
    else:
        configs = gc.configs.list(**kwargs)
        columns = ['ID', 'Section', 'Key', 'Value', 'Description',
                   'Config_file_id', 'Config_version', 'Running_version']
        utils.print_list(configs, columns)


@utils.arg('name', metavar='<NAME>', help='NAME of network.')
@utils.arg('description', metavar='<DESCRIPTION>',
           help='Description of network.')
@utils.arg('network_type', metavar='<NETWORK_TYPE>',
           help='type of network:PUBLICAPI,DATAPLANE,STORAGE,\
           MANAGEMENT,EXTERNAL,DEPLOYMENT,HEARTBEAT')
@utils.arg('--cluster-id', metavar='<CLUSTER>',
           help='ID of cluster, must be given.')
@utils.arg('--vlan-start', metavar='<VLAN_START>',
           help='vlan start of network.it should be a integer in "1~4096",\
            and it must be appeared with vlan end')
@utils.arg('--vlan-end', metavar='<VLAN_END>',
           help='vlan end of network.it should be a integer in "1~4096",\
            and it must be appeared with vlan start')
@utils.arg('--gre-id-start', metavar='<GRE_ID_START>',
           help='gre-id start of network.it should be a integer in "1~4096",\
            and it must be appeared with gre-id end')
@utils.arg('--gre-id-end', metavar='<GRE_ID_END>',
           help='gre-id end of network.it should be a integer in "1~4096",\
            and it must be appeared with gre-id start')
@utils.arg('--vni-start', metavar='<VNI_START>',
           help='vni start of network.it should be a integer in "1~16777216",\
            and it must be appeared with vni end')
@utils.arg('--vni-end', metavar='<VNI_END>',
           help='vni end of network.it should be a integer in "1~16777216",\
            and it must be appeared with vni start')
@utils.arg('--cidr', metavar='<CIDR>',
           help='specifying ip range of network. eg:192.168.1.1/24')
@utils.arg('--ip', metavar='<IP>',
           help='ip of build pxe server')
@utils.arg('--ip-ranges', metavar='<IP_RANGES>', nargs='+',
           help='ip ranges of network.  \
           for example:"start":"172.16.0.2", "end":"172.16.0.126", \
           "cidr":"172.16.0.126/24", "gateway":"172.16.0.1"')
@utils.arg('--gateway', metavar='<GATEWAY>',
           help='gate way of network')
@utils.arg('--type', metavar='<TYPE>',
           help='type of network:custom or template')
@utils.arg('--ml2-type', metavar='<ML2_TYPE>',
           help='ml2 type:"ovs", "sriov(direct)", "sriov(macvtap)", \
           "ovs,sriov(direct)" or "ovs,sriov(macvtap)".\
                 when network-type is DATAPLANE, ml2-type must be given')
@utils.arg('--physnet-name', metavar='<PHYSNET_NAME>',
           help='physnet name,eg:physnet_eth0')
@utils.arg('--capability', metavar='<CAPABILITY>',
           help='CAPABILITY of network:high or low')
@utils.arg('--vlan-id', metavar='<VLAN_ID>',
           help='Vlan Tag.')
@utils.arg('--mtu', metavar='<MTU>',
           help='Private plane mtu.eg.:1600.')
@utils.arg('--segmentation-type', metavar='<SEGMENTATION_TYPE>',
           help='network plane segmentation type.')
@utils.arg('--svlan-start', metavar='<SVLAN_START>',
           help='svlan start of network.it should be a integer in "1~4096",\
            and it must be appeared with svlan end')
@utils.arg('--svlan-end', metavar='<SVLAN_END>',
           help='svlan end of network.it should be a integer in "1~4096",\
            and it must be appeared with svlan start')
def do_network_add(gc, args):
    """Add a network."""
    ip_range_list = []
    if args.ip_ranges:
        for ip_range in args.ip_ranges:
            ip_range_ref = {}
            for range_value in ip_range.split(","):
                try:
                    k, v = range_value.split(":", 1)
                    if str(k) == "start":
                        ip_range_ref['start'] = str(v)
                    if str(k) == "end":
                        ip_range_ref['end'] = str(v)
                    if str(k) == "cidr":
                        ip_range_ref['cidr'] = str(v)
                    if str(k) == "gateway":
                        ip_range_ref['gateway'] = str(v)
                except ValueError:
                    raise exc.CommandError("ip_ranges error")
            ip_range_list.append(ip_range_ref)
        args.ip_ranges = ip_range_list

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.networks.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    network = gc.networks.add(**fields)

    _daisy_show(network)


@utils.arg('network', metavar='<NETWORK>', help='ID of network.')
@utils.arg('--network-type', metavar='<NETWORK_TYPE>',
           help='type of network:PUBLICAPI,DATAPLANE,\
           STORAGE,MANAGEMENT,EXTERNAL,DEPLOYMENT,HEARTBEAT')
@utils.arg('--name', metavar='<NAME>',
           help='Name of network.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of network.')
@utils.arg('--vlan-start', metavar='<VLAN_START>',
           help='vlan start of network.it should be a integer in "1~4096", \
           and it must be appeared with vlan end')
@utils.arg('--vlan-end', metavar='<VLAN_END>',
           help='vlan end of network.it should be a integer in "1~4096",\
            and it must be appeared with vlan start')
@utils.arg('--gre-id-start', metavar='<GRE_ID_START>',
           help='gre-id start of network.it should be a integer in "1~4096",\
            and it must be appeared with gre-id end')
@utils.arg('--gre-id-end', metavar='<GRE_ID_END>',
           help='gre-id end of network.it should be a integer in "1~4096",\
            and it must be appeared with gre-id start')
@utils.arg('--vni-start', metavar='<VNI_START>',
           help='vni start of network.it should be a integer in "1~16777216",\
            and it must be appeared with vni end')
@utils.arg('--vni-end', metavar='<VNI_END>',
           help='vni end of network.it should be a integer in "1~16777216",\
            and it must be appeared with vni start')
@utils.arg('--cidr', metavar='<CIDR>',
           help='specifying ip range of network. eg:192.168.1.1/24')
@utils.arg('--ip', metavar='<IP>',
           help='ip of build pxe server')
@utils.arg('--ip-ranges', metavar='<IP_RANGES>', nargs='+',
           help='ip ranges of network,for example:"start":\
           "172.16.0.2","end":"172.16.0.126","cidr":"172.16.0.126/24",\
           "gateway":"172.16.0.1"')
@utils.arg('--gateway', metavar='<GATEWAY>',
           help='gate way of network')
@utils.arg('--type', metavar='<TYPE>',
           help='type of network:custom or template')
@utils.arg('--ml2-type', metavar='<ML2_TYPE>',
           help='ml2 type:"ovs", "sriov(direct)", "sriov(macvtap)", \
           "ovs,sriov(direct)" or "ovs,sriov(macvtap)".\
                 when network-type is DATAPLANE, ml2-type must be given')
@utils.arg('--physnet-name', metavar='<PHYSNET_NAME>',
           help='physnet name,eg:physnet_eth0')
@utils.arg('--capability', metavar='<CAPABILITY>',
           help='CAPABILITY of network:high or low')
@utils.arg('--vlan-id', metavar='<VLAN_ID>',
           help='Vlan Tag.')
@utils.arg('--mtu', metavar='<MTU>',
           help='Private plane mtu.eg.:1600.')
@utils.arg('--alias', metavar='<ALIAS>',
           help='alias of network')
@utils.arg('--segmentation-type', metavar='<SEGMENTATION_TYPE>',
           help='network plane segmentation type.')
@utils.arg('--svlan-start', metavar='<SVLAN_START>',
           help='svlan start of network.it should be a integer in "1~4096",\
            and it must be appeared with svlan end')
@utils.arg('--svlan-end', metavar='<SVLAN_END>',
           help='svlan end of network.it should be a integer in "1~4096",\
            and it must be appeared with svlan start')
def do_network_update(gc, args):
    """Update a specific network."""
    # Filter out None values

    ip_range_list = []

    if args.ip_ranges:
        for ip_range in args.ip_ranges:
            ip_range_ref = {}
            for range_value in ip_range.split(","):
                try:
                    k, v = range_value.split(":", 1)
                    if str(k) == "start":
                        ip_range_ref['start'] = str(v)
                    if str(k) == "end":
                        ip_range_ref['end'] = str(v)
                    if str(k) == "cidr":
                        ip_range_ref['cidr'] = str(v)
                    if str(k) == "gateway":
                        ip_range_ref['gateway'] = str(v)
                except ValueError:
                    raise exc.CommandError("ip_ranges error")
            ip_range_list.append(ip_range_ref)
        args.ip_ranges = ip_range_list
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    network_arg = fields.pop('network')

    network = utils.find_resource(gc.networks, network_arg)
    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.networks.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))

    network = gc.networks.update(network, **fields)
    _daisy_show(network)


@utils.arg('networks', metavar='<NETWORK>', nargs='+', help='ID of network.')
@utils.arg('--cluster-id', metavar='<CLUSTER>', help='ID of cluster .')
def do_network_delete(gc, args):
    """Delete specified network(s)."""

    for args_network in args.networks:
        network = utils.find_resource(gc.networks, args_network)
        if network and network.deleted:
            msg = "No network with an ID of '%s' exists." % network.id
            raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting network delete for %s ...' %
                      encodeutils.safe_decode(args_network), end=' ')
            gc.networks.delete(network)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete network %s' % (e, args_network))


@utils.arg('--cluster-id', metavar='<cluster ID>',
           help='Filter networks to those that have this name.')
@utils.arg('--type', metavar='<TYPE>',
           help='Filter networks by type, '
                'support "custom", "default", "template" and "system".')
@utils.arg('--page-size', metavar='<SIZE>', default=None, type=int,
           help='Number of networks to request in each paginated request.')
@utils.arg('--sort-key', default='name',
           choices=daisyclient.v1.networks.SORT_KEY_VALUES,
           help='Sort networks list by specified field.')
@utils.arg('--sort-dir', default='asc',
           choices=daisyclient.v1.networks.SORT_DIR_VALUES,
           help='Sort networks list in specified direction.')
def do_network_list(gc, args):
    """List networks you can access."""
    filter_keys = ['cluster_id', 'type']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    kwargs = {'id': args.cluster_id, 'filters': filters}
    if args.page_size is not None:
        kwargs['page_size'] = args.page_size

    kwargs['sort_key'] = args.sort_key
    kwargs['sort_dir'] = args.sort_dir

    networks = gc.networks.list(**kwargs)

    columns = ['ID', 'Name', 'Cluster_id', 'Description',
               'Vlan_start', 'Vlan_end', 'Gateway', 'Cidr',
               'Type', 'Ip_ranges', 'Segmentation_type']
    utils.print_list(networks, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter network to those that have this id.')
def do_network_detail(gc, args):
    """List network you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        network = utils.find_resource(gc.networks, fields.pop('id'))
        _daisy_show(network)
    else:
        network = gc.networks.list(**kwargs)
        columns = ['ID', 'Name', 'Cluster_id', 'Description',
                   'Vlan_start', 'Vlan_end', 'Gateway', 'Cidr',
                   'Type', 'Ip_ranges', 'Segmentation_type']
        utils.print_list(network, columns)


@utils.arg('cluster_id', metavar='<CLUSTER>',
           help='ID of cluster to install TECS.')
@utils.arg('--version-id', metavar='<VERSION>',
           help='Version of TECS.')
@utils.arg('--deployment-interface', metavar='<DEPLOYMNET>',
           help='Network interface construction of PXE server(eg:eth0).')
@utils.arg('--skip-pxe-ipmi', metavar='<SKIP>',
           help='skip pxe and ipmi(eg:true).')
@utils.arg('--pxe-only', metavar='<PXE>',
           help='build pxe of os(eg:true).')
def do_install(dc, args):
    """Install TECS."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.install.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    install = dc.install.install(**fields)

    _daisy_show(install)


@utils.arg('cluster_id', metavar='<CLUSTER_ID>',
           help='The cluster ID to uninstall TECS.')
def do_uninstall(gc, args):
    """Uninstall TECS."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.uninstall.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    uninstall = gc.uninstall.uninstall(**fields)
    _daisy_show(uninstall)


@utils.arg('cluster_id', metavar='<CLUSTER_ID>',
           help='The cluster ID to query progress of uninstall TECS .')
def do_query_uninstall_progress(gc, args):
    """Query uninstall progress."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    CREATE_PARAMS = daisyclient.v1.uninstall.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    query_progress = gc.uninstall.query_progress(**fields)

    _daisy_show(query_progress)


@utils.arg('cluster_id', metavar='<CLUSTER_ID>',
           help='The cluster ID to update os and TECS.')
@utils.arg('--hosts', metavar='<HOSTS>', nargs='+',
           help='The host ID to update')
@utils.arg('--update-object', metavar='<UPDATE_OBJECT>',
           help='update object:vplat or tecs or zenic......')
@utils.arg('--version-id', metavar='<VERSION>',
           help='if not patch, update version id is used to update.')
@utils.arg('--version-patch-id', metavar='<VERSION_PATCH>',
           help='if update version patch, version patch id is needed')
@utils.arg('--update-script', metavar='<UPDATE_SCRIPT>',
           help='update script in /var/lib/daisy/os')
def do_update(gc, args):
    """update TECS."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.update.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    update = gc.update.update(**fields)
    _daisy_show(update)


@utils.arg('cluster_id', metavar='<CLUSTER_ID>',
           help='The cluster ID to query progress of update os and TECS .')
def do_query_update_progress(gc, args):
    """Query update progress."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    CREATE_PARAMS = daisyclient.v1.update.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    query_progress = gc.update.query_progress(**fields)
    _daisy_show(query_progress)


@utils.arg('cluster_id', metavar='<CLUSTER_ID>',
           help='The cluster ID on which to export tecs \
           and HA config file from database.')
def do_export_db(gc, args):
    """export database."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.install.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    config_file = gc.install.export_db(**fields)
    _daisy_show(config_file)


@utils.arg('--cluster', metavar='<CLUSTER>',
           help='cluster id to add config. '
           'when add config to role, cluster must be given.')
@utils.arg('--role', metavar='<ROLE_NAME>',
           help='add config to role, this is the first way to add config.')
@utils.arg('--host-id', metavar='<HOST_ID>',
           help='add config to host, '
                'this is the second way to add config.')
@utils.arg('--config-set', metavar='<config_set>',
           help='add config by config set id, '
                'this is the third way to add config.')
@utils.arg('--config', metavar='<file-name=name,section=section,\
                                key=key,value=value,description=description>',
           nargs='+',
           help='file-name must take full path.such as:\
                 file-name=/etc/nova/nova.conf,section=DEFAULT,\
                 key=port,value=5661,description=description')
def do_config_add(gc, args):
    """add and update config interfaces."""
    config_interface_list = []
    if args.config:
        for interfaces in args.config:
            interface_info = {
                "file-name": "", "section": "", "key": "",
                "value": "", "description": ""}
            # if ',' in value of a confit item, merge them.
            config_items = interfaces.split(",")
            real_config_items = []
            for item in config_items:
                try:
                    if len(item.split("=")) == 1:
                        real_config_items[
                            len(real_config_items) - 1] += (',' + item)
                    else:
                        real_config_items.append(item)
                except ValueError:
                    raise exc.CommandError("config arguments error")

            # get key and value of config item
            for kv_str in real_config_items:
                try:
                    k, v = kv_str.split("=", 1)
                except ValueError:
                    raise exc.CommandError("config-interface error")
                if k in interface_info:
                    interface_info[k] = v
            config_interface_list.append(interface_info)
        args.config = config_interface_list
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    CREATE_PARAMS = daisyclient.v1.configs.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    config_interface_info = gc.configs.add(**fields)
    _daisy_show(config_interface_info)


@utils.arg('cluster', metavar='<CLUSTER>',
           help='ID of cluster to config file.')
@utils.arg('--role', metavar='<NAME>',
           nargs='+',
           help=' role name.')
def do_cluster_config_set_update(gc, args):
    """the cluster of config effect."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    CREATE_PARAMS = daisyclient.v1.configs.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    config_interface_info = gc.config_sets.cluster_config_set_update(**fields)
    _daisy_show(config_interface_info)


@utils.arg('cluster', metavar='<CLUSTER>',
           help='ID of cluster to config file.')
@utils.arg('--role', metavar='<NAME>',
           nargs='+',
           help=' role name.')
def do_cluster_config_set_progress(gc, args):
    """query cluster of config progress."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    CREATE_PARAMS = daisyclient.v1.configs.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    config_set_progress = gc.config_sets.cluster_config_set_progress(**fields)
    _daisy_show(config_set_progress)


@utils.arg('--cluster-id', metavar='<CLUSTER_ID>',
           help='the host that will discover for cluster.')
def do_discover_host(gc, args):
    filter_keys = ['cluster_id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])

    discover_host = gc.hosts.discover_host(**filters)
    _daisy_show(discover_host)


@utils.arg('service', metavar='<SERVICE>',
           help='service name who will use disk storage, suport db, \
           glance and dbbackup.')
@utils.arg('role_id', metavar='<ROLE_ID>',
           help='which role service come from.')
@utils.arg('--disk-location', metavar='<DISK_LOCATION>',
           help='where disks from, default is "local". \
                 "local" means disks come from local host,\
                 "share" means disks come from share storage devices,\
                 "share cluster" means disks come from share cluster \
                 storage devices.')
@utils.arg('--data-ips', metavar='<DATA_IPS>',
           help='data interfaces ip of Disk Array device, separate by ",", \
                  when DISK_LOCATION is share, DATA_IPS cannot be empty')
@utils.arg('--size', metavar='<SIZE>',
           help='unit is G, and default is -1,\
            it means to use all of the disk.')
@utils.arg('--lun', metavar='<LUN>',
           help='mark which volume is used for glance sharing disk.')
@utils.arg('--protocol-type', metavar='<PROTOCOL_TYPE>',
           help='protocol type of share disks')
@utils.arg('--partition', metavar='<PARTITION>',
           help='partition name of local disks')
def do_service_disk_add(dc, args):
    """ config services share disk. """

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    SERVICE_DISK_PARAMS = daisyclient.v1.disk_array.CREATE_SERVICE_DISK_PARAMS
    fields = dict(
        filter(lambda x: x[0] in SERVICE_DISK_PARAMS, fields.items()))
    # if fields.has_key('data_ips'):
    #    fields['data_ips'] = fields['data_ips'].split(",")

    service_disk_info = dc.disk_array.service_disk_add(**fields)

    _daisy_show(service_disk_info)


@utils.arg('service_disks', metavar='<SERVICE_DISKS>', nargs='+',
           help='ID(s) of service_disk to delete.')
def do_service_disk_delete(dc, args):
    """Delete specified service_disk."""

    for service_disk_id in args.service_disks:
        # service_disk = utils.find_resource(dc.disk_array, service_disk_id)
        # if service_disk and service_disk.deleted:
            # msg = "No service_disk with ID '%s' exists." % service_disk_id
            # raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting service_disk_id delete for %s ...' %
                      encodeutils.safe_decode(service_disk_id), end=' ')
            dc.disk_array.service_disk_delete(service_disk_id)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete service_disk %s' %
                  (e, service_disk_id))


@utils.arg('id', metavar='<ID>',
           help='ID of service_disk.')
@utils.arg('--service', metavar='<SERVICE>',
           help='service name who will use Disk Array device, '
                'suport db, glance and dbbackup.')
@utils.arg('--role-id', metavar='<ROLE_ID>',
           help='which role service come from.')
@utils.arg('--disk-location', metavar='<DISK_LOCATION>',
           help='where disks from, default is "local". \
                 "local" means disks come from local host,\
                 "share" means disks come from Disk Array device')
@utils.arg('--data-ips', metavar='<DATA_IPS>',
           help='data interfaces ip of Disk Array device, separate by ",", \
                  when DISK_LOCATION is share, DATA_IPS cannot be empty')
@utils.arg('--size', metavar='<SIZE>',
           help='unit is G, and default is -1, '
                'it means to use all of the disk.')
@utils.arg('--lun', metavar='<LUN>',
           help='mark which lun is used for Disk Array device,'
                'default is 0.')
@utils.arg('--protocol-type', metavar='<PROTOCOL_TYPE>',
           help='protocol type of share disks')
def do_service_disk_update(dc, args):
    """Update a specific service_disk."""
    # Filter out None values
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    id = fields.pop('id')
    utils.find_resource(dc.disk_array, id)

    # Filter out values we can't use
    SERVICE_DISK_PARAMS = daisyclient.v1.disk_array.CREATE_SERVICE_DISK_PARAMS
    fields = dict(
        filter(lambda x: x[0] in SERVICE_DISK_PARAMS, fields.items()))

    service_disk_info = dc.disk_array.service_disk_update(id, **fields)
    _daisy_show(service_disk_info)


@utils.arg('--role-id', metavar='<ROLE_ID>',
           help='filter service_disks by role id.')
def do_service_disk_list(dc, args):
    """List service_disk you can access."""
    filter_keys = ['role_id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    # fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}

    disk_array_list = dc.disk_array.service_disk_list(**kwargs)
    columns = ['ID', 'SERVICE', 'ROLE_ID',
               'DISK_LOCATION', 'DATA_IPS', 'SIZE', 'LUN']
    utils.print_list(disk_array_list, columns)


@utils.arg('id', metavar='<ID>',
           help='get service_disk detail by its id.')
def do_service_disk_detail(dc, args):
    """detail service_disk you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        # service_disk = utils.find_resource(dc.disk_array, fields.pop('id'))
        service_disk_info = dc.disk_array.service_disk_detail(
            fields.pop('id'), **fields)
        _daisy_show(service_disk_info)
    else:
        service_disk = dc.disk_array.service_disk_list(**kwargs)
        columns = ['ID', 'SERVICE', 'ROLE_ID',
                   'DISK_LOCATION', 'DATA_IPS', 'SIZE', 'LUN']
        utils.print_list(service_disk, columns)


def _paraser_disk_array(disk_array):
    disk_arrays = []
    CINDER_VOLUME_BACKEND_PARAMS =\
        daisyclient.v1.disk_array.CREATE_CINDER_BACKEND_INTER_PARAMS
    if disk_array:
        for array in disk_array:
            disk_array_info = {}
            for kv_str in array.split(","):
                try:
                    k, v = kv_str.split("=", 1)
                except ValueError:
                    raise exc.CommandError("disk_array error")
                if k in CINDER_VOLUME_BACKEND_PARAMS:
                    if (k == 'pools' or
                            k == 'data_ips' or
                            k == 'management_ips'):
                        disk_array_info[k] = ','.join(v.split("_"))
                    else:
                        disk_array_info[k] = v
            disk_arrays.append(disk_array_info)
    return disk_arrays


@utils.arg('disk_array', metavar='<management_ips=ip1_ip2,data_ips=ip3_ip4,'
           'pools=pool1_pool2,user_name=user_name,user_pwd=user_pwd,'
           'volume_driver=KS3200_FCSAN,volume_type=KISP-1>',
           nargs='+',
           help='management_ips: management interfaces ip of Disk Array\
                device, separate by "_";\
                data_ips:data interfaces ip of Disk Array device,\
                separate by ",", \
                when using FUJITSU Disk Array, DATA_IPS cannot be empty;\
                pools: pools name which are configed in Disk Array device;\
                user_name: user name to login Disk Array device;\
                user_pwd: user password to login Disk Array device;\
                volume_driver: supports "KS3200_FCSAN", "KS3200_IPSAN"\
                and "FUJITSU_ETERNUS" according by Disk Array device type,\
                separate by "_";\
                volume_type: maybe same in two backends.')
@utils.arg('role_id', metavar='<ROLE_ID>',
           help='filter cinder_volumes by role id.')
def do_cinder_volume_add(dc, args):
    """config cinder volume backend."""
    args.disk_array = _paraser_disk_array(args.disk_array)
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    # Filter out values we can't use
    CINDER_BACKEND_PARAMS = (daisyclient.v1.disk_array.
                             CREATE_CINDER_BACKEND_PARAMS)
    fields = dict(
        filter(lambda x: x[0] in CINDER_BACKEND_PARAMS, fields.items()))
    cinder_volume_info = dc.disk_array.cinder_volume_add(**fields)

    _daisy_show(cinder_volume_info)


@utils.arg('cinder_volumes', metavar='<CINDER_VOLUMES>', nargs='+',
           help='ID(s) of cinder volumes to delete.')
def do_cinder_volume_delete(dc, args):
    """delete specified cinder_volume backend."""
    for cinder_volume_id in args.cinder_volumes:
        # cinder_volume = utils.find_resource(dc.disk_array, cinder_volume_id)
        # if cinder_volume and cinder_volume.deleted:
        #    msg = "No cinder_volume with ID '%s' exists." % cinder_volume_id
        #    raise exc.CommandError(msg)
        try:
            if args.verbose:
                print('Requesting cinder_volume_id delete for %s ...' %
                      encodeutils.safe_decode(cinder_volume_id), end=' ')
            dc.disk_array.cinder_volume_delete(cinder_volume_id)

            if args.verbose:
                print('[Done]')

        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete cinder volume %s' %
                  (e, cinder_volume_id))


@utils.arg('id', metavar='<ID>',
           help='ID of cinder_volume.')
@utils.arg('--management-ips', metavar='<MANAGEMENT_IPS>',
           help='management interfaces ip of Disk Array device, \
           separate by ","')
@utils.arg('--data-ips', metavar='<DATA_IPS>',
           help='data interfaces ip of Disk Array device, separate by ",", \
                  when using FUJITSU Disk Array, DATA_IPS cannot be empty')
@utils.arg('--pools', metavar='<POOLS>',
           help='pools name which are configed in Disk Array device')
@utils.arg('--volume-driver', metavar='<VOLUME_DRIVER>',
           help='supports "KS3200_FCSAN", "KS3200_IPSAN" and "FUJITSU_ETERNUS"\
            according by Disk Array device type, separate by ","')
@utils.arg('--volume-type', metavar='<VOLUME_TYPE>',
           help='it maybe same in two backends, supprot "" and ""')
@utils.arg('--role-id', metavar='<ROLE_ID>',
           help='which role cinder_volume come from.')
@utils.arg('--user-name', metavar='<USER_NAME>',
           help='user name of disk array')
@utils.arg('--user-pwd', metavar='<USER_PWD>',
           help='user password of disk arry')
def do_cinder_volume_update(dc, args):
    """Update a specific cinder_volume."""
    # Filter out None values
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    id = fields.pop('id')
    # Filter out values we can't use
    CINDER_VOLUME_PARAMS =\
        daisyclient.v1.disk_array.CREATE_CINDER_BACKEND_INTER_PARAMS
    fields = dict(
        filter(lambda x: x[0] in CINDER_VOLUME_PARAMS, fields.items()))

#    if fields.has_key('management_ips'):
    if 'management_ips' in fields:
        fields['management_ips'] = ','.join(
            fields['management_ips'].split("_"))
#    if fields.has_key():
    if 'data_ips' in fields:
        fields['data_ips'] = ','.join(fields['data_ips'].split("_"))
#    if fields.has_key():
    if 'pools' in fields:
        fields['pools'] = ','.join(fields['pools'].split("_"))

    cinder_volume_info = dc.disk_array.cinder_volume_update(id, **fields)
    _daisy_show(cinder_volume_info)


@utils.arg('--role-id', metavar='<ROLE_ID>',
           help='filter cinder_volumes by role id.')
def do_cinder_volume_list(dc, args):
    """List cinder_volume you can access."""
    filter_keys = ['role_id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    # fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}

    disk_array_list = dc.disk_array.cinder_volume_list(**kwargs)

    columns = ['ID', 'MANAGEMENT_IPS', 'DATA_IPS', 'POOLS',
               'VOLUME_DRIVER', 'VOLUME_TYPE', 'BACKEND_INDEX',
               'USER_NAME', 'USER_PWD', 'ROLE_ID']
    utils.print_list(disk_array_list, columns)


@utils.arg('id', metavar='<ID>',
           help='get cinder_volume detail by its id.')
def do_cinder_volume_detail(dc, args):
    """detail cinder_volume you can access."""
    filter_keys = ['id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    kwargs = {'filters': filters}
    if filters:
        cinder_volume_info = dc.disk_array.cinder_volume_detail(
            fields.pop('id'), **fields)
        _daisy_show(cinder_volume_info)
    else:
        cinder_volume = dc.disk_array.service_disk_list(**kwargs)
        columns = ['ID', 'MANAGEMENT_IPS', 'DATA_IPS', 'POOLS',
                   'VOLUME_DRIVER', 'VOLUME_TYPE', 'BACKEND_INDEX',
                   'USER_NAME', 'USER_PWD', 'ROLE_ID']
        utils.print_list(cinder_volume, columns)


@utils.arg('cluster', metavar='<CLUSTER>',
           help='ID of cluster to update disk array.')
def do_disk_array_update(dc, args):
    """update cluster disk array configuration for tecs backend only."""
    # Filter out None values
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    cluster_id = fields.pop('cluster')
    # Filter out values we can't use
    DISK_ARRAY_PARAMS = []
    fields = dict(filter(lambda x: x[0] in DISK_ARRAY_PARAMS, fields.items()))

    update_result = dc.install.disk_array_update(cluster_id, **fields)
    _daisy_show(update_result)


@utils.arg('name', metavar='<NAME>',
           help='Template name of the cluster.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of the template.')
@utils.arg('--type', metavar='<TYPE>',
           help='Type of the cluster.')
@utils.arg('--hosts', metavar='<HOSTS>',
           help='Hosts informations of the cluster.')
@utils.arg('--content', metavar='<CONTENT>',
           help='Contents of the cluster.')
def do_template_add(gc, args):
    """Add a template."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    CREATE_PARAMS = daisyclient.v1.template.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    template = gc.template.add(**fields)
    _daisy_show(template)


@utils.arg('id', metavar='<ID>',
           help='Id of the cluster template.')
@utils.arg('--name', metavar='<NAME>',
           help='Template name of the cluster.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of the template.')
@utils.arg('--type', metavar='<TYPE>',
           help='Type of the cluster.')
@utils.arg('--hosts', metavar='<HOSTS>',
           help='Hosts informations of the cluster.')
@utils.arg('--content', metavar='<CONTENT>',
           help='Contents of the cluster.')
def do_template_update(gc, args):
    """Update a template."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    template_id = fields.get('id', None)
    # Filter out values we can't use
    UPDATE_PARAMS = daisyclient.v1.template.UPDATE_PARAMS
    fields = dict(filter(lambda x: x[0] in UPDATE_PARAMS, fields.items()))
    template = gc.template.update(template_id, **fields)
    _daisy_show(template)


@utils.arg('id', metavar='<ID>', nargs='+',
           help='ID of templates.')
def do_template_delete(gc, args):
    """Delete specified template(s)."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    templates = fields.get('id', None)
    for template in templates:
        try:
            if args.verbose:
                print('Requesting host delete for %s ...' %
                      encodeutils.safe_decode(template), end=' ')
            gc.template.delete(template)
            if args.verbose:
                print('[Done]')
        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete cluster template %s' % (e, template))


@utils.arg('--name', metavar='<NAME>',
           help='Filter cluster templates to those that have this name.')
@utils.arg('--type', metavar='<TYPE>',
           help='Filter cluster template type.')
@utils.arg('--sort-key', default='name',
           choices=daisyclient.v1.template.SORT_KEY_VALUES,
           help='Sort cluster templates list by specified field.')
@utils.arg('--sort-dir', default='asc',
           choices=daisyclient.v1.template.SORT_DIR_VALUES,
           help='Sort cluster templates list in specified direction.')
def do_template_list(gc, args):
    """List templates you can access."""
    filter_keys = ['name', 'type']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    kwargs = {'filters': filters}
    kwargs['sort_key'] = args.sort_key
    kwargs['sort_dir'] = args.sort_dir
    templates = gc.template.list(**kwargs)
    columns = ['ID', 'Name', 'Type', 'Hosts', 'Content']
    utils.print_list(templates, columns)


@utils.arg('id', metavar='<ID>',
           help='ID of template.')
def do_template_detail(gc, args):
    """Get specified template."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    template_id = fields.get('id', None)
    try:
        if args.verbose:
            print('Requesting get template infomation for %s ...' %
                  encodeutils.safe_decode(template_id), end=' ')
        template = gc.template.get(template_id)
        if args.verbose:
            print('[Done]')
        _daisy_show(template)

    except exc.HTTPException as e:
        if args.verbose:
            print('[Fail]')
        print('%s: Unable to get template infomation %s' % (e, template_id))


@utils.arg('cluster_name', metavar='<CLUSTER_NAME>',
           help='Name of cluster to create template.')
@utils.arg('template_name', metavar='<TEMPLATE_NAME>',
           help='the name of json.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='Description of the template.')
@utils.arg('--type', metavar='<TYPE>',
           help='Export backend database based on type,'
                'for example:tecs,zenic')
def do_export_db_to_json(dc, args):
    """export db to json."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    CREATE_PARAMS = daisyclient.v1.template.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    export_db_to_json = dc.template.export_db_to_json(**fields)
    _daisy_show(export_db_to_json)


@utils.arg('json_file_path', metavar='<json_file_path>',
           help='The json file of path')
def do_import_json_to_template(dc, args):
    """import json to tempalte"""
    json_file = args.json_file_path
    if not os.path.exists(json_file):
        print("the json file not exist or permission deiny.")
        return
    with open(json_file) as tfp:
        params_json = tfp.read()
        params_json = json.dumps((json.loads(params_json)))
        dict_params = {'template': params_json}
    import_json_to_template = dc.template.import_json_to_template(
        **dict_params)
    _daisy_show(import_json_to_template)


@utils.arg('template_name', metavar='<TEMPLATE_NAME>',
           help='the name of json.')
@utils.arg('cluster', metavar='<CLUSTER>',
           help='The name of create cluster')
def do_import_template_to_db(dc, args):
    """import template to db"""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    CREATE_PARAMS = daisyclient.v1.template.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    import_template_to_db = dc.template.import_template_to_db(**fields)
    _daisy_show(import_template_to_db)


@utils.arg('cluster_name', metavar='<CLUSTER>',
           help='name of template.')
@utils.arg('host_id', metavar='<HOST>', help='host id.')
@utils.arg('host_template_name', metavar='<HOST_TEMPLATE_NAME>',
           help='host template name.')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='host template description.')
def do_host_to_template(dc, args):
    """HOST TO TEMPLATE."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.template.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    host_to_template = dc.template.host_to_template(**fields)
    _daisy_show(host_to_template)


@utils.arg('cluster_name', metavar='<CLUSTER>',
           help='name of cluster to config file.')
@utils.arg('host_template_name', metavar='<HOST_TEMPLATE_NAME>',
           help='host template name.')
@utils.arg('host_id', metavar='<HOST>',
           help='host id list')
def do_template_to_host(dc, args):
    """TEMPLATE TO HOST."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.template.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    template_to_host = dc.template.template_to_host(**fields)
    _daisy_show(template_to_host)


@utils.arg('cluster_name', metavar='<CLUSTER>',
           help='name of cluster.')
def do_host_template_list(dc, args):
    """GET ALL HOST TEMPLATE."""
    filter_keys = ['cluster_name']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])
    kwargs = {'filters': filters}
    get_all_host_template = dc.template.host_template_list(**kwargs)
    columns = ['name', 'description', 'os_version_file', 'role',
               'interfaces']
    utils.print_list(get_all_host_template, columns)


@utils.arg('cluster_name', metavar='<CLUSTER>',
           help='name of cluster to config file.')
@utils.arg('host_template_name', metavar='<HOST_TEMPLATE_NAME>',
           help='host template name.')
def do_delete_host_template(dc, args):
    """DELETE HOST TEMPLATE."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    CREATE_PARAMS = daisyclient.v1.template.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    host_template = dc.template.delete_host_template(**fields)
    _daisy_show(host_template)


@utils.arg('--provider-ip', metavar='<PROVIDER_IP>',
           help='The ip of provider.')
@utils.arg('--operation', metavar='<OPERATION>',
           help='The operation of cloud.')
@utils.arg('--name', metavar='<NAME>', help='The name of cloud.')
@utils.arg('--url', metavar='<URL>',
           help='The url of cloud.')
def do_inform_cloud_state(gc, args):
    """To inform provider the cloud state."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    try:
        gc.node.cloud_state(**fields)
    except exc.HTTPException as e:
        print('%s: Unable to inform provider' % e)


def do_backup(dc, args):
    """Backup daisy data."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    BACKUP_PARAMS = daisyclient.v1.backup_restore.BACKUP_PARAMS
    fields = dict(filter(lambda x: x[0] in BACKUP_PARAMS, fields.items()))
    backup = dc.backup_restore.backup(**fields)
    _daisy_show(backup)


@utils.arg('backup_file_path', metavar='<BACKUP_FILE_PATH>',
           help='The full path of backup file.')
def do_restore(dc, args):
    """Restore daisy data."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    RESTORE_PARAMS = daisyclient.v1.backup_restore.RESTORE_PARAMS
    fields = dict(filter(lambda x: x[0] in RESTORE_PARAMS, fields.items()))
    dc.backup_restore.restore(**fields)


@utils.arg('backup_file_path', metavar='<BACKUP_FILE_PATH>',
           help='The full path of backup file.')
def do_backup_file_version(dc, args):
    """Get version of backup file."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    RESTORE_PARAMS = daisyclient.v1.backup_restore.RESTORE_PARAMS
    fields = dict(filter(lambda x: x[0] in RESTORE_PARAMS, fields.items()))
    file_version = dc.backup_restore.backup_file_version(**fields)
    _daisy_show(file_version)


@utils.arg('--type', metavar='<TYPE>',
           help='Type of daisy version, supported types are '
                '"internal": the internal version of daisy,'
                '"pbr": the git version of daisy.')
def do_version(dc, args):
    """Get version of daisy."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    VERSION_PARAMS = daisyclient.v1.backup_restore.VERSION_PARAMS
    fields = dict(filter(lambda x: x[0] in VERSION_PARAMS, fields.items()))
    version = dc.backup_restore.version(**fields)
    _daisy_show(version)


def do_backend_types_get(dc, args):
    """Get backend_types of daisy."""
    backend_types_get = dc.backend_types.get()
    _daisy_show(backend_types_get)


@utils.arg('id', metavar='<ID>',
           help='Filter version to those that have this id.')
def do_version_detail(dc, args):
    """Get backend_types of daisy."""
    version = utils.find_resource(dc.versions, args.id)
    _daisy_show(version)


@utils.arg('name', metavar='<NAME>',
           help='name of version.')
@utils.arg('type', metavar='<TYPE>',
           help='version type.eg redhat7.0...')
@utils.arg('--size', metavar='<SIZE>',
           help='size of the version file.')
@utils.arg('--checksum', metavar='<CHECKSUM>',
           help='md5 of version file')
@utils.arg('--version', metavar='<VERSION>',
           help='version number of version file')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='description of version file')
@utils.arg('--status', metavar='<STATUS>',
           help='version file status.default:init')
def do_version_add(dc, args):
    """Add a version."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.versions.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))

    version = dc.versions.add(**fields)
    _daisy_show(version)


@utils.arg('id', metavar='<ID>',
           help='ID of versions.')
@utils.arg('--name', metavar='<NAME>',
           help='name of version.')
@utils.arg('--type', metavar='<TYPE>',
           help='version type.eg redhat7.0...')
@utils.arg('--size', metavar='<SIZE>',
           help='size of the version file.')
@utils.arg('--checksum', metavar='<CHECKSUM>',
           help='md5 of version file')
@utils.arg('--version', metavar='<VERSION>',
           help='version number of version file')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='description of version file')
@utils.arg('--status', metavar='<STATUS>',
           help='version file status.default:init')
def do_version_update(dc, args):
    """Add a version."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.versions.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    version_id = fields.get('id', None)
    version = dc.versions.update(version_id, **fields)
    _daisy_show(version)


@utils.arg('id', metavar='<ID>', nargs='+',
           help='ID of versions.')
def do_version_delete(dc, args):
    """Delete specified template(s)."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    versions = fields.get('id', None)
    for version in versions:
        try:
            if args.verbose:
                print('Requesting version delete for %s ...' %
                      encodeutils.safe_decode(version), end=' ')
            dc.versions.delete(version)
            if args.verbose:
                print('[Done]')
        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete version %s' % (e, version))


@utils.arg('--name', metavar='<NAME>',
           help='Filter version to those that have this name.')
@utils.arg('--status', metavar='<STATUS>',
           help='Filter version status.')
@utils.arg('--type', metavar='<type>',
           help='Filter by type.')
@utils.arg('--version', metavar='<version>',
           help='Filter by version number.')
@utils.arg('--page-size', metavar='<SIZE>', default=None, type=int,
           help='Number to request in each paginated request.')
@utils.arg('--sort-key', default='name',
           choices=daisyclient.v1.versions.SORT_KEY_VALUES,
           help='Sort version list by specified field.')
@utils.arg('--sort-dir', default='asc',
           choices=daisyclient.v1.versions.SORT_DIR_VALUES,
           help='Sort version list in specified direction.')
def do_version_list(dc, args):
    """List hosts you can access."""
    filter_keys = ['name', 'type', 'status', 'version']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])

    kwargs = {'filters': filters}
    if args.page_size is not None:
        kwargs['page_size'] = args.page_size

    kwargs['sort_key'] = args.sort_key
    kwargs['sort_dir'] = args.sort_dir

    versions = dc.versions.list(**kwargs)

    columns = ['ID', 'NAME', 'TYPE', 'VERSION', 'size',
               'checksum', 'description', 'status', 'VERSION_PATCH']

    utils.print_list(versions, columns)


@utils.arg('id', metavar='<ID>',
           help='Filter version patch to those that have this id.')
def do_version_patch_detail(dc, args):
    """Get version_patch of daisy."""
    version = utils.find_resource(dc.version_patchs, args.id)
    _daisy_show(version)


@utils.arg('name', metavar='<NAME>',
           help='name of version.')
@utils.arg('version_id', metavar='<VERSION>',
           help='the version id of the patch belong to.')
@utils.arg('--size', metavar='<SIZE>',
           help='size of the version file.')
@utils.arg('--checksum', metavar='<CHECKSUM>',
           help='md5 of version file')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='description of version file')
@utils.arg('--status', metavar='<STATUS>',
           help='version file status.default:init')
def do_version_patch_add(dc, args):
    """Add a version."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.version_patchs.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    version = dc.version_patchs.add(**fields)
    _daisy_show(version)


@utils.arg('--host-id', metavar='<HOST_ID>',
           help='name of version.')
@utils.arg('--version-id', metavar='<VERSION>',
           help='version id')
@utils.arg('--type', metavar='<TYPE>',
           help='type is tecs,vplat.....')
@utils.arg('--patch-name', metavar='<PATCH>',
           help='patch name')
def do_host_patch_history_add(dc, args):
    """Add a host patch history."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.version_patchs.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    patch_history = dc.version_patchs.add_host_patch_history(**fields)
    _daisy_show(patch_history)


@utils.arg('--host-id', metavar='<HOST>',
           help='Filter patch history with host id.')
@utils.arg('--type', metavar='<type>',
           help='Filter by type.')
@utils.arg('--version-id', metavar='<version>',
           help='Filter by version number.')
@utils.arg('--page-size', metavar='<SIZE>', default=None, type=int,
           help='Number to request in each paginated request.')
@utils.arg('--sort-key', default='name',
           choices=daisyclient.v1.versions.SORT_KEY_VALUES,
           help='Sort version list by specified field.')
@utils.arg('--sort-dir', default='asc',
           choices=daisyclient.v1.versions.SORT_DIR_VALUES,
           help='Sort version list in specified direction.')
def do_patch_history_list(dc, args):
    """List hosts you can access."""
    filter_keys = ['host_id', 'type', 'version_id']
    filter_items = [(key, getattr(args, key)) for key in filter_keys]
    filters = dict([item for item in filter_items if item[1] is not None])

    kwargs = {'filters': filters}
    if args.page_size is not None:
        kwargs['page_size'] = args.page_size

    kwargs['sort_key'] = args.sort_key
    kwargs['sort_dir'] = args.sort_dir

    versions = dc.version_patchs.list_host_patch_history(**kwargs)

    columns = ['ID', 'HOST_ID', 'TYPE', 'VERSION_ID', 'VERSION_NAME',
               'PATCH_NAME']

    utils.print_list(versions, columns)


@utils.arg('id', metavar='<ID>',
           help='ID of version patch.')
@utils.arg('--name', metavar='<NAME>',
           help='name of version patch.')
@utils.arg('--size', metavar='<SIZE>',
           help='size of the version patch file.')
@utils.arg('--checksum', metavar='<CHECKSUM>',
           help='md5 of version patch file')
@utils.arg('--description', metavar='<DESCRIPTION>',
           help='description of version patch file')
@utils.arg('--status', metavar='<STATUS>',
           help='version patch file status.default:init')
def do_version_patch_update(dc, args):
    """Add a version."""

    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))

    # Filter out values we can't use
    CREATE_PARAMS = daisyclient.v1.version_patchs.CREATE_PARAMS
    fields = dict(filter(lambda x: x[0] in CREATE_PARAMS, fields.items()))
    version_id = fields.get('id', None)
    version = dc.version_patchs.update(version_id, **fields)
    _daisy_show(version)


@utils.arg('id', metavar='<ID>', nargs='+',
           help='ID of version patchs.')
def do_version_patch_delete(dc, args):
    """Delete specified template(s)."""
    fields = dict(filter(lambda x: x[1] is not None, vars(args).items()))
    version_patchs = fields.get('id', None)
    for version_patch in version_patchs:
        try:
            if args.verbose:
                print('Requesting version_patch delete for %s ...' %
                      encodeutils.safe_decode(version_patch), end=' ')
            dc.version_patchs.delete(version_patch)
            if args.verbose:
                print('[Done]')
        except exc.HTTPException as e:
            if args.verbose:
                print('[Fail]')
            print('%s: Unable to delete version_patch %s'
                  % (e, version_patch))


@utils.arg('--page-size', metavar='<SIZE>', default=None, type=int,
           help='Number to request in each paginated request.')
@utils.arg('--sort-key', default='id',
           choices=daisyclient.v1.deploy_server.SORT_KEY_VALUES,
           help='Sort deploy server list by specified field.')
@utils.arg('--sort-dir', default='asc',
           choices=daisyclient.v1.deploy_server.SORT_DIR_VALUES,
           help='Sort deploy server list in specified direction.')
def do_deploy_server_list(dc, args):
    """List deploy servers you can access."""
    kwargs = {'filters': {}}
    if args.page_size is not None:
        kwargs['page_size'] = args.page_size

    kwargs['sort_key'] = args.sort_key
    kwargs['sort_dir'] = args.sort_dir

    template_funcs = dc.deploy_server.list(**kwargs)
    columns = ['ID', 'Name', 'Cluster_id', 'Description',
               'Vlan_start', 'Vlan_end', 'Gateway', 'Cidr',
               'Type', 'Ip_ranges', 'Segmentation_type',
               'custom_name', 'nics', 'pxe_nic']
    utils.print_list(template_funcs, columns)


@utils.arg('deployment_interface', metavar='<DEPLOYMENT_INTERFACE>',
           help='The interface to deploy.')
@utils.arg('server_ip', metavar='<SERVER_IP>',
           help='The server ip to deploy.')
def do_pxe_env_check(gc, args):
    """Check pxe env."""
    fields = {}
    fields.update({
        'deployment_interface': args.deployment_interface,
        'server_ip': args.server_ip})
    pxe_env = gc.deploy_server.pxe_env_check(**fields)
    _daisy_show(pxe_env)
