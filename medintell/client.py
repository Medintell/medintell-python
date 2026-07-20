"""MedIntell — official Python client for the MedIntell REST API.

Zero third-party dependencies (standard-library ``urllib``).
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request

__version__ = "0.4.0"
import uuid
from typing import Any, Iterator

DEFAULT_BASE_URL = "https://api.medintell.co"


class MedIntellError(Exception):
    """Raised on any non-2xx API response or transport failure."""

    def __init__(self, message: str, *, status: int | None = None, code: str | None = None,
                 type: str | None = None, request_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.type = type
        self.request_id = request_id


class _Http:
    def __init__(self, api_key: str, base_url: str, timeout: float, max_retries: int):
        if not api_key:
            raise MedIntellError("api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries

    def request(self, method: str, path: str, *, query: dict | None = None,
                body: Any | None = None, idempotency_key: str | None = None) -> Any:
        url = self._base_url + path
        if query:
            clean = {k: v for k, v in query.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)

        data = json.dumps(body).encode() if body is not None else None
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            # Explicit UA — WAFs (e.g. Cloudflare) commonly block the default
            # Python-urllib/x.y agent outright.
            "User-Agent": f"medintell-python/{__version__}",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        if method == "POST":
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())

        attempt = 0
        while True:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    raw = resp.read().decode()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    if attempt < self._max_retries:
                        retry_after = e.headers.get("Retry-After")
                        time.sleep(float(retry_after) if retry_after else 2 ** attempt * 0.2 + random.random() * 0.1)
                        attempt += 1
                        continue
                raw = e.read().decode() if e.fp else ""
                payload = json.loads(raw) if raw else {}
                err = payload.get("error", {}) if isinstance(payload, dict) else {}
                raise MedIntellError(
                    err.get("message") or f"HTTP {e.code}",
                    status=e.code,
                    code=err.get("code"),
                    type=err.get("type"),
                    request_id=err.get("request_id") or e.headers.get("X-Request-ID"),
                ) from None
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < self._max_retries:
                    time.sleep(2 ** attempt * 0.2 + random.random() * 0.1)
                    attempt += 1
                    continue
                raise MedIntellError(f"network error: {e}") from None

    def get(self, path, query=None):
        return self.request("GET", path, query=query)

    def post(self, path, body=None, idempotency_key=None):
        return self.request("POST", path, body=body, idempotency_key=idempotency_key)

    def put(self, path, body=None):
        return self.request("PUT", path, body=body)


class _Resource:
    def __init__(self, http: _Http, base: str):
        self._http = http
        self._base = base

    def iterate(self, **query) -> Iterator[dict]:
        """Yield every row, walking pages via the cursor."""
        cursor = ""  # empty cursor = keyset mode from page one
        while True:
            page = self._http.get(self._base, {"limit": 200, "cursor": cursor, **query})
            for row in page.get("data", []):
                yield row
            if not page.get("has_more") or not page.get("next_cursor"):
                return
            cursor = page["next_cursor"]


class _Organizations(_Resource):
    def list(self):
        return self._http.get(self._base)

    def retrieve(self, org_id):
        return self._http.get(f"{self._base}/{org_id}")


class _Facilities(_Resource):
    def list(self):
        return self._http.get(self._base)

    def create(self, *, org_id, **body):
        return self._http.post(f"/api/v1/organizations/{org_id}/branches", body)


class _Departments(_Resource):
    def list(self, **query):
        return self._http.get(self._base, query)

    def retrieve(self, department_id):
        return self._http.get(f"{self._base}/{department_id}")

    def create(self, *, idempotency_key=None, **body):
        return self._http.post(self._base, body, idempotency_key)

    def update(self, department_id, **body):
        return self._http.put(f"{self._base}/{department_id}", body)

    def kpis(self, **query):
        return self._http.get(f"{self._base}/kpis", query)


class _Doctors(_Resource):
    def list(self, **query):
        return self._http.get(self._base, query)

    def retrieve(self, doctor_id):
        return self._http.get(f"{self._base}/{doctor_id}")

    def create(self, *, idempotency_key=None, **body):
        return self._http.post(self._base, body, idempotency_key)

    def update(self, doctor_id, **body):
        return self._http.put(f"{self._base}/{doctor_id}", body)

    def kpis(self, **query):
        return self._http.get(f"{self._base}/kpis", query)


class _Payers(_Resource):
    def list(self, **query):
        return self._http.get(self._base, query)

    def retrieve(self, payer_id):
        return self._http.get(f"{self._base}/{payer_id}")

    def create(self, *, idempotency_key=None, **body):
        return self._http.post(self._base, body, idempotency_key)

    def update(self, payer_id, **body):
        return self._http.put(f"{self._base}/{payer_id}", body)


class _Patients(_Resource):
    def list(self, **query):
        return self._http.get(self._base, query)

    def retrieve(self, patient_id):
        return self._http.get(f"{self._base}/{patient_id}")

    def create(self, *, idempotency_key=None, **body):
        return self._http.post(self._base, body, idempotency_key)

    def update(self, patient_id, **body):
        return self._http.put(f"{self._base}/{patient_id}", body)

    def screening_eligibility(self, patient_id):
        return self._http.get(f"{self._base}/{patient_id}/screening-eligibility")

    def screening_matches(self, patient_id):
        return self._http.get(f"{self._base}/{patient_id}/screening-matches")

    def vbc_eligibility(self, patient_id):
        return self._http.get(f"{self._base}/{patient_id}/vbc-eligibility")

    def vbc_enrollments(self, patient_id):
        return self._http.get(f"{self._base}/{patient_id}/vbc-enrollments")


class _Visits(_Resource):
    def list(self, **query):
        return self._http.get(self._base, query)

    def stats(self):
        return self._http.get(f"{self._base}/stats")

    def create(self, *, idempotency_key=None, **body):
        return self._http.post(self._base, body, idempotency_key)

    def update(self, visit_id, **body):
        return self._http.put(f"{self._base}/{visit_id}", body)

    def correct_diagnosis(self, visit_id, **body):
        return self._http.put(f"{self._base}/{visit_id}/diagnoses", body)


class _Ingest:
    def __init__(self, http: _Http):
        self._http = http

    def patients(self, *, idempotency_key=None, **body):
        return self._http.post("/api/v1/ingest/patients", body, idempotency_key)

    def schema(self):
        return self._http.get("/api/v1/ingest/schema")


class _Analytics:
    """Analysis Hub — the same aggregates the MedIntell dashboard shows.

    Overviews accept the shared filter set (lists become comma-separated):
    start_date, end_date, branch_id, department_ids, doctor_ids, genders,
    age_min, age_max, visit_types, visit_modes, payers, payment_types,
    marital_statuses, nationalities, smoker, segment_id, mdc_code.
    Id filters take the numeric ids returned by ``filter_options()``.
    financial/operational/data_range/filter_options and the two main
    overviews need an analyst+ credential.
    """

    def __init__(self, http: _Http):
        self._http = http
        self._base = "/api/v1/analytics"

    @staticmethod
    def _q(query: dict) -> dict:
        return {
            k: ",".join(str(x) for x in v) if isinstance(v, (list, tuple)) else v
            for k, v in query.items()
            if v is not None
        }

    def overview(self, **query):
        """Headline KPIs: visits, patients, revenue, readmission/revisit rates."""
        return self._http.get(f"{self._base}/overview", self._q(query))

    def clinical(self, **query):
        """Top ICD categories and chronic disease burden."""
        return self._http.get(f"{self._base}/clinical/overview", self._q(query))

    def demographics(self, **query):
        """Gender / nationality / age / BMI distributions (disease_name profiles one condition)."""
        return self._http.get(f"{self._base}/demographics/overview", self._q(query))

    def financial(self, **query):
        """Revenue totals, average cost, revenue per patient."""
        return self._http.get(f"{self._base}/financial/overview", self._q(query))

    def operational(self, **query):
        """Total visits, unique patients, doctors, departments."""
        return self._http.get(f"{self._base}/operational/overview", self._q(query))

    def patients(self, **query):
        """Drill-down patient line list (page/limit, search, risk_level, disease_name)."""
        return self._http.get(f"{self._base}/patients", self._q(query))

    def data_range(self, **query):
        """Years/months that actually have visit data — call before picking dates."""
        return self._http.get(f"{self._base}/data-range", self._q(query))

    def filter_options(self, dimension, **query):
        """Valid values (with counts) for a filter dimension, e.g. 'department_ids'."""
        return self._http.get(f"{self._base}/filter-options/{dimension}", self._q(query))

    _REPORT_PATHS = {
        "payer": "financial/payer",
        "payment_type": "financial/payment-type",
        "revenue_trends": "financial/revenue-trends",
        "gender": "demographics/gender",
        "age_group": "demographics/age-group",
        "nationality": "demographics/nationality",
        "bmi": "demographics/bmi",
        "visit_mode": "service/visit-mode",
        "visit_type": "service/visit-type",
        "patient_type": "service/patient-type",
        "appointment_mode": "service/appointment-mode",
        "registered_at_hospital": "service/registered-at-hospital",
        "departments": "performance/departments",
        "physicians": "performance/physicians",
        "physicians_per_department": "performance/physicians-per-department",
        "physician_visit_time": "performance/physician-visit-time",
        "average_los": "utilization/average-los",
        "average_lov": "utilization/average-lov",
        "waiting_time": "utilization/waiting-time",
    }

    def analysis(self, report, **query):
        """Run any Analysis Hub report — returns {items, stats}.

        bmi, physicians_per_department, average_los, average_lov and
        waiting_time need an analyst+ credential.
        """
        path = self._REPORT_PATHS.get(report)
        if path is None:
            raise MedIntellError(f"unknown analysis report: {report}")
        return self._http.get(f"{self._base}/{path}", self._q(query))

    def disease_prevalence(self, *, disease_name, **query):
        """Disease prevalence vs city/national estimates."""
        return self._http.get(
            f"{self._base}/clinical/disease-prevalence-analysis",
            self._q({"disease_name": disease_name, **query}),
        )


class _Vbc:
    def __init__(self, http: _Http):
        self._http = http
        self._base = "/api/v1/vbc"

    def patient_journeys(self, patient):
        """All VBC journeys for a patient. patient = pat_… id or 'mrn:<MRN>'."""
        return self._http.get(f"{self._base}/patients/{patient}/journeys")

    def patient_due(self, patient):
        """Point-of-care: what this patient owes now, with fill links."""
        return self._http.get(f"{self._base}/patients/{patient}/due")

    def patient_eligibility(self, patient):
        return self._http.get(f"{self._base}/patients/{patient}/eligibility")

    def enroll(self, patient, *, program_id, index_date=None):
        body = {"program_id": program_id}
        if index_date is not None:
            body["index_date"] = index_date
        return self._http.post(f"{self._base}/patients/{patient}/journeys", body)

    def decline(self, journey_id, *, reason=None):
        return self._http.post(f"{self._base}/journeys/{journey_id}/decline", {"reason": reason})

    def defer_item(self, journey_id, task_id, *, until):
        return self._http.post(f"{self._base}/journeys/{journey_id}/items/{task_id}/defer", {"until": until})

    def decline_item(self, journey_id, task_id, *, reason=None):
        return self._http.post(f"{self._base}/journeys/{journey_id}/items/{task_id}/decline", {"reason": reason})

    def worklist(self, **query):
        return self._http.get(f"{self._base}/journeys/items", query)

    def programs(self, **query):
        """List the org's VBC programs (discover program ids to enroll into)."""
        return self._http.get("/api/v1/vbc/programs", query)

    def events(self, **query):
        return self._http.get(f"{self._base}/events", query)


class _Screening:
    def __init__(self, http: _Http):
        self._http = http
        self._base = "/api/v1/screening"

    def patient_statuses(self, patient):
        """All screening statuses for a patient. patient = pat_… id or 'mrn:<MRN>'."""
        return self._http.get(f"{self._base}/patients/{patient}/statuses")

    def worklist(self, **query):
        """Org action list. status=eligible|overdue|notified|completed|declined|deferred."""
        return self._http.get(f"{self._base}/worklist", query)

    def notified(self, status_id):
        return self._http.post(f"{self._base}/statuses/{status_id}/notified", {})

    def report(self, status_id, *, completed_on=None):
        return self._http.post(f"{self._base}/statuses/{status_id}/report", {"completed_on": completed_on})

    def defer(self, status_id, *, until):
        return self._http.post(f"{self._base}/statuses/{status_id}/defer", {"until": until})

    def decline(self, status_id, *, reason=None):
        return self._http.post(f"{self._base}/statuses/{status_id}/decline", {"reason": reason})

    def exclude(self, status_id, *, reason=None, until=None):
        return self._http.post(f"{self._base}/statuses/{status_id}/exclude", {"reason": reason, "until": until})

    def criteria(self, **query):
        """List the org's screening criteria (discover criteria ids)."""
        return self._http.get("/api/v1/population-screening/criteria", query)

    def events(self, **query):
        return self._http.get(f"{self._base}/events", query)


class MedIntell:
    """Entry point. ``MedIntell(api_key=...)`` then ``client.<resource>.<action>()``."""

    def __init__(self, api_key: str, *, base_url: str = DEFAULT_BASE_URL,
                 timeout: float = 30.0, max_retries: int = 2):
        http = _Http(api_key, base_url, timeout, max_retries)
        self._http = http
        self.organizations = _Organizations(http, "/api/v1/organizations")
        self.facilities = _Facilities(http, "/api/v1/branches")
        self.departments = _Departments(http, "/api/v1/departments")
        self.doctors = _Doctors(http, "/api/v1/doctors")
        self.payers = _Payers(http, "/api/v1/payers")
        self.patients = _Patients(http, "/api/v1/patients")
        self.visits = _Visits(http, "/api/v1/visits")
        self.ingest = _Ingest(http)
        self.analytics = _Analytics(http)
        self.vbc = _Vbc(http)
        self.screening = _Screening(http)

    def health(self) -> dict:
        """Authenticated connectivity check."""
        return self._http.get("/api/v1/health")
