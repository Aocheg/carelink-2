from datetime import timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.database import models as m
from app.workflows import schemas as s
from app.workflows import service

r = APIRouter(prefix="/api", tags=["carelink"])
def out(x): return service.serialise(x)
def list_for(db, cls, field=None, ident=None):
    q=select(cls) if field is None else select(cls).where(getattr(cls,field)==ident)
    return [out(x) for x in db.scalars(q).all()]
def create(db, cls, data, actor=None):
    obj=cls(**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE",cls.__name__,obj,actor); service.commit(db); return out(obj)

@r.post("/users", status_code=status.HTTP_201_CREATED)
def users(data:s.UserIn,db:Session=Depends(get_db)):
    obj=m.User(username=data.username, password_hash=service.password_hash(data.password),full_name=data.full_name,role=data.role); db.add(obj); db.flush(); service.audit(db,"CREATE","User",obj,obj.id); service.commit(db); return out(obj)
@r.get("/users")
def users_list(db:Session=Depends(get_db)): return list_for(db,m.User)
@r.post("/facilities",status_code=201)
def facilities(data:s.FacilityIn,db:Session=Depends(get_db)): return create(db,m.Facility,data)
@r.get("/facilities")
def facilities_list(db:Session=Depends(get_db)): return list_for(db,m.Facility)
@r.post("/wards",status_code=201)
def wards(data:s.WardIn,db:Session=Depends(get_db)): service.get(db,m.Facility,data.facility_id); return create(db,m.Ward,data)
@r.post("/beds",status_code=201)
def beds(data:s.BedIn,db:Session=Depends(get_db)): service.get(db,m.Ward,data.ward_id); return create(db,m.Bed,data)
@r.get("/wards/{ward_id}/beds")
def ward_beds(ward_id:int,db:Session=Depends(get_db)): return list_for(db,m.Bed,"ward_id",ward_id)

@r.post("/patients",status_code=201)
def patients(data:s.PatientIn,db:Session=Depends(get_db)):
    duplicate=db.scalar(select(m.Patient).where(m.Patient.full_name==data.full_name,m.Patient.date_of_birth==data.date_of_birth))
    obj=m.Patient(patient_number=service.numbered(db,m.Patient,"CL","patient_number"),**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","Patient",obj)
    service.commit(db); return {**out(obj),"possible_duplicate": bool(duplicate)}
@r.get("/patients")
def patients_list(db:Session=Depends(get_db)): return list_for(db,m.Patient)
@r.get("/patients/{patient_id}")
def patient(patient_id:int,db:Session=Depends(get_db)): return out(service.get(db,m.Patient,patient_id))
@r.post("/patients/{patient_id}/next-of-kin",status_code=201)
def kin(patient_id:int,data:s.KinIn,db:Session=Depends(get_db)):
    service.get(db,m.Patient,patient_id)
    if data.is_primary:
        for x in db.scalars(select(m.NextOfKin).where(m.NextOfKin.patient_id==patient_id)): x.is_primary=False
    obj=m.NextOfKin(patient_id=patient_id,**data.model_dump()); db.add(obj); db.flush(); service.commit(db); return out(obj)

@r.post("/admissions",status_code=201)
def admissions(data:s.AdmissionIn,db:Session=Depends(get_db)): return out(service.create_admission(db,data))
@r.get("/admissions/{admission_id}")
def admission(admission_id:int,db:Session=Depends(get_db)): return out(service.get(db,m.Admission,admission_id))
@r.get("/patients/{patient_id}/admissions")
def patient_admissions(patient_id:int,db:Session=Depends(get_db)): return list_for(db,m.Admission,"patient_id",patient_id)

@r.post("/admissions/{admission_id}/vitals",status_code=201)
def vitals(admission_id:int,data:s.VitalIn,db:Session=Depends(get_db)): return out(service.record_vitals(db,admission_id,data))
@r.get("/admissions/{admission_id}/vitals")
def vitals_list(admission_id:int,db:Session=Depends(get_db)): return list_for(db,m.VitalSign,"admission_id",admission_id)
@r.get("/vitals/{vital_id}")
def vital(vital_id:int,db:Session=Depends(get_db)): return out(service.get(db,m.VitalSign,vital_id))

@r.post("/admissions/{admission_id}/medications",status_code=201)
def medication(admission_id:int,data:s.MedicationOrderIn,db:Session=Depends(get_db)):
    service.get(db,m.Admission,admission_id); service.active_user(db,data.prescribed_by,doctor=True); obj=m.MedicationOrder(admission_id=admission_id,status="ACTIVE",**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","MedicationOrder",obj,data.prescribed_by); service.commit(db); return out(obj)
@r.get("/admissions/{admission_id}/medications")
def medications(admission_id:int,db:Session=Depends(get_db)): return list_for(db,m.MedicationOrder,"admission_id",admission_id)
@r.get("/medications/{order_id}")
def medication_one(order_id:int,db:Session=Depends(get_db)): return out(service.get(db,m.MedicationOrder,order_id))
@r.post("/medications/{order_id}/administrations",status_code=201)
def administration(order_id:int,data:s.AdministrationIn,db:Session=Depends(get_db)): return out(service.administer(db,order_id,data))
@r.get("/medications/{order_id}/administrations")
def administrations(order_id:int,db:Session=Depends(get_db)): return list_for(db,m.MedicationAdministration,"medication_order_id",order_id)

@r.post("/admissions/{admission_id}/investigations",status_code=201)
def investigation(admission_id:int,data:s.InvestigationIn,db:Session=Depends(get_db)):
    service.get(db,m.Admission,admission_id); service.active_user(db,data.requested_by); req=m.InvestigationRequest(admission_id=admission_id,requested_by=data.requested_by,clinical_notes=data.clinical_notes); db.add(req); db.flush()
    for test in data.tests: db.add(m.InvestigationItem(request_id=req.id,test_name=test))
    service.audit(db,"CREATE","InvestigationRequest",req,data.requested_by); service.commit(db); return out(req)
@r.get("/admissions/{admission_id}/investigations")
def investigations(admission_id:int,db:Session=Depends(get_db)): return list_for(db,m.InvestigationRequest,"admission_id",admission_id)
@r.get("/investigations/{request_id}/items")
def items(request_id:int,db:Session=Depends(get_db)): return list_for(db,m.InvestigationItem,"request_id",request_id)
@r.post("/investigation-items/{item_id}/processing")
def processing(item_id:int,data:s.ActorIn,db:Session=Depends(get_db)): service.active_user(db,data.actor_id); return out(service.transition_item(db,item_id,"PROCESSING",actor=data.actor_id))
@r.post("/investigation-items/{item_id}/result")
def result(item_id:int,data:s.ResultIn,db:Session=Depends(get_db)): return out(service.transition_item(db,item_id,"AVAILABLE",result=data))

@r.post("/admissions/{admission_id}/reviews",status_code=201)
def review(admission_id:int,data:s.ReviewIn,db:Session=Depends(get_db)):
    service.get(db,m.Admission,admission_id); service.active_user(db,data.reviewed_by,doctor=True); obj=m.DoctorReview(admission_id=admission_id,reviewed_at=data.reviewed_at.astimezone(timezone.utc),**data.model_dump(exclude={"reviewed_at"})); db.add(obj); db.flush(); service.audit(db,"CREATE","DoctorReview",obj,data.reviewed_by); service.commit(db); return out(obj)
@r.post("/admissions/{admission_id}/clinical-orders",status_code=201)
def clinical_order(admission_id:int,data:s.ClinicalOrderIn,db:Session=Depends(get_db)):
    service.get(db,m.Admission,admission_id); service.active_user(db,data.ordered_by,doctor=True); obj=m.ClinicalOrder(admission_id=admission_id,**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","ClinicalOrder",obj,data.ordered_by); service.commit(db); return out(obj)

@r.post("/admissions/{admission_id}/handovers",status_code=201)
def handover(admission_id:int,data:s.HandoverIn,db:Session=Depends(get_db)):
    service.get(db,m.Admission,admission_id); service.active_user(db,data.sent_by); 
    if data.received_by: service.active_user(db,data.received_by)
    obj=m.NursingHandover(admission_id=admission_id,**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","NursingHandover",obj,data.sent_by); service.commit(db); return out(obj)
@r.get("/admissions/{admission_id}/handovers")
def handovers(admission_id:int,db:Session=Depends(get_db)): return list_for(db,m.NursingHandover,"admission_id",admission_id)

@r.post("/admissions/{admission_id}/alerts",status_code=201)
def alert(admission_id:int,data:s.AlertIn,db:Session=Depends(get_db)):
    service.get(db,m.Admission,admission_id); obj=m.SafetyAlert(admission_id=admission_id,**data.model_dump()); db.add(obj); db.flush(); service.audit(db,"CREATE","SafetyAlert",obj); service.commit(db); return out(obj)
@r.get("/admissions/{admission_id}/alerts")
def alerts(admission_id:int,db:Session=Depends(get_db)): return list_for(db,m.SafetyAlert,"admission_id",admission_id)
@r.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id:int,data:s.ActorIn,db:Session=Depends(get_db)):
    obj=service.get(db,m.SafetyAlert,alert_id); service.active_user(db,data.actor_id)
    if obj.status!="OPEN": service.fail(409,"only open alerts can be acknowledged")
    obj.status="ACKNOWLEDGED"; obj.acknowledged_by=data.actor_id; service.audit(db,"ACKNOWLEDGE","SafetyAlert",obj,data.actor_id); service.commit(db); return out(obj)
@r.post("/alerts/{alert_id}/resolve")
def resolve(alert_id:int,data:s.ActorIn,db:Session=Depends(get_db)):
    obj=service.get(db,m.SafetyAlert,alert_id); service.active_user(db,data.actor_id)
    if obj.status not in {"OPEN","ACKNOWLEDGED"}: service.fail(409,"alert is already resolved")
    obj.status="RESOLVED"; obj.resolved_by=data.actor_id; service.audit(db,"RESOLVE","SafetyAlert",obj,data.actor_id); service.commit(db); return out(obj)

@r.post("/admissions/{admission_id}/discharge",status_code=201)
def discharge(admission_id:int,data:s.DischargeIn,db:Session=Depends(get_db)): return out(service.discharge(db,admission_id,data))
