from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import urlparse
import uuid

from .telemetry_store import SAFE_FIELDS, persist_analysis_event


def new_analysis_id() -> str:
    """Create a short non-identifying ID for joining related log events."""
    return uuid.uuid4().hex[:16]


def safe_url_domain(url: str) -> str:
    """Return only the hostname so query strings and paths never enter logs."""
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def emit_analysis_event(
    event: str,
    analysis_id: str,
    *,
    private_trace: dict[str, object] | None = None,
    **fields: object,
) -> bool:
    """Write one privacy-conscious JSON event to stdout for Render logs.

    Callers should pass derived fields only. In particular, never pass CV text,
    job text, filenames, full URLs, or exception messages as fields. Opt-in
    evidence is passed separately as private_trace and never printed.
    """
    payload: dict[str, object] = {
        "event": event,
        "analysis_id": analysis_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update({key: value for key, value in fields.items() if key in SAFE_FIELDS})
    stored = persist_analysis_event(payload, private_trace=private_trace)
    log_payload = dict(payload, storage_status="stored" if stored else "failed_or_disabled")
    print(json.dumps(log_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True), flush=True)
    return stored
