from sqlalchemy import text

from app.db import Base, engine
from app.seed import seed_builtin_plugins


def _ensure_sqlite_compat_columns() -> None:
    with engine.begin() as connection:
        thread_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(thread)")).all()
        }
        if "status" not in thread_columns:
            connection.execute(text("ALTER TABLE thread ADD COLUMN status VARCHAR(40) DEFAULT 'regular'"))


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_compat_columns()
    seed_builtin_plugins()
