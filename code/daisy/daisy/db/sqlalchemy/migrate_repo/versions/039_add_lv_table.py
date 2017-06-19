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


def define_logical_volume_table(meta):
    lvs = Table(
        'logical_volume',
        meta,
        Column('id', String(36), primary_key=True),
        Column('name', String(255), nullable=False),
        Column('size', Integer, default=0),
        Column('host_id', String(36), ForeignKey('hosts.id')),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return lvs


def insert_lv_data(conn, name, size, host_id):
    sql = "select * from logical_volume as lv where lv.name='%s' " \
          "and lv.host_id='%s' and lv.deleted=0;" % (name, host_id)
    ret = conn.execute(sql).fetchall()
    if not ret:
        col = "id,name,size,host_id,created_at,updated_at,deleted"
        val = "'%s','%s','%s','%s',now(),now(),0" % (str(uuid.uuid4()), name,
                                                     size, host_id)
        ins = "insert into logical_volume(%s) values(%s)" % (col, val)
        conn.execute(ins)


def compatible_role_table(conn):
    sql = "select host_roles.host_id, roles.name as role_name, " \
          "roles.glance_lv_size, roles.db_lv_size, roles.nova_lv_size " \
          "from host_roles inner join roles on host_roles.role_id=roles.id " \
          "where roles.deleted=0 and host_roles.deleted=0;"
    metas = conn.execute(sql).fetchall()
    for meta in metas:
        if meta.role_name == 'CONTROLLER_HA':
            insert_lv_data(conn, 'glance', meta.glance_lv_size, meta.host_id)
            insert_lv_data(conn, 'db', meta.db_lv_size, meta.host_id)
        elif meta.role_name == 'COMPUTER':
            insert_lv_data(conn, 'nova', meta.nova_lv_size, meta.host_id)


def compatible_service_disk_table(conn):
    sql = "select host_roles.host_id, service_disks.service, service_disks.size " \
          "from host_roles inner join service_disks on " \
          "host_roles.role_id=service_disks.role_id where " \
          "service_disks.disk_location='local' and service_disks.deleted=0 and " \
          "host_roles.deleted=0;"
    metas = conn.execute(sql).fetchall()
    for meta in metas:
        if meta.service in ['db_backup', 'mongodb', 'provider']:
            insert_lv_data(conn, meta.service, meta.size, meta.host_id)


def upgrade(migrate_engine):
    print("039 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    Table('hosts', meta, autoload=True)
    tables = [define_logical_volume_table(meta)]
    create_tables(tables)

    conn = migrate_engine.connect()
    compatible_role_table(conn)
    compatible_service_disk_table(conn)
    conn.close()


def downgrade(migrate_engine):
    print("039 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_logical_volume_table(meta)]
    drop_tables(tables)
