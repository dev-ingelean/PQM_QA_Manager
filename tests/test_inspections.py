from datetime import date
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from pqm_quality_manager.database.models import Base, Inspection, InspectionEvidence
from pqm_quality_manager.config.evidence_catalog import EVIDENCE_CATALOG
from pqm_quality_manager.services.inspection_service import InspectionService, InspectionError

@pytest.fixture
def service(monkeypatch):
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr("pqm_quality_manager.services.inspection_service.SessionLocal",factory)
    return InspectionService(),factory

def test_create_adds_exact_catalog_and_rejects_duplicate(service):
    svc,factory=service
    iid=svc.create(date.today(),"Cliente","PQM-001","ACT-1","Técnico")
    with factory() as s:
        item=s.get(Inspection,iid)
        assert len(item.evidences)==35
        assert [x.code for x in item.evidences]==[x.code for x in EVIDENCE_CATALOG]
    with pytest.raises(InspectionError):svc.create(date.today(),"Cliente","PQM-001","ACT-2","Técnico")

def test_required_fields_and_na_reason(service):
    svc,factory=service
    with pytest.raises(InspectionError):svc.create(date.today(),"","PQM-1","ACT","Tech")
    iid=svc.create(date.today(),"Cliente","PQM-2","ACT","Tech")
    with factory() as s:eid=s.scalar(select(InspectionEvidence.id).where(InspectionEvidence.inspection_id==iid))
    with pytest.raises(InspectionError):svc.save_evidence(eid,status="No aplica")
    svc.save_evidence(eid,status="No aplica",na_reason="No corresponde a esta configuración")

def test_submission_requires_all_evaluated_and_photographed(service):
    svc,factory=service
    iid=svc.create(date.today(),"Cliente","PQM-3","ACT","Tech")
    with pytest.raises(InspectionError):svc.transition(iid,"PENDIENTE_REVISION")
    with factory() as s:
        for ev in s.scalars(select(InspectionEvidence).where(InspectionEvidence.inspection_id==iid)):
            ev.status="No aplica";ev.na_reason="No aplica en esta revisión"
        s.commit()
    svc.transition(iid,"PENDIENTE_REVISION")
    with pytest.raises(InspectionError):svc.transition(iid,"CERRADA")

def test_approval_flow_and_locked_records(service):
    svc,factory=service
    iid=svc.create(date.today(),"Cliente","PQM-4","ACT","Tech")
    with factory() as s:
        for ev in s.scalars(select(InspectionEvidence).where(InspectionEvidence.inspection_id==iid)):
            ev.status="No aplica";ev.na_reason="No aplica a esta inspección"
        s.commit()
    svc.transition(iid,"PENDIENTE_REVISION")
    svc.transition(iid,"APROBADA",actor="Revisor",notes="Validado")
    with pytest.raises(InspectionError):
        svc.update_general(iid,inspection_date=date.today(),company="Cliente",pqm_number="PQM-4",act_number="ACT",author="Tech")
    svc.transition(iid,"CERRADA",actor="Revisor")
    assert svc.get(iid).status=="CERRADA"


def test_delete_requires_key_and_preserves_record_on_failure(service):
    svc, factory = service
    iid = svc.create(date.today(), "Cliente", "PQM-DELETE", "ACT", "Tech")
    for password in ("", "incorrecta"):
        with pytest.raises(InspectionError, match="Clave de eliminación incorrecta"):
            svc.soft_delete(iid, password=password)
        with factory() as session:
            assert session.get(Inspection, iid).deleted is False
    svc.soft_delete(iid, password="1ng3l3an20**")
    with factory() as session:
        item = session.get(Inspection, iid)
        assert item.deleted is True
        assert len(item.evidences) == 35


@pytest.mark.parametrize("code,expected", [("ALIM-UPS-IN", "V"), ("ARE1-VAB", "V"), ("ARE2-MULTIMETRO", "V"), ("ARE3-IA", "A")])
def test_electrical_units_are_fixed_when_saving(service, code, expected):
    svc, factory = service
    iid = svc.create(date.today(), "Cliente", "PQM-UNIT", "ACT", "Tech")
    with factory() as session:
        eid = session.scalar(select(InspectionEvidence.id).where(
            InspectionEvidence.inspection_id == iid, InspectionEvidence.code == code))
    svc.save_evidence(eid, status="Conforme", measured_value="120", unit="incorrecta")
    with factory() as session:
        assert session.get(InspectionEvidence, eid).unit == expected
