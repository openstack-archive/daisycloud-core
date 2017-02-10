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

from sqlalchemy.schema import (Column, MetaData, Table)
from daisy.db.sqlalchemy.migrate_repo.schema import (
    Boolean, DateTime, Integer, String, Text,
    create_tables)

template_config_id = Column('template_config_id', String(36))


def define_template_config_table(meta):
    template_config = \
        Table('template_config',
              meta,
              Column('id', String(36), primary_key=True, nullable=False),
              Column('name', String(50), nullable=False),
              Column('section_name', String(50)),
              Column('ch_desc', Text()),
              Column('en_desc', Text()),
              Column('data_type', String(50), nullable=False),
              Column('default_value', String(100)),
              Column('length', Integer()),
              Column('suggested_range', String(256)),
              Column('config_file', Text(), nullable=False),
              Column('data_check_script', Text()),
              Column('updated_at', DateTime(), nullable=False),
              Column('deleted_at', DateTime()),
              Column('created_at', DateTime(), nullable=False),
              Column('deleted', Boolean(), nullable=False, default=False,
                     index=True),
              mysql_engine='InnoDB',
              extend_existing=True)
    return template_config


def define_template_func_table(meta):
    template_func = \
        Table('template_func',
              meta,
              Column('id', String(36), primary_key=True, nullable=False),
              Column('name', String(50), nullable=False),
              Column('ch_desc', Text()),
              Column('en_desc', Text()),
              Column('data_check_script', Text()),
              Column('updated_at', DateTime(), nullable=False),
              Column('deleted_at', DateTime()),
              Column('created_at', DateTime(), nullable=False),
              Column('deleted', Boolean(), nullable=False, default=False,
                     index=True),
              mysql_engine='InnoDB',
              extend_existing=True)
    return template_func


def define_template_func_configs_table(meta):
    template_func_configs = \
        Table('template_func_configs',
              meta,
              Column('id', String(36), primary_key=True, nullable=False),
              Column('func_id', String(36)),
              Column('config_id', String(36)),
              Column('updated_at', DateTime(), nullable=False),
              Column('deleted_at', DateTime()),
              Column('created_at', DateTime(), nullable=False),
              Column('deleted', Boolean(), nullable=False, default=False,
                     index=True),
              mysql_engine='InnoDB',
              extend_existing=True)
    return template_func_configs


def define_template_service_table(meta):
    template_service = \
        Table('template_service',
              meta,
              Column('id', String(36), primary_key=True, nullable=False),
              Column('service_name', String(100), nullable=False),
              Column('force_type', String(50)),
              Column('updated_at', DateTime(), nullable=False),
              Column('deleted_at', DateTime()),
              Column('created_at', DateTime(), nullable=False),
              Column('deleted', Boolean(), nullable=False, default=False,
                     index=True),
              mysql_engine='InnoDB',
              extend_existing=True)
    return template_service


def define_config_service_table(meta):
    config_service = \
        Table('config_service',
              meta,
              Column('id', String(36), primary_key=True,
                     nullable=False),
              Column('config_id', String(36)),
              Column('service_id', String(36)),
              Column('updated_at', DateTime(), nullable=False),
              Column('deleted_at', DateTime()),
              Column('created_at', DateTime(), nullable=False),
              Column('deleted', Boolean(), nullable=False, default=False,
                     index=True),
              mysql_engine='InnoDB',
              extend_existing=True)
    return config_service


def upgrade(migrate_engine):
    print("018 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_template_config_table(meta),
              define_template_func_table(meta),
              define_template_func_configs_table(meta),
              define_template_service_table(meta),
              define_config_service_table(meta)]
    create_tables(tables)

    configs = Table('configs', meta, autoload=True)
    configs.create_column(template_config_id)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
