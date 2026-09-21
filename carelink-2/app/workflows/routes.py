from datetime import timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.security import (
    current_user, require_roles, hash_password, verify_password, create_access_token, ROLES
)
from app.database.connection import get_db
from app.database import models as m
from app.workflows import schemas as s
from app.workflows import service

r = APIRouter(prefix="/api", tags=["carelink"])

def out(x): return service.serialise(x)

def list_for(db, cls, field=None, ident=None):
    q = select(cls) if field is None else select(cls).where(getattr(cls, field) == ident)
    return [out(x) for x in db.scalars(q).all()]

def create(db, cls, data, actor=None):
    obj = cls(**data.model_dump())
    db.add(obj); db.flush()
    service.audit(db, "CREATE", cls.__name__, obj, actor)
    service.commit(db)
    return out(obj)

def actor_matches(user, supplied: int):
    if user.role == "ADMIN":
        return
    if user.id != supplied:
        service.fail(403, "actor_id must match the authenticated user")

@r.post("/auth/bootstrap", status_code=201, tags=["auth"])
def bootstrap(data: s.BootstrapIn, db: Session = Depends(get_db)):
    if db.scalar(select(func.count(m.User.id))):
        service.fail(409, "bootstrap is disabled because a user already exists")
    obj = m.User(username=data.username, password_hash=hash_password(data.password), full_name=data.full_name, role="ADMIN")
    db.add(obj); db.flush()
    service.audit(db, "CREATE", "User", obj, obj.id, "initial administrator")
    service.commit(db)
    return {"message": "administrator created", "user": out(obj)}

@r.post("/auth/login", tags=["auth"])
def login(data: s.LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(m.User).where(m.User.username == data.username))
    if not user or not verify_password(data.password, user.password_hash) or not user.is_active:
        service.fail(401, "invalid username or password")
    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
        "expires_in_minutes": 60,
        "user": out(user),
    }

@r.get("/auth/me", tags=["auth"])
def me(user: m.User = Depends(current_user)):
    return out(user)

@r.post("/users", status_code=201)
def users(data: s.UserIn, db: Session = Depends(get_db), actor: m.User = Depends(require_roles("ADMIN"))):
    if data.role not in ROLES:
        service.fail(422, f"role must be one of: {', '.join(sorted(ROLES))}")
    if db.scalar(select(m.User).where(m.User.username == data.username)):
        service.fail(409, "username already exists")
    obj = m.User(
        username=data.username,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(obj); db.flush(); service.audit(db, "CREATE", "User", obj, actor.id); service.commit(db)
    return out(obj)

@r.get("/users")
def users_list(db: Session = Depends(get_db), _: m.User = Depends(current_user)):
    return list_for(db, m.User)

@r.post("/facilities", status_code=201)
def facilities(data:s.FacilityIn, db:Session=Depends(get_db), actor:m.User=Depends(current_user)):
    return create(db,m.Facility,data,actor.id)

@r.get("/facilities")
def facilities_list(db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    return list_for(db,m.Facility)

@r.post("/wards",status_code=201)
def wards(data:s.WardIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    service.get(db,m.Facility,data.facility_id)
    return create(db,m.Ward,data,actor.id)

@r.get("/wards")
def wards_list(db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    return list_for(db,m.Ward)

@r.post("/beds",status_code=201)
def beds(data:s.BedIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    service.get(db,m.Ward,data.ward_id)
    return create(db,m.Bed,data,actor.id)

@r.get("/wards/{ward_id}/beds")
def ward_beds(ward_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Ward,ward_id)
    return list_for(db,m.Bed,"ward_id",ward_id)

@r.get("/beds")
def beds_list(db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    return list_for(db,m.Bed)

@r.post("/patients",status_code=201)
def patients(data:s.PatientIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    duplicate=db.scalar(select(m.Patient).where(
        func.lower(m.Patient.full_name)==data.full_name.lower(),
        m.Patient.date_of_birth==data.date_of_birth
    ))
    obj=m.Patient(patient_number=service.numbered(db,m.Patient,"CL","id"),**data.model_dump())
    db.add(obj); db.flush(); service.audit(db,"CREATE","Patient",obj,actor.id)
    service.commit(db)
    return {**out(obj),"possible_duplicate":bool(duplicate)}

@r.get("/patients")
def patients_list(db:Session=Depends(get_db), _:m.User=Depends(current_user)): return list_for(db,m.Patient)

@r.get("/patients/{patient_id}")
def patient(patient_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)): return out(service.get(db,m.Patient,patient_id))

@r.post("/patients/{patient_id}/next-of-kin",status_code=201)
def kin(patient_id:int,data:s.KinIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    service.get(db,m.Patient,patient_id)
    if data.is_primary:
        for x in db.scalars(select(m.NextOfKin).where(m.NextOfKin.patient_id==patient_id)): x.is_primary=False
    obj=m.NextOfKin(patient_id=patient_id,**data.model_dump()); db.add(obj); db.flush()
    service.audit(db,"CREATE","NextOfKin",obj,actor.id); service.commit(db); return out(obj)

@r.get("/patients/{patient_id}/admissions")
def patient_admissions(patient_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Patient,patient_id)
    return list_for(db,m.Admission,"patient_id",patient_id)

@r.post("/admissions",status_code=201)
def admissions(data:s.AdmissionIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.admitted_by)
    return out(service.create_admission(db,data,actor.id))

@r.get("/admissions")
def admissions_list(db:Session=Depends(get_db), _:m.User=Depends(current_user)): return list_for(db,m.Admission)

@r.get("/admissions/{admission_id}")
def admission(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)): return out(service.get(db,m.Admission,admission_id))

@r.post("/admissions/{admission_id}/vitals",status_code=201)
def vitals(admission_id:int,data:s.VitalIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.recorded_by)
    return out(service.record_vitals(db,admission_id,data,actor.id))

@r.get("/admissions/{admission_id}/vitals")
def vitals_list(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id); return list_for(db,m.VitalSign,"admission_id",admission_id)

@r.get("/vitals/{vital_id}")
def vital(vital_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)): return out(service.get(db,m.VitalSign,vital_id))

@r.post("/admissions/{admission_id}/medications",status_code=201)
def medication(admission_id:int,data:s.MedicationOrderIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.prescribed_by)
    return out(service.create_medication_order(db,admission_id,data,actor.id))

@r.get("/admissions/{admission_id}/medications")
def medications(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id); return list_for(db,m.MedicationOrder,"admission_id",admission_id)

@r.get("/medications/{order_id}")
def medication_one(order_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)): return out(service.get(db,m.MedicationOrder,order_id))

@r.post("/medications/{order_id}/administrations",status_code=201)
def administration(order_id:int,data:s.AdministrationIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.administered_by)
    return out(service.administer(db,order_id,data,actor.id))

@r.get("/medications/{order_id}/administrations")
def administrations(order_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.MedicationOrder,order_id); return list_for(db,m.MedicationAdministration,"medication_order_id",order_id)

@r.post("/medications/{order_id}/status")
def medication_status(order_id:int,data:s.StatusTransitionIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    return out(service.transition_medication(db,order_id,data.status,actor.id))

@r.post("/admissions/{admission_id}/investigations",status_code=201)
def investigation(admission_id:int,data:s.InvestigationIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.requested_by)
    return out(service.create_investigation(db,admission_id,data,actor.id))

@r.get("/admissions/{admission_id}/investigations")
def investigations(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id); return list_for(db,m.InvestigationRequest,"admission_id",admission_id)

@r.get("/investigations/{request_id}/items")
def items(request_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.InvestigationRequest,request_id); return list_for(db,m.InvestigationItem,"request_id",request_id)

@r.post("/investigation-items/{item_id}/processing")
def processing(item_id:int,data:s.ActorIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.actor_id)
    return out(service.transition_item(db,item_id,"PROCESSING",actor=actor.id))

@r.post("/investigation-items/{item_id}/result")
def result(item_id:int,data:s.ResultIn,db:Session=Depends(get_db),actor:m.User=Depends(require_roles("LAB","DOCTOR","ADMIN"))):
    return out(service.transition_item(db,item_id,"AVAILABLE",result=data,actor=actor.id))

@r.post("/admissions/{admission_id}/reviews",status_code=201)
def review(admission_id:int,data:s.ReviewIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.reviewed_by); service.get(db,m.Admission,admission_id); service.active_user(db,actor.id,doctor=True)
    if data.reviewed_at.tzinfo is None: service.fail(422,"reviewed_at must be timezone-aware")
    obj=m.DoctorReview(admission_id=admission_id,reviewed_at=data.reviewed_at.astimezone(timezone.utc),**data.model_dump(exclude={"reviewed_at"}))
    db.add(obj); db.flush(); service.audit(db,"CREATE","DoctorReview",obj,actor.id); service.commit(db); return out(obj)

@r.get("/admissions/{admission_id}/reviews")
def reviews(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id); return list_for(db,m.DoctorReview,"admission_id",admission_id)

@r.post("/admissions/{admission_id}/clinical-orders",status_code=201)
def clinical_order(admission_id:int,data:s.ClinicalOrderIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.ordered_by); service.get(db,m.Admission,admission_id); service.active_user(db,actor.id,doctor=True)
    obj=m.ClinicalOrder(admission_id=admission_id,**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","ClinicalOrder",obj,actor.id); service.commit(db); return out(obj)

@r.get("/admissions/{admission_id}/clinical-orders")
def clinical_orders(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id); return list_for(db,m.ClinicalOrder,"admission_id",admission_id)

@r.post("/admissions/{admission_id}/handovers",status_code=201)
def handover(admission_id:int,data:s.HandoverIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.sent_by); service.get(db,m.Admission,admission_id); service.active_user(db,actor.id)
    if data.received_by: service.active_user(db,data.received_by)
    obj=m.NursingHandover(admission_id=admission_id,**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","NursingHandover",obj,actor.id); service.commit(db); return out(obj)

@r.get("/admissions/{admission_id}/handovers")
def handovers(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id); return list_for(db,m.NursingHandover,"admission_id",admission_id)

@r.post("/admissions/{admission_id}/alerts",status_code=201)
def alert(admission_id:int,data:s.AlertIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id)
    obj=m.SafetyAlert(admission_id=admission_id,**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","SafetyAlert",obj,actor.id); service.commit(db); return out(obj)

@r.get("/alerts")
def alerts_all(db:Session=Depends(get_db), _:m.User=Depends(current_user)): return list_for(db,m.SafetyAlert)

@r.get("/admissions/{admission_id}/alerts")
def alerts(admission_id:int,db:Session=Depends(get_db), _:m.User=Depends(current_user)):
    service.get(db,m.Admission,admission_id); return list_for(db,m.SafetyAlert,"admission_id",admission_id)

@r.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id:int,data:s.ActorIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.actor_id)
    obj=service.get(db,m.SafetyAlert,alert_id)
    if obj.status!="OPEN": service.fail(409,"only open alerts can be acknowledged")
    obj.status="ACKNOWLEDGED"; obj.acknowledged_by=actor.id; service.audit(db,"ACKNOWLEDGE","SafetyAlert",obj,actor.id); service.commit(db); return out(obj)

@r.post("/alerts/{alert_id}/resolve")
def resolve(alert_id:int,data:s.ActorIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.actor_id)
    obj=service.get(db,m.SafetyAlert,alert_id)
    if obj.status not in {"OPEN","ACKNOWLEDGED"}: service.fail(409,"alert is already resolved")
    obj.status="RESOLVED"; obj.resolved_by=actor.id; service.audit(db,"RESOLVE","SafetyAlert",obj,actor.id); service.commit(db); return out(obj)

@r.post("/admissions/{admission_id}/discharge",status_code=201)
def discharge(admission_id:int,data:s.DischargeIn,db:Session=Depends(get_db),actor:m.User=Depends(current_user)):
    actor_matches(actor,data.discharged_by); service.active_user(db,actor.id,doctor=True)
    return out(service.discharge(db,admission_id,data,actor.id))

@r.get("/audit")
def audit_logs(db:Session=Depends(get_db), _:m.User=Depends(require_roles("ADMIN"))):
    return list_for(db,m.AuditLog)
