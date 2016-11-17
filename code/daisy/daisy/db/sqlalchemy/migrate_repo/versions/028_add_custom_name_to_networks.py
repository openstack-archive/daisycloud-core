from sqlalchemy import MetaData, Table, Column, String

meta = MetaData()
custom_name = Column('custom_name', String(255))


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    networks = Table('networks', meta, autoload=True)
    networks.create_column(custom_name)
