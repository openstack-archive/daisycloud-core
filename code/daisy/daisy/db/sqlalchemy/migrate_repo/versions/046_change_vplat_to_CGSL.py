
from sqlalchemy import MetaData, Column, String

ipmi_addr = Column('ipmi_addr', String(255))
hwm_id = Column('hwm_id', String(36))
hwm_ip = Column('hwm_ip', String(255))
discover_mode = Column('discover_mode', String(36))


def upgrade(migrate_engine):
    print("046 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine
    sql = "update versions set type='CGSL' where type='vplat' " \
          "and deleted=0;"
    migrate_engine.execute(sql)


def downgrade(migrate_engine):
    print("046 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine
