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


def define_neutron_backend_table(meta):
    # NOTE(bcwaldon): load the images table for the ForeignKey below
    sqlalchemy.Table('roles', meta, autoload=True)
    neutron_backend = Table('neutron_backend',
                            meta,
                            Column('id', String(36),
                                   primary_key=True,
                                   nullable=False),
                            Column('role_id', String(36),
                                   ForeignKey('roles.id'), nullable=False),
                            Column('user_name', String(255)),
                            Column('user_pwd', String(255)),
                            Column('controller_ip', String(255)),
                            Column('neutron_backends_type', String(255)),
                            Column('sdn_type', String(255)),
                            Column('port', String(255)),
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
    return neutron_backend


def upgrade(migrate_engine):
    print("033 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_neutron_backend_table(meta), ]
    create_tables(tables)


def downgrade(migrate_engine):
    print("033 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    tables = [define_neutron_backend_table(meta)]
    drop_tables(tables)
