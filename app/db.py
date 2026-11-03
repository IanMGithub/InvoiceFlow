from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_DIR / "invoiceflow.db"


engine = create_engine(f"sqlite:///{DATABASE_PATH}")


def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def listen_for_sqlite_foreign_keys(target_engine):
    event.listen(target_engine, "connect", enable_sqlite_foreign_keys)


listen_for_sqlite_foreign_keys(engine)


class Base(DeclarativeBase):
    pass
