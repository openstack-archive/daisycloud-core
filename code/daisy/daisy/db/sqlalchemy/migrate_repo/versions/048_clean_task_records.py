from sqlalchemy import orm
from sqlalchemy import (MetaData)
from daisy.db.sqlalchemy import models


def upgrade(migrate_engine):
    print("048 upgrade")
    meta = MetaData()
    meta.bind = migrate_engine

    session = orm.sessionmaker(bind=migrate_engine)()
    session.query(models.TaskHost).delete()
    session.query(models.Task).delete()
    session.commit()


def downgrade(migrate_engine):
    print("048 downgrade")
    session.commit()
