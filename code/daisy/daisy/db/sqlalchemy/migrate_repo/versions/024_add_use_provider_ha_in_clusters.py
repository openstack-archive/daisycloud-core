from sqlalchemy import MetaData, Table, Column, Integer

meta = MetaData()
use_provider_ha = Column('use_provider_ha', Integer(), default=0)


def upgrade(migrate_engine):
    meta.bind = migrate_engine
    clusters = Table('clusters', meta, autoload=True)
    clusters.create_column(use_provider_ha)
