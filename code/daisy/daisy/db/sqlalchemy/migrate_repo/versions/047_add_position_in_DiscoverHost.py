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

from sqlalchemy import (String,
                        Column, MetaData, Table)

dis_position = Column('position', String(255))
host_position = Column('position', String(255))


def upgrade(migrate_engine):
    print("047 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    discover_hosts = Table('discover_hosts', meta, autoload=True)
    discover_hosts.create_column(dis_position)
    hosts = Table('hosts', meta, autoload=True)
    hosts.create_column(host_position)


def downgrade(migrate_engine):
    print("047 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    discover_hosts = Table('discover_hosts', meta, autoload=True)
    discover_hosts.drop_column(dis_position)

    hosts = Table('hosts', meta, autoload=True)
    hosts.drop_column(host_position)
