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

from sqlalchemy import MetaData, Table, Column, String

enable_l2_or_l3 = Column('enable_l2_or_l3', String(255))


def upgrade(migrate_engine):
    print("053 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    neutron_backend = Table('neutron_backend', meta, autoload=True)
    neutron_backend.create_column(enable_l2_or_l3)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("053 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    neutron_backend = Table('neutron_backend', meta, autoload=True)
    neutron_backend.drop_column(enable_l2_or_l3)
