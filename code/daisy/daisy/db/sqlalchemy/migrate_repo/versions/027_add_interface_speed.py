# Copyright 2012 OpenStack Foundation.
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

from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import String


meta = MetaData()
state = Column('state', String(64))
max_speed = Column('max_speed', String(64))
current_speed = Column('current_speed', String(64))


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    print("027 upgrade")
    meta.bind = migrate_engine
    host_interfaces = Table('host_interfaces', meta, autoload=True)
    host_interfaces.create_column(state)
    host_interfaces.create_column(max_speed)
    host_interfaces.create_column(current_speed)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("027 downgrade")
