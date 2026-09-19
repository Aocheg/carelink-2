"""Business rules and transaction helpers. Routes do not commit directly."""
import hashlib, os
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import models as m

def utcnow(): return datetime.now(timezone.utc)
def fail(code: int, detail: str): raise HTTPException(code, detail)
def get(db: Session, cls, ident: int):
    obj = db.get(cls, ident)
    if not obj: fail(404, f"{cls.__name__} not found")
    return obj
def active_user(db, ident: int, doctor=False):
    user = get(db, m.User, ident)
    if not user.is_active: fail(409, "user is inactive")
    if doctor and user.role != "DOCTOR": fail(403, "action requires a doctor")
    return user
def audit(db, action, entity, obj, actor=None, details=None):
    db.add(m.AuditLog(action=action, entity_type=entity, entity_id=getattr(obj, "id", None), actor_id=actor, details=details))
def commit(db):
    try: db.commit()
    except Exception as exc: db.rollback(); fail(409, "operation conflicts with an existing record")
def serialise(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
def numbered(db, cls, prefix, attr):
    count = db.scalar(select(cls).count()) if False else (db.scalar(select(m.func.count()) if False else select(cls.id).order_by(cls.id.desc()).limit(1)) or 0)
    return f"{prefix}-{count + 1:06d}"
def password_hash(password):
    salt=os.urandom(16); return salt.hex()+":"+hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1).hex()

def create_admission(db, data):
    get(db,m.Patient,data.patient_id); ward=get(db,m.Ward,data.ward_id); bed=get(db,m.Bed,data.bed_id); active_user(db,data.admitted_by)
    if bed.ward_id != ward.id: fail(422,"bed does not belong to ward")
    if bed.status != "AVAILABLE": fail(409,"bed is not available")
    admission=m.Admission(admission_number=numbered(db,m.Admission,"AD", "admission_number"), admitted_at=utcnow(), status="ACTIVE", **data.model_dump())
    bed.status="OCCUPIED"; db.add(admission); db.flush(); audit(db,"CREATE","Admission",admission,data.admitted_by); commit(db); return admission

def record_vitals(db, admission_id, data):
    admission=get(db,m.Admission,admission_id); active_user(db,data.recorded_by)
    if admission.status != "ACTIVE": fail(409,"admission is not active")
    vital=m.VitalSign(admission_id=admission_id, **data.model_dump()); db.add(vital); db.flush(); audit(db,"CREATE","VitalSign",vital,data.recorded_by)
    # Documented operational alert rule: SpO2 < 90 or systolic BP >= 180.
    if (vital.spo2 is not None and vital.spo2 < 90) or (vital.systolic_bp is not None and vital.systolic_bp >= 180):
        alert=m.SafetyAlert(admission_id=admission_id,alert_type="ABNORMAL_VITAL",severity="HIGH",message="Abnormal vital sign meets CARELINK escalation rule")
        db.add(alert); db.flush(); audit(db,"GENERATE","SafetyAlert",alert,data.recorded_by)
    commit(db); return vital

def administer(db, order_id, data):
    order=get(db,m.MedicationOrder,order_id); active_user(db,data.administered_by)
    if order.status != "ACTIVE": fail(409,"medication order is not active")
    obj=m.MedicationAdministration(medication_order_id=order_id,**data.model_dump()); db.add(obj); db.flush(); audit(db,"CREATE","MedicationAdministration",obj,data.administered_by); commit(db); return obj

def transition_item(db,item_id,status,result=None,actor=None):
    item=get(db,m.InvestigationItem,item_id)
    valid={"REQUESTED":{"PROCESSING"},"PROCESSING":{"AVAILABLE"},"AVAILABLE":set()}
    if status not in valid.get(item.status,set()): fail(409,f"cannot transition {item.status} to {status}")
    item.status=status
    if result: item.result_value=result.result_value; item.result_notes=result.result_notes; item.is_critical=result.is_critical
    if status=="AVAILABLE": item.available_at=utcnow()
    db.flush(); audit(db,"TRANSITION","InvestigationItem",item,actor,status)
    if item.is_critical:
        req=get(db,m.InvestigationRequest,item.request_id); a=m.SafetyAlert(admission_id=req.admission_id,alert_type="CRITICAL_RESULT",severity="CRITICAL",message=f"Critical result available: {item.test_name}"); db.add(a)
    commit(db); return item

def discharge(db, admission_id, data):
    admission=get(db,m.Admission,admission_id); active_user(db,data.discharged_by,doctor=True)
    if admission.status != "ACTIVE": fail(409,"only an active admission can be discharged")
    if data.discharged_at.tzinfo is None: fail(422,"discharged_at must be timezone-aware")
    obj=m.Discharge(admission_id=admission_id,discharged_at=data.discharged_at.astimezone(timezone.utc),**data.model_dump(exclude={"discharged_at"}))
    admission.status="DISCHARGED"; get(db,m.Bed,admission.bed_id).status="AVAILABLE"; db.add(obj); db.flush(); audit(db,"DISCHARGE","Admission",admission,data.discharged_by); commit(db); return obj
