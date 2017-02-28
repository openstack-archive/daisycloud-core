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

import sqlalchemy
from sqlalchemy.schema import (Column, ForeignKey, MetaData, Table)
from daisy.db.sqlalchemy.migrate_repo.schema import (Boolean, DateTime,
                                                     String, create_tables,
                                                     drop_tables)


def define_host_patch_history_table(meta):
    host_patch_history = Table('host_patch_history',
                               meta,
                               Column('id', String(36),
                                      primary_key=True,
                                      nullable=False),
                               Column('host_id', String(36), nullable=False),
                               Column('type', String(30), nullable=False),
                               Column('version_id', String(36)),
                               Column('patch_name', String(255)),
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
    return host_patch_history


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_host_patch_history_table(meta), ]
    create_tables(tables)


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_host_patch_history_table(meta)]
    drop_tables(tables)
