# Copyright (c) 2015 ZTE, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from sqlalchemy.schema import (Column, ForeignKey, MetaData, Table)


from daisy.db.sqlalchemy.migrate_repo.schema import (
    BigInteger, Boolean, DateTime, Integer, String, Text,
    create_tables)  # noqa


def define_hosts_table(meta):
    hosts = Table('hosts',
                  meta,
                  Column('id', String(36), primary_key=True,
                         nullable=False),
                  Column('dmi_uuid', String(36)),
                  Column('name', String(255), nullable=False),
                  Column('description', Text()),
                  Column('resource_type', String(36)),
                  Column('ipmi_user', String(36)),
                  Column('ipmi_passwd', String(36)),
                  Column('ipmi_addr', String(256)),
                  Column('status', String(36), default='init', nullable=False),
                  Column('root_disk', String(256)),
                  Column('root_lv_size', Integer()),
                  Column('swap_lv_size', Integer()),
                  Column('root_pwd', String(36)),
                  Column('isolcpus', String(256)),
                  Column('os_version_id', String(36)),
                  Column('os_version_file', String(255)),
                  Column('os_progress', Integer()),
                  Column('os_status', String(36)),
                  Column('messages', Text()),
                  Column('hugepagesize', String(36)),
                  Column('hugepages', Integer()),
                  Column('system',String(2550)),
                  Column('cpu',String(2550)),
                  Column('memory',String(2550)),
                  Column('disk',String(2550)),
                  Column('devices',String(2550)),
                  Column('pci',String(2550)),
                  Column('created_at', DateTime(), nullable=False),
                  Column('updated_at', DateTime(), nullable=False),
                  Column('deleted_at', DateTime()),
                  Column('deleted',
                         Boolean(),
                         nullable=False,
                         default=False,
                         index=True),
                  mysql_engine='InnoDB',
                  extend_existing=True)

    return hosts


def define_discover_hosts_table(meta):
    discover_hosts = Table('discover_hosts',
                           meta,
                           Column('id', String(36), primary_key=True,
                                  nullable=False),
                           Column('ip', String(255), nullable=True),
                           Column('user', String(36)),
                           Column('passwd', String(36), nullable=True),
                           Column(
                               'status', String(255), default='init',
                               nullable=True),
                           Column('created_at', DateTime(), nullable=True),
                           Column('updated_at', DateTime(), nullable=True),
                           Column('deleted_at', DateTime()),
                           Column('deleted',
                                  Boolean(),
                                  nullable=False,
                                  default=False,
                                  index=True),
                           mysql_engine='InnoDB',
                           extend_existing=True)

    return discover_hosts


def define_clusters_table(meta):
    clusters = Table('clusters',
                     meta,
                     Column('id', String(36), primary_key=True,
                            nullable=False),
                     Column(
                         'name', String(255), default='TECS', nullable=False),
                     Column('owner', String(255)),
                     Column('description', Text()),
                     Column('net_l23_provider', String(64)),
                     Column('base_mac', String(128)),
                     Column('gre_id_start', Integer()),
                     Column('gre_id_end', Integer()),
                     Column('vlan_start', Integer()),
                     Column('vlan_end', Integer()),
                     Column('vni_start', BigInteger()),
                     Column('vni_end', BigInteger()),
                     Column('public_vip', String(128)),
                     Column('segmentation_type', String(64)),
                     Column(
                         'auto_scale', Integer(), nullable=False, default=0),
                     Column('created_at', DateTime(), nullable=False),
                     Column('updated_at', DateTime(), nullable=False),
                     Column('deleted_at', DateTime()),
                     Column('deleted',
                            Boolean(),
                            nullable=False,
                            default=False,
                            index=True),
                     mysql_engine='InnoDB',
                     extend_existing=True)

    return clusters


def define_cluster_hosts_table(meta):
    cluster_hosts = Table('cluster_hosts',
                          meta,
                          Column('id', String(36), primary_key=True,
                                 nullable=False),
                          Column('cluster_id', String(36),
                                 ForeignKey('clusters.id'),
                                 nullable=False),
                          Column('host_id', String(36),
                                 nullable=False),
                          Column('created_at', DateTime(), nullable=False),
                          Column('updated_at', DateTime(), nullable=False),
                          Column('deleted_at', DateTime()),
                          Column('deleted',
                                 Boolean(),
                                 nullable=False,
                                 default=False,
                                 index=True),
                          mysql_engine='InnoDB',
                          extend_existing=True)

    return cluster_hosts


def define_networks_table(meta):
    networks = Table('networks',
                     meta,
                     Column('id', String(36), primary_key=True,
                            nullable=False),
                     Column('name', String(255), nullable=False),
                     Column('description', Text()),
                     Column('cluster_id', String(36)),
                     Column('cidr', String(255)),
                     Column('vlan_id', String(36)),
                     Column(
                         'vlan_start', Integer(), nullable=False, default=1),
                     Column(
                         'vlan_end', Integer(), nullable=False, default=4094),
                     Column('ip', String(256)),
                     Column('gateway', String(128)),
                     Column(
                         'type', String(36), nullable=False,
                         default='default'),
                     Column('ml2_type', String(36)),
                     Column('network_type', String(36), nullable=False),
                     Column('physnet_name', String(108)),
                     Column('capability', String(36), default='high'),
                     Column('mtu', Integer(), nullable=False, default=1500),
                     Column('alias', String(255)),
                     Column('created_at', DateTime(), nullable=False),
                     Column('updated_at', DateTime(), nullable=False),
                     Column('deleted_at', DateTime()),
                     Column('deleted',
                            Boolean(),
                            nullable=False,
                            default=False,
                            index=True),
                     mysql_engine='InnoDB',
                     extend_existing=True)

    return networks


def define_ip_ranges_table(meta):
    ip_ranges = Table('ip_ranges',
                      meta,
                      Column('id', String(36), primary_key=True,
                             nullable=False),
                      Column('start', String(128)),
                      Column('end', String(128)),
                      Column('network_id', String(36)),
                      Column('created_at', DateTime(), nullable=False),
                      Column('updated_at', DateTime(), nullable=False),
                      Column('deleted_at', DateTime()),
                      Column('deleted',
                             Boolean(),
                             nullable=False,
                             default=False,
                             index=True),
                      mysql_engine='InnoDB',
                      extend_existing=True)

    return ip_ranges


def define_host_interfaces_table(meta):
    host_interfaces = Table('host_interfaces',
                            meta,
                            Column('id', String(36), primary_key=True,
                                   nullable=False),
                            Column('host_id', String(36),
                                   ForeignKey('hosts.id'),
                                   nullable=False),
                            Column('name', String(64)),
                            Column('ip', String(256)),
                            Column('netmask', String(256)),
                            Column('gateway', String(256)),
                            Column('mac', String(256)),
                            Column('pci', String(32)),
                            Column(
                                'type', String(32), nullable=False,
                                default='ether'),
                            Column('slave1', String(32)),
                            Column('slave2', String(32)),
                            Column('mode', String(36)),
                            Column('is_deployment', Boolean(), default=False),
                            Column('created_at', DateTime(), nullable=False),
                            Column('updated_at', DateTime(), nullable=False),
                            Column('deleted_at', DateTime()),
                            Column('deleted',
                                   Boolean(),
                                   nullable=False,
                                   default=False,
                                   index=True),
                            mysql_engine='InnoDB',
                            extend_existing=True)

    return host_interfaces


def define_host_roles_table(meta):
    host_roles = Table('host_roles',
                       meta,
                       Column('id', String(36), primary_key=True,
                              nullable=False),
                       Column('host_id',
                              String(36),
                              ForeignKey('hosts.id'),
                              nullable=False),
                       Column('role_id',
                              String(36),
                              ForeignKey('roles.id'),
                              nullable=False),
                       Column(
                           'status', String(32), nullable=False,
                           default='init'),
                       Column('progress', Integer(), default=0),
                       Column('messages', Text()),
                       Column('created_at', DateTime(), nullable=False),
                       Column('updated_at', DateTime(), nullable=False),
                       Column('deleted_at', DateTime()),
                       Column('deleted',
                              Boolean(),
                              nullable=False,
                              default=False,
                              index=True),
                       mysql_engine='InnoDB',
                       extend_existing=True)

    return host_roles


def define_roles_table(meta):
    roles = Table('roles',
                  meta,
                  Column('id',
                         String(36), primary_key=True,
                         nullable=False, index=True),
                  Column('name',
                         String(255),
                         nullable=False),
                  Column('status', String(32), nullable=False, default='init'),
                  Column('progress', Integer(), default=0),
                  Column('config_set_id',
                         String(36),
                         ForeignKey('config_sets.id')),
                  Column('description', Text()),
                  Column('cluster_id', String(36)),
                  Column('type', String(36), nullable=False, default='custom'),
                  Column('vip', String(256)),
                  Column('messages', Text()),
                  Column('db_lv_size', Integer()),
                  Column('glance_lv_size', Integer()),
                  Column('nova_lv_size', Integer(), default=0),
                  Column(
                      'disk_location', String(255), nullable=False,
                      default='local'),
                  Column('deployment_backend', String(36)),
                  Column('config_set_update_progress', Integer(), default=0),
                  Column('ntp_server', String(255)),
                  Column('created_at', DateTime(), nullable=False),
                  Column('updated_at', DateTime(), nullable=False),
                  Column('deleted_at', DateTime()),
                  Column('deleted',
                         Boolean(),
                         nullable=False,
                         default=False,
                         index=True),
                  mysql_engine='InnoDB',
                  extend_existing=True)

    return roles


def define_service_roles_table(meta):
    service_roles = Table('service_roles',
                          meta,
                          Column('id', String(36), primary_key=True,
                                 nullable=False),
                          Column('role_id', String(36), ForeignKey('roles.id'),
                                 nullable=False),
                          Column(
                              'service_id', String(36), ForeignKey(
                                  'services.id'), nullable=False),
                          Column('created_at', DateTime(), nullable=False),
                          Column('updated_at', DateTime(), nullable=False),
                          Column('deleted_at', DateTime()),
                          Column('deleted',
                                 Boolean(),
                                 nullable=False,
                                 default=False,
                                 index=True),
                          mysql_engine='InnoDB',
                          extend_existing=True)

    return service_roles


def define_services_table(meta):
    services = Table('services',
                     meta,
                     Column('id', String(36), primary_key=True,
                            nullable=False),
                     Column('name', String(255), nullable=False),
                     Column('component_id', String(36), ForeignKey(
                         'components.id'), nullable=True),
                     Column('description', Text()),
                     Column(
                         'backup_type', String(32), nullable=False,
                         default='none'),
                     Column('created_at', DateTime(), nullable=False),
                     Column('updated_at', DateTime(), nullable=False),
                     Column('deleted_at', DateTime()),
                     Column('deleted',
                            Boolean(),
                            nullable=False,
                            default=False,
                            index=True),
                     mysql_engine='InnoDB',
                     extend_existing=True)

    return services


def define_components_table(meta):
    components = Table('components',
                       meta,
                       Column('id', String(36), primary_key=True,
                              nullable=False),
                       Column('name', String(255), nullable=False),
                       Column('description', Text()),
                       Column('created_at', DateTime(), nullable=False),
                       Column('updated_at', DateTime(), nullable=False),
                       Column('deleted_at', DateTime()),
                       Column('deleted',
                              Boolean(),
                              nullable=False,
                              default=False,
                              index=True),
                       mysql_engine='InnoDB',
                       extend_existing=True)

    return components


def define_config_sets_table(meta):
    config_sets = Table('config_sets',
                        meta,
                        Column('id', String(36), primary_key=True,
                               nullable=False),
                        Column('name', String(255), nullable=False),
                        Column('description', Text()),
                        Column('created_at', DateTime(), nullable=False),
                        Column('updated_at', DateTime(), nullable=False),
                        Column('deleted_at', DateTime()),
                        Column('deleted',
                               Boolean(),
                               nullable=False,
                               default=False,
                               index=True),
                        mysql_engine='InnoDB',
                        extend_existing=True)

    return config_sets


def define_configs_table(meta):
    configs = Table('configs',
                    meta,
                    Column('id', String(36), primary_key=True,
                           nullable=False),
                    Column('section', String(255)),
                    Column('key', String(255), nullable=False),
                    Column('value', String(255)),
                    Column('config_file_id', String(36), ForeignKey(
                        'config_files.id'), nullable=False),
                    Column('config_version', Integer(), default=0),
                    Column('running_version', Integer(), default=0),
                    Column('description', Text()),
                    Column('created_at', DateTime(), nullable=False),
                    Column('updated_at', DateTime(), nullable=False),
                    Column('deleted_at', DateTime()),
                    Column('deleted',
                           Boolean(),
                           nullable=False,
                           default=False,
                           index=True),
                    mysql_engine='InnoDB',
                    extend_existing=True)

    return configs


def define_config_files_table(meta):
    config_files = Table('config_files',
                         meta,
                         Column('id', String(36), primary_key=True,
                                nullable=False),
                         Column('name', String(255), nullable=False),
                         Column('description', Text()),
                         Column('created_at', DateTime(), nullable=False),
                         Column('updated_at', DateTime(), nullable=False),
                         Column('deleted_at', DateTime()),
                         Column('deleted',
                                Boolean(),
                                nullable=False,
                                default=False,
                                index=True),
                         mysql_engine='InnoDB',
                         extend_existing=True)

    return config_files


def define_config_set_items_table(meta):
    config_set_items = Table('config_set_items',
                             meta,
                             Column('id', String(36), primary_key=True,
                                    nullable=False),
                             Column('config_set_id', String(36),
                                    ForeignKey('config_sets.id'),
                                    nullable=False),
                             Column('config_id', String(36), ForeignKey(
                                 'configs.id'), nullable=False),
                             Column('created_at', DateTime(), nullable=False),
                             Column('updated_at', DateTime(), nullable=False),
                             Column('deleted_at', DateTime()),
                             Column('deleted',
                                    Boolean(),
                                    nullable=False,
                                    default=False,
                                    index=True),
                             mysql_engine='InnoDB',
                             extend_existing=True)

    return config_set_items


def define_config_historys_table(meta):
    config_historys = Table('config_historys',
                            meta,
                            Column('id', String(36), primary_key=True,
                                   nullable=False),
                            Column('config_id', String(36)),
                            Column('value', String(255)),
                            Column('version', Integer()),
                            Column('created_at', DateTime(), nullable=False),
                            Column('updated_at', DateTime(), nullable=False),
                            Column('deleted_at', DateTime()),
                            Column('deleted',
                                   Boolean(),
                                   nullable=False,
                                   default=False,
                                   index=True),
                            mysql_engine='InnoDB',
                            extend_existing=True)

    return config_historys


def define_tasks_table(meta):
    tasks = Table('tasks',
                  meta,
                  Column('id', String(36), primary_key=True, nullable=False),
                  Column('type', String(30), nullable=False),
                  Column('status', String(30), nullable=False),
                  Column('owner', String(255), nullable=False),
                  Column('expires_at', DateTime()),
                  Column('created_at', DateTime(), nullable=False),
                  Column('updated_at', DateTime(), nullable=False),
                  Column('deleted_at', DateTime()),
                  Column('deleted',
                         Boolean(),
                         nullable=False,
                         default=False,
                         index=True),
                  mysql_engine='InnoDB',
                  extend_existing=True)

    return tasks


def define_task_infos_table(meta):
    task_infos = Table('task_infos',
                       meta,
                       Column('task_id', String(36)),
                       Column('input', Text()),
                       Column('result', Text()),
                       Column('message', Text()),
                       Column('created_at', DateTime(), nullable=False),
                       Column('updated_at', DateTime(), nullable=False),
                       Column('deleted_at', DateTime()),
                       Column('deleted',
                              Boolean(),
                              nullable=False,
                              default=False,
                              index=True),
                       mysql_engine='InnoDB',
                       extend_existing=True)

    return task_infos


def define_repositorys_table(meta):
    repositorys = Table('repositorys',
                        meta,
                        Column(
                            'id', String(36), primary_key=True,
                            nullable=False),
                        Column('url', String(255)),
                        Column('description', Text()),
                        Column('created_at', DateTime(), nullable=False),
                        Column('updated_at', DateTime(), nullable=False),
                        Column('deleted_at', DateTime()),
                        Column('deleted',
                               Boolean(),
                               nullable=False,
                               default=False,
                               index=True),
                        mysql_engine='InnoDB',
                        extend_existing=True)

    return repositorys


def define_users_table(meta):
    users = Table('users',
                  meta,
                  Column('id', String(36), primary_key=True,
                         nullable=False),
                  Column('name', String(256), nullable=False),
                  Column('password', String(256)),
                  Column('email', String(256)),
                  Column('phone', String(128)),
                  Column('address', String(256)),
                  Column('created_at', DateTime(), nullable=False),
                  Column('updated_at', DateTime(), nullable=False),
                  Column('deleted_at', DateTime()),
                  Column('deleted',
                         Boolean(),
                         nullable=False,
                         default=False,
                         index=True),
                  mysql_engine='InnoDB',
                  extend_existing=True)

    return users


def define_versions_table(meta):
    versions = Table('versions',
                     meta,
                     Column('id', String(36), primary_key=True,
                            nullable=False),
                     Column('name', String(256), nullable=False),
                     Column('size', BigInteger()),
                     Column('status', String(30)),
                     Column('checksum', String(128)),
                     Column('owner', String(256)),
                     Column('version', String(32)),
                     Column('type', String(30), default='0'),
                     Column('description', Text()),
                     Column('created_at', DateTime(), nullable=False),
                     Column('updated_at', DateTime(), nullable=False),
                     Column('deleted_at', DateTime()),
                     Column('deleted',
                            Boolean(),
                            nullable=False,
                            default=False,
                            index=True),
                     mysql_engine='InnoDB',
                     extend_existing=True)

    return versions


def define_assigned_networks_table(meta):
    assigned_networks = Table('assigned_networks',
                              meta,
                              Column('id', String(36), primary_key=True,
                                     nullable=False),
                              Column('mac', String(128)),
                              Column('network_id', String(36)),
                              Column('interface_id', String(36)),
                              Column('ip', String(256)),
                              Column('vswitch_type', String(256)),
                              Column('created_at', DateTime(), nullable=False),
                              Column('updated_at', DateTime(), nullable=False),
                              Column('deleted_at', DateTime()),
                              Column('deleted',
                                     Boolean(),
                                     nullable=False,
                                     default=False,
                                     index=True),
                              mysql_engine='InnoDB',
                              extend_existing=True)

    return assigned_networks


def define_logic_networks_table(meta):
    logic_networks = Table('logic_networks',
                           meta,
                           Column('id', String(36), primary_key=True,
                                  nullable=False),
                           Column('name', String(255), nullable=False),
                           Column('type', String(36)),
                           Column('physnet_name', String(255)),
                           Column('cluster_id', String(36), ForeignKey(
                               'clusters.id'), nullable=False),
                           Column('segmentation_id', BigInteger()),
                           Column(
                               'segmentation_type', String(64),
                               nullable=False),
                           Column('shared', Boolean(), default=False),
                           Column('created_at', DateTime(), nullable=False),
                           Column('updated_at', DateTime(), nullable=False),
                           Column('deleted_at', DateTime()),
                           Column('deleted',
                                  Boolean(),
                                  nullable=False,
                                  default=False,
                                  index=True),
                           mysql_engine='InnoDB',
                           extend_existing=True)
    return logic_networks


def define_subnets_table(meta):
    subnets = Table('subnets',
                    meta,
                    Column('id', String(36), primary_key=True,
                           nullable=False),
                    Column('cidr', String(128)),
                    Column('gateway', String(128)),
                    Column('logic_network_id', String(36), ForeignKey(
                        'logic_networks.id'), nullable=False),
                    Column('name', String(255), nullable=False),
                    Column('router_id', String(36), ForeignKey('routers.id')),
                    Column('created_at', DateTime(), nullable=False),
                    Column('updated_at', DateTime(), nullable=False),
                    Column('deleted_at', DateTime()),
                    Column('deleted',
                           Boolean(),
                           nullable=False,
                           default=False,
                           index=True),
                    mysql_engine='InnoDB',
                    extend_existing=True)
    return subnets


def define_float_ip_ranges_table(meta):
    float_ip_ranges = Table('float_ip_ranges',
                            meta,
                            Column('id', String(36), primary_key=True,
                                   nullable=False),
                            Column('start', String(128)),
                            Column('end', String(128)),
                            Column('subnet_id', String(36), ForeignKey(
                                'subnets.id'), nullable=False),
                            Column('created_at', DateTime(), nullable=False),
                            Column('updated_at', DateTime(), nullable=False),
                            Column('deleted_at', DateTime()),
                            Column('deleted',
                                   Boolean(),
                                   nullable=False,
                                   default=False,
                                   index=True),
                            mysql_engine='InnoDB',
                            extend_existing=True)

    return float_ip_ranges


def define_dns_nameservers_table(meta):
    dns_nameservers = Table('dns_nameservers',
                            meta,
                            Column('id', String(36), primary_key=True,
                                   nullable=False),
                            Column('dns', String(128)),
                            Column(
                                'subnet_id', String(36),
                                ForeignKey('subnets.id'), nullable=False),
                            Column('created_at', DateTime(), nullable=False),
                            Column('updated_at', DateTime(), nullable=False),
                            Column('deleted_at', DateTime()),
                            Column('deleted',
                                   Boolean(),
                                   nullable=False,
                                   default=False,
                                   index=True),
                            mysql_engine='InnoDB',
                            extend_existing=True)

    return dns_nameservers


def define_routers_table(meta):
    routers = Table('routers',
                    meta,
                    Column('id', String(36), primary_key=True,
                           nullable=False),
                    Column('name', String(255)),
                    Column('description', Text()),
                    Column('cluster_id', String(36), ForeignKey(
                        'clusters.id'), nullable=False),
                    Column('external_logic_network', String(255)),
                    Column('created_at', DateTime(), nullable=False),
                    Column('updated_at', DateTime(), nullable=False),
                    Column('deleted_at', DateTime()),
                    Column('deleted',
                           Boolean(),
                           nullable=False,
                           default=False,
                           index=True),
                    mysql_engine='InnoDB',
                    extend_existing=True)

    return routers


def define_service_disks_table(meta):
    disks = Table('service_disks',
                  meta,
                  Column('id', String(36), primary_key=True,
                         nullable=False),
                  Column('service', String(255)),
                  Column('role_id',
                         String(36),
                         ForeignKey('roles.id'),
                         nullable=False),
                  Column(
                      'disk_location', String(255),
                      nullable=False, default='local'),
                  Column('lun', Integer()),
                  Column('data_ips', String(255)),
                  Column('size', Integer()),
                  Column('created_at', DateTime(), nullable=False),
                  Column('updated_at', DateTime(), nullable=False),
                  Column('deleted_at', DateTime()),
                  Column('deleted',
                         Boolean(),
                         nullable=False,
                         default=False,
                         index=True),
                  mysql_engine='InnoDB',
                  extend_existing=True)

    return disks


def define_cinder_volumes_table(meta):
    disks = Table('cinder_volumes',
                  meta,
                  Column('id', String(36), primary_key=True,
                         nullable=False),
                  Column('user_name', String(255)),
                  Column('user_pwd', String(255)),
                  Column('management_ips', String(255)),
                  Column('pools', String(255)),
                  Column('volume_driver', String(255)),
                  Column('volume_type', String(255)),
                  Column('backend_index', String(255)),
                  Column('role_id',
                         String(36),
                         ForeignKey('roles.id'),
                         nullable=False),
                  Column('created_at', DateTime(), nullable=False),
                  Column('updated_at', DateTime(), nullable=False),
                  Column('deleted_at', DateTime()),
                  Column('deleted',
                         Boolean(),
                         nullable=False,
                         default=False,
                         index=True),
                  mysql_engine='InnoDB',
                  extend_existing=True)

    return disks


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_hosts_table(meta),
              define_discover_hosts_table(meta),
              define_clusters_table(meta),
              define_cluster_hosts_table(meta),
              define_networks_table(meta),
              define_ip_ranges_table(meta),
              define_host_interfaces_table(meta),
              define_config_sets_table(meta),
              define_components_table(meta),
              define_services_table(meta),
              define_roles_table(meta),
              define_host_roles_table(meta),
              define_service_roles_table(meta),
              define_config_files_table(meta),
              define_configs_table(meta),
              define_config_set_items_table(meta),
              define_config_historys_table(meta),
              define_tasks_table(meta),
              define_task_infos_table(meta),
              define_repositorys_table(meta),
              define_users_table(meta),
              define_versions_table(meta),
              define_assigned_networks_table(meta),
              define_logic_networks_table(meta),
              define_routers_table(meta),
              define_subnets_table(meta),
              define_float_ip_ranges_table(meta),
              define_dns_nameservers_table(meta),
              define_service_disks_table(meta),
              define_cinder_volumes_table(meta)]
    create_tables(tables)
