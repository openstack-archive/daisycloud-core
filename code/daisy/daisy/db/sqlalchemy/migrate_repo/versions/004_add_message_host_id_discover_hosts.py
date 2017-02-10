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

from sqlalchemy import MetaData, Table, Column, String, Text

meta = MetaData()
message = Column('message', Text(), nullable=True)
host_id = Column('host_id', String(36), nullable=True)


def upgrade(migrate_engine):
    print("004 upgrade")
    meta.bind = migrate_engine

    discover_hosts = Table('discover_hosts', meta, autoload=True)
    discover_hosts.create_column(message)
    discover_hosts.create_column(host_id)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
