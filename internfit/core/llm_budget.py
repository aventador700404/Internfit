"""Small, server-side budget guard for optional LLM calls.

The preferred path reserves an estimated Luna call cost through a Supabase
RPC. If the migration has not been run yet, a process-local lock still keeps
the public beta from issuing an unbounded number of calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_UP
import json
import math
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_BUDGET_USD = Decimal("1.00")
INPUT_PRICE_PER_MILLION = Decimal("0.20")
OUTPUT_PRICE_PER_MILLION = Decimal("1.20")
RESERVATION_MULTIPLIER = Decimal("1.50")
REQUEST_TIMEOUT_SECONDS = 2.0
DEFAULT_BUDGET_KEY = "mvp-luna"


@dataclass(frozen=True)
class BudgetReservation:
    allowed: bool
    mode: str
    estimated_cost_usd: float


_local_lock = threading.Lock()
_local_reserved_usd = Decimal("0")


def _budget_limit() -> Decimal:
    raw = os.environ.get("LLM_BUDGET_USD", str(DEFAULT_BUDGET_USD)).strip()
    try:
        value = Decimal(raw)
    except Exception:
        value = DEFAULT_BUDGET_USD
    return max(Decimal("0"), value)


def estimate_luna_cost(input_chars: int, max_output_tokens: int) -> float:
    """Return a conservative USD estimate used only for budget reservation."""
    # Character-to-token ratios vary by language. This deliberately assumes a
    # relatively expensive ratio and adds headroom for provider-side tokens.
    input_tokens = max(1, math.ceil(max(0, input_chars) / 2.5))
    output_tokens = max(1, max_output_tokens)
    cost = (
        (Decimal(input_tokens) / Decimal(1_000_000)) * INPUT_PRICE_PER_MILLION
        + (Decimal(output_tokens) / Decimal(1_000_000)) * OUTPUT_PRICE_PER_MILLION
    ) * RESERVATION_MULTIPLIER
    return float(cost.quantize(Decimal("0.000001"), rounding=ROUND_UP))


def _supabase_settings() -> tuple[str, str] | None:
    base_url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    # Support the current name as well as Supabase's new server-only key name.
    service_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    )
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc or not service_key:
        return None
    return base_url, service_key


def _parse_rpc_boolean(body: bytes) -> bool | None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(payload, bool):
        return payload
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, bool):
            return first
        if isinstance(first, dict):
            values = list(first.values())
            if values and isinstance(values[0], bool):
                return values[0]
    if isinstance(payload, dict):
        values = list(payload.values())
        if values and isinstance(values[0], bool):
            return values[0]
    return None


def _reserve_in_supabase(
    analysis_id: str,
    model: str,
    estimated_cost_usd: float,
) -> bool | None:
    settings = _supabase_settings()
    if settings is None:
        return None
    base_url, service_key = settings
    budget_key = os.environ.get("LLM_BUDGET_KEY", DEFAULT_BUDGET_KEY).strip() or DEFAULT_BUDGET_KEY
    request = Request(
        f"{base_url}/rest/v1/rpc/reserve_llm_budget",
        data=json.dumps(
            {
                "p_budget_key": budget_key,
                "p_analysis_id": analysis_id,
                "p_model": model,
                "p_estimated_cost_usd": estimated_cost_usd,
                "p_budget_limit_usd": float(_budget_limit()),
            },
            separators=(",", ":"),
        ).encode("utf-8"),
        method="POST",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return _parse_rpc_boolean(response.read(4096))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, TypeError):
        # A missing migration or a temporary DB issue should not make the
        # analyzer unusable; the caller falls back to the local guard.
        return None


def reserve_luna_budget(
    analysis_id: str,
    model: str,
    estimated_cost_usd: float,
) -> BudgetReservation:
    """Reserve one estimated call, preferring durable Supabase accounting."""
    estimated = max(Decimal("0.000001"), Decimal(str(estimated_cost_usd)))
    remote = _reserve_in_supabase(analysis_id, model, float(estimated))
    if remote is True:
        return BudgetReservation(True, "supabase", float(estimated))
    if remote is False:
        return BudgetReservation(False, "supabase", float(estimated))

    global _local_reserved_usd
    with _local_lock:
        if _local_reserved_usd + estimated > _budget_limit():
            return BudgetReservation(False, "process_local", float(estimated))
        _local_reserved_usd += estimated
    return BudgetReservation(True, "process_local", float(estimated))


def reset_local_budget_for_tests() -> None:
    global _local_reserved_usd
    with _local_lock:
        _local_reserved_usd = Decimal("0")
