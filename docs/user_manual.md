# Manual de usuario

1. Cree una inspección e ingrese fecha, empresa, registro PQM, acta y responsable.
2. Abra una evidencia del panel izquierdo. Agregue las fotografías originales, complete medición/observaciones y seleccione su evaluación.
3. Espere el mensaje «Avance guardado» después de editar (1,5 segundos de pausa). Los botones «Guardar evidencia» y «Guardar datos generales» permiten guardar inmediatamente o reintentar. Si falla la conexión o falta un dato, el editor conserva el texto y muestra el aviso. Consulte «Ver checkpoints» para revisar las instantáneas guardadas.
4. Envíe a revisión cuando las 35 evidencias tengan evaluación, las aplicables tengan fotografía y cada «No aplica» tenga justificación.
5. Un responsable puede aprobar o rechazar; una aprobada puede cerrarse. El PDF final se habilita después de aprobar.
6. En Historial puede buscar, filtrar, reabrir, duplicar, generar borrador o eliminar lógicamente.
7. En Configuración pruebe SMTP antes de remitir archivos y cree respaldos periódicos.

Para centralizar datos, fotos y PDF en un servidor, consulte [la guía de PostgreSQL](postgresql.md).

En **Configuración → Base de datos**, seleccione PostgreSQL y complete servidor, puerto, base, usuario y contraseña. Pulse **Probar conexión**, después **Guardar conexión** y vuelva a abrir la aplicación. Si no puede conectar al iniciar, el mismo formulario permite corregirla.

La pantalla de Configuración se organiza en tres pestañas: **Base de datos**, **Correo** y **Respaldos**. Cada una tiene sus propios campos y botones; el indicador superior muestra la base utilizada en la sesión actual.

El panel principal muestra tarjetas de resumen que se redistribuyen al cambiar el ancho de la ventana. En Inspecciones, use los filtros de búsqueda y estado y el menú **Informes** para los PDF. El editor separa **Datos generales** y **Evidencias**, con **Evaluación** y **Fotografías** juntas en la misma vista. **Guardar avance** guarda los cambios; **Documentos** agrupa la generación y envío de informes, y **Cambiar estado** contiene revisión, aprobación, rechazo y cierre.
