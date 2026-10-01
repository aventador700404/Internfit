"""Bounded, process-local reuse of validated Luna results; never CV files/text.

Keys are content digests kept only in memory. Current-request metadata,
consent, telemetry, and deterministic scoring remain outside this cache.
"""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass
import hashlib
import json
import threading
import time
from typing import Callable

from .llm_client import (
    MAX_CV_CHARS, MAX_JOB_CHARS, MAX_OUTPUT_TOKENS, PROMPT_VERSION,
    VALIDATOR_VERSION, LunaResult,
)


CACHE_TTL_SECONDS = 30 * 60


def analysis_cache_key(candidate, job, *, model: str, engine_version: str) -> str:
    """Use exact parser output: source IDs/quotes must resolve identically."""
    digest = hashlib.sha256()
    parts = (
        "luna-cache-v1", model, engine_version, PROMPT_VERSION,
        VALIDATOR_VERSION, str((MAX_CV_CHARS, MAX_JOB_CHARS, MAX_OUTPUT_TOKENS)),
        candidate.raw_text, job.title, job.text,
    )
    for part in parts:
        encoded = part.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


class AnalysisBusyError(Exception):
    """Bound the pending-key table and wait time without duplicate AI calls."""


@dataclass
class CachedAnalysis:
    luna: LunaResult
    status: str
    age_seconds: int = 0


class AnalysisCache:
    def __init__(
        self, *, ttl_seconds: float = CACHE_TTL_SECONDS,
        max_entries: int = 100, max_bytes: int = 4 * 1024 * 1024,
        max_entry_bytes: int = 64 * 1024, max_inflight: int = 32,
        wait_seconds: float = 30, clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.max_entry_bytes = max_entry_bytes
        self.max_inflight = max_inflight
        self.wait_seconds = wait_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._bytes = 0
        self._inflight: dict[str, Future] = {}

    def _prune_locked(self, now: float) -> None:
        for key, (created_at, blob) in list(self._entries.items()):
            if now - created_at >= self.ttl_seconds:
                self._entries.pop(key)
                self._bytes -= len(blob)

    def prune(self) -> None:
        # Also called by the HTTP server loop, even without new analyses.
        with self._lock:
            self._prune_locked(self._clock())

    def _reused(self, blob: bytes, created_at: float, status: str) -> CachedAnalysis:
        return CachedAnalysis(
            LunaResult(**json.loads(blob)), status,
            max(0, int(self._clock() - created_at)),
        )

    def get_or_compute(self, key: str, compute: Callable[[], LunaResult]) -> CachedAnalysis:
        with self._lock:
            self._prune_locked(self._clock())
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
                return self._reused(entry[1], entry[0], "hit")
            future = self._inflight.get(key)
            owner = future is None
            if owner:
                if len(self._inflight) >= self.max_inflight:
                    raise AnalysisBusyError("The analyzer is busy. Please try again shortly.")
                future = Future()
                self._inflight[key] = future

        if not owner:
            try:
                blob, created_at = future.result(timeout=self.wait_seconds)
            except FutureTimeout as exc:
                raise AnalysisBusyError(
                    "This analysis is still running. Please try again shortly."
                ) from exc
            return self._reused(blob, created_at, "shared")

        try:
            luna = compute()
            # Only bounded, validated outputs travel to a waiter/cache. Each
            # reuse gets a fresh object and zero new tokens/cost/reservations.
            reusable = LunaResult(
                status="cached" if luna.used else luna.status,
                model=luna.model, semantic=luna.semantic, used=luna.used,
                validation=luna.validation,
                validation_summary=luna.validation_summary,
                error_type=luna.error_type,
                budget_mode="cache" if luna.used else "shared",
            )
            blob = json.dumps(asdict(reusable), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            created_at = self._clock()
            with self._lock:
                self._prune_locked(created_at)
                if (
                    luna.used and luna.status == "used"
                    and len(blob) <= min(self.max_entry_bytes, self.max_bytes)
                    and self.max_entries > 0
                ):
                    while self._entries and (
                        len(self._entries) >= self.max_entries
                        or self._bytes + len(blob) > self.max_bytes
                    ):
                        _, (_, removed) = self._entries.popitem(last=False)
                        self._bytes -= len(removed)
                    self._entries[key] = (created_at, blob)
                    self._bytes += len(blob)
                # Share even an unsuccessful response with current waiters,
                # but never retain it: the next attempt can recover normally.
                future.set_result((blob, created_at))
                self._inflight.pop(key, None)
            return CachedAnalysis(luna, "miss")
        except BaseException as exc:
            with self._lock:
                future.set_exception(exc)
                self._inflight.pop(key, None)
            raise
