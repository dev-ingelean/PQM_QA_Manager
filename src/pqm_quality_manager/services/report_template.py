"""Corporate background and SIG header based on static/reports/main.tex."""
from io import BytesIO
from copy import copy
from hashlib import sha256
from pathlib import Path
import re
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image, Paragraph, Table, TableStyle

ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "reports"
LEFT_MARGIN = RIGHT_MARGIN = 23.5 * mm
TOP_MARGIN = 45 * mm
BOTTOM_MARGIN = 40 * mm


def sig_values():
    source = (ASSET_DIR / "main.tex").read_text(encoding="utf-8")
    fields = {}
    for name in ("CodigoDocumento", "VersionDocumento", "FechaDocumento", "ProcesoDocumento"):
        match = re.search(r"\\newcommand\{\\" + name + r"\}\s*\{([^{}]*)\}", source)
        if not match:
            raise ValueError(f"Falta {name} en la plantilla SIG main.tex.")
        fields[name] = match.group(1).strip()
    return fields


def sig_header(width, page, total, values):
    small = ParagraphStyle("SIGCell", fontName="Helvetica", fontSize=7, leading=8.5,
                           alignment=TA_CENTER, textColor=colors.black)
    bold = ParagraphStyle("SIGBold", parent=small, fontName="Helvetica-Bold")
    white = ParagraphStyle("SIGWhite", parent=bold, textColor=colors.white)
    brand_style = ParagraphStyle("SIGBrand", parent=bold, fontSize=14, leading=16)
    logo = ASSET_DIR / "logo-ingelean.png"
    brand = Image(str(logo), width=35*mm, height=14*mm, kind="proportional") if logo.is_file() else Paragraph("INGE-LEAN", brand_style)
    def cell(value, style=small):
        return Paragraph(escape(str(value)), style)
    rows = [
        [cell("SISTEMA INTEGRADO DE GESTIÓN (SIG)", white), "", "", ""],
        [brand, cell("TIPO DE DOCUMENTO: INFORME DE INSPECCIÓN PQM", bold), cell("Código:", white), cell(values["CodigoDocumento"])],
        ["", "", cell("Versión:", white), cell(values["VersionDocumento"])],
        ["", cell("PROCESO: " + values["ProcesoDocumento"], bold), cell("Fecha:", white), cell(values["FechaDocumento"])],
        ["", "", cell("Página:", white), cell(f"{page} de {total}")],
    ]
    table = Table(rows, colWidths=[width*.255, width*.435, width*.12, width*.19], rowHeights=[5*mm]*5)
    grey = colors.Color(76/255, 76/255, 76/255)
    table.setStyle(TableStyle([
        ("SPAN", (0,0), (-1,0)), ("SPAN", (0,1), (0,4)),
        ("SPAN", (1,1), (1,2)), ("SPAN", (1,3), (1,4)),
        ("BACKGROUND", (0,0), (-1,0), grey), ("BACKGROUND", (2,1), (2,4), grey),
        ("BACKGROUND", (0,1), (1,4), colors.white), ("BACKGROUND", (3,1), (3,4), colors.white),
        ("GRID", (0,0), (-1,-1), .5, colors.black), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("LEFTPADDING", (0,0), (-1,-1), 3), ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 0), ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    return table


def template_signature():
    digest = sha256(b"PQM-SIG-layout-v2")
    for name in ("Fondo.jpg", "logo-ingelean.png", "main.tex"):
        digest.update((ASSET_DIR / name).read_bytes())
    return digest.hexdigest()


def apply_template(content, destination, *, fit_existing=False):
    background = ASSET_DIR / "Fondo.jpg"
    if not background.is_file():
        raise ValueError("No se encuentra el fondo corporativo Fondo.jpg.")
    values = sig_values()
    reader = PdfReader(content)
    writer = PdfWriter()
    width, height = A4
    for index, source in enumerate(reader.pages, 1):
        stream = BytesIO()
        canvas = Canvas(stream, pagesize=A4)
        canvas.drawImage(str(background), 0, 0, width=width, height=height)
        header = sig_header(width-LEFT_MARGIN-RIGHT_MARGIN, index, len(reader.pages), values)
        _, header_height = header.wrap(width, height)
        header.drawOn(canvas, LEFT_MARGIN, height-12*mm-header_height)
        canvas.save()
        stream.seek(0)
        page = writer.add_page(PdfReader(stream).pages[0])
        if fit_existing:
            # Preserve the saved report content, removing only its old page furniture.
            corporate = "SISTEMA INTEGRADO DE GESTIÓN (SIG)" in (source.extract_text() or "")
            left = LEFT_MARGIN if corporate else 16*mm
            bottom = BOTTOM_MARGIN if corporate else 17*mm
            right = float(source.mediabox.width) - (RIGHT_MARGIN if corporate else 16*mm)
            top = float(source.mediabox.height) - (TOP_MARGIN if corporate else 17*mm)
            cropped = copy(source)
            cropped.cropbox = RectangleObject((left, bottom, right, top))
            scale = min((width-LEFT_MARGIN-RIGHT_MARGIN)/(right-left),
                        (height-TOP_MARGIN-BOTTOM_MARGIN)/(top-bottom))
            x = LEFT_MARGIN + ((width-LEFT_MARGIN-RIGHT_MARGIN)-(right-left)*scale)/2
            y = height-TOP_MARGIN-(top-bottom)*scale
            transform = Transformation().translate(-left, -bottom).scale(scale).translate(x, y)
            page.merge_transformed_page(cropped, transform)
        else:
            page.merge_page(source)
    if reader.metadata:
        writer.add_metadata({key: str(value) for key, value in reader.metadata.items()})
    writer.add_metadata({"/PQMTemplate": template_signature()})
    with Path(destination).open("wb") as output:
        writer.write(output)
