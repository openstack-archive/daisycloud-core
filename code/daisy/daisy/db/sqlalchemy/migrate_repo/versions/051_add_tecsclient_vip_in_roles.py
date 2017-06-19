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

from sqlalchemy import MetaData, Table, Column, String

meta = MetaData()
tecsclient_vip = Column('tecsclient_vip', String(255))
provider_mgnt_vip = Column('provider_mgnt_vip', String(255))


def upgrade(migrate_engine):
    print("051 upgrade")
    meta.bind = migrate_engine
    role = Table('roles', meta, autoload=True)
    role.create_column(tecsclient_vip)
    role.create_column(provider_mgnt_vip)


def downgrade(migrate_engine):
    print("051 downgrade")
    meta.bind = migrate_engine
    role = Table('roles', meta, autoload=True)
    role.drop_column(tecsclient_vip)
    role.drop_column(provider_mgnt_vip)
