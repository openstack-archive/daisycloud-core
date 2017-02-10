from sqlalchemy import MetaData, Table, Column, String

meta = MetaData()
custom_name = Column('custom_name', String(255))


def upgrade(migrate_engine):
    print("028 upgrade")
    meta.bind = migrate_engine
    networks = Table('networks', meta, autoload=True)
    networks.create_column(custom_name)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("028 downgrade")
