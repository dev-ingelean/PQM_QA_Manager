import json
import os
import stat
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from pqm_quality_manager.config import database_connection as config
from pqm_quality_manager.database import engine as database


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "connection.json")
    monkeypatch.setattr(config, "DATABASE_URL", "")
    secrets = {}
    monkeypatch.setattr("keyring.set_password", lambda service, name, value: secrets.__setitem__(name, value))
    monkeypatch.setattr("keyring.get_password", lambda service, name: secrets.get(name))
    return secrets


def postgres():
    return config.ConnectionConfig(backend="postgresql", host="192.168.20.237", port=5433,
                                   database="pqm", username="pqm_app", password="p@ss:/#%word")


def test_settings_override_env_and_password_roundtrip_without_url_escaping(storage, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql+psycopg://old:old@old:5432/old")
    assert config.load_connection().host == "old"
    current = postgres()
    assert config.save_connection(current) == "keyring"
    payload = json.loads(config.CONFIG_PATH.read_text())
    assert "password" not in payload
    assert current.password not in config.CONFIG_PATH.read_text()
    loaded = config.load_connection()
    assert loaded.host == current.host
    assert loaded.url().password == current.password
    assert database.database_url().password == current.password
    assert config.load_connection(include_password=False).password == ""


def test_unavailable_keyring_uses_private_file_and_sqlite_can_override_env(storage, monkeypatch):
    def unavailable(*args):
        raise RuntimeError("No desktop keyring")
    monkeypatch.setattr("keyring.set_password", unavailable)
    current = postgres()
    assert config.save_connection(current) == "local"
    assert config.load_connection().password == current.password
    if os.name != "nt":
        assert stat.S_IMODE(config.CONFIG_PATH.stat().st_mode) == 0o600
    config.save_connection(config.ConnectionConfig())
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql://user:password@remote/pqm")
    assert config.load_connection().backend == "sqlite"
    assert "password" not in json.loads(config.CONFIG_PATH.read_text())


def test_atomic_write_failure_keeps_previous_settings(storage, monkeypatch):
    config.save_connection(postgres())
    original = config.CONFIG_PATH.read_bytes()
    def fail(*args):
        raise OSError("write failed")
    monkeypatch.setattr(config.os, "replace", fail)
    with pytest.raises(OSError):
        config.save_connection(config.ConnectionConfig())
    assert config.CONFIG_PATH.read_bytes() == original
    assert not list(config.CONFIG_PATH.parent.glob(".database-*"))


def test_failed_activation_keeps_current_engine_and_factory(storage, monkeypatch):
    current = database.engine
    factory_bind = database.SessionLocal.kw["bind"]
    candidate = MagicMock()
    monkeypatch.setattr(database, "make_engine", lambda **kwargs: candidate)
    def fail(*args):
        raise RuntimeError("failed connection")
    monkeypatch.setattr(database, "apply_migrations", fail)
    with pytest.raises(RuntimeError):
        database.configure_engine()
    assert database.engine is current
    assert database.SessionLocal.kw["bind"] is factory_bind
    candidate.dispose.assert_called_once()


def application():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_form_tests_connection_without_migrating_or_saving(storage, tmp_path):
    from PySide6.QtTest import QTest
    from pqm_quality_manager.ui.database_settings import DatabaseSettings
    from sqlalchemy import create_engine, inspect
    app = application()
    form = DatabaseSettings()
    # SELECT 1 opens an empty database but must not create business tables.
    form.initial.sqlite_path = str(tmp_path / "test.sqlite3")
    form.test_connection()
    for _ in range(200):
        QTest.qWait(10)
        if not form.testing:
            break
    assert not form.testing
    assert form.status.text() == "Conexión correcta."
    assert not config.CONFIG_PATH.exists()
    probe = create_engine(f"sqlite:///{form.initial.sqlite_path}")
    assert inspect(probe).get_table_names() == []
    probe.dispose()
    form.mode.setCurrentIndex(form.mode.findData("postgresql"))
    form.host.setText("192.168.20.237")
    form.password.setText("special@:/pass")
    form.save()
    assert config.load_connection().url().password == "special@:/pass"
    assert "vuelva a abrir" in form.status.text()
    form.deleteLater(); app.processEvents()


def test_recovery_form_available_with_broken_configuration(storage):
    from pqm_quality_manager.ui.database_settings import DatabaseConnectionDialog
    from PySide6.QtWidgets import QDialog
    app = application()
    config.CONFIG_PATH.write_text("bad json")
    dialog = DatabaseConnectionDialog(RuntimeError("bad connection"))
    dialog.form.host.setText("192.168.20.237")
    dialog.form.password.setText("replacement")
    dialog.form.save()
    assert dialog.result() == QDialog.Accepted
    assert config.load_connection().host == "192.168.20.237"
    dialog.deleteLater(); app.processEvents()


def test_connection_messages_do_not_leak_password(storage):
    error = RuntimeError('password authentication failed for user "pqm_app" secret=do-not-show')
    assert "do-not-show" not in config.connection_error(error)
    assert "contraseña" in config.connection_error(error)


def test_saved_connection_rebinds_services_and_settings_page(storage, tmp_path):
    from datetime import date
    from pqm_quality_manager.services.inspection_service import InspectionService
    from pqm_quality_manager.ui.main_window import MainWindow
    from pqm_quality_manager.ui.database_settings import DatabaseSettings
    from pqm_quality_manager.services import backup_service
    app = application()
    previous = database.engine
    previous_bind = database.SessionLocal.kw["bind"]
    active = None
    window = None
    try:
        config.save_connection(config.ConnectionConfig(sqlite_path=str(tmp_path / "active.sqlite3")))
        active = database.configure_engine()
        assert database.SessionLocal.kw["bind"] is active
        assert backup_service.database_engine.engine is active
        service = InspectionService()
        iid = service.create(date.today(), "Conexión guardada", "PQM-CONFIG", "ACT", "QA")
        assert service.get(iid).company == "Conexión guardada"
        window = MainWindow()
        window.navigate("settings")
        assert window.findChild(DatabaseSettings) is not None
    finally:
        if window is not None:
            window.deleteLater(); app.processEvents()
        database.engine = previous
        database.SessionLocal.configure(bind=previous_bind)
        if active is not None:
            active.dispose()
