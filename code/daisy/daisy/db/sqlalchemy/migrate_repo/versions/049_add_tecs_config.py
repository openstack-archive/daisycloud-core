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
    print("049 downgrade")
