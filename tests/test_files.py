from datetime import date
from hashlib import sha256
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from PIL import Image
from pqm_quality_manager.database.models import Base, InspectionEvidence, EvidenceImage, Report
from pqm_quality_manager.services.inspection_service import InspectionService
from pqm_quality_manager.services.image_service import ImageService
from pqm_quality_manager.services.pdf_service import PDFReportService
from pqm_quality_manager.services.backup_service import BackupService
import pqm_quality_manager.services.inspection_service as inspection_module
import pqm_quality_manager.services.image_service as image_module
import pqm_quality_manager.services.pdf_service as pdf_module
import pqm_quality_manager.services.backup_service as backup_module

def test_photograph_original_pdf_and_backup_roundtrip(tmp_path, monkeypatch):
    data=tmp_path/"data";photos=data/"photos";thumbs=data/"thumbnails";reports=data/"reports"
    for p in (data,photos,thumbs,reports):p.mkdir(parents=True,exist_ok=True)
    db=data/"pqm.sqlite3";engine=create_engine(f"sqlite:///{db}");Base.metadata.create_all(engine);factory=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(inspection_module,"SessionLocal",factory);monkeypatch.setattr(image_module,"SessionLocal",factory);monkeypatch.setattr(pdf_module,"SessionLocal",factory)
    monkeypatch.setattr(image_module,"DATA_DIR",data);monkeypatch.setattr(image_module,"PHOTO_DIR",photos);monkeypatch.setattr(image_module,"THUMB_DIR",thumbs)
    monkeypatch.setattr(pdf_module,"DATA_DIR",data);monkeypatch.setattr(pdf_module,"REPORT_DIR",reports)
    monkeypatch.setattr(backup_module,"DATA_DIR",data);monkeypatch.setattr(backup_module,"DB_PATH",db)
    iid=InspectionService().create(date.today(),"Cliente","PQM-FILE","A-1","QA")
    with factory() as s:eid=s.scalar(select(InspectionEvidence.id).where(InspectionEvidence.inspection_id==iid))
    original=tmp_path/"evidence.png";Image.new("RGB",(1200,800),(20,80,140)).save(original)
    original_bytes=original.read_bytes();stored=ImageService().add(eid,[original])[0]
    assert stored.read_bytes()==original_bytes
    with factory() as s:
        image=s.scalar(select(EvidenceImage).where(EvidenceImage.evidence_id==eid))
        assert image.sha256==sha256(original_bytes).hexdigest()
        image_id=image.id
    evidence=InspectionService().evidence(eid)
    assert ImageService().thumbnail_path(evidence.images[0]).exists()
    pdf=PDFReportService().generate(iid,"BORRADOR")
    assert pdf.exists() and pdf.stat().st_size>1000
    with factory() as s:assert s.scalar(select(Report).where(Report.inspection_id==iid)) is not None
    backup=BackupService().create(tmp_path/"backup.zip")
    with sqlite3.connect(db) as conn:conn.execute("DELETE FROM inspections");conn.commit()
    BackupService().restore(backup)
    with sqlite3.connect(db) as conn:assert conn.execute("SELECT COUNT(*) FROM inspections").fetchone()[0]==1

