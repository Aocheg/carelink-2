from datetime import date, datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.connection import Base
from app.database import models as m
from app.workflows import schemas as s, service

def session():
    engine=create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

def seed(db):
    user=m.User(username="nurse",password_hash="x",full_name="Nurse",role="NURSE")
    doctor=m.User(username="doctor",password_hash="x",full_name="Doctor",role="DOCTOR")
    facility=m.Facility(name="Main")
    db.add_all([user,doctor,facility]);db.flush()
    ward=m.Ward(facility_id=facility.id,name="Ward A"); db.add(ward);db.flush()
    bed=m.Bed(ward_id=ward.id,bed_number="A1"); patient=m.Patient(patient_number="CL-000001",full_name="Ada Patient",date_of_birth=date(1990,1,1),sex="F")
    db.add_all([bed,patient]);db.commit(); return user,doctor,ward,bed,patient

def test_admission_vital_alert_and_discharge_transaction():
    db=session(); nurse,doctor,ward,bed,patient=seed(db)
    admission=service.create_admission(db,s.AdmissionIn(patient_id=patient.id,ward_id=ward.id,bed_id=bed.id,admitted_by=nurse.id,source="ER",reason_for_admission="Observation"))
    assert db.get(m.Bed,bed.id).status == "OCCUPIED"
    vital=service.record_vitals(db,admission.id,s.VitalIn(recorded_by=nurse.id,recorded_at=datetime.now(timezone.utc),systolic_bp=185,diastolic_bp=100,pulse=90,temperature=37,respiratory_rate=18,spo2=95,measurement_status="COMPLETE"))
    assert vital.id and db.query(m.SafetyAlert).count() == 1
    service.discharge(db,admission.id,s.DischargeIn(discharged_by=doctor.id,discharged_at=datetime.now(timezone.utc),discharge_status="HOME",discharge_summary="Stable"))
    assert db.get(m.Bed,bed.id).status == "AVAILABLE"

def test_vital_schema_rejects_unpaired_bp():
    import pytest
    with pytest.raises(ValueError): s.VitalIn(recorded_by=1,recorded_at=datetime.now(timezone.utc),systolic_bp=120,measurement_status="PARTIAL",not_measured_reason="cuff unavailable")
