"""Run with PYTHONPATH=src python -m pqm_quality_manager.database.manage."""
import argparse
from pathlib import Path
from sqlalchemy import create_engine, inspect, select, text, func
from sqlalchemy.orm import Session
from sqlalchemy.engine import URL
from pqm_quality_manager.config.settings import DB_PATH, DATA_DIR
from pqm_quality_manager.database.engine import make_engine
from pqm_quality_manager.database.models import Base, Inspection, EvidenceImage, Report, StoredFile
from pqm_quality_manager.services.checkpoint_service import checkpoint
from pqm_quality_manager.services.file_storage import store


def migrate_sqlite(source_path, destination, files_dir):
    """Copy into an empty destination in one transaction. Never modify the source."""
    source_path = Path(source_path).resolve()
    if not source_path.is_file():
        raise ValueError("No existe la base SQLite de origen.")
    source = create_engine(URL.create("sqlite", database=f"{source_path.as_uri()}?mode=ro", query={"uri": "true"}))
    counts = {}
    try:
        with source.connect() as src, destination.begin() as dst:
            src.exec_driver_sql("BEGIN")
            tables = Base.metadata.sorted_tables
            if destination.dialect.name == "postgresql":
                names = ", ".join(destination.dialect.identifier_preparer.quote(t.name) for t in tables)
                dst.execute(text(f"LOCK TABLE {names} IN EXCLUSIVE MODE"))
            if any(dst.scalar(select(func.count()).select_from(table)) for table in tables):
                raise ValueError("El destino debe estar vacío; no se mezclarán ni sobrescribirán registros.")
            available = set(inspect(src).get_table_names())
            if "inspections" not in available:
                raise ValueError("El origen no contiene el esquema de inspecciones PQM.")
            for table in tables:
                if table.name not in available:
                    continue
                count = 0
                result = src.execute(select(table))
                while rows := result.mappings().fetchmany(100):
                    dst.execute(table.insert(), [dict(row) for row in rows])
                    count += len(rows)
                counts[table.name] = count
            if destination.dialect.name == "postgresql":
                for table in tables:
                    pk = list(table.primary_key.columns)
                    if len(pk) == 1 and pk[0].name == "id":
                        sequence = dst.scalar(text("SELECT pg_get_serial_sequence(:table, 'id')"), {"table": table.name})
                        if sequence:
                            highest = dst.scalar(select(func.max(table.c.id)))
                            dst.execute(text("SELECT setval(CAST(:sequence AS regclass), :value, :called)"),
                                        {"sequence": sequence, "value": highest or 1, "called": highest is not None})
            with Session(bind=dst) as session:
                # Upload originals, not just workstation-specific paths. Fail atomically if missing.
                paths = list(session.scalars(select(EvidenceImage.relative_path)))
                paths += list(session.scalars(select(Report.path)))
                files_dir = Path(files_dir).resolve()
                for relative in set(paths):
                    if session.get(StoredFile, relative) is not None:
                        continue
                    local = (files_dir / relative).resolve()
                    if files_dir not in local.parents or not local.is_file():
                        raise ValueError("Falta una foto o PDF del origen. Restablezca los archivos antes de migrar.")
                    store(session, relative, local)
                for item in session.scalars(select(Inspection)):
                    checkpoint(session, item, "Importación desde SQLite")
                session.flush()
                # Commit remains owned by the outer transaction.
    finally:
        source.dispose()
    return counts


def main():
    parser = argparse.ArgumentParser(description="Conexión y migración de PQM")
    parser.add_argument("command", choices=("check", "init", "migrate-sqlite"))
    parser.add_argument("--source", type=Path, default=DB_PATH)
    parser.add_argument("--files-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    target = None
    try:
        target = make_engine(initialize=args.command != "check")
        if args.command == "check":
            with target.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Conexión correcta:", target.dialect.name)
        elif args.command == "init":
            print("Esquema preparado:", target.dialect.name)
        else:
            if target.dialect.name != "postgresql":
                raise ValueError("Configure el destino PostgreSQL en Configuración de la aplicación antes de migrar.")
            counts = migrate_sqlite(args.source, target, args.files_dir)
            print("Migración completada; origen intacto. Registros copiados:", counts)
        return 0
    except ValueError as exc:
        print(str(exc))
        return 1
    except Exception:
        print("Operación fallida. Revise conexión, permisos, versión del esquema y archivos. No se muestran credenciales.")
        return 1
    finally:
        if target is not None:
            target.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
