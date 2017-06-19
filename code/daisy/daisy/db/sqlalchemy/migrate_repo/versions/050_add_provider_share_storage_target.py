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
from sqlalchemy import MetaData

target_names = ["config_apply_provider_share_storage",
                "provider_config"]

target_description = {"config_apply_provider_share_storage":
                      "Config Apply Provider Share Storage",
                      "provider_config": "config provider"}


def create_targets(migrate_engine):
    targets_info = {}
    if migrate_engine.name == "mysql":
        sql = ""
        for name in target_names:
            tid = str(uuid.uuid4())
            targets_info[name] = tid
            desc = target_description.get(name)
            sql += "insert into targets(id,name,description," \
                   "created_at,updated_at,deleted) " \
                   "values('%s','%s','%s',now(),now(),0);" % (tid, name, desc)
        migrate_engine.execute(sql)
    return targets_info


def upgrade(migrate_engine):
    print("050 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    target_info = create_targets(migrate_engine)


def downgrade(migrate_engine):
    print("050 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
