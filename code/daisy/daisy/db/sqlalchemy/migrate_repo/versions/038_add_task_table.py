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

import uuid
from migrate import ForeignKeyConstraint
from sqlalchemy import (Boolean, DateTime, Integer, String, Text,
                        Column, MetaData, Table, ForeignKey)
from daisy.db.sqlalchemy.migrate_repo.schema import create_tables
from daisy.db.sqlalchemy.migrate_repo.schema import drop_tables


def define_tasks_table(meta):
    tasks = Table(
        'tasks',
        meta,
        Column('id', String(36), primary_key=True),
        Column('name', String(36), nullable=False),
        Column('type', String(30)),
        Column('status', Text, nullable=False),
        Column('expires_at', DateTime),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return tasks


def define_task_infos_table(meta):
    task_infos = Table(
        "task_infos",
        meta,
        Column('id', String(36), primary_key=True),
        Column('task_id', String(36), ForeignKey('tasks.id')),
        Column('targets', Text),
        Column('hosts', Text),
        Column('messages', Text),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        Column('deleted_at', DateTime),
        Column('deleted', Boolean, default=False, index=True),
        mysql_engine='InnoDB',
        extend_existing=True)
    return task_infos


def upgrade(migrate_engine):
    print("038 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    tables = [define_tasks_table(meta),
              define_task_infos_table(meta)]
    drop_tables(tables)
    create_tables(tables)


def downgrade(migrate_engine):
    print("038 downgrade")
