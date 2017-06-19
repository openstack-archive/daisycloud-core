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

meta = MetaData()
cluster_id = Column('cluster_id', String(36))


def upgrade(migrate_engine):
    print("041 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tasks = Table('tasks', meta, autoload=True)
    tasks.create_column(cluster_id)


def downgrade(migrate_engine):
    print("041 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tasks = Table('tasks', meta, autoload=True)
    tasks.drop_column(cluster_id)
