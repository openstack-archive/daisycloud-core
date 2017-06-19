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
from sqlalchemy import orm
from sqlalchemy.schema import (Column, MetaData, Table)
from daisy.db.sqlalchemy.migrate_repo.schema import (Boolean, DateTime,
                                                     String, create_tables,
                                                     drop_tables)
from daisy.db.sqlalchemy import models


def define_template_config_roles_table(meta):
    template_config_roles = \
        Table('template_config_roles',
              meta,
              Column('id', String(36), primary_key=True, nullable=False),
              Column('config_id', String(80)),
              Column('role_name', String(36)),
              Column('updated_at', DateTime(), nullable=False),
              Column('deleted_at', DateTime()),
              Column('created_at', DateTime(), nullable=False),
              Column('deleted', Boolean(), nullable=False, default=False,
                     index=True),
              mysql_engine='InnoDB',
              extend_existing=True)
    return template_config_roles


def upgrade(migrate_engine):
    print("042 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_template_config_roles_table(meta)]
    create_tables(tables)

    configs = Table('configs', meta, autoload=True)
    template_config_id_reserve = getattr(configs.c, 'template_config_id')
    template_config_id_reserve.alter(type=String(80))

    template_config = Table('template_config', meta, autoload=True)
    id_reserve = getattr(template_config.c, 'id')
    id_reserve.alter(type=String(80))
    name_reserve = getattr(template_config.c, 'name')
    name_reserve.alter(type=String(128))

    template_func = Table('template_func', meta, autoload=True)
    id_reserve = getattr(template_func.c, 'id')
    id_reserve.alter(type=String(80))
    name_reserve = getattr(template_func.c, 'name')
    name_reserve.alter(type=String(128))

    template_func_configs = Table('template_func_configs', meta, autoload=True)
    id_reserve = getattr(template_func_configs.c, 'func_id')
    id_reserve.alter(type=String(80))
    name_reserve = getattr(template_func_configs.c, 'config_id')
    name_reserve.alter(type=String(80))

    config_service = Table('config_service', meta, autoload=True)
    config_id_reserve = getattr(config_service.c, 'config_id')
    config_id_reserve.alter(type=String(80))

    session = orm.sessionmaker(bind=migrate_engine)()
    session.query(models.TemplateService).\
        filter(models.TemplateService.service_name == "compute").\
        update({"service_name": "openstack-nova-compute"})
    template_config_roles_count = session.query(
        models.TemplateConfigRoles).count()
    if not template_config_roles_count:
        session.add_all([
            models.TemplateConfigRoles(id=str(uuid.uuid4()),
                                       config_id='001',
                                       role_name="COMPUTER"),
            models.TemplateConfigRoles(id=str(uuid.uuid4()),
                                       config_id='002',
                                       role_name="COMPUTER"),
            models.TemplateConfigRoles(id=str(uuid.uuid4()),
                                       config_id='003',
                                       role_name="COMPUTER"),
            models.TemplateConfigRoles(id=str(uuid.uuid4()),
                                       config_id='003',
                                       role_name="COMPUTER"),
        ])
    session.commit()


def downgrade(migrate_engine):
    print("042 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_template_config_roles_table(meta)]
    drop_tables(tables)

    configs = Table('configs', meta, autoload=True)
    template_config_id_reserve = getattr(configs.c, 'template_config_id')
    template_config_id_reserve.alter(type=String(36))

    template_config = Table('template_config', meta, autoload=True)
    id_reserve = getattr(template_config.c, 'id')
    id_reserve.alter(type=String(36))
    name_reserve = getattr(template_config.c, 'name')
    name_reserve.alter(type=String(50))

    template_func = Table('template_func', meta, autoload=True)
    id_reserve = getattr(template_func.c, 'id')
    id_reserve.alter(type=String(36))
    name_reserve = getattr(template_func.c, 'name')
    name_reserve.alter(type=String(36))

    template_func_configs = Table('template_func_configs', meta, autoload=True)
    id_reserve = getattr(template_func_configs.c, 'func_id')
    id_reserve.alter(type=String(36))
    name_reserve = getattr(template_func_configs.c, 'config_id')
    name_reserve.alter(type=String(36))

    config_service = Table('config_service', meta, autoload=True)
    config_id_reserve = getattr(config_service.c, 'config_id')
    config_id_reserve.alter(type=String(36))
