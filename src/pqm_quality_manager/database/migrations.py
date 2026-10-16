"""Migraciones incrementales y compatibles con instalaciones locales."""
from sqlalchemy import text
from pqm_quality_manager.database.models import Base

CURRENT_VERSION = 2

def apply_migrations(engine) -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(72381042)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (CAST(CURRENT_TIMESTAMP AS TEXT)))"))
        current = conn.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")).scalar_one()
        if current < 1:
            # Initial revision creates the modeled tables without dropping data.
            Base.metadata.create_all(bind=conn)
            conn.execute(text("INSERT INTO schema_migrations(version) VALUES (1)"))
        if current < 2:
            from pqm_quality_manager.database.models import InspectionCheckpoint, StoredFile
            InspectionCheckpoint.__table__.create(bind=conn, checkfirst=True)
            StoredFile.__table__.create(bind=conn, checkfirst=True)
            conn.execute(text("INSERT INTO schema_migrations(version) VALUES (2)"))
