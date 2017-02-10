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

from sqlalchemy import MetaData, Table, Column, String, BigInteger, Integer

meta = MetaData()
segmentation_type = Column('segmentation_type', String(64))
vni_start = Column('vni_start', BigInteger())
vni_end = Column('vni_end', BigInteger())
gre_id_start = Column('gre_id_start', Integer())
gre_id_end = Column('gre_id_end', Integer())


def upgrade(migrate_engine):
    print("015 upgrade")
    meta.bind = migrate_engine
    networks = Table('networks', meta, autoload=True)
    networks.create_column(segmentation_type)
    networks.create_column(vni_start)
    networks.create_column(vni_end)
    networks.create_column(gre_id_start)
    networks.create_column(gre_id_end)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
