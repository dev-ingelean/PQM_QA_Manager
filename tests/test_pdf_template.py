from datetime import date
import pytest
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4

from pqm_quality_manager.config.evidence_catalog import EVIDENCE_CATALOG
from pqm_quality_manager.services.pdf_service import PDFReportService
from pqm_quality_manager.services.report_template import sig_values, ASSET_DIR
from PIL import Image


@pytest.mark.parametrize("report_type", ["BORRADOR", "FINAL", "HISTORICO"])
def test_sig_header_background_and_page_count_on_every_page(tmp_path, report_type):
    groups = [(e.code, e.category, e.title, "Conforme", "110", "V", "Verificación realizada. "*8, "", [])
              for e in EVIDENCE_CATALOG]
    output = tmp_path / f"{report_type}.pdf"
    PDFReportService()._render(output, "PQM-2026-001", "Empresa de prueba & Asociados "*6,
        "ACT-01", date(2026, 10, 16), "Técnico de Calidad", "Revisor",
        "APROBADA" if report_type == "FINAL" else "EN_ELABORACION", "Observaciones <con caracteres especiales>",
        "Verificaciones realizadas", groups, report_type, 2)
    reader = PdfReader(output)
    assert len(reader.pages) > 1
    values = sig_values()
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        from pypdf.generic import ContentStream
        for operands, operator in ContentStream(page.get_contents(), reader).operations:
            if operator == b"rg":
                assert float(operands[0]) == pytest.approx(float(operands[1]))
                assert float(operands[1]) == pytest.approx(float(operands[2]))
        for font in page["/Resources"].get("/Font", {}).values():
            assert str(font.get_object().get("/BaseFont", "")).startswith("/Helvetica")
        assert "SISTEMA INTEGRADO DE GESTIÓN (SIG)" in text
        assert "TIPO DE DOCUMENTO: INFORME DE INSPECCIÓN PQM" in " ".join(text.split())
        assert values["CodigoDocumento"] in text
        assert values["VersionDocumento"] in text
        assert values["FechaDocumento"] in text
        assert f"{number} de {len(reader.pages)}" in text
        assert "GUÍA DE USUARIO" not in text
        assert tuple(float(value) for value in page.mediabox[2:]) == pytest.approx(A4)
        assert any(image.image.size == (1236, 1600) for image in page.images)
        with Image.open(ASSET_DIR / "logo-ingelean.png") as logo:
            assert any(image.image.size == logo.size for image in page.images)
    text = " ".join(" ".join(page.extract_text().split()) for page in reader.pages)
    assert "Empresa de prueba & Asociados" in text
    assert "Observaciones <con caracteres especiales>" in text
    assert "Resumen de inspección" in text
    for evidence in EVIDENCE_CATALOG:
        assert evidence.code in text
    assert ("DOCUMENTO PRELIMINAR" in text) == (report_type == "BORRADOR")


def test_view_latest_keeps_saved_content_and_immutable_original(tmp_path, monkeypatch):
    from reportlab.pdfgen.canvas import Canvas
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import sessionmaker
    from pqm_quality_manager.database.models import Base, Inspection, Report
    import pqm_quality_manager.services.pdf_service as module
    from pqm_quality_manager.services.report_template import template_signature
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(module, "REPORT_DIR", tmp_path / "reports")
    reports = tmp_path / "reports"; reports.mkdir()
    original = reports / "original-final.pdf"
    canvas = Canvas(str(original), pagesize=A4)
    canvas.setFont("Times-Roman", 11)
    canvas.setFillColorRGB(.1, .3, .6)
    canvas.drawString(50, 700, "Contenido aprobado original")
    canvas.save()
    original_bytes = original.read_bytes()
    with factory() as session:
        item = Inspection(uuid="test-report", inspection_date=date.today(), company="Datos actuales distintos",
                          pqm_number="PQM-TEST", act_number="ACT", author="QA")
        session.add(item); session.flush()
        iid = item.id
        session.add(Report(inspection_id=iid, version=1, report_type="FINAL", path="reports/original-final.pdf", immutable=True))
        session.commit()
    service = PDFReportService()
    path = service.latest_path(iid)
    assert path != original
    assert original.read_bytes() == original_bytes
    text = PdfReader(path).pages[0].extract_text()
    preview_reader = PdfReader(path)
    fonts = [font.get_object().get("/BaseFont") for font in preview_reader.pages[0]["/Resources"]["/Font"].values()]
    assert "/Times-Roman" not in fonts
    assert "/Helvetica" in fonts
    assert "Contenido aprobado original" in text
    assert "SISTEMA INTEGRADO DE GESTIÓN (SIG)" in text
    assert "Datos actuales distintos" not in text
    assert service.latest_path(iid) == path
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 1
        assert session.scalar(select(Report)).immutable
    # Once saved with the current template, open the original without restamping it.
    new_path = reports / "current.pdf"; new_path.write_bytes(path.read_bytes())
    with factory() as session:
        session.add(Report(inspection_id=iid, version=2, report_type="FINAL", path="reports/current.pdf", immutable=True))
        session.commit()
    assert PdfReader(new_path).metadata["/PQMTemplate"] == template_signature()
    assert service.latest_path(iid) == new_path
    assert service.latest_path(9999) is None
    engine.dispose()
