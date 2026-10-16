"""Migraciones incrementales y compatibles con instalaciones locales."""
from sqlalchemy import text
from pqm_quality_manager.database.models import Base

CURRENT_VERSION = 1

def apply_migrations(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"))
        current = conn.execute(text("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")).scalar_one()
        if current < 1:
            # Initial revision creates the modeled tables without dropping data.
            Base.metadata.create_all(bind=conn)
            conn.execute(text("INSERT INTO schema_migrations(version) VALUES (1)"))
        # Future revisions belong here as guarded, transactional SQLAlchemy operations.
