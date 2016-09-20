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

from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from daisy.db.sqlalchemy.models import JSONEncodedDict


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    meta = MetaData()
    system = Column('system', JSONEncodedDict(), default={}, nullable=False)
    cpu = Column('cpu', JSONEncodedDict(), default={}, nullable=False)
    memory = Column('memory', JSONEncodedDict(), default={}, nullable=False)
    disks = Column('disks', JSONEncodedDict(), default={}, nullable=False)
    devices = Column('devices', JSONEncodedDict(), default={}, nullable=False)
    pci = Column('pci', JSONEncodedDict(), default={}, nullable=False)

    meta.bind = migrate_engine
    hosts = Table('hosts', meta, autoload=True)
    hosts.create_column(system)
    hosts.create_column(cpu)
    hosts.create_column(memory)
    hosts.create_column(disks)
    hosts.create_column(devices)
    hosts.create_column(pci)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
