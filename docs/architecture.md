# Arquitectura

La interfaz Qt (`ui`) consume servicios de aplicación (`services`). Los servicios usan modelos SQLAlchemy y SQLite (`database`) y configuración/rutas independientes (`config`). Las fotos originales se guardan en archivos y la base contiene su ruta relativa, tamaño y SHA-256. El PDF se construye desde un conjunto de datos de inspección y no desde widgets.

El estado documental pertenece a Inspection; el estado de evaluación está en cada InspectionEvidence. Las transiciones y validaciones están centralizadas en `InspectionService`. Todo cambio relevante agrega `AuditLog`.
