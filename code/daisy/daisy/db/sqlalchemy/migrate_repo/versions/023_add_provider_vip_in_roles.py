from sqlalchemy import MetaData, Table, Column, String

meta = MetaData()
outband_vip = Column('outband_vip', String(255))
provider_public_vip = Column('provider_public_vip', String(255))


def upgrade(migrate_engine):
    print("023 upgrade")
    meta.bind = migrate_engine
    role = Table('roles', meta, autoload=True)
    role.create_column(outband_vip)
    role.create_column(provider_public_vip)


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    print("023 downgrade")
