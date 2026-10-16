# PQM Quality Manager

Aplicación de escritorio en español para registrar inspecciones y entregas de tableros PQM de INGELEAN S.A.S.

## Requisitos y ejecución

- Python 3.12 o superior (compatible con Python 3.13).
- `uv` instalado.

```bash
uv sync
uv run python main.py
```

Para ejecutar las pruebas: `uv sync --extra dev` y `uv run pytest`.

## Funcionalidades

- Panel de control e historial con búsqueda por PQM/empresa y filtro de estado.
- Registro persistente de inspecciones con número PQM único entre registros activos.
- Catálogo centralizado de 35 evidencias con evaluación, medición, justificación de No aplica y varias fotografías originales por evidencia.
- Validación de requisitos para remitir a revisión y transiciones auditadas de aprobación/rechazo/cierre.
- Informes PDF borrador y final con imágenes; los finales requieren aprobación.
- Configuración SMTP, credencial protegida con keyring y prueba explícita.
- Respaldos ZIP y restauración validada con copia preventiva.

## PostgreSQL y guardado automático

Admite PostgreSQL en un servidor y SQLite local. La conexión se configura en **Configuración → Base de datos**, con campos de servidor, puerto, base, usuario y contraseña, prueba de conexión y guardado por equipo. Si falla al iniciar, permite corregirla antes de abrir los datos. `.env` sigue siendo compatible cuando no hay una configuración guardada desde la app. La aplicación se conecta directamente a la IP del servidor por la red local. El editor guarda avances automáticamente y mantiene checkpoints consultables; fotos originales y PDF nuevos también quedan en la base. Incluye migración transaccional de los registros y archivos existentes.

Consulta [la guía de despliegue, conexión, migración y respaldo](docs/postgresql.md). Los archivos para desplegar PostgreSQL con Docker Compose están en `deploy/`.

## Datos locales

En Windows: `%APPDATA%/Ingelean/PQMQualityManager`.

En Linux: `~/.local/share/Ingelean/PQMQualityManager` (o `$XDG_DATA_HOME/Ingelean/PQMQualityManager`).

La carpeta contiene SQLite (si se usa modo local), caché de fotos e informes, miniaturas y logs. Las contraseñas SMTP se conservan en el llavero del sistema. En PostgreSQL los registros y archivos se almacenan en el servidor.

## Compilar para Windows

Desde Windows, ejecute `scripts/build_windows.ps1` en PowerShell. PyInstaller debe ejecutarse en Windows para producir un ejecutable Windows; compilar desde Linux no se considera validación del ejecutable.

## Respaldo y actualización

Use Configuración → Crear respaldo ZIP antes de actualizar o mover el equipo. La restauración genera un respaldo preventivo. Conserve fotos e informes junto con la base de datos. Las actualizaciones aplican revisiones de esquema en `schema_migrations`; los nuevos campos deben añadirse con migraciones incrementales, sin borrar datos existentes.

## Plantilla corporativa PDF

El generador está aislado en `services/pdf_service.py`. La primera versión genera una plantilla estándar, sin logotipo ni códigos institucionales inventados. Para integrar la plantilla real se puede añadir una estrategia de plantilla que dibuje los datos en las páginas base con pypdf, dejando intactos los servicios de inspección, imágenes y persistencia.

## Limitaciones conocidas de esta entrega

- La configuración de ubicación de almacenamiento y la migración entre volúmenes todavía no está expuesta en la interfaz.
- El flujo de aprobación captura el nombre declarado por el usuario; no constituye firma digital certificada.
- La restauración reemplaza datos de trabajo, por eso requiere confirmación y crea un respaldo previo.
- La generación de PDF corre en el hilo de interfaz; en una estación con grandes colecciones fotográficas conviene moverla a un trabajador Qt.
