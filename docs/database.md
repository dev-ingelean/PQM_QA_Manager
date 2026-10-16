# Base de datos

SQLite con claves foráneas activas y modo WAL. Tablas: `inspections`, `inspection_evidence`, `evidence_images`, `reports`, `email_dispatches`, `audit_log` y `app_settings`. La relación inspección/evidencias se genera en una transacción al crear el registro. El respaldo usa la API SQLite `backup()` para obtener una instantánea consistente.

`schema_migrations` registra la revisión inicial. La migración 1 crea el modelo idempotentemente, sin borrar datos existentes. Las revisiones posteriores deben implementarse de forma incremental en `database/migrations.py` y registrar su versión solo al terminar.
