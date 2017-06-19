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

from sqlalchemy import MetaData, Table, Column, String
from daisy.db.sqlalchemy.migrate_repo.schema import (Boolean, DateTime, Text,
                                                     create_tables, BigInteger)

version_patch_id = Column('version_patch_id', String(36))
target_system = Column('target_systems', String(255))


def define_version_patch_table(meta):
    version_patchs = Table('version_patchs',
                           meta,
                           Column('id', String(36), primary_key=True,
                                  nullable=False),
                           Column('name', String(256), nullable=False),
                           Column('version_id', String(36), nullable=False),
                           Column('size', BigInteger()),
                           Column('checksum', String(128)),
                           Column('status', String(30)),
                           Column('description', Text()),
                           Column('updated_at', DateTime(), nullable=False),
                           Column('deleted_at', DateTime()),
                           Column('created_at', DateTime(), nullable=False),
                           Column('deleted', Boolean(), nullable=False,
                                  default=False,
                                  index=True),
                           mysql_engine='InnoDB',
                           extend_existing=True)

    return version_patchs


def upgrade(migrate_engine):
    print("016 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_version_patch_table(meta), ]
    create_tables(tables)

    hosts = Table('hosts', meta, autoload=True)
    hosts.create_column(version_patch_id)
    clusters = Table('clusters', meta, autoload=True)
    clusters.create_column(target_system)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
