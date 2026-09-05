"""Optional durable storage for privacy-conscious analysis telemetry.

The beta keeps Render stdout logs as the fallback. When Supabase credentials
are configured on the server, the same derived event is appended to a private
Postgres table through Supabase's REST Data API.
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid


TABLE_NAME = "analysis_events"
REQUEST_TIMEOUT_SECONDS = 2.0
ALLOWED_EVENTS = {"analysis_completed", "analysis_blocked", "analysis_error"}

# This is an allowlist rather than a blacklist. If a caller accidentally adds
# a new field later, it will not silently become durable user data.
SAFE_FIELDS = {
    "duration_ms",
    "cv_format",
    "cv_size_bytes",
    "candidate_tags",
    "candidate_languages",
    "candidate_tools",
    "candidate_evidence_tag_count",
    "education_detected",
    "graduation_detected",
    "analysis_source",
    "job_fetch_status",
    "job_domain",
    "job_text_chars",
    "job_title_chars",
    "company_known",
    "score",
    "grade",
    "recommendation",
    "decision",
    "eligibility",
    "breakdown",
    "penalty_points",
    "penalty_reasons",
    "strengths",
    "gaps",
    "blockers",
    "error_type",
    "status",
    "reason",
    "llm_status",
    "llm_used",
    "llm_model",
    "llm_input_chars",
    "llm_output_chars",
    "llm_input_tokens",
    "llm_output_tokens",
    "llm_estimated_cost_usd",
    "llm_budget_mode",
    "llm_error_type",
}


def _settings() -> tuple[str, str] | None:
    base_url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or not service_key:
        return None
    return base_url, service_key


def build_storage_row(payload: Mapping[str, object]) -> dict[str, object] | None:
    """Build the only shape allowed to leave the application for storage."""
    event = str(payload.get("event", ""))
    analysis_id = str(payload.get("analysis_id", ""))
    if event not in ALLOWED_EVENTS or not analysis_id:
        return None

    safe_payload = {
        key: payload[key]
        for key in SAFE_FIELDS
        if key in payload
    }
    return {
        "event_id": uuid.uuid4().hex,
        "analysis_id": analysis_id,
        "event": event,
        "occurred_at": str(payload.get("timestamp", "")),
        "payload": safe_payload,
    }


def persist_analysis_event(payload: Mapping[str, object]) -> bool:
    """Append one event to Supabase, returning False on disabled/failed storage.

    Persistence is deliberately best-effort: a database outage must never make
    an otherwise valid CV analysis fail. Error details are not emitted because
    they can contain provider response data.
    """
    settings = _settings()
    if settings is None:
        return False
    row = build_storage_row(payload)
    if row is None:
        return False

    base_url, service_key = settings
    request = Request(
        f"{base_url}/rest/v1/{TABLE_NAME}",
        data=json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS):
            return True
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        return False
