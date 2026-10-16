from datetime import date, datetime
from uuid import uuid4
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from pqm_quality_manager.database.engine import SessionLocal
from pqm_quality_manager.database.models import Inspection, InspectionEvidence, EvidenceImage, AuditLog
from pqm_quality_manager.config.evidence_catalog import EVIDENCE_CATALOG

from pqm_quality_manager.services.checkpoint_service import checkpoint

VALID_TRANSITIONS = {
    "EN_ELABORACION": {"PENDIENTE_REVISION"},
    "PENDIENTE_REVISION": {"APROBADA", "RECHAZADA"},
    "RECHAZADA": {"EN_ELABORACION"},
    "APROBADA": {"CERRADA"},
    "CERRADA": set(),
}

class InspectionError(ValueError):
    pass

class InspectionService:
    def create(self, inspection_date: date, company: str, pqm_number: str, act_number: str, author: str, observations="") -> int:
        fields = {"Empresa": company, "Número PQM": pqm_number, "Número de acta": act_number, "Persona que elabora": author}
        missing = [name for name, value in fields.items() if not value.strip()]
        if missing:
            raise InspectionError("Complete los campos obligatorios: " + ", ".join(missing))
        with SessionLocal() as s:
            if s.scalar(select(Inspection).where(Inspection.pqm_number == pqm_number.strip(), Inspection.deleted.is_(False))):
                raise InspectionError(f"Ya existe una inspección activa con el número PQM {pqm_number.strip()}.")
            item = Inspection(uuid=str(uuid4()), inspection_date=inspection_date, company=company.strip(), pqm_number=pqm_number.strip(), act_number=act_number.strip(), author=author.strip(), observations=observations.strip())
            item.evidences = [InspectionEvidence(code=e.code, category=e.category, title=e.title, order=e.order) for e in EVIDENCE_CATALOG]
            s.add(item)
            s.flush()
            s.add(AuditLog(inspection_id=item.id, event="INSPECCION_CREADA", actor=item.author, detail="Registro inicial y 35 evidencias creadas"))
            checkpoint(s, item, "Inspección creada")
            s.commit()
            return item.id

    def update_general(self, inspection_id: int, *, inspection_date, company, pqm_number, act_number, author, observations="", conclusion=""):
        with SessionLocal() as s:
            item = self._get(s, inspection_id)
            self._editable(item)
            if not all(str(v).strip() for v in (company, pqm_number, act_number, author)):
                raise InspectionError("Fecha, empresa, número PQM, acta y responsable son obligatorios.")
            duplicate = s.scalar(select(Inspection).where(Inspection.pqm_number == pqm_number.strip(), Inspection.deleted.is_(False), Inspection.id != item.id))
            if duplicate:
                raise InspectionError(f"El número PQM {pqm_number.strip()} ya está asignado.")
            item.inspection_date, item.company, item.pqm_number = inspection_date, company.strip(), pqm_number.strip()
            item.act_number, item.author = act_number.strip(), author.strip()
            item.observations, item.conclusion = observations.strip(), conclusion.strip()
            item.updated_at = datetime.now()
            s.add(AuditLog(inspection_id=item.id, event="DATOS_ACTUALIZADOS", actor=author, detail="Datos generales actualizados"))
            checkpoint(s, item, "Datos generales guardados")
            s.commit()

    def get(self, inspection_id: int):
        with SessionLocal() as s:
            item = s.scalar(select(Inspection).where(Inspection.id == inspection_id, Inspection.deleted.is_(False)))
            if not item:
                raise InspectionError("No se encontró la inspección.")
            # Eagerly detach-safe materialization for UI and services.
            _ = [(e.images[:]) for e in item.evidences]
            return item

    def list(self, search="", status="Todos", limit=500):
        with SessionLocal() as s:
            q = select(Inspection).where(Inspection.deleted.is_(False))
            if search.strip():
                term = f"%{search.strip()}%"
                q = q.where((Inspection.pqm_number.ilike(term)) | (Inspection.company.ilike(term)))
            if status != "Todos": q = q.where(Inspection.status == status)
            return list(s.scalars(q.order_by(Inspection.updated_at.desc()).limit(limit)).all())

    def dashboard(self):
        with SessionLocal() as s:
            counts = {status: s.scalar(select(func.count()).select_from(Inspection).where(Inspection.deleted.is_(False), Inspection.status == status)) or 0 for status in VALID_TRANSITIONS}
            total = s.scalar(select(func.count()).select_from(Inspection).where(Inspection.deleted.is_(False))) or 0
            incomplete_evidence = select(InspectionEvidence.inspection_id).where(or_(InspectionEvidence.status == "Pendiente", InspectionEvidence.id.not_in(select(EvidenceImage.evidence_id))))
            incomplete = s.scalar(select(func.count()).select_from(Inspection).where(Inspection.deleted.is_(False), Inspection.id.in_(incomplete_evidence))) or 0
            return {"total": total, "incomplete": incomplete, **counts, "recent": list(s.scalars(select(Inspection).where(Inspection.deleted.is_(False)).order_by(Inspection.updated_at.desc()).limit(8)).all())}

    def evidence(self, evidence_id):
        from pqm_quality_manager.database.models import EvidenceImage
        with SessionLocal() as s:
            obj = s.get(InspectionEvidence, evidence_id)
            if not obj: raise InspectionError("No se encontró la evidencia.")
            _ = obj.inspection
            for image in obj.images:
                _ = image.evidence.inspection
            return obj

    def save_evidence(self, evidence_id, *, status, measured_value="", unit="", observations="", na_reason=""):
        allowed = {"Pendiente", "Conforme", "No conforme", "No aplica"}
        if status not in allowed: raise InspectionError("Estado de evidencia no válido.")
        with SessionLocal() as s:
            e = s.get(InspectionEvidence, evidence_id)
            if not e: raise InspectionError("No se encontró la evidencia.")
            self._editable(e.inspection)
            if status == "No aplica" and not na_reason.strip(): raise InspectionError("Escriba la justificación para marcar No aplica.")
            if status != "No aplica": na_reason = ""
            e.status, e.measured_value, e.unit = status, measured_value.strip(), unit.strip()
            e.observations, e.na_reason = observations.strip(), na_reason.strip()
            e.updated_at = datetime.now()
            e.inspection.updated_at = datetime.now()
            s.add(AuditLog(inspection_id=e.inspection_id, event="EVIDENCIA_ACTUALIZADA", detail=f"{e.code}: {status}"))
            checkpoint(s, e.inspection, f"Evidencia {e.code} guardada")
            s.commit()

    def progress(self, inspection_id):
        item = self.get(inspection_id)
        counts = {k: 0 for k in ("documented", "missing_photos", "Conforme", "No conforme", "No aplica", "Pendiente")}
        for e in item.evidences:
            if e.images: counts["documented"] += 1
            else: counts["missing_photos"] += 1
            counts[e.status] += 1
        counts["total"] = len(item.evidences)
        counts["percent"] = round(100 * counts["documented"] / max(counts["total"], 1))
        return counts

    def transition(self, inspection_id, target, actor="", notes=""):
        with SessionLocal() as s:
            item = self._get(s, inspection_id)
            if target not in VALID_TRANSITIONS.get(item.status, set()):
                raise InspectionError(f"No se permite cambiar de {item.status} a {target}.")
            if target == "PENDIENTE_REVISION":
                missing = [e.code for e in item.evidences if e.status == "Pendiente" or (e.status == "No aplica" and not e.na_reason.strip()) or (e.status != "No aplica" and not e.images)]
                if missing: raise InspectionError(f"Faltan evidencias por evaluar o documentar ({len(missing)}): " + ", ".join(missing[:8]))
            if target in {"APROBADA", "RECHAZADA", "CERRADA"} and not actor.strip(): raise InspectionError("Indique el responsable de esta acción.")
            previous = item.status
            item.status = target
            if target in {"APROBADA", "RECHAZADA", "CERRADA"}:
                item.reviewer = actor.strip(); item.approval_date = datetime.now(); item.approval_notes = notes.strip()
            item.updated_at = datetime.now()
            s.add(AuditLog(inspection_id=item.id, event="CAMBIO_ESTADO", actor=actor, detail=f"{previous} -> {target}. {notes}"))
            checkpoint(s, item, f"Estado: {target}")
            s.commit()

    def soft_delete(self, inspection_id, actor=""):
        with SessionLocal() as s:
            item = self._get(s, inspection_id)
            item.deleted = True; item.updated_at = datetime.now()
            s.add(AuditLog(inspection_id=item.id, event="ELIMINACION_LOGICA", actor=actor, detail="Inspección ocultada del historial"))
            checkpoint(s, item, "Eliminación lógica")
            s.commit()

    def duplicate(self, inspection_id):
        src = self.get(inspection_id)
        return self.create(date.today(), src.company, f"{src.pqm_number}-COPIA-{datetime.now():%H%M%S}", src.act_number, src.author, src.observations)

    @staticmethod
    def _get(s, inspection_id):
        item = s.scalar(select(Inspection).where(Inspection.id == inspection_id, Inspection.deleted.is_(False)))
        if not item: raise InspectionError("No se encontró la inspección.")
        return item

    @staticmethod
    def _editable(item):
        if item.status in {"APROBADA", "CERRADA", "PENDIENTE_REVISION"}:
            raise InspectionError(f"La inspección en estado {item.status} está bloqueada para edición.")
