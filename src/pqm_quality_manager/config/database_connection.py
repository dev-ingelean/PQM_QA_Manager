"""Per-workstation connection settings, independent of the database being configured."""
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from sqlalchemy.engine import URL, make_url
from pqm_quality_manager.config.settings import DATA_DIR, DB_PATH, DATABASE_URL

CONFIG_PATH = DATA_DIR / "database_connection.json"
KEYRING_SERVICE = "PQM Quality Manager Database"


class ConnectionConfigError(ValueError):
    pass


@dataclass
class ConnectionConfig:
    backend: str = "sqlite"
    host: str = ""
    port: int = 5433
    database: str = "pqm"
    username: str = "pqm_app"
    password: str = field(default="", repr=False)
    sqlite_path: str = str(DB_PATH)
    options: dict = field(default_factory=lambda: {"sslmode": "disable"})

    def url(self):
        if self.backend == "sqlite":
            return URL.create("sqlite", database=self.sqlite_path)
        if self.backend != "postgresql":
            raise ConnectionConfigError("Seleccione SQLite o PostgreSQL.")
        if not all(value.strip() for value in (self.host, self.database, self.username)):
            raise ConnectionConfigError("Complete servidor, base de datos y usuario.")
        if not 1 <= self.port <= 65535:
            raise ConnectionConfigError("El puerto debe estar entre 1 y 65535.")
        return URL.create("postgresql+psycopg", host=self.host.strip(), port=self.port,
                          database=self.database.strip(), username=self.username.strip(),
                          password=self.password, query=self.options)

    @classmethod
    def from_url(cls, value):
        try:
            url = make_url(value)
            if url.get_backend_name() == "sqlite":
                return cls(sqlite_path=url.database or str(DB_PATH))
            if url.get_backend_name() not in {"postgresql", "postgres"}:
                raise ValueError()
            return cls(backend="postgresql", host=url.host or "", port=url.port or 5432,
                       database=url.database or "", username=url.username or "",
                       password=url.password or "", options=dict(url.query))
        except Exception:
            raise ConnectionConfigError("La conexión anterior no tiene un formato válido. Complete los campos de conexión.") from None


def load_connection(*, include_password=True):
    if not CONFIG_PATH.exists():
        return ConnectionConfig.from_url(DATABASE_URL) if DATABASE_URL else ConnectionConfig()
    try:
        values = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        password_ref = values.pop("password_ref", None)
        if password_ref and include_password:
            import keyring
            password = keyring.get_password(KEYRING_SERVICE, password_ref)
            if password is None:
                raise ValueError()
            values["password"] = password
        if not include_password:
            values.pop("password", None)
        config = ConnectionConfig(**values)
        config.url()
        return config
    except Exception:
        raise ConnectionConfigError("No se pudo leer la configuración o recuperar la contraseña. Vuelva a introducir los datos de conexión.") from None


def save_connection(config):
    config.url()
    values = asdict(config)
    password_ref = None
    if config.backend == "postgresql":
        try:
            import keyring
            password_ref = uuid4().hex
            keyring.set_password(KEYRING_SERVICE, password_ref, config.password)
            values.pop("password")
            values["password_ref"] = password_ref
        except Exception:
            # No desktop keyring (e.g. minimal Linux): private per-user file, mode 0600.
            password_ref = None
    else:
        values.pop("password")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".database-", dir=CONFIG_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(values, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, CONFIG_PATH)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return "keyring" if password_ref else "local"


def connection_error(error):
    """Useful messages without echoing driver strings, URLs or passwords."""
    if isinstance(error, ConnectionConfigError):
        return str(error)
    message = str(getattr(error, "orig", error)).lower()
    if "password authentication failed" in message:
        return "PostgreSQL rechazó el usuario o la contraseña. Compruebe que el usuario exista en el servidor."
    if "connection refused" in message:
        return "El servidor rechazó la conexión. Revise la IP, el puerto y que PostgreSQL esté iniciado."
    if "timeout" in message or "timed out" in message:
        return "El servidor no respondió. Revise la IP y la conexión a la red local."
    if "permission denied" in message or "insufficient privilege" in message:
        return "El usuario no tiene permisos suficientes para preparar la base de datos."
    if "does not exist" in message and "database" in message:
        return "La base de datos indicada no existe en el servidor."
    return "No se pudo conectar o preparar la base de datos. Revise servidor, puerto, base de datos, usuario y contraseña."
