# CARELINK 1.0

CARELINK is an independently implemented clinical care coordination application built with **Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic 2.x and SQLite/PostgreSQL-compatible models**.

It provides one authenticated workspace for:

1. Patient registration and next-of-kin
2. Facilities, wards, beds and admissions
3. Vital signs and abnormal-vital safety alerts
4. Medication orders and administration
5. Investigations and laboratory result workflow
6. Doctor reviews and clinical orders
7. Nursing handover
8. Safety alerts and acknowledgement/resolution
9. Discharge and bed release
10. Audit logging
11. Browser workspace and OpenAPI documentation

## What changed in the finished build

The earlier CARELINK-2 handoff had the eight workflow areas but explicitly identified login/JWT authentication and request-bound role authorization as production follow-up work. This version closes that gap for the application itself:

- Passwords are stored as one-way scrypt hashes.
- Login issues short-lived signed bearer access tokens.
- Protected API endpoints require authentication.
- ADMIN, DOCTOR, NURSE, LAB and STAFF roles are supported.
- Doctor-only operations are enforced at the service boundary.
- Laboratory result entry is restricted to LAB/DOCTOR/ADMIN.
- Audit records are generated for important create, transition, alert and discharge operations.
- SQLite foreign-key enforcement is enabled.
- Datetimes are normalized to UTC through a portable SQLAlchemy type.
- The browser workspace provides setup, login, foundation, patient, admission, clinical, laboratory, safety and administration screens.
- Automated API and workflow tests cover authentication, the core admission lifecycle, abnormal-vital alerts and investigation result lifecycle.

## Architecture

`HTTP route → Pydantic validation → domain service → SQLAlchemy → database`

Routes handle HTTP/authentication concerns. Services enforce workflow rules and transaction boundaries. SQLAlchemy models are portable enough for a future PostgreSQL deployment.

## Run locally

Requires Python 3.12+.

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
# .venv\Scripts\activate

pip install -e '.[dev]'
cp .env.example .env
python -m app.database.init_db
uvicorn app.main:app --reload
```

Open:

- `http://127.0.0.1:8000/` — CARELINK browser workspace
- `http://127.0.0.1:8000/app` — same workspace
- `http://127.0.0.1:8000/docs` — interactive API
- `http://127.0.0.1:8000/redoc` — API reference
- `http://127.0.0.1:8000/health` — service health

### Fastest first-time setup

Option A — use the browser:

1. Start the server.
2. Open `/`.
3. Click **Create initial admin**.
4. Sign in.
5. Create your facility → ward → bed.
6. Register a patient.
7. Admit the patient.
8. Continue with vitals, medication, investigations, doctor review, handover, alerts and discharge.

Option B — create a complete demo environment:

```bash
python -m app.database.init_db --demo
```

Demo accounts:

```text
admin  / Admin123!
doctor / Doctor123!
nurse  / Nurse123!
lab    / Lab12345!
```

Change demo credentials before any shared deployment.

## Authentication

The initial bootstrap endpoint is available only when the database contains no users:

```http
POST /api/auth/bootstrap
```

After the first administrator exists, bootstrap is disabled.

Login:

```http
POST /api/auth/login
```

The returned bearer token must be sent as:

```http
Authorization: Bearer <token>
```

The `/api` clinical endpoints are protected.

## Core workflow rules

- A bed must belong to the selected ward and be AVAILABLE before admission.
- A patient cannot have two simultaneous ACTIVE admissions.
- Discharge is permitted only for an ACTIVE admission and releases its bed atomically.
- Vitals support COMPLETE, PARTIAL and NOT_MEASURED states.
- Blood pressure values must be supplied as a pair.
- Vitals timestamps must be timezone-aware and are normalized to UTC.
- SpO₂ below 90% or systolic BP at least 180 creates a HIGH abnormal-vital alert. This is an application escalation rule, not a substitute for clinical judgement.
- Medication administration is allowed only for ACTIVE orders.
- NOT_ADMINISTERED, REFUSED and HELD administrations require a reason.
- Investigations follow REQUESTED → PROCESSING → AVAILABLE.
- Results cannot become AVAILABLE directly from REQUESTED.
- Critical results create CRITICAL safety alerts.
- Doctor reviews, prescribing/clinical orders and discharge require an active DOCTOR.
- Laboratory result entry requires LAB, DOCTOR or ADMIN.
- Safety alerts move OPEN → ACKNOWLEDGED → RESOLVED (with OPEN → RESOLVED also supported).
- Important workflow changes are audited.

## Testing

Run:

```bash
pytest -q
```

The finished repository includes unit/workflow and API authentication tests. Tests use an isolated in-memory SQLite database and do not require the development database.

## Database

The default database is:

```text
sqlite:///./carelink.db
```

Initialization is explicit and **does not drop existing data**:

```bash
python -m app.database.init_db
```

Do not delete the database casually. For a production PostgreSQL deployment, add formal schema migrations (for example Alembic), managed secrets, backups, monitoring and deployment configuration.

## Production-readiness boundary

This repository is a **working software product/demo and development system**, not a certified clinical medical device or a substitute for a hospital's approved clinical governance.

Before real clinical deployment, the operator should still complete:

- formal clinical workflow and safety validation
- privacy/data-protection review
- PostgreSQL + migrations
- managed secret/key storage
- HTTPS/TLS and reverse proxy
- backups and disaster recovery
- structured logging and monitoring
- rate limiting and abuse protection
- stronger session/token revocation strategy
- infrastructure hardening
- role/permission review against the actual organization
- security testing/penetration testing
- data retention and audit policy
- regulatory/legal review appropriate to the deployment jurisdiction

## Project structure

```text
carelink-2/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── database/
│   │   ├── connection.py
│   │   ├── init_db.py
│   │   └── models.py
│   ├── workflows/
│   │   ├── routes.py
│   │   ├── schemas.py
│   │   └── service.py
│   └── main.py
├── frontend/
│   └── index.html
├── tests/
│   ├── test_health.py
│   ├── test_workflows.py
│   └── test_api.py
├── .env.example
├── pyproject.toml
└── README.md
```
