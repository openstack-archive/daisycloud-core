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

from sqlalchemy import (Boolean, DateTime, String, Text,
                        Column, MetaData, Table, ForeignKey)
from daisy.db.sqlalchemy.migrate_repo.schema import create_tables
from daisy.db.sqlalchemy.migrate_repo.schema import drop_tables

meta = MetaData()
targets = Column('targets', Text())
status = Column('status', Text())


def define_task_host_table(meta):
    task_host = Table(
        'task_host',
        meta,
        Column('id', String(36), primary_key=True),
        Column('task_id', String(36), ForeignKey('tasks.id')),
        Column('host_id', String(36), ForeignKey('hosts.id')),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return task_host


def upgrade(migrate_engine):
    print("044 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tasks = Table('tasks', meta, autoload=True)
    Table('hosts', meta, autoload=True)
    tasks_status_reserve = getattr(tasks.c, 'status')
    tasks_status_reserve.alter(name='cur_step')
    tasks_status_reserve.alter(nullable=True)
    tasks.create_column(targets)
    tasks.create_column(status)
    tables = [define_task_host_table(meta)]
    create_tables(tables)


def downgrade(migrate_engine):
    print("044 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tasks = Table('tasks', meta, autoload=True)
    tasks.drop_column(targets)
    tasks.drop_column(status)
    tables = [define_task_host_table(meta)]
    drop_tables(tables)
