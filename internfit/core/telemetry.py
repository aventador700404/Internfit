from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import urlparse
import uuid

from .telemetry_store import persist_analysis_event


def new_analysis_id() -> str:
    """Create a short non-identifying ID for joining related log events."""
    return uuid.uuid4().hex[:16]


def safe_url_domain(url: str) -> str:
    """Return only the hostname so query strings and paths never enter logs."""
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def emit_analysis_event(event: str, analysis_id: str, **fields: object) -> None:
    """Write one privacy-conscious JSON event to stdout for Render logs.

    Callers should pass derived fields only. In particular, never pass CV text,
    job text, filenames, full URLs, or exception messages here.
    """
    payload: dict[str, object] = {
        "event": event,
        "analysis_id": analysis_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(fields)
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True), flush=True)
    persist_analysis_event(payload)
