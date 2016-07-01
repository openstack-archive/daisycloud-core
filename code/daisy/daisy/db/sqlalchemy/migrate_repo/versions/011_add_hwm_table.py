# Copyright 2013 OpenStack Foundation
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

from sqlalchemy import MetaData, Table, Column, String
from daisy.db.sqlalchemy.migrate_repo.schema import (Boolean, DateTime, Text,
                                                     create_tables)

hwm_id = Column('hwm_id', String(36))
host_hwm_ip = Column('hwm_ip', String(256))
cluster_hwm_ip = Column('hwm_ip', String(256))


def define_hwm_table(meta):
    hwm = Table('hwm',
                meta,
                Column('id', String(36), primary_key=True, nullable=False),
                Column('hwm_ip', String(36), nullable=False),
                Column('description', Text()),
                Column('updated_at', DateTime(), nullable=False),
                Column('deleted_at', DateTime()),
                Column('created_at', DateTime(), nullable=False),
                Column('deleted', Boolean(), nullable=False, default=False,
                       index=True),
                mysql_engine='InnoDB',
                extend_existing=True)

    return hwm


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_hwm_table(meta), ]
    create_tables(tables)

    hosts = Table('hosts', meta, autoload=True)
    hosts.create_column(hwm_id)
    hosts.create_column(host_hwm_ip)

    clusters = Table('clusters', meta, autoload=True)
    clusters.create_column(cluster_hwm_ip)
