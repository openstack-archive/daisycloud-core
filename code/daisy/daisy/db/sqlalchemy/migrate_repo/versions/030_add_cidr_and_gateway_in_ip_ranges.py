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

from sqlalchemy import MetaData, Table, Column, String, Integer, Boolean

cidr = Column('cidr', String(255))
gateway = Column('gateway', String(255))


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    ip_ranges = Table('ip_ranges', meta, autoload=True)
    ip_ranges.create_column(cidr)
    ip_ranges.create_column(gateway)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("030 downgrade")
