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

from sqlalchemy import (Boolean, DateTime, String,
                        Column, MetaData, Table, ForeignKey)
from daisy.db.sqlalchemy.migrate_repo.schema import create_tables
from daisy.db.sqlalchemy.migrate_repo.schema import drop_tables


def define_cluster_versions_table(meta):
    cluster_versions = Table(
        'cluster_versions',
        meta,
        Column('id', String(36), primary_key=True),
        Column('cluster_id', String(36), ForeignKey('clusters.id')),
        Column('version_id', String(36), ForeignKey('versions.id')),
        Column('target_id', String(36), ForeignKey('targets.id')),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return cluster_versions


def upgrade(migrate_engine):
    print("040 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_cluster_versions_table(meta)]
    Table('targets', meta, autoload=True)
    Table('versions', meta, autoload=True)
    Table('clusters', meta, autoload=True)
    create_tables(tables)


def downgrade(migrate_engine):
    print("040 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_cluster_versions_table(meta)]
    drop_tables(tables)
