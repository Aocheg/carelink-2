"""Business rules and transaction helpers. Routes remain thin."""
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.database import models as m
from app.core.security import hash_password

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def fail(code: int, detail: str) -> None:
    raise HTTPException(status_code=code, detail=detail)

def get(db: Session, cls, ident: int):
    obj = db.get(cls, ident)
    if not obj:
        fail(404, f"{cls.__name__} not found")
    return obj

def active_user(db: Session, ident: int, doctor: bool = False, roles: set[str] | None = None):
    user = get(db, m.User, ident)
    if not user.is_active:
        fail(409, "user is inactive")
    if doctor and user.role != "DOCTOR":
        fail(403, "action requires a doctor")
    if roles and user.role not in roles:
        fail(403, f"action requires one of: {', '.join(sorted(roles))}")
    return user

def audit(db, action, entity, obj, actor=None, details=None):
    db.add(m.AuditLog(
        action=action,
        entity_type=entity,
        entity_id=getattr(obj, "id", None),
        actor_id=actor,
        details=details,
    ))

def commit(db):
    try:
        db.commit()
    except Exception:
        db.rollback()
        fail(409, "operation conflicts with an existing record")

def serialise(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

def numbered(db, cls, prefix, attr=None):
    column = getattr(cls, attr or "id")
    value = db.scalar(select(func.max(column)))
    return f"{prefix}-{(value or 0) + 1:06d}"

def create_admission(db, data, actor_id: int | None = None):
    get(db, m.Patient, data.patient_id)
    ward = get(db, m.Ward, data.ward_id)
    bed = get(db, m.Bed, data.bed_id)
    active_user(db, data.admitted_by)
    if bed.ward_id != ward.id:
        fail(422, "bed does not belong to ward")
    if bed.status != "AVAILABLE":
        fail(409, "bed is not available")
    # A patient may have multiple historical admissions, but only one active admission.
    active = db.scalar(select(m.Admission).where(
        m.Admission.patient_id == data.patient_id,
        m.Admission.status == "ACTIVE",
    ))
    if active:
        fail(409, "patient already has an active admission")
    admission = m.Admission(
        admission_number=numbered(db, m.Admission, "AD", "id"),
        admitted_at=utcnow(),
        status="ACTIVE",
        **data.model_dump(),
    )
    bed.status = "OCCUPIED"
    db.add(admission)
    db.flush()
    audit(db, "CREATE", "Admission", admission, actor_id or data.admitted_by)
    commit(db)
    return admission

def record_vitals(db, admission_id, data, actor_id: int | None = None):
    admission = get(db, m.Admission, admission_id)
    active_user(db, data.recorded_by)
    if admission.status != "ACTIVE":
        fail(409, "admission is not active")
    vital = m.VitalSign(admission_id=admission_id, **data.model_dump())
    db.add(vital)
    db.flush()
    actor = actor_id or data.recorded_by
    audit(db, "CREATE", "VitalSign", vital, actor)
    if (vital.spo2 is not None and vital.spo2 < 90) or (vital.systolic_bp is not None and vital.systolic_bp >= 180):
        alert = m.SafetyAlert(
            admission_id=admission_id,
            alert_type="ABNORMAL_VITAL",
            severity="HIGH",
            message="Abnormal vital sign meets CARELINK escalation rule.",
        )
        db.add(alert)
        db.flush()
        audit(db, "GENERATE", "SafetyAlert", alert, actor)
    commit(db)
    return vital

def create_medication_order(db, admission_id, data, actor_id: int | None = None):
    admission = get(db, m.Admission, admission_id)
    if admission.status != "ACTIVE":
        fail(409, "admission is not active")
    active_user(db, data.prescribed_by, doctor=True)
    obj = m.MedicationOrder(admission_id=admission_id, status="ACTIVE", **data.model_dump())
    db.add(obj)
    db.flush()
    audit(db, "CREATE", "MedicationOrder", obj, actor_id or data.prescribed_by)
    commit(db)
    return obj

def administer(db, order_id, data, actor_id: int | None = None):
    order = get(db, m.MedicationOrder, order_id)
    active_user(db, data.administered_by)
    if order.status != "ACTIVE":
        fail(409, "medication order is not active")
    obj = m.MedicationAdministration(medication_order_id=order_id, **data.model_dump())
    db.add(obj)
    db.flush()
    audit(db, "CREATE", "MedicationAdministration", obj, actor_id or data.administered_by)
    commit(db)
    return obj

def transition_medication(db, order_id, status, actor_id):
    obj = get(db, m.MedicationOrder, order_id)
    active_user(db, actor_id)
    if status not in {"ACTIVE", "COMPLETED", "DISCONTINUED"}:
        fail(422, "invalid medication status")
    if obj.status in {"COMPLETED", "DISCONTINUED"} and status != obj.status:
        fail(409, "terminal medication orders cannot be reopened")
    if status == "ACTIVE" and obj.status != "ACTIVE":
        fail(409, "terminal medication orders cannot be reopened")
    obj.status = status
    audit(db, "STATUS_CHANGE", "MedicationOrder", obj, actor_id, status)
    commit(db)
    return obj

def create_investigation(db, admission_id, data, actor_id=None):
    admission = get(db, m.Admission, admission_id)
    if admission.status != "ACTIVE":
        fail(409, "admission is not active")
    active_user(db, data.requested_by)
    tests = [t.strip() for t in data.tests if t.strip()]
    if not tests:
        fail(422, "at least one investigation test is required")
    req = m.InvestigationRequest(
        admission_id=admission_id,
        requested_by=data.requested_by,
        clinical_notes=data.clinical_notes,
    )
    db.add(req)
    db.flush()
    for test in tests:
        db.add(m.InvestigationItem(request_id=req.id, test_name=test))
    audit(db, "CREATE", "InvestigationRequest", req, actor_id or data.requested_by)
    commit(db)
    return req

def transition_item(db, item_id, status, result=None, actor=None):
    item = get(db, m.InvestigationItem, item_id)
    active_user(db, actor) if actor else None
    valid = {"REQUESTED": {"PROCESSING"}, "PROCESSING": {"AVAILABLE"}, "AVAILABLE": set()}
    if status not in valid.get(item.status, set()):
        fail(409, f"cannot transition {item.status} to {status}")
    item.status = status
    if result is not None:
        item.result_value = result.result_value
        item.result_notes = result.result_notes
        item.is_critical = result.is_critical
    if status == "AVAILABLE":
        item.available_at = utcnow()
    db.flush()
    audit(db, "TRANSITION", "InvestigationItem", item, actor, status)
    if item.is_critical:
        req = get(db, m.InvestigationRequest, item.request_id)
        alert = m.SafetyAlert(
            admission_id=req.admission_id,
            alert_type="CRITICAL_RESULT",
            severity="CRITICAL",
            message=f"Critical result available: {item.test_name}",
        )
        db.add(alert)
        db.flush()
        audit(db, "GENERATE", "SafetyAlert", alert, actor)
    commit(db)
    return item

def discharge(db, admission_id, data, actor_id=None):
    admission = get(db, m.Admission, admission_id)
    active_user(db, data.discharged_by, doctor=True)
    if admission.status != "ACTIVE":
        fail(409, "only an active admission can be discharged")
    if data.discharged_at.tzinfo is None:
        fail(422, "discharged_at must be timezone-aware")
    obj = m.Discharge(
        admission_id=admission_id,
        discharged_at=data.discharged_at.astimezone(timezone.utc),
        **data.model_dump(exclude={"discharged_at"}),
    )
    admission.status = "DISCHARGED"
    bed = get(db, m.Bed, admission.bed_id)
    bed.status = "AVAILABLE"
    db.add(obj)
    db.flush()
    audit(db, "DISCHARGE", "Admission", admission, actor_id or data.discharged_by)
    commit(db)
    return obj
