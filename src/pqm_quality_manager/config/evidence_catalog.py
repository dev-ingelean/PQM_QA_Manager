"""Catálogo único, ordenado y estable de requisitos PQM."""
from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceDefinition:
    code: str
    category: str
    title: str
    order: int
    optional: bool = False


_GROUPS = [
    ("Sistema de alimentación", [
        ("ALIM-UPS-IN", "Voltaje Entrada UPS"),
        ("ALIM-UPS-OUT", "Voltaje Salida UPS"),
        ("ALIM-FUENTE-IN", "Voltaje Entrada Fuente Aisladora"),
        ("ALIM-FUENTE-OUT-1", "Voltaje SALIDA 1 Fuente Aisladora"),
        ("ALIM-FUENTE-OUT-2", "Voltaje SALIDA 2 Fuente Aisladora"),
        ("ALIM-FUENTE-OUT-3", "Voltaje SALIDA 3 Fuente Aisladora"),
    ]),
    ("ARE 1: INPUT PST", [(f"ARE1-{x}", t) for x, t in [
        ("VAB", "VAB"), ("VCB", "VCB"), ("VAC", "VAC"),
        ("MULTIMETRO", "Voltaje entre fases (multímetro)"),
        ("WIFI", "MÉTRICAS WIFI"), ("IA", "IA"), ("IB", "IB"), ("IC", "IC")]]),
    ("ARE 2: INPUT SUT", [(f"ARE2-{x}", t) for x, t in [
        ("VAB", "VAB"), ("VCB", "VCB"), ("VAC", "VAC"),
        ("MULTIMETRO", "Voltaje entre fases (multímetro)"),
        ("WIFI", "MÉTRICAS WIFI"), ("IA", "IA"), ("IB", "IB"), ("IC", "IC")]]),
    ("ARE 3: OUTPUT PST", [(f"ARE3-{x}", t) for x, t in [
        ("VAB", "VAB"), ("VCB", "VCB"), ("VAC", "VAC"),
        ("MULTIMETRO", "Voltaje entre fases (multímetro)"),
        ("WIFI", "MÉTRICAS WIFI"), ("IA", "IA"), ("IB", "IB"), ("IC", "IC")]]),
    ("Validaciones adicionales", [
        ("BALIZA-PROG", "PROGRAMACIÓN MÓDULO DE BALIZA"),
        ("BALIZA-FUNC", "Módulo Baliza en funcionamiento"),
        ("SCADA-REG", "Registros SCADA"), ("RTC", "RTC"),
        ("SO-ALMACENAMIENTO", "ALMACENAMIENTO EN SO")]),
]

EVIDENCE_CATALOG = tuple(
    EvidenceDefinition(code, category, title, idx)
    for idx, (category, code, title) in enumerate(
        ((category, code, title) for category, items in _GROUPS for code, title in items), start=1
    )
)
assert len(EVIDENCE_CATALOG) == 35
