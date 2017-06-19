# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
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

import uuid
from migrate import ForeignKeyConstraint
from sqlalchemy import (Boolean, DateTime, Integer, String, Text,
                        Column, MetaData, Table, ForeignKey)
from daisy.db.sqlalchemy.migrate_repo.schema import create_tables
from daisy.db.sqlalchemy.migrate_repo.schema import drop_tables

target_names = ["os",
                "tecs",
                "zenic",
                "provider",
                "dvs",
                "ovs",
                "zenic-agent",
                "config_apply_local_storage",
                "config_apply_share_storage",
                "config_apply_network",
                "config_apply_neutron_agent",
                "config_apply_cinder_backend",
                "config_apply_openstack",
                "config_apply_provider_network",
                "config_apply_provider_storage",
                "config_update_network",
                "config_apply_numa_hugepages",
                "config_apply_controller_dataplane",
                "diagnose_network",
                "diagnose_yum_repository"]

target_description = {"os": "Operating System of support."
                            "eg:vplat,redhat,centos",
                      "tecs": "Tulip Elastic Cloud System",
                      "zenic": "Sdn Controller",
                      "provider": "Provider",
                      "dvs": "Distributed Virtual Switch",
                      "ovs": "Open VSwitch",
                      "zenic-agent": "Zenic Agent",
                      "config_apply_local_storage":
                          "Config Apply Local Storage",
                      "config_apply_share_storage":
                          "Config Apply Share Storage",
                      "config_apply_network": "Config Apply Network",
                      "config_apply_neutron_agent":
                          "Config Apply Neutron Agent",
                      "config_apply_cinder_backend":
                          "Config Apply Cinder Backend",
                      "config_apply_openstack": "Config Apply Openstack",
                      "config_apply_provider_network":
                          "Config Apply Provider Network",
                      "config_apply_provider_storage":
                          "Config Apply Provider Storage",
                      "config_update_network": "Config Update Network",
                      "config_apply_numa_hugepages": "Config Numa Hugepages",
                      "config_apply_controller_dataplane": "Config dataplane for cluster controllers",
                      "diagnose_network": "Diagnose network",
                      "diagnose_yum_repository": "Diagnose yum repository"}

target_id = Column('target_id', String(36), ForeignKey('targets.id'))


def define_targets_table(meta):
    targets = Table(
        'targets',
        meta,
        Column('id', String(36), primary_key=True),
        Column('name', String(255), nullable=False),
        Column('description', Text),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return targets


def define_target_status_table(meta):
    target_status = Table(
        "target_status",
        meta,
        Column('id', String(36), primary_key=True),
        Column('host_id', String(36), ForeignKey('hosts.id')),
        Column('target_id', String(36), ForeignKey('targets.id')),
        Column('type', String(50)),
        Column('status', String(50)),
        Column('sub_status', String(50)),
        Column('last_status', String(50)),
        Column('progress', Integer),
        Column('messages', Text),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return target_status


def define_host_versions_table(meta):
    host_versions = Table(
        "host_versions",
        meta,
        Column('id', String(36), primary_key=True),
        Column('host_id', String(36), ForeignKey('hosts.id')),
        Column('version_id', String(36), ForeignKey('versions.id')),
        Column('patch_id', String(36), ForeignKey('version_patchs.id')),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return host_versions


def create_targets(migrate_engine):
    targets_info = {}
    if migrate_engine.name == "mysql":
        sql = ""
        for name in target_names:
            tid = str(uuid.uuid4())
            targets_info[name] = tid
            desc = target_description.get(name)
            sql += "insert into targets(id,name,description," \
                   "created_at,updated_at,deleted) " \
                   "values('%s','%s','%s',now(),now(),0);" % (tid, name, desc)
        migrate_engine.execute(sql)
    return targets_info


def update_versions(migrate_engine, targets_info):
    if migrate_engine.name == "mysql":
        if targets_info:
            os_target_id = targets_info.get("os")
            tecs_target_id = targets_info.get("tecs")

            sql = "update versions set target_id='%s' where type='tecs';"\
                  % tecs_target_id
            sql += "update versions set target_id='%s' where type in " \
                   "('vplat','redhat 7.0','centos 7.0');" % os_target_id
            migrate_engine.execute(sql)


def compatible_status(migrate_engine, targets_info):
    if migrate_engine.name == "mysql":
        if targets_info:
            os_target_id = targets_info.get("os")
            tecs_target_id = targets_info.get("tecs")
            sql = "insert into target_status select id, id as host_id,'%s'," \
                  "'life_cycle',os_status ,NULL,NULL,os_progress,messages," \
                  "now(),now(),NULL,0 from hosts where deleted=0;"\
                  % os_target_id
            sql += "insert into target_status select id, host_id,'%s'," \
                   "'life_cycle',status ,NULL,NULL,progress,messages,now()," \
                   "now(),NULL,0 from host_roles where deleted=0 " \
                   "group by host_id;" % tecs_target_id
            migrate_engine.execute(sql)


def insert_host_version(conn, host_id, version_id, patch_id=''):
    if patch_id:
        cols = "id,host_id,version_id,patch_id,created_at,updated_at,deleted"
        vals = "'%s','%s','%s','%s',now(),now(),0" % (
            str(uuid.uuid4()), host_id, version_id, patch_id)
    else:
        cols = "id,host_id,version_id,created_at,updated_at,deleted"
        vals = "'%s','%s','%s',now(),now(),0" % (
            str(uuid.uuid4()), host_id, version_id)
    sql = "insert into host_versions(%s) values(%s)" % (cols, vals)
    conn.execute(sql)


def query_host_version(conn, host_id, version_id, patch_id):
    sql = "select * from host_versions as h where h.host_id='%s' and " \
          "h.version_id='%s' and h.patch_id='%s';" % \
          (host_id, version_id, patch_id)
    return conn.execute(sql).fetchall()


def move_history_patch_table_data_to_host_version(conn):
    sql = "insert into host_versions select h.id,h.host_id, h.version_id, " \
          "v.id as patch_id, h.created_at,h.updated_at,NULL,0 from " \
          "host_patch_history as h, version_patchs as v where " \
          "h.patch_name=v.name and h.deleted=0;"
    conn.execute(sql)


def move_host_table_data_to_host_version(conn):
    hsql = "select * from hosts where deleted=0"
    records = conn.execute(hsql).fetchall()
    for record in records:
        os_version_id = ''
        if record.os_version_id:
            os_version_id = record.os_version_id
        elif record.os_version_file:
            try:
                vsql = "select id from versions where versions.name='%s' " \
                       "deleted=0" % record.os_version_file
                ret = conn.execute(vsql).fetchone()
            except Exception:
                print("Query '%s' from versions failed." %
                      record.os_version_file)
            else:
                os_version_id = ret.id
        set_host_version_patch(conn, record.id, os_version_id,
                               record.version_patch_id)
        set_host_version_patch(conn, record.id, record.tecs_version_id,
                               record.tecs_patch_id)


def set_host_version_patch(conn, host_id, version_id, patch_id):
    if version_id:
        insert_host_version(conn, host_id, version_id)
        if patch_id and \
                not query_host_version(conn, host_id, version_id, patch_id):
            insert_host_version(conn, host_id, version_id, patch_id)


def compatible_host_versions(migrate_engine):
    if migrate_engine.name == "mysql":
        conn = migrate_engine.connect()
        move_history_patch_table_data_to_host_version(conn)
        move_host_table_data_to_host_version(conn)
        conn.close()


def upgrade(migrate_engine):
    print("037 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_host_versions_table(meta),
              define_targets_table(meta),
              define_target_status_table(meta)]

    versions = Table('versions', meta, autoload=True)
    Table('hosts', meta, autoload=True)
    Table('version_patchs', meta, autoload=True)
    create_tables(tables)
    versions.create_column(target_id)
    target_info = create_targets(migrate_engine)
    update_versions(migrate_engine, target_info)
    compatible_status(migrate_engine, target_info)
    compatible_host_versions(migrate_engine)


def downgrade(migrate_engine):
    print("037 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    versions = Table('versions', meta, autoload=True)
    targets = Table('targets', meta, autoload=True)
    params = {'columns': [versions.c['target_id']],
              'refcolumns': [targets.c['id']],
              'name': 'versions_ibfk_1'}
    foreign = ForeignKeyConstraint(**params)
    foreign.drop()
    versions.drop_column(target_id)

    tables = [define_target_status_table(meta),
              define_targets_table(meta),
              define_host_versions_table(meta)]
    drop_tables(tables)
