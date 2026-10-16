"""SQLite for local use, PostgreSQL for shared server persistence."""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url, URL
from sqlalchemy.orm import sessionmaker
from pqm_quality_manager.config.settings import DB_PATH
from pqm_quality_manager.database.migrations import apply_migrations


def database_url(value=None):
    if value is None:
        from pqm_quality_manager.config.database_connection import load_connection
        return load_connection().url()
    if isinstance(value, Path):
        value = f"sqlite:///{value.as_posix()}"
    url = value if isinstance(value, URL) else make_url(str(value))
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername not in {"sqlite", "postgresql+psycopg"}:
        raise ValueError("Use una URL sqlite:/// o postgresql+psycopg:// válida.")
    return url


def make_engine(path=None, *, initialize=True):
    url = database_url(path)
    options = {"pool_pre_ping": True, "hide_parameters": True}
    if url.get_backend_name() == "postgresql":
        options["connect_args"] = {"connect_timeout": 5, "application_name": "PQM Quality Manager"}
    engine = create_engine(url, **options)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    if initialize:
        apply_migrations(engine)
    return engine


# No connection or schema changes at import time. Startup reports connectivity errors.
engine = make_engine(DB_PATH, initialize=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def configure_engine():
    """Publish a validated connection without changing imported session factories."""
    global engine
    candidate = make_engine(initialize=False)
    try:
        apply_migrations(candidate)
    except Exception:
        candidate.dispose()
        raise
    previous = engine
    engine = candidate
    SessionLocal.configure(bind=candidate)
    previous.dispose()
    return candidate
