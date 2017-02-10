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

from sqlalchemy.schema import (Column, MetaData, Table)
from daisy.db.sqlalchemy.migrate_repo.schema import (
    Boolean, DateTime, String, Text,
    create_tables)


def define_template_table(meta):
    templates = Table('template',
                      meta,
                      Column('id', String(36), primary_key=True,
                             nullable=False),
                      Column('name', String(36), nullable=False),
                      Column('description', Text()),
                      Column('type', String(36), nullable=True),
                      Column('hosts', Text(), nullable=True),
                      Column('content', Text(), nullable=True),
                      Column('updated_at', DateTime(), nullable=False),
                      Column('deleted_at', DateTime()),
                      Column('created_at', DateTime(), nullable=False),
                      Column('deleted',
                             Boolean(),
                             nullable=False,
                             default=False,
                             index=True),
                      mysql_engine='InnoDB',
                      extend_existing=True)

    return templates


def define_host_template_table(meta):
    host_templates = Table('host_templates',
                           meta,
                           Column('id', String(36), primary_key=True,
                                  nullable=False),
                           Column('cluster_name', String(36), nullable=False),
                           Column('hosts', Text(), nullable=True),
                           Column('updated_at', DateTime(), nullable=False),
                           Column('deleted_at', DateTime()),
                           Column('created_at', DateTime(), nullable=False),
                           Column('deleted',
                                  Boolean(),
                                  nullable=False,
                                  default=False,
                                  index=True),
                           mysql_engine='InnoDB',
                           extend_existing=True)

    return host_templates


def upgrade(migrate_engine):
    print("003 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_template_table(meta),
              define_host_template_table(meta)]
    create_tables(tables)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
