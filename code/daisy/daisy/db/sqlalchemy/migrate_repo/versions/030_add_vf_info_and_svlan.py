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

parent_id = Column('parent_id', String(36))
vf_index = Column('vf_index', Integer)
is_support_vf = Column('is_support_vf', Boolean, default=0)
is_vf = Column('is_vf', Boolean, default=0)

#vxlan+sriov need svlan,default 3000:4094
svlan_start = Column('svlan_start', Integer, default=3000)
svlan_end = Column('svlan_end', Integer, default=4094)


def upgrade(migrate_engine):
    print("030 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    host_interfaces = Table('host_interfaces', meta, autoload=True)
    host_interfaces.create_column(is_support_vf)
    host_interfaces.create_column(is_vf)
    host_interfaces.create_column(parent_id)
    host_interfaces.create_column(vf_index)

    networks = Table('networks', meta, autoload=True)
    networks.create_column(svlan_start)
    networks.create_column(svlan_end)


def downgrade(migrate_engine):
    print("030 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    host_interfaces = Table('host_interfaces', meta, autoload=True)
    host_interfaces.drop_column(parent_id)
    host_interfaces.drop_column(vf_index)
    host_interfaces.drop_column(is_support_vf)
    host_interfaces.drop_column(is_vf)

    networks = Table('networks', meta, autoload=True)
    networks.drop_column(svlan_start)
    networks.drop_column(svlan_end)
