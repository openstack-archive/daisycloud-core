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

from sqlalchemy import MetaData, Table, Column
from daisy.db.sqlalchemy.migrate_repo.schema import Integer

docker_vg_size = Column('docker_vg_size', Integer(), default=0)


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine
    roles = Table('roles', meta, autoload=True)
    roles.create_column(docker_vg_size)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("032 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    roles = Table('roles', meta, autoload=True)
    roles.drop_column(docker_vg_size)
