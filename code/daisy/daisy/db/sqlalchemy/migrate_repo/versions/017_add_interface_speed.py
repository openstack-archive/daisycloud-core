from sqlalchemy import Column
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import String


meta = MetaData()
state = Column('state',String(64))
max_speed = Column('max_speed',String(64))
current_speed =Column('current_speed',String(64))


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    meta.bind = migrate_engine
    host_interfaces = Table('host_interfaces', meta, autoload=True)
    host_interfaces.create_column(state)
    host_interfaces.create_column(max_speed)
    host_interfaces.create_column(current_speed)

def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pass
