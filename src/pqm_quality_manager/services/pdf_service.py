from pathlib import Path
from uuid import uuid4
from io import BytesIO
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
from pqm_quality_manager.services.file_storage import store
from pqm_quality_manager.services.checkpoint_service import checkpoint

class PDFReportService:
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
        doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=17*mm, bottomMargin=17*mm, title=f"Informe PQM {pqm}", author="INGELEAN S.A.S.")
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="PQMTitle", parent=styles["Title"], textColor=colors.HexColor("#12365a"), fontSize=19, leading=24, spaceAfter=6))
        styles.add(ParagraphStyle(name="PQMSection", parent=styles["Heading2"], textColor=colors.HexColor("#145b83"), fontSize=12, leading=15, spaceBefore=9, spaceAfter=5))
        styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8.5, leading=11))
        story = [Paragraph("INGELEAN S.A.S.", styles["PQMTitle"]), Paragraph("INFORME DE INSPECCIÓN Y ENTREGA DE TABLERO PQM", styles["Heading2"])]
        if report_type == "BORRADOR": story.append(Paragraph("<b>DOCUMENTO PRELIMINAR — BORRADOR</b>", styles["Heading2"]))
        story += [Spacer(1, 5), self._table([["Registro PQM", pqm, "Acta", act], ["Fecha", inspection_date.strftime("%Y-%m-%d"), "Estado", status], ["Empresa", company, "Versión", str(version)]], [27*mm, 53*mm, 20*mm, 62*mm]), Spacer(1, 8), Paragraph("Información general", styles["PQMSection"]), Paragraph(f"<b>Elaborado por:</b> {self._esc(author)} &nbsp;&nbsp; <b>Revisado por:</b> {self._esc(reviewer or 'Pendiente')}", styles["BodyText"])]
        if general_obs: story.append(Paragraph(f"<b>Observaciones generales:</b> {self._esc(general_obs)}", styles["BodyText"]))
        categories = []
        for row in groups:
            if row[1] not in categories:
                categories.append(row[1]); story.append(Paragraph(self._esc(row[1]), styles["PQMSection"]))
            code, category, title, state, value, unit, obs, na, images = row
            story.append(Paragraph(f"<b>{self._esc(code)} — {self._esc(title)}</b> &nbsp; <font color='#145b83'>[{self._esc(state)}]</font>", styles["BodyText"]))
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
                            pic = PDFImage(buffer, width=82*mm, height=55*mm, kind="proportional")
                            cells.append([pic, Paragraph(self._esc(original), styles["Small"])])
                        except Exception as exc:
                            cells.append(Paragraph(f"No se pudo incluir {self._esc(original)}: {self._esc(str(exc))}", styles["Small"]))
                for i in range(0, len(cells), 2):
                    rowcells = cells[i:i+2]
                    if len(rowcells) == 1: rowcells.append("")
                    story.append(Table([rowcells], colWidths=[85*mm, 85*mm], style=TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"), ("LEFTPADDING",(0,0),(-1,-1),2), ("RIGHTPADDING",(0,0),(-1,-1),2)])))
            else: story.append(Paragraph("Sin fotografías adjuntas.", styles["Small"]))
            story.append(Spacer(1,5))
        counts = {k: sum(1 for g in groups if g[3] == k) for k in ("Conforme", "No conforme", "No aplica", "Pendiente")}
        story += [Paragraph("Resumen de inspección", styles["PQMSection"]), self._table([["Total evidencias", str(len(groups)), "Documentadas", str(sum(bool(g[8]) for g in groups))], ["Conformes", str(counts["Conforme"]), "No conformes", str(counts["No conforme"])], ["No aplican", str(counts["No aplica"]), "Pendientes", str(counts["Pendiente"])]], [35*mm, 30*mm, 35*mm, 62*mm])]
        if conclusion: story.append(Paragraph(f"<b>Conclusión técnica:</b> {self._esc(conclusion)}", styles["BodyText"]))
        story.append(Spacer(1, 16)); story.append(Paragraph(f"Elaborado por: {self._esc(author)} &nbsp;&nbsp;&nbsp; Revisado por: {self._esc(reviewer or 'Pendiente')}", styles["Small"]))
        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)

    @staticmethod
    def _table(rows, widths):
        t = Table(rows, colWidths=widths, repeatRows=0)
        t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#cbd5df")), ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#edf3f8")), ("BACKGROUND",(2,0),(2,-1),colors.HexColor("#edf3f8")), ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"), ("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8.5), ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6), ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        return t

    @staticmethod
    def _esc(v):
        from xml.sax.saxutils import escape
        return escape(str(v or ""))

    @staticmethod
    def _footer(canvas, doc):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#657386"))
        canvas.drawString(16*mm, 9*mm, "INGELEAN S.A.S. | Informe de inspección PQM")
        canvas.drawRightString(A4[0]-16*mm, 9*mm, f"Página {doc.page}")
        canvas.restoreState()
