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
root_pwd = Column('root_pwd', String(255))
resource_pools = Column('resource_pools', String(255))


def upgrade(migrate_engine):
    meta.bind = migrate_engine

    cinder_volumes = Table('cinder_volumes', meta, autoload=True)
    cinder_volumes.create_column(root_pwd)
    cinder_volumes.create_column(resource_pools)

