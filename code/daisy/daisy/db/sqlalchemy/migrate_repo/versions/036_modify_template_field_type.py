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

from sqlalchemy.schema import (Column, ForeignKey, MetaData, Table)
from daisy.db.sqlalchemy.migrate_repo.schema import (
    Boolean, DateTime, Integer, String, Text,
    create_tables, drop_tables)


def define_component_config_table(meta):
    component_config = \
        Table('component_config',
              meta,
              Column('id', String(36), primary_key=True, nullable=False),
              Column('component_id', String(36), nullable=False),
              Column('cluster_id', String(36), nullable=False),
              Column('enable', Integer(), nullable=False, default=0),
              Column('updated_at', DateTime(), nullable=False),
              Column('deleted_at', DateTime()),
              Column('created_at', DateTime(), nullable=False),
              Column('deleted', Boolean(), nullable=False, default=False,
                     index=True),
              mysql_engine='InnoDB',
              extend_existing=True)
    return component_config


def upgrade(migrate_engine):
    print("036 upgrade")
    if migrate_engine.name == "mysql":
        sql1 = "alter table host_templates modify column hosts longtext;"
        sql2 = "alter table template modify column hosts longtext;"
        migrate_engine.execute(sql1+sql2)
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_component_config_table(meta)]
    create_tables(tables)


def downgrade(migrate_engine):
    print("036 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_component_config_table(meta)]
    drop_tables(tables)
