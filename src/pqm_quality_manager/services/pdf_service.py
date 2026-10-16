from pathlib import Path
from uuid import uuid4
from io import BytesIO
from hashlib import sha256
from pypdf import PdfReader
import re
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as PDFImage, KeepTogether, PageBreak
from PIL import Image as PILImage, ImageOps
from sqlalchemy import select, func
from pqm_quality_manager.config.settings import REPORT_DIR, DATA_DIR
from pqm_quality_manager.database.engine import SessionLocal
from pqm_quality_manager.database.models import Inspection, Report
from pqm_quality_manager.services.image_service import ImageService
from pqm_quality_manager.services.inspection_service import InspectionError
from pqm_quality_manager.services.file_storage import store, materialize
from pqm_quality_manager.services.checkpoint_service import checkpoint
from pqm_quality_manager.services.report_template import apply_template, template_signature, LEFT_MARGIN, RIGHT_MARGIN, TOP_MARGIN, BOTTOM_MARGIN

class PDFReportService:
    def latest_path(self, inspection_id):
        """Open the last saved content with current branding, keeping originals immutable."""
        with SessionLocal() as session:
            report = session.scalar(select(Report).where(Report.inspection_id == inspection_id)
                                    .order_by(Report.version.desc(), Report.id.desc()))
            if report is None:
                return None
            source = materialize(session, report.path, DATA_DIR)
        if not source.is_file():
            raise InspectionError("No se encuentra el archivo del último informe guardado.")
        signature = template_signature()
        reader = PdfReader(source)
        if reader.metadata and reader.metadata.get("/PQMTemplate") == signature:
            return source
        key = sha256(source.read_bytes() + signature.encode()).hexdigest()
        preview_dir = REPORT_DIR / "previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview = preview_dir / f"SIG_{key}.pdf"
        if not preview.exists():
            temporary = preview_dir / f".{uuid4().hex}.tmp"
            try:
                apply_template(source, temporary, fit_existing=True)
                temporary.replace(preview)
            finally:
                temporary.unlink(missing_ok=True)
        return preview

    def generate(self, inspection_id: int, report_type="BORRADOR") -> Path:
        if report_type not in {"BORRADOR", "FINAL", "HISTORICO"}: raise ValueError("Tipo de informe inválido")
        with SessionLocal() as s:
            item = s.scalar(select(Inspection).where(Inspection.id == inspection_id, Inspection.deleted.is_(False)))
            if not item: raise InspectionError("No se encontró la inspección.")
            if report_type == "FINAL" and item.status not in {"APROBADA", "CERRADA"}:
                raise InspectionError("El PDF final solo se genera después de aprobar la inspección.")
            _ = [(e.images[:]) for e in item.evidences]
            version = (s.scalar(select(func.max(Report.version)).where(Report.inspection_id == item.id)) or 0) + 1
            # Snapshot only; approved copies are immutable files and are never overwritten.
            title_num, company, act, inspection_date = item.pqm_number, item.company, item.act_number, item.inspection_date
            author, reviewer, status, observations, conclusion = item.author, item.reviewer, item.status, item.observations, item.conclusion
            groups = []
            for ev in item.evidences:
                image_items = [(ImageService.absolute(im.relative_path), im.original_name) for im in ev.images]
                groups.append((ev.code, ev.category, ev.title, ev.status, ev.measured_value, ev.unit, ev.observations, ev.na_reason, image_items))
            safe_number = re.sub(r"[^A-Za-z0-9._-]+", "_", title_num).strip("._") or "sin_numero"
            out = REPORT_DIR / f"PQM_{safe_number}_{report_type}_v{version}_{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:12]}.pdf"
            report_values = (item.id, version, report_type, out.relative_to(DATA_DIR).as_posix(), report_type == "FINAL")
        self._render(out, title_num, company, act, inspection_date, author, reviewer, status, observations, conclusion, groups, report_type, version)
        with SessionLocal() as s:
            item = s.get(Inspection, inspection_id)
            item.reports.append(Report(inspection_id=report_values[0], version=report_values[1], report_type=report_values[2], path=report_values[3], immutable=report_values[4]))
            store(s, report_values[3], out)
            checkpoint(s, item, "Informe PDF generado")
            s.commit()
        return out

    def _render(self, path, pqm, company, act, inspection_date, author, reviewer, status, general_obs, conclusion, groups, report_type, version):
        content = BytesIO()
        doc = SimpleDocTemplate(content, pagesize=A4, rightMargin=RIGHT_MARGIN, leftMargin=LEFT_MARGIN, topMargin=TOP_MARGIN, bottomMargin=BOTTOM_MARGIN, title=f"Informe PQM {pqm}", author="INGELEAN S.A.S.")
        styles = getSampleStyleSheet()
        for style in styles.byName.values():
            if not isinstance(style, ParagraphStyle):
                continue
            style.fontName = "Helvetica-Bold" if "Bold" in style.fontName else "Helvetica"
            style.textColor = colors.black
        styles["BodyText"].fontSize = 11
        styles["BodyText"].leading = 11 * 1.2 * 1.09
        styles["BodyText"].spaceAfter = 3.3
        styles["Heading2"].fontName = "Helvetica-Bold"
        styles["Heading2"].fontSize = 13
        styles["Heading2"].leading = 16
        styles.add(ParagraphStyle(name="PQMTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                                  textColor=colors.black, fontSize=20, leading=24, spaceAfter=14))
        styles.add(ParagraphStyle(name="PQMSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
                                  textColor=colors.black, fontSize=13, leading=16, spaceBefore=12, spaceAfter=5))
        styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=12.4))
        story = [Paragraph("INFORME DE INSPECCIÓN Y ENTREGA DE TABLERO PQM", styles["PQMTitle"])]
        if report_type == "BORRADOR": story.append(Paragraph("<b>DOCUMENTO PRELIMINAR — BORRADOR</b>", styles["Heading2"]))
        story += [Spacer(1, 5), self._table([["Registro PQM", pqm, "Acta", act], ["Fecha", inspection_date.strftime("%Y-%m-%d"), "Estado", status], ["Empresa", company, "Versión", str(version)]], [31*mm, 49*mm, 22*mm, 60*mm]), Spacer(1, 8), Paragraph("Información general", styles["PQMSection"]), Paragraph(f"<b>Elaborado por:</b> {self._esc(author)} &nbsp;&nbsp; <b>Revisado por:</b> {self._esc(reviewer or 'Pendiente')}", styles["BodyText"])]
        if general_obs: story.append(Paragraph(f"<b>Observaciones generales:</b> {self._esc(general_obs)}", styles["BodyText"]))
        categories = []
        for row in groups:
            if row[1] not in categories:
                categories.append(row[1]); story.append(Paragraph(self._esc(row[1]), styles["PQMSection"]))
            code, category, title, state, value, unit, obs, na, images = row
            story.append(Paragraph(f"<b>{self._esc(code)} — {self._esc(title)}</b> &nbsp; [{self._esc(state)}]", styles["BodyText"]))
            if value: story.append(Paragraph(f"Medición: {self._esc(value)} {self._esc(unit)}", styles["Small"]))
            if obs: story.append(Paragraph(f"Observaciones: {self._esc(obs)}", styles["Small"]))
            if na: story.append(Paragraph(f"Justificación No aplica: {self._esc(na)}", styles["Small"]))
            if images:
                cells = []
                for imgpath, original in images:
                    if not imgpath.exists():
                        cells.append(Paragraph(f"Imagen no disponible: {self._esc(original)}", styles["Small"]))
                    else:
                        try:
                            with PILImage.open(imgpath) as im:
                                im = ImageOps.exif_transpose(im).convert("RGB")
                                im.thumbnail((780, 520))
                                buffer = BytesIO(); im.save(buffer, "JPEG", quality=82); buffer.seek(0)
                            pic = PDFImage(buffer, width=doc.width/2-6*mm, height=55*mm, kind="proportional")
                            cells.append([pic, Paragraph(self._esc(original), styles["Small"])])
                        except Exception as exc:
                            cells.append(Paragraph(f"No se pudo incluir {self._esc(original)}: {self._esc(str(exc))}", styles["Small"]))
                for i in range(0, len(cells), 2):
                    rowcells = cells[i:i+2]
                    if len(rowcells) == 1: rowcells.append("")
                    story.append(Table([rowcells], colWidths=[doc.width/2, doc.width/2], style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"), ("LEFTPADDING",(0,0),(-1,-1),2), ("RIGHTPADDING",(0,0),(-1,-1),2)])))
            else: story.append(Paragraph("Sin fotografías adjuntas.", styles["Small"]))
            story.append(Spacer(1,5))
        counts = {k: sum(1 for g in groups if g[3] == k) for k in ("Conforme", "No conforme", "No aplica", "Pendiente")}
        story += [Paragraph("Resumen de inspección", styles["PQMSection"]), self._table([["Total evidencias", str(len(groups)), "Documentadas", str(sum(bool(g[8]) for g in groups))], ["Conformes", str(counts["Conforme"]), "No conformes", str(counts["No conforme"])], ["No aplican", str(counts["No aplica"]), "Pendientes", str(counts["Pendiente"])]], [35*mm, 30*mm, 35*mm, 62*mm])]
        if conclusion: story.append(Paragraph(f"<b>Conclusión técnica:</b> {self._esc(conclusion)}", styles["BodyText"]))
        story.append(Spacer(1, 16)); story.append(Paragraph(f"Elaborado por: {self._esc(author)} &nbsp;&nbsp;&nbsp; Revisado por: {self._esc(reviewer or 'Pendiente')}", styles["Small"]))
        doc.build(story)
        content.seek(0)
        apply_template(content, path)

    @staticmethod
    def _table(rows, widths):
        normal = ParagraphStyle("TableValue", fontName="Helvetica", fontSize=10, leading=13)
        bold = ParagraphStyle("TableLabel", parent=normal, fontName="Helvetica-Bold")
        wrapped = [[Paragraph(PDFReportService._esc(value), bold if col in (0, 2) else normal)
                    for col, value in enumerate(row)] for row in rows]
        t = Table(wrapped, colWidths=widths, repeatRows=0)
        t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.35,colors.black), ("BACKGROUND",(0,0),(0,-1),colors.Color(235/255,235/255,235/255)), ("BACKGROUND",(2,0),(2,-1),colors.Color(235/255,235/255,235/255)), ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"), ("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),10), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        return t

    @staticmethod
    def _esc(v):
        from xml.sax.saxutils import escape
        return escape(str(v or ""))
