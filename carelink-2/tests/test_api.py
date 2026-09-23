from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.connection import Base, get_db
from app.database import models as m

def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    def override():
        db = Session()
        try: yield db
        finally: db.close()
    app.dependency_overrides[get_db] = override
    return TestClient(app)

def bootstrap_login(c):
    r = c.post("/api/auth/bootstrap", json={"username":"admin","password":"Admin123!","full_name":"Admin"})
    assert r.status_code == 201
    r = c.post("/api/auth/login", json={"username":"admin","password":"Admin123!"})
    assert r.status_code == 200
    c.headers.update({"Authorization": "Bearer " + r.json()["access_token"]})

def test_auth_bootstrap_login_and_protected_api():
    c = client()
    assert c.get("/api/patients").status_code == 401
    bootstrap_login(c)
    assert c.get("/api/auth/me").json()["role"] == "ADMIN"
    assert c.get("/api/patients").status_code == 200

def test_full_api_workflow():
    c = client(); bootstrap_login(c)
    assert c.post("/api/facilities", json={"name":"General Hospital","description":"Main"}).status_code == 201
    facility = c.get("/api/facilities").json()[0]
    ward = c.post("/api/wards", json={"facility_id":facility["id"],"name":"Ward A"}).json()
    bed = c.post("/api/beds", json={"ward_id":ward["id"],"bed_number":"A-01"}).json()
    patient = c.post("/api/patients", json={
        "full_name":"Test Patient","date_of_birth":"1990-01-01","sex":"F","allergy_status":False
    }).json()
    admission = c.post("/api/admissions", json={
        "patient_id":patient["id"],"ward_id":ward["id"],"bed_id":bed["id"],
        "admitted_by":1,"source":"ER","reason_for_admission":"Observation"
    })
    assert admission.status_code == 201
    aid = admission.json()["id"]
    vital = c.post(f"/api/admissions/{aid}/vitals", json={
        "recorded_by":1,"recorded_at":datetime.now(timezone.utc).isoformat(),
        "systolic_bp":190,"diastolic_bp":100,"pulse":90,"temperature":37,
        "respiratory_rate":18,"spo2":88,"measurement_status":"COMPLETE"
    })
    assert vital.status_code == 201
    alerts = c.get("/api/alerts").json()
    assert len(alerts) == 1 and alerts[0]["severity"] == "HIGH"

    investigation = c.post(f"/api/admissions/{aid}/investigations", json={
        "requested_by":1,"tests":["FBC","Electrolytes"]
    })
    assert investigation.status_code == 201
    req_id = investigation.json()["id"]
    item = c.get(f"/api/investigations/{req_id}/items").json()[0]
    assert c.post(f"/api/investigation-items/{item['id']}/result",
                  json={"result_value":"12","is_critical":False}).status_code == 409
    assert c.post(f"/api/investigation-items/{item['id']}/processing",
                  json={"actor_id":1}).status_code == 200
    assert c.post(f"/api/investigation-items/{item['id']}/result",
                  json={"result_value":"12","is_critical":True}).status_code == 200
    assert any(a["alert_type"] == "CRITICAL_RESULT" for a in c.get("/api/alerts").json())

def test_bootstrap_can_only_run_once_and_wrong_password_fails():
    c = client(); bootstrap_login(c)
    r = c.post("/api/auth/bootstrap", json={"username":"second","password":"Admin123!","full_name":"Second"})
    assert r.status_code == 409
    c.headers.clear()
    r = c.post("/api/auth/login", json={"username":"admin","password":"wrong-password"})
    assert r.status_code == 401


def test_admission_options_only_returns_available_beds_and_invalid_ward_bed_is_rejected():
    c = client(); bootstrap_login(c)
    facility = c.post("/api/facilities", json={"name":"Options Hospital","description":"Main"}).json()
    ward_a = c.post("/api/wards", json={"facility_id":facility["id"],"name":"Ward A"}).json()
    ward_b = c.post("/api/wards", json={"facility_id":facility["id"],"name":"Ward B"}).json()
    bed_a = c.post("/api/beds", json={"ward_id":ward_a["id"],"bed_number":"A-01"}).json()
    bed_b = c.post("/api/beds", json={"ward_id":ward_b["id"],"bed_number":"B-01"}).json()
    patient = c.post("/api/patients", json={
        "full_name":"Options Patient","date_of_birth":"1992-02-02","sex":"M","allergy_status":False
    }).json()

    options = c.get("/api/admission-options")
    assert options.status_code == 200
    assert {b["id"] for b in options.json()["beds"]} == {bed_a["id"], bed_b["id"]}

    admitted = c.post("/api/admissions", json={
        "patient_id":patient["id"],"ward_id":ward_a["id"],"bed_id":bed_a["id"],
        "admitted_by":1,"source":"ER","reason_for_admission":"Observation"
    })
    assert admitted.status_code == 201

    options = c.get("/api/admission-options").json()
    assert {b["id"] for b in options["beds"]} == {bed_b["id"]}

    mismatch_patient = c.post("/api/patients", json={
        "full_name":"Mismatch Patient","date_of_birth":"1993-03-03","sex":"F","allergy_status":False
    }).json()
    mismatch = c.post("/api/admissions", json={
        "patient_id":mismatch_patient["id"],"ward_id":ward_a["id"],"bed_id":bed_b["id"],
        "admitted_by":1,"source":"ER","reason_for_admission":"Wrong pairing"
    })
    assert mismatch.status_code == 422
    assert mismatch.json()["detail"] == "bed does not belong to ward"
