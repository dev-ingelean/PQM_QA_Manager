from datetime import datetime, date
from sqlalchemy import String, Text, Integer, Date, DateTime, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Inspection(Base):
    __tablename__ = "inspections"
    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    inspection_date: Mapped[date] = mapped_column(Date)
    company: Mapped[str] = mapped_column(String(200), index=True)
    pqm_number: Mapped[str] = mapped_column(String(80), index=True)
    act_number: Mapped[str] = mapped_column(String(80))
    author: Mapped[str] = mapped_column(String(160))
    observations: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="EN_ELABORACION", index=True)
    reviewer: Mapped[str] = mapped_column(String(160), default="")
    approval_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    evidences: Mapped[list["InspectionEvidence"]] = relationship(back_populates="inspection", cascade="all, delete-orphan", order_by="InspectionEvidence.order")
    reports: Mapped[list["Report"]] = relationship(back_populates="inspection", cascade="all, delete-orphan")

class InspectionEvidence(Base):
    __tablename__ = "inspection_evidence"
    __table_args__ = (UniqueConstraint("inspection_id", "code", name="uq_inspection_evidence_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(160))
    order: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="Pendiente")
    measured_value: Mapped[str] = mapped_column(String(100), default="")
    unit: Mapped[str] = mapped_column(String(40), default="")
    observations: Mapped[str] = mapped_column(Text, default="")
    na_reason: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    inspection: Mapped[Inspection] = relationship(back_populates="evidences")
    images: Mapped[list["EvidenceImage"]] = relationship(back_populates="evidence", cascade="all, delete-orphan", order_by="EvidenceImage.order")

class EvidenceImage(Base):
    __tablename__ = "evidence_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("inspection_evidence.id", ondelete="CASCADE"), index=True)
    relative_path: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(255))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    order: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    evidence: Mapped[InspectionEvidence] = relationship(back_populates="images")

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    report_type: Mapped[str] = mapped_column(String(20))
    path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    immutable: Mapped[bool] = mapped_column(Boolean, default=False)
    inspection: Mapped[Inspection] = relationship(back_populates="reports")

class EmailDispatch(Base):
    __tablename__ = "email_dispatches"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspections.id"), index=True)
    recipient: Mapped[str] = mapped_column(String(320))
    result: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id"), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(80))
    actor: Mapped[str] = mapped_column(String(160), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
