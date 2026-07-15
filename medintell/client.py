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

__version__ = "0.1.1"
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

    def health(self) -> dict:
        """Authenticated connectivity check."""
        return self._http.get("/api/v1/health")
