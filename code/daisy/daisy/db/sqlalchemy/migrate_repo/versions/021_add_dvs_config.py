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
dvs_config_type = Column('dvs_config_type', String(255))
dvsc_cpus = Column('dvsc_cpus', String(255))
dvsp_cpus = Column('dvsp_cpus', String(255))
dvsv_cpus = Column('dvsv_cpus', String(255))
dvsblank_cpus = Column('dvsblank_cpus', String(255))
flow_mode = Column('flow_mode', String(255))
virtio_queue_size = Column('virtio_queue_size', String(255))
dvs_config_desc = Column('dvs_config_desc', String(255))


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    hosts = Table('hosts', meta, autoload=True)
    hosts.create_column(dvs_config_type)
    hosts.create_column(dvsc_cpus)
    hosts.create_column(dvsp_cpus)
    hosts.create_column(dvsv_cpus)
    hosts.create_column(dvsblank_cpus)
    hosts.create_column(flow_mode)
    hosts.create_column(virtio_queue_size)
    hosts.create_column(dvs_config_desc)
