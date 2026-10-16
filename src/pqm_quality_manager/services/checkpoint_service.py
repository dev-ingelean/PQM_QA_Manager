"""Immutable inspection snapshots, committed with the change they describe."""
import json
from sqlalchemy import select
from pqm_quality_manager.database.models import InspectionCheckpoint


def checkpoint(session, inspection, reason):
    session.flush()
    def values(obj):
        return {col.key: getattr(obj, col.key) for col in obj.__table__.columns}
    snapshot = values(inspection)
    snapshot["evidences"] = []
    for evidence in inspection.evidences:
        entry = values(evidence)
        entry["images"] = [values(image) for image in evidence.images if image not in session.deleted]
        snapshot["evidences"].append(entry)
    snapshot["reports"] = [values(report) for report in inspection.reports]
    session.add(InspectionCheckpoint(inspection_id=inspection.id, reason=reason,
                                    snapshot=json.dumps(snapshot, default=str, ensure_ascii=False)))


def history(session, inspection_id):
    return list(session.scalars(select(InspectionCheckpoint)
        .where(InspectionCheckpoint.inspection_id == inspection_id)
        .order_by(InspectionCheckpoint.id.desc()).limit(100)))
