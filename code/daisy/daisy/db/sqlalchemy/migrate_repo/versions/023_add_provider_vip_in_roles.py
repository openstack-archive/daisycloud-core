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

from sqlalchemy import MetaData, Table, Column, String

meta = MetaData()
outband_vip = Column('outband_vip', String(255))
provider_public_vip = Column('provider_public_vip', String(255))


def upgrade(migrate_engine):
    print("023 upgrade")
    meta.bind = migrate_engine
    role = Table('roles', meta, autoload=True)
    role.create_column(outband_vip)
    role.create_column(provider_public_vip)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("023 downgrade")
