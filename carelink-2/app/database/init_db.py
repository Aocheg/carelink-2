"""Initialize CARELINK tables without deleting existing data.

Usage:
    python -m app.database.init_db
    python -m app.database.init_db --demo
"""
import argparse

from sqlalchemy import select

from app.core.security import hash_password
from app.database.connection import Base, engine, SessionLocal
from app.database import models as m

def init(demo: bool = False):
    Base.metadata.create_all(engine)
    if demo:
        with SessionLocal() as db:
            if db.scalar(select(m.User.id).limit(1)):
                print("Demo seed skipped: users already exist.")
                return
            admin = m.User(username="admin", password_hash=hash_password("Admin123!"), full_name="CARELINK Administrator", role="ADMIN")
            doctor = m.User(username="doctor", password_hash=hash_password("Doctor123!"), full_name="Demo Doctor", role="DOCTOR")
            nurse = m.User(username="nurse", password_hash=hash_password("Nurse123!"), full_name="Demo Nurse", role="NURSE")
            lab = m.User(username="lab", password_hash=hash_password("Lab12345!"), full_name="Demo Laboratory", role="LAB")
            facility = m.Facility(name="CARELINK Demo Hospital", description="Development/demo facility")
            db.add_all([admin, doctor, nurse, lab, facility]); db.flush()
            ward = m.Ward(facility_id=facility.id, name="General Ward")
            db.add(ward); db.flush()
            db.add_all([m.Bed(ward_id=ward.id, bed_number="A-01"), m.Bed(ward_id=ward.id, bed_number="A-02")])
            db.commit()
            print("Demo environment created.")
            print("admin / Admin123!  |  doctor / Doctor123!  |  nurse / Nurse123!  |  lab / Lab12345!")
    else:
        print("CARELINK database tables created; existing data was preserved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="create demo users and a sample facility/ward/beds")
    args = parser.parse_args()
    init(args.demo)
