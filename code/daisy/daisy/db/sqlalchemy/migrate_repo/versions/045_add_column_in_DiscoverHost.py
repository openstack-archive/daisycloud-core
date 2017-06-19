from sqlalchemy import MetaData, Table, Column, String

ipmi_addr = Column('ipmi_addr', String(255))
hwm_id = Column('hwm_id', String(36))
hwm_ip = Column('hwm_ip', String(255))
discover_mode = Column('discover_mode', String(36))


def upgrade(migrate_engine):
    print("045 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    discover_hosts = Table('discover_hosts', meta, autoload=True)
    discover_hosts.create_column(ipmi_addr)
    discover_hosts.create_column(hwm_id)
    discover_hosts.create_column(hwm_ip)
    discover_hosts.create_column(discover_mode)
    sql1 = "update discover_hosts set discover_mode='SSH' where "\
           "status!='DISCOVERY_SUCCESSFUL' and ip is not NULL;"
    migrate_engine.execute(sql1)


def downgrade(migrate_engine):
    print("045 downgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    discover_hosts = Table('discover_hosts', meta, autoload=True)
    discover_hosts.drop_column(ipmi_addr)
    discover_hosts.drop_column(hwm_id)
    discover_hosts.drop_column(hwm_ip)
    discover_hosts.drop_column(discover_mode)
