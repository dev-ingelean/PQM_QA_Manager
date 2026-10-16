from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from pqm_quality_manager.config.settings import DB_PATH
from pqm_quality_manager.database.migrations import apply_migrations

def make_engine(path=DB_PATH):
    engine = create_engine(f"sqlite:///{path.as_posix()}", future=True)
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    apply_migrations(engine)
    return engine

engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
