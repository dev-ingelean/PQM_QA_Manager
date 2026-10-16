from datetime import date
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text, func
from sqlalchemy.orm import sessionmaker

from pqm_quality_manager.database.engine import make_engine, database_url
from pqm_quality_manager.database.manage import migrate_sqlite
from pqm_quality_manager.database.migrations import apply_migrations
from pqm_quality_manager.database.models import (
    Base, Inspection, InspectionEvidence, InspectionCheckpoint, StoredFile, EvidenceImage, Report,
)
from pqm_quality_manager.services.inspection_service import InspectionService, InspectionError
from pqm_quality_manager.services.image_service import ImageService
from pqm_quality_manager.services.pdf_service import PDFReportService


@pytest.fixture(params=["sqlite", "postgresql"])
def target(request, tmp_path):
    if request.param == "sqlite":
        engine = make_engine(tmp_path / "target.sqlite3")
        yield engine
        engine.dispose()
        return
    url = os.environ.get("PQM_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("Set PQM_TEST_POSTGRES_URL for an isolated PostgreSQL integration test")
    admin = create_engine(database_url(url))
    schema = "pqm_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(database_url(url), connect_args={"options": f"-csearch_path={schema}"})
    try:
        apply_migrations(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def use_services(monkeypatch, engine, data):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    for module in ("inspection_service", "image_service", "pdf_service"):
        monkeypatch.setattr(f"pqm_quality_manager.services.{module}.SessionLocal", factory)
    for module in ("image_service", "pdf_service"):
        monkeypatch.setattr(f"pqm_quality_manager.services.{module}.DATA_DIR", data)
    monkeypatch.setattr("pqm_quality_manager.services.image_service.PHOTO_DIR", data / "photos")
    monkeypatch.setattr("pqm_quality_manager.services.image_service.THUMB_DIR", data / "thumbnails")
    monkeypatch.setattr("pqm_quality_manager.services.pdf_service.REPORT_DIR", data / "reports")
    for folder in ("photos", "reports", "thumbnails"):
        (data / folder).mkdir(parents=True, exist_ok=True)
    return factory


def test_migration_checkpoints_originals_and_sequences(target, tmp_path, monkeypatch):
    from PIL import Image
    source_path = tmp_path / "source.sqlite3"
    source = make_engine(source_path)
    data = tmp_path / "source-files"
    factory = use_services(monkeypatch, source, data)
    service = InspectionService()
    iid = service.create(date.today(), "Cliente original", "PQM-IMPORT", "ACT-1", "QA")
    evidence = service.get(iid).evidences[0]
    service.save_evidence(evidence.id, status="No aplica", na_reason="No instalado")
    original = tmp_path / "original.png"
    Image.new("RGB", (120, 80), (20, 80, 140)).save(original)
    image_path = ImageService().add(evidence.id, [original])[0]
    report_path = PDFReportService().generate(iid)
    pdf_bytes = report_path.read_bytes()
    image_bytes = image_path.read_bytes()
    with factory() as session:
        old_count = session.scalar(select(func.count()).select_from(InspectionCheckpoint))
    migrate_sqlite(source_path, target, data)
    # Original source remains untouched.
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(InspectionCheckpoint)) == old_count
    factory = use_services(monkeypatch, target, tmp_path / "new-workstation")
    item = service.get(iid)
    assert item.company == "Cliente original"
    assert item.evidences[0].na_reason == "No instalado"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(StoredFile)) == 2
        checkpoints = list(session.scalars(select(InspectionCheckpoint).order_by(InspectionCheckpoint.id)))
        assert len(checkpoints) == old_count + 1
        assert json.loads(checkpoints[-1].snapshot)["evidences"][0]["na_reason"] == "No instalado"
        image = session.scalar(select(EvidenceImage))
        relative_image = image.relative_path
        report = session.scalar(select(Report))
        relative_pdf = report.path
    assert ImageService.absolute(relative_image).read_bytes() == image_bytes
    assert ImageService.absolute(relative_pdf).read_bytes() == pdf_bytes
    new_id = service.create(date.today(), "Nuevo", "PQM-NEW", "ACT-2", "QA")
    assert new_id > iid
    service.save_evidence(item.evidences[0].id, status="Conforme", observations="Nueva evaluación")
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(InspectionCheckpoint))
    with pytest.raises(InspectionError):
        service.save_evidence(item.evidences[0].id, status="No aplica")
    with factory() as session:
        assert session.get(InspectionEvidence, evidence.id).status == "Conforme"
        assert session.scalar(select(func.count()).select_from(InspectionCheckpoint)) == before
    with pytest.raises(ValueError, match="vacío"):
        migrate_sqlite(source_path, target, data)
    source.dispose()


def test_missing_original_rolls_back_entire_import(target, tmp_path, monkeypatch):
    source_path = tmp_path / "missing.sqlite3"
    source = make_engine(source_path)
    factory = use_services(monkeypatch, source, tmp_path / "data")
    iid = InspectionService().create(date.today(), "Cliente", "PQM-MISSING", "A", "QA")
    with factory() as session:
        eid = session.scalar(select(InspectionEvidence.id))
        session.add(EvidenceImage(evidence_id=eid, relative_path="photos/missing.png", original_name="missing.png", order=0, size_bytes=1, sha256="0"*64))
        session.commit()
    with pytest.raises(ValueError, match="Falta"):
        migrate_sqlite(source_path, target, tmp_path / "data")
    with target.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(Inspection)) == 0
        assert connection.scalar(select(func.count()).select_from(InspectionCheckpoint)) == 0
    source.dispose()


def test_existing_v1_database_upgrade_keeps_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'v1.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO schema_migrations(version) VALUES (1)"))
        for table in Base.metadata.sorted_tables:
            if table.name not in {"inspection_checkpoints", "stored_files"}:
                table.create(connection)
        connection.execute(text("INSERT INTO app_settings(key,value) VALUES ('kept','yes')"))
    apply_migrations(engine)
    apply_migrations(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT value FROM app_settings WHERE key='kept'")) == "yes"
        assert connection.scalar(text("SELECT MAX(version) FROM schema_migrations")) == 2
        connection.execute(select(InspectionCheckpoint))
    engine.dispose()


def test_editor_autosave_switch_and_failed_connection_keep_changes(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtTest import QTest
    from pqm_quality_manager.ui.main_window import InspectionEditor
    app = QApplication.instance() or QApplication([])
    engine = make_engine(tmp_path / "editor.sqlite3")
    factory = use_services(monkeypatch, engine, tmp_path / "editor-files")
    service = InspectionService()
    iid = service.create(date.today(), "Cliente", "PQM-UI", "A", "QA")
    parent = QMainWindow(); parent.service = service
    editor = InspectionEditor(parent, iid)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args))
    editor.company.setText("Cliente actualizado")
    QTest.qWait(1700)
    assert service.get(iid).company == "Cliente actualizado"
    entries = [editor.list.item(i) for i in range(editor.list.count()) if editor.list.item(i).data(Qt.UserRole)]
    editor.list.setCurrentItem(entries[0])
    editor.obs.setPlainText("Avance de evidencia")
    editor.list.setCurrentItem(entries[1])
    assert service.evidence(entries[0].data(Qt.UserRole)).observations == "Avance de evidencia"
    editor.obs.setPlainText("Avance sin conexión")
    real_save = service.save_evidence
    def unavailable(*args, **kwargs):
        raise ConnectionError("simulated disconnection")
    monkeypatch.setattr(service, "save_evidence", unavailable)
    editor.list.setCurrentItem(entries[2])
    assert editor.list.currentItem() is entries[1]
    assert editor.current == entries[1].data(Qt.UserRole)
    assert editor.obs.toPlainText() == "Avance sin conexión"
    event = QCloseEvent()
    editor.closeEvent(event)
    assert not event.isAccepted()
    assert messages
    monkeypatch.setattr(service, "save_evidence", real_save)
    assert editor.autosave()
    assert service.evidence(entries[1].data(Qt.UserRole)).observations == "Avance sin conexión"
    with factory() as session:
        count = session.scalar(select(func.count()).select_from(InspectionCheckpoint))
    assert editor.autosave()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(InspectionCheckpoint)) == count
    editor.autosave_timer.stop()
    editor.deleteLater(); parent.deleteLater(); app.processEvents()
    engine.dispose()
