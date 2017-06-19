from sqlalchemy import (Boolean, DateTime, Integer, String, Text,
                        Column, MetaData, Table, ForeignKey)

dis_position = Column('position', String(255))
host_position = Column('position', String(255))

def upgrade(migrate_engine):
    print("047 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    discover_hosts = Table('discover_hosts', meta, autoload=True)
    discover_hosts.create_column(dis_position)
    hosts = Table('hosts', meta, autoload=True)
    hosts.create_column(host_position)

def downgrade(migrate_engine):
    print("047 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    discover_hosts = Table('discover_hosts', meta, autoload=True)
    discover_hosts.drop_column(dis_position)

    hosts = Table('hosts', meta, autoload=True)
    hosts.drop_column(host_position)

