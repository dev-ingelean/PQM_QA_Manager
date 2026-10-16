# Arquitectura

La interfaz Qt (`ui`) consume servicios de aplicación (`services`). Los servicios usan modelos SQLAlchemy (`database`) sobre SQLite o PostgreSQL y configuración/rutas independientes (`config`). El destino se configura en la interfaz y se guarda en la carpeta de usuario del equipo. Si no hay configuración guardada se lee el entorno o `.env`. Un formulario independiente de la base permite corregir la conexión cuando falla el inicio. La creación del esquema y la comprobación de conexión ocurren al iniciar, no al importar los módulos.

`InspectionService` centraliza validaciones y transiciones. El estado documental pertenece a `Inspection`; la evaluación pertenece a cada `InspectionEvidence`. Las operaciones de escritura guardan instantáneas mediante `checkpoint_service` dentro de su transacción. Los eventos de inspección también mantienen `AuditLog`.

`file_storage` conserva originales y PDF en la base y materializa caché local bajo demanda. `ImageService` valida originales y crea miniaturas; `PDFReportService` construye informes desde los datos persistidos. Los originales retirados de las evidencias se conservan en la base para las referencias históricas.

El editor usa un temporizador Qt de 1,5 segundos para guardar cambios, sin recargar ni borrar campos pendientes; también guarda antes de cambiar de evidencia o cerrar. Un fallo mantiene los datos en pantalla. El historial ofrece lectura de los últimos 100 checkpoints, sin restauración automática. Las operaciones de red siguen siendo síncronas; no hay cola sin conexión ni resolución de ediciones simultáneas de una misma inspección.

El despliegue de referencia utiliza PostgreSQL 17 en Docker con volumen persistente, cuenta de aplicación sin superusuario y conexión directa por la red local al puerto 5433 del servidor. Los respaldos se realizan mediante `pg_dump`. Consulta [PostgreSQL](postgresql.md).
