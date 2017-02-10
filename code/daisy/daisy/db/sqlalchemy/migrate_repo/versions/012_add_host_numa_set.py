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
vcpu_pin_set = Column('vcpu_pin_set', String(255))
dvs_high_cpuset = Column('dvs_high_cpuset', String(255))
pci_high_cpuset = Column('pci_high_cpuset', String(255))
os_cpus = Column('os_cpus', String(255))
dvs_cpus = Column('dvs_cpus', String(255))


def upgrade(migrate_engine):
    print("012 upgrade")
    meta.bind = migrate_engine

    hosts = Table('hosts', meta, autoload=True)
    hosts.create_column(vcpu_pin_set)
    hosts.create_column(dvs_high_cpuset)
    hosts.create_column(pci_high_cpuset)
    hosts.create_column(os_cpus)
    hosts.create_column(dvs_cpus)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
