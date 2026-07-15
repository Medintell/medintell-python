# medintell

Official Python SDK for the [MedIntell REST API](https://docs.medintell.co/api/overview).
Zero third-party dependencies (standard-library only).

## Install

```bash
pip install medintell
```

## Quickstart

```python
import os
from medintell import MedIntell

mi = MedIntell(api_key=os.environ["MI_KEY"])

# Verify the connection
health = mi.health()
# {"status": "ok", "org_id": "org_3aK9Lm", "role": "manager", "facility_id": "fac_1B7dQ2"}

# Seed reference data in dependency order, reusing the returned ids
dept = mi.departments.create(name="Cardiology", facility_id="fac_1B7dQ2")
doc = mi.doctors.create(name="Dr. Shakshouka Hummusi", department_id=dept["id"], facility_id="fac_1B7dQ2")
payer = mi.payers.create(name="Falafel Assurance Co.")

patient = mi.patients.create(
    mrn="MRN-2026-00001",
    facility_id="fac_1B7dQ2",
    first_name="Kabsa",
    last_name="Al-Majboos",
    dob="1985-03-15",
    gender="M",
)

visit = mi.visits.create(
    facility_id="fac_1B7dQ2",
    patient_mrn="MRN-2026-00001",
    source_visit_id="V-2026-12345",
    visit_date="2026-06-15T10:30:00",
    type_of_visit="Consultation",
    department_id=dept["id"],
    doctor_id=doc["id"],
    payer_id=payer["payer_id"],
    total_cost=1500.0,
)
```

## Features

- **Resource model** — `mi.<resource>.<action>()` mirrors the REST API.
- **Auth** — the API key is attached to every request.
- **Idempotency** — every create sends an `Idempotency-Key` automatically; pass
  `idempotency_key=...` to make a specific retry idempotent.
- **Retries** — `429` / `5xx` / network errors retry with backoff (honours `Retry-After`).
- **Cursor pagination** — `for patient in mi.patients.iterate(): ...`.
- **Typed errors** — failures raise `MedIntellError` with `.status`, `.code`, `.request_id`.

## Pagination

```python
for patient in mi.patients.iterate(search="MRN-2026"):
    print(patient["mrno"])
```

## Errors

```python
from medintell import MedIntell, MedIntellError

try:
    mi.patients.retrieve("pat_does_not_exist")
except MedIntellError as err:
    print(err.status, err.code, err.request_id)
```

## License

MIT
