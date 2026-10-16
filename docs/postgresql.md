# PostgreSQL en un servidor y checkpoints

La aplicación admite SQLite local (predeterminado) y PostgreSQL configurado desde la aplicación. No cambia automáticamente a SQLite cuando PostgreSQL falla: evita guardar información en un destino distinto sin que lo sepas.

Las inspecciones, evaluaciones, auditoría, checkpoints, fotos originales y PDF nuevos quedan en la base elegida. Las fotos/PDF también tienen una copia local para abrirlos con programas de escritorio; al abrirlos desde otro equipo, se descargan de la base cuando faltan en su caché. Las miniaturas se regeneran. Los checkpoints son instantáneas de datos y referencias a archivos, consultables desde el editor; no son una restauración automática ni un reemplazo de los respaldos. Los originales almacenados se conservan aunque se retire una foto de la inspección, para mantener las referencias históricas.

## 1. Preparar el PC servidor Linux

Instala Docker Engine y Docker Compose siguiendo las instrucciones oficiales para tu distribución: https://docs.docker.com/engine/install/. En el PC servidor, abre una terminal en la carpeta `deploy/` del proyecto. Si tu usuario no tiene acceso a Docker, antepone `sudo` a los comandos Docker.

Para una instalación nueva:

```bash
umask 077
mkdir -p secrets
openssl rand -hex 32 > secrets/postgres_password.txt
openssl rand -hex 32 > secrets/app_password.txt
chmod 600 secrets/*.txt
docker compose up -d --wait
docker compose ps
docker compose exec db pg_isready -U postgres -d pqm
```

Si ya desplegaste la base, conserva los archivos `secrets/` existentes: no vuelvas a generar las contraseñas. La aplicación utiliza `pqm_app`, sin privilegios de superusuario; `postgres` se reserva para administración. El esquema se crea al iniciar o migrar con la aplicación.

El archivo `compose.yaml` publica **5433:5432**: los clientes usan el puerto 5433 del PC servidor y PostgreSQL escucha en el 5432 del contenedor. Se mantiene 5433 porque el servidor ya tiene ocupado el 5432. Si actualizas un despliegue que solo escuchaba en `127.0.0.1`, sustituye su bloque de puertos por:

```yaml
    ports:
      - "5433:5432"
```

Aplica el cambio desde la misma carpeta `deploy/` con `docker compose up -d --wait`. Conserva el volumen y el nombre del proyecto Compose. No ejecutes `docker compose down -v`: elimina los datos.

Consulta la IP de la red local del servidor:

```bash
hostname -I
```

Usa la IP de su conexión Ethernet o Wi-Fi, por ejemplo `192.168.1.100`. Si aparece más de una dirección, selecciona la que corresponda a la misma red que el PC cliente. Si tienes firewall configurado, permite conexiones desde los clientes al puerto TCP 5433.

## 2. Conectar el PC cliente por la red local

En el cliente, dentro del proyecto:

```bash
uv sync
uv run python main.py
```

Abre **Configuración → Base de datos**. Si la conexión anterior falla, la aplicación muestra directamente el formulario de conexión.

Completa estos campos:

- Ubicación: **PostgreSQL en servidor**.
- Servidor: IP del PC servidor, por ejemplo `192.168.20.237`.
- Puerto: **5433**.
- Base de datos: **pqm**.
- Usuario: **pqm_app**.
- Contraseña: la asignada a `pqm_app` en PostgreSQL; inicialmente se genera en `secrets/app_password.txt` del servidor.
- Conexión: **Red local (sin TLS)**.

Pulsa **Probar conexión**. Esta prueba comprueba acceso y autenticación sin cambiar el esquema ni trasladar datos. Después pulsa **Guardar conexión** y vuelve a abrir la aplicación. En el formulario de recuperación el botón **Guardar y conectar** reintenta inmediatamente.

La IP debe ser la del **PC servidor**, no `127.0.0.1`, que en el cliente se refiere al propio cliente. La conexión es directa por la red local. Las contraseñas con caracteres especiales se escriben tal cual en el campo; no necesitas construir ni codificar una URL.

La configuración se guarda por equipo en `database_connection.json`, dentro de la carpeta de datos de la aplicación. Se usa el llavero del sistema para la contraseña cuando está disponible; si no hay llavero, el archivo local la conserva, con permisos 0600 en Linux. La conexión no se guarda en `app_settings` de PostgreSQL, para poder corregirla aunque el servidor esté desconectado. Los respaldos de inspecciones no copian esta configuración del cliente.

La configuración guardada desde la aplicación tiene prioridad sobre `.env` y las variables de entorno. El `.env` anterior se carga para completar los campos si todavía no hay una configuración guardada. Puedes conservarlo como configuración inicial, pero ya no necesitas editarlo. Los comandos `database.manage` también usan lo guardado desde la app.

Para volver a SQLite, selecciona **SQLite en este equipo**, guarda y vuelve a abrir la aplicación. Cambiar de destino no traslada ni sincroniza los registros automáticamente.

## 3. Trasladar tus datos actuales

Cierra todas las instancias de la aplicación durante la migración. Antes de configurar PostgreSQL, usa **Configuración → Crear respaldo ZIP** para respaldar SQLite y sus archivos. Conserva la carpeta local completa.

Con el servidor encendido y la conexión PostgreSQL guardada desde la aplicación, ejecuta en tu equipo:

```bash
PYTHONPATH=src uv run python -m pqm_quality_manager.database.manage migrate-sqlite
```

El origen predeterminado es `~/.local/share/Ingelean/PQMQualityManager/pqm_quality_manager.sqlite3` en Linux, o la carpeta de datos configurada por `XDG_DATA_HOME` / `APPDATA`. Para otro origen:

```bash
PYTHONPATH=src uv run python -m pqm_quality_manager.database.manage migrate-sqlite \
  --source /ruta/copia/pqm_quality_manager.sqlite3 \
  --files-dir /ruta/copia
```

`--files-dir` debe contener `photos/` y `reports/` con sus rutas originales. La herramienta copia registros con sus identificadores, fechas, auditorías, configuración SMTP y checkpoints previos; incorpora originales y PDF a la base y crea un checkpoint de importación por inspección. Lee SQLite en modo de solo lectura. Si falta un archivo o hay un error, revierte la copia de datos. El destino debe estar vacío: no mezcla bases ni sobrescribe datos existentes. Una segunda ejecución tras una migración exitosa se rechaza. El esquema puede permanecer creado tras un intento fallido.

Las contraseñas SMTP están en el llavero del equipo, no se transfieren con la base. Configúralas en cada equipo que envíe informes. Si empiezas sin datos anteriores, prepara solo el esquema:

```bash
PYTHONPATH=src uv run python -m pqm_quality_manager.database.manage init
```

Abre la aplicación:

```bash
uv run python main.py
```

Comprueba en Configuración que indique **PostgreSQL en servidor**. Abre una inspección, modifica un campo, espera el mensaje **Avance guardado**, cierra y vuelve a abrir. Comprueba también una foto y un PDF.

## 4. Guardado de avances

El editor guarda los datos generales y la evidencia seleccionada después de 1,5 segundos sin cambios. También intenta guardar antes de cambiar de evidencia, cerrar, generar un borrador o cambiar el estado. Los botones Guardar permiten reintentar. Cada operación confirmada crea su checkpoint en la misma transacción que los datos que describe. Agregar/quitar fotos y generar PDF también crea checkpoints. Si cambias datos generales y evidencia, se confirman como dos operaciones y dos checkpoints.

**Ver checkpoints** muestra las últimas 100 instantáneas, con fecha, motivo y contenido. Se conservan todas las instantáneas en la base; no se aplica una limpieza automática.

El guardado valida los mismos requisitos de antes: por ejemplo, “No aplica” requiere justificación. Si hay un error de validación o conexión, el editor avisa y conserva el texto en pantalla, y bloquea el cambio de evidencia/cierre hasta poder guardarlo. Corrige el campo o restablece la conexión con el servidor y pulsa Guardar. No hay cola de trabajo sin conexión: cerrar el proceso por la fuerza pierde lo que todavía no se confirmó. El formulario de una inspección nueva se guarda al pulsar Guardar; el autoguardado empieza después de crearla.

Las consultas y escrituras siguen siendo síncronas: una red lenta puede pausar brevemente la interfaz. Esta versión comparte la base pero no resuelve ediciones simultáneas de la misma inspección; coordina un editor por inspección para evitar sobrescribir el trabajo de otra persona. La conexión directa utiliza una cuenta de base de datos: la aprobación sigue basada en el nombre declarado, no hay autenticación individual ni permisos por persona.

## 5. Respaldar y restaurar PostgreSQL

Los checkpoints recuperan contexto histórico de la inspección; el respaldo permite recuperar el servidor completo. En el servidor:

```bash
cd ~/pqm-postgres
mkdir -p backups
chmod 700 backups
docker compose exec -T db pg_dump -U postgres -d pqm -Fc --no-owner --no-acl > backups/pqm_$(date +%Y%m%d_%H%M%S).dump
```

Verifica el código de salida antes de dar el respaldo por válido. Programa este comando diariamente con tu sistema de tareas y conserva copias fuera del servidor. El dump incluye fotos, PDF y checkpoints. Conserva también las credenciales administrativas por separado. Ensaya restauraciones periódicas.

Para ensayar una restauración en **otra base vacía**, con todos los clientes cerrados:

```bash
docker compose exec db createdb -U postgres -O pqm_app pqm_restored
docker compose exec -T db pg_restore -U postgres --role=pqm_app -d pqm_restored \
  --no-owner --no-acl --exit-on-error --single-transaction < backups/ARCHIVO.dump
```

Apunta temporalmente la aplicación a `/pqm_restored` para validar inspecciones, archivos e historial antes de decidir el cambio definitivo. Esta operación no reemplaza la base `pqm`.

**Crear respaldo ZIP** desde la aplicación ejecuta `pg_dump` cuando usa PostgreSQL; requiere instalar en el equipo un cliente PostgreSQL de la misma versión del servidor. El ZIP contiene `database/postgresql.dump` y la caché local de fotos/PDF. El dump ya incluye todos los archivos guardados en la base, aunque no estén en esa caché. La restauración PostgreSQL desde la interfaz se rechaza con una indicación para realizarla en el servidor. Los ZIP SQLite siguen funcionando en modo SQLite.

## Referencias

- Imagen oficial y secretos: https://github.com/docker-library/docs/blob/master/postgres/content.md
- Respaldos y restauración: https://www.postgresql.org/docs/17/backup-dump.html
