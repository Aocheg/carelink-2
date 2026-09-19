# CARELINK

CARELINK is an independently designed clinical-care coordination API. It supports the eight requested workflow areas: admissions, monitoring, medications, investigations, doctor review, handover, safety alerts and discharge.

## Current milestone — complete independent implementation

The application provides the requested eight workflow units via a REST API and a lightweight browser landing workspace at `/app`. It does **not** initialize, drop, or mutate database tables at import/startup time.

## Architecture

`HTTP route → Pydantic schema → domain service → SQLAlchemy session/model → database`

Each domain will own `models.py`, `schemas.py`, `service.py`, and `routes.py`; cross-cutting database, UTC timestamps, configuration, security, and audit facilities live under `app/core` and `app/database`. Routes remain thin and services own transaction boundaries. SQLite is used locally and model choices use normal foreign keys, constraints, and portable SQLAlchemy types for PostgreSQL migration.

### Proposed domain model

| Area | Core records | Key rule |
|---|---|---|
| Foundation | User, Facility, Ward, Bed, AuditLog | ward/bed scoped uniqueness; caller controls audit transaction |
| Admission | Patient, NextOfKin, Admission | available bed in selected ward; transactional occupancy |
| Monitoring | VitalSign | state-dependent completeness and paired blood pressure |
| Medication | MedicationOrder, MedicationAdministration | only active orders may be administered |
| Laboratory | InvestigationRequest, InvestigationItem, LabResult | requested → processing → result available lifecycle |
| Review | DoctorReview, ClinicalOrder | active doctor and defined order transitions |
| Handover | NursingHandover | structured sender/recipient and clinical-state fields |
| Safety | SafetyAlert | generated, acknowledged, resolved separately |
| Discharge | Discharge | only active admission; frees bed atomically |

### Assumptions

- User roles are an enum-like controlled value; authentication is a foundation concern until a real identity provider/JWT configuration is added.
- Alerts are generated only from documented rules. The first rule will be a clearly labelled abnormal-vital rule, not an undocumented clinical threshold.
- An investigation request may contain multiple requested tests; results become available only after an item is processing.
- Discharge is allowed only for an active admission and changes the linked bed to available in the same transaction.

## Roadmap

1. Foundation and database primitives — complete
2. Patients, facilities, users and admissions — complete
3. Vitals, medication, investigations, reviews, handover, alerts and discharge — complete
4. Authentication hardening (token-based identity and role enforcement at transport boundary) — future production work

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m app.database.init_db
uvicorn app.main:app --reload
```

Visit `/docs` for OpenAPI, `/app` for the frontend, and `/health` for the health response. Database table creation is an explicit development command, never automatic.

## Development log

- 2026-09-19: Completed the backend workflow implementation and initial browser workspace. Documented alert rule: SpO₂ <90% or systolic BP ≥180 generates a high-severity abnormal-vital alert.
