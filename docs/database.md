# Base de datos

SQLAlchemy admite SQLite local (claves foráneas y WAL) y PostgreSQL con psycopg 3. El destino se configura en la aplicación y se guarda por equipo en `database_connection.json`, fuera de la propia base de datos. Esta configuración tiene prioridad sobre `PQM_DATABASE_URL` en `.env`; sin ninguna de las dos se usa SQLite local. La contraseña se guarda en el llavero del sistema cuando está disponible; si no lo está, se conserva en el archivo local con permisos 0600 en Linux. La conexión comprueba disponibilidad antes de reutilizar conexiones del pool y limita el establecimiento de conexiones PostgreSQL a cinco segundos.

Tablas de negocio: `inspections`, `inspection_evidence`, `evidence_images`, `reports`, `email_dispatches`, `audit_log`, `app_settings`. La creación de la inspección y sus 35 evidencias es transaccional. `inspection_checkpoints` conserva instantáneas JSON completas de la inspección, evidencias y referencias a originales/reportes. Cada checkpoint se confirma en la misma transacción que su operación. `stored_files` conserva originales y PDF como binarios (`BYTEA` en PostgreSQL); las rutas relativas permiten regenerar copias locales.

`schema_migrations` registra revisiones idempotentes. La revisión 1 crea las tablas iniciales; la 2 añade checkpoints y almacenamiento binario sin alterar los datos anteriores. En PostgreSQL un bloqueo asesor transaccional serializa las migraciones concurrentes.

La herramienta `database.manage migrate-sqlite` lee el origen sin modificarlo, copia registros a un destino vacío, sube los archivos existentes y ajusta secuencias antes de crear nuevos checkpoints. La copia de datos se revierte si falta algún archivo o falla una operación. No implementa fusión ni sincronización entre bases.

SQLite usa la API `backup()` para respaldos consistentes. PostgreSQL usa `pg_dump`; se restaura con `pg_restore` en el servidor. Consulta [la guía de PostgreSQL](postgresql.md) para despliegue, conexión y recuperación.
