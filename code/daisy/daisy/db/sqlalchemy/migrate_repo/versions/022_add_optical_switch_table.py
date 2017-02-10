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

from sqlalchemy.schema import (Column, MetaData, Table)
from daisy.db.sqlalchemy.migrate_repo.schema import (Boolean, DateTime,
                                                     String, create_tables)


def define_optical_switchs_table(meta):
    optical_switchs = Table('optical_switchs',
                            meta,
                            Column('id', String(36),
                                   primary_key=True,
                                   nullable=False),
                            Column('user_name', String(255)),
                            Column('user_pwd', String(255)),
                            Column('switch_ip', String(36)),
                            Column('switch_port', String(36)),
                            Column('role_id', String(36)),
                            Column('fc_driver', String(36)),
                            Column('fc_zoneing_policy', String(36)),
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
    return optical_switchs


def upgrade(migrate_engine):
    print("022 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_optical_switchs_table(meta), ]
    create_tables(tables)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("022 downgrade")
