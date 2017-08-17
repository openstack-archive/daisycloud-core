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

import uuid
from sqlalchemy import MetaData


def upgrade(migrate_engine):
    print("049 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    if migrate_engine.name == "mysql":
        tid = str(uuid.uuid4())
        name = "tecs_config"
        desc = "Config and start tecs by ansible"
        sql = "insert into targets(id,name,description," \
            "created_at,updated_at,deleted) " \
            "values('%s','%s','%s',now(),now(),0);" % (tid, name, desc)
        migrate_engine.execute(sql)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("049 downgrade")
