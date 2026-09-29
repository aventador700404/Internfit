"""Bounded, opt-in evidence records for reviewing matching mistakes.

Derived diagnostics can be logged for every analysis. Source excerpts and
model-written explanations are built separately and sent only to private DB
storage after explicit per-upload consent. No extra model call is made.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re

from .llm_client import MAX_CV_CHARS, MAX_JOB_CHARS, PROMPT_VERSION, VALIDATOR_VERSION
from .scoring import TAG_PATTERNS, _contains_term, _is_metadata_line


TRACE_VERSION = "1"
CONSENT_VERSION = "evidence-v1"
MAX_EXCERPT_CHARS = 280
MAX_EXCERPTS_PER_SOURCE = 24


@lru_cache(maxsize=1)
def engine_version() -> str:
    digest = hashlib.sha256()
    for filename in ("cv_parser.py", "job_parser.py", "scoring.py"):
        digest.update(Path(__file__).with_name(filename).read_bytes())
    return digest.hexdigest()[:12]


def build_trace_summary(candidate, job, luna, baseline, result, before, after) -> dict[str, object]:
    """Return only derived data: safe for stdout and non-consenting users."""
    semantic = luna.semantic if luna.used else {}
    semantic_tags = set(semantic.get("candidate", {}).get("semantic_evidence", {}))
    revision = os.environ.get("RENDER_GIT_COMMIT", "")
    return {
        "trace_version": TRACE_VERSION,
        "engine_version": engine_version(),
        "prompt_version": PROMPT_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "code_revision": revision if re.fullmatch(r"[a-fA-F0-9]{40}", revision) else "",
        "rule_only_score": baseline.score,
        "rule_only_breakdown": baseline.breakdown,
        "rule_only_blockers": baseline.blockers,
        "rule_only_penalty_reasons": baseline.penalty_reasons,
        "llm_score_delta": result.score - baseline.score,
        "breakdown_delta": {
            key: value - baseline.breakdown.get(key, 0)
            for key, value in result.breakdown.items()
        },
        "scoring_diagnostics": {"rule_only": before, "final": after},
        "llm_candidate_tags": sorted(semantic_tags),
        "llm_added_candidate_tags": sorted(semantic_tags - candidate.evidence_tags),
        "llm_job_overlay": semantic.get("job", {}),
        "llm_validation": luna.validation,
        "llm_source_truncated": {
            "cv": len(candidate.raw_text) > MAX_CV_CHARS,
            "job": len("\n".join((job.title, job.text))) > MAX_JOB_CHARS,
        },
    }


def _scrub_excerpt(value: str) -> str:
    """Mask obvious contacts; this does NOT make excerpts anonymous."""
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", value)
    value = re.sub(r"(?:https?://|www\.)\S+", "[link]", value, flags=re.I)
    value = re.sub(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)", "[number]", value)
    return value[:MAX_EXCERPT_CHARS] + ("…" if len(value) > MAX_EXCERPT_CHARS else "")


def build_evidence_trace(candidate, job, luna, result, diagnostics) -> dict[str, object]:
    """Build selected excerpts only. Caller must enforce consent before use."""
    excerpts: list[dict[str, str]] = []
    index: dict[tuple[str, str], str] = {}
    counts = {"cv": 0, "job": 0}
    omitted = {"cv": 0, "job": 0}

    def excerpt(source: str, text: str) -> str:
        clean = _scrub_excerpt(text)
        if not clean:
            return ""
        key = (source, clean)
        if key in index:
            return index[key]
        if counts[source] >= MAX_EXCERPTS_PER_SOURCE:
            omitted[source] += 1
            return ""
        counts[source] += 1
        reference = f"{source}-{counts[source]}"
        index[key] = reference
        excerpts.append({"id": reference, "source": source, "text": clean})
        return reference

    def refs(source: str, lines: list[str]) -> list[str]:
        return list(dict.fromkeys(ref for line in lines if (ref := excerpt(source, line))))

    semantic = luna.semantic if luna.used else {}
    llm_candidate = semantic.get("candidate", {})
    llm_evidence = llm_candidate.get("semantic_evidence", {})
    llm_strengths = llm_candidate.get("semantic_strengths", {})
    matches = [{
        "tag": item["tag"],
        "statement": _scrub_excerpt(item["statement"]),
        "cv_excerpt": excerpt("cv", item["cv_evidence"]),
    } for item in semantic.get("matches", [])[:4]]
    gaps = [{
        "tag": item["tag"],
        "suggestion": _scrub_excerpt(item["suggestion"]),
        "cv_excerpt": excerpt("cv", item["cv_evidence"]),
        "job_excerpt": excerpt("job", item["job_evidence"]),
    } for item in semantic.get("gaps", [])[:6]]

    units = re.split(r"[\r\n]+|(?<=[.!?])\s+", "\n".join((job.title, job.text)))
    requirements = diagnostics["requirements"]
    tag_evidence = []
    for tag, strength in sorted(diagnostics["candidate_tag_strengths"].items()):
        if tag not in TAG_PATTERNS:
            continue
        rule_lines = sorted(candidate.evidence.get(tag, []), key=_is_metadata_line)
        semantic_lines = llm_evidence.get(tag, [])
        contexts = [unit for unit in units if any(_contains_term(unit, term) for term in TAG_PATTERNS[tag])]
        tag_evidence.append({
            "tag": tag,
            "requirement_groups": [key for key, values in requirements.items() if tag in values],
            "final_strength": strength,
            "rule_cv_excerpts": refs("cv", rule_lines[:2]),
            "rule_evidence_count": len(rule_lines),
            "llm_cv_excerpts": refs("cv", semantic_lines[:2]),
            "llm_evidence_count": len(semantic_lines),
            "llm_tag_strength": llm_strengths.get(tag, 0),
            # Keyword context helps manual review; it does not prove that
            # the LLM sourced a semantic tag from this particular sentence.
            "job_keyword_context": refs("job", contexts[:2]),
        })

    education = refs("cv", candidate.education[:3])
    return {
        "version": TRACE_VERSION,
        "consent_version": CONSENT_VERSION,
        "job_title": _scrub_excerpt(job.title),
        "company": _scrub_excerpt(job.company),
        "excerpts": excerpts,
        "excerpt_limits": {"chars": MAX_EXCERPT_CHARS, "per_source": MAX_EXCERPTS_PER_SOURCE},
        "omitted_excerpt_count": omitted,
        "tag_evidence": tag_evidence,
        "education_excerpts": education,
        "llm_matches": matches,
        "llm_gaps": gaps,
        "displayed_matches": [_scrub_excerpt(item) for item in result.match_explanations[:4]],
        "displayed_gaps": [_scrub_excerpt(item) for item in result.gap_details[:6]],
    }
