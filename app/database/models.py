"""Persistence models for all CARELINK workflow units."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(40), default="NURSE")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Facility(Timestamped, Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Ward(Timestamped, Base):
    __tablename__ = "wards"
    __table_args__ = (UniqueConstraint("facility_id", "name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    name: Mapped[str] = mapped_column(String(100))


class Bed(Timestamped, Base):
    __tablename__ = "beds"
    __table_args__ = (UniqueConstraint("ward_id", "bed_number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    bed_number: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="AVAILABLE")


class Patient(Timestamped, Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    date_of_birth: Mapped[datetime] = mapped_column(Date)
    sex: Mapped[str] = mapped_column(String(20))
    marital_status: Mapped[Optional[str]] = mapped_column(String(40))
    religion: Mapped[Optional[str]] = mapped_column(String(80))
    occupation: Mapped[Optional[str]] = mapped_column(String(100))
    address: Mapped[Optional[str]] = mapped_column(Text)
    phone_number: Mapped[Optional[str]] = mapped_column(String(40))
    blood_group: Mapped[Optional[str]] = mapped_column(String(10))
    genotype: Mapped[Optional[str]] = mapped_column(String(10))
    allergy_status: Mapped[bool] = mapped_column(Boolean, default=False)
    allergy_details: Mapped[Optional[str]] = mapped_column(Text)


class NextOfKin(Timestamped, Base):
    __tablename__ = "next_of_kin"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    relationship: Mapped[str] = mapped_column(String(60))
    phone_number: Mapped[str] = mapped_column(String(40))
    address: Mapped[Optional[str]] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class Admission(Timestamped, Base):
    __tablename__ = "admissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    bed_id: Mapped[int] = mapped_column(ForeignKey("beds.id"))
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(80))
    reason_for_admission: Mapped[str] = mapped_column(Text)
    presenting_complaint: Mapped[Optional[str]] = mapped_column(Text)
    patient_account: Mapped[Optional[str]] = mapped_column(String(80))
    doctor_assessment: Mapped[Optional[str]] = mapped_column(Text)
    nursing_assessment: Mapped[Optional[str]] = mapped_column(Text)
    nursing_diagnosis: Mapped[Optional[str]] = mapped_column(Text)
    admitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class VitalSign(Timestamped, Base):
    __tablename__ = "vital_signs"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), index=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    systolic_bp: Mapped[Optional[int]] = mapped_column(Integer)
    diastolic_bp: Mapped[Optional[int]] = mapped_column(Integer)
    pulse: Mapped[Optional[int]] = mapped_column(Integer)
    temperature: Mapped[Optional[float]] = mapped_column(Float)
    respiratory_rate: Mapped[Optional[int]] = mapped_column(Integer)
    spo2: Mapped[Optional[float]] = mapped_column(Float)
    measurement_status: Mapped[str] = mapped_column(String(20))
    not_measured_reason: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class MedicationOrder(Timestamped, Base):
    __tablename__ = "medication_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), index=True)
    medication_name: Mapped[str] = mapped_column(String(160))
    dose: Mapped[str] = mapped_column(String(80))
    route: Mapped[str] = mapped_column(String(50))
    frequency: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[datetime] = mapped_column(Date)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date)
    prescribed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    instructions: Mapped[Optional[str]] = mapped_column(Text)


class MedicationAdministration(Timestamped, Base):
    __tablename__ = "medication_administrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    medication_order_id: Mapped[int] = mapped_column(ForeignKey("medication_orders.id"), index=True)
    administered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    administered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30))
    not_administered_reason: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class InvestigationRequest(Timestamped, Base):
    __tablename__ = "investigation_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    clinical_notes: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="REQUESTED")


class InvestigationItem(Timestamped, Base):
    __tablename__ = "investigation_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("investigation_requests.id"), index=True)
    test_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="REQUESTED")
    result_value: Mapped[Optional[str]] = mapped_column(Text)
    result_notes: Mapped[Optional[str]] = mapped_column(Text)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    available_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DoctorReview(Timestamped, Base):
    __tablename__ = "doctor_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), index=True)
    reviewed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assessment: Mapped[str] = mapped_column(Text)
    plan: Mapped[Optional[str]] = mapped_column(Text)


class ClinicalOrder(Timestamped, Base):
    __tablename__ = "clinical_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), index=True)
    ordered_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    order_type: Mapped[str] = mapped_column(String(80))
    details: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class NursingHandover(Timestamped, Base):
    __tablename__ = "nursing_handovers"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), index=True)
    sent_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    received_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    shift: Mapped[str] = mapped_column(String(40))
    current_condition: Mapped[str] = mapped_column(Text)
    recent_observations: Mapped[Optional[str]] = mapped_column(Text)
    outstanding_issues: Mapped[Optional[str]] = mapped_column(Text)
    risks: Mapped[Optional[str]] = mapped_column(Text)
    nursing_notes: Mapped[Optional[str]] = mapped_column(Text)


class SafetyAlert(Timestamped, Base):
    __tablename__ = "safety_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), index=True)
    alert_type: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    acknowledged_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    resolved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))


class Discharge(Timestamped, Base):
    __tablename__ = "discharges"
    id: Mapped[int] = mapped_column(primary_key=True)
    admission_id: Mapped[int] = mapped_column(ForeignKey("admissions.id"), unique=True)
    discharged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    discharge_status: Mapped[str] = mapped_column(String(50))
    discharge_summary: Mapped[str] = mapped_column(Text)
    diagnosis_outcome: Mapped[Optional[str]] = mapped_column(Text)
    medications_instructions: Mapped[Optional[str]] = mapped_column(Text)
    follow_up: Mapped[Optional[str]] = mapped_column(Text)
    discharged_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer)
    details: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
