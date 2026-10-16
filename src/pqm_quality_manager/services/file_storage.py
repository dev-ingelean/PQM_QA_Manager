"""Database-backed originals with a local cache for desktop viewers."""
from pathlib import Path
from pqm_quality_manager.database.models import StoredFile


def store(session, relative_path, source):
    content = Path(source).read_bytes()
    record = session.get(StoredFile, relative_path)
    if record is None:
        session.add(StoredFile(path=relative_path, content=content))
    elif record.content != content:
        raise ValueError("Ya existe un archivo diferente con la misma ruta.")


def materialize(session, relative_path, data_dir):
    path = (data_dir / relative_path).resolve()
    if data_dir.resolve() not in path.parents:
        raise ValueError("Ruta de archivo inválida")
    if not path.exists():
        record = session.get(StoredFile, relative_path)
        if record is not None:
            from uuid import uuid4
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{uuid4().hex}.tmp")
            try:
                temporary.write_bytes(record.content)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
    return path
