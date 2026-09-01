from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re

from .cv_parser import CandidateProfile
from .job_parser import JobPosting


TAG_PATTERNS = {
    "strategy": ("strategy", "strategic", "planning", "portfolio"),
    "research": ("research", "market", "analysis", "insight", "report"),
    "operations": ("operation", "execution", "workflow", "process", "logistics", "coordination"),
    "stakeholder": ("stakeholder", "communication", "ecosystem", "partner", "event", "workshop"),
    "data_analysis": ("data", "quantitative", "excel", "analytics", "dashboard"),
    "technology": ("technology", "digital", "ai", "robotics", "systems", "deep tech"),
    "finance": ("finance", "financial", "capital markets", "bond", "debt", "investment"),
    "event_management": ("event", "workshop", "training", "logistics", "coordination"),
    "marketing": ("marketing", "social media", "campaign", "influencer", "content strategy", "brand"),
    "sales": ("sales", "business development", "lead generation", "account management"),
    "software_engineering": ("software engineer", "software engineering", "backend", "frontend", "api", "programming", "developer", "coding"),
    "accounting": ("accounting", "audit", "journal entries", "reconciliation", "monthly close", "bookkeeping"),
    "capital_markets": ("capital markets", "bond", "debt capital", "dc m"),
    "market_monitoring": ("market monitoring", "financial markets", "trading"),
    "pitch_materials": ("pitch", "marketing material", "investor presentation"),
    "robotics_data": ("robotics", "3d scanning", "data labeling", "sensor", "robot learning"),
}

TOOL_PATTERNS = {
    "excel": ("excel",),
    "powerpoint": ("powerpoint",),
    "word": ("word",),
    "sql": ("sql",),
    "ai_tools": ("ai tool", "ai collaboration", "generative ai", "artificial intelligence"),
    "python": ("python",),
    "java": ("java",),
    "javascript": ("javascript", "typescript"),
    "git": ("git", "github"),
    "docker": ("docker",),
    "kubernetes": ("kubernetes",),
    "power_bi": ("power bi",),
    "notion": ("notion",),
    "asana": ("asana",),
    "sap": ("sap",),
    "erp": ("erp",),
    "figma": ("figma",),
}

LANGUAGE_PATTERNS = {
    "japanese": ("japanese",),
    "chinese": ("chinese", "mandarin"),
    "english": ("english",),
    "korean": ("korean",),
}


@dataclass
class FitResult:
    score: int
    grade: str
    recommendation: str
    eligibility: str
    blockers: list[str]
    strengths: list[str]
    gaps: list[str]
    breakdown: dict[str, int]
    evidence: list[str]


def _present_tags(text: str, patterns: dict[str, tuple[str, ...]]) -> set[str]:
    lowered = text.lower()
    return {tag for tag, words in patterns.items() if any(_contains_term(lowered, word) for word in words)}


def _contains_term(text: str, term: str) -> bool:
    """Match a whole word/phrase so `ai`, `git`, and `word` don't hit substrings."""
    escaped = re.escape(term.lower().strip()).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))


def _score_coverage(required: set[str], candidate: set[str], weight: int) -> int:
    if not required:
        return weight // 2
    return round(weight * len(required & candidate) / len(required))


def _passed_core_checks(candidate: CandidateProfile, checks: set[str]) -> set[str]:
    passed: set[str] = set()
    if "business_degree" in checks and "b.b.a" in candidate.raw_text.lower():
        passed.add("business_degree")
    if "english" in checks and "english" in candidate.languages:
        passed.add("english")
    if "student" in checks and candidate.graduation:
        passed.add("student")
    if "japanese" in checks and "japanese" in candidate.languages:
        passed.add("japanese")
    if "capital_markets_knowledge" in checks and "capital markets" in candidate.raw_text.lower():
        passed.add("capital_markets_knowledge")
    if "computer_science_degree" in checks and _contains_term(candidate.raw_text, "computer science"):
        passed.add("computer_science_degree")
    if "accounting_degree" in checks and _contains_term(candidate.raw_text, "accounting"):
        passed.add("accounting_degree")
    return passed


def _grade(score: int) -> str:
    if score >= 85:
        return "S"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    return "C"


def _recommendation(score: int, blockers: Iterable[str]) -> str:
    if blockers:
        return "Hold — eligibility gap"
    if score >= 80:
        return "Apply now"
    if score >= 60:
        return "Apply after targeted CV edits"
    return "Lower priority"


def assess_fit(candidate: CandidateProfile, job: JobPosting) -> FitResult:
    text = job.text.lower()
    job_tags = _present_tags(text, TAG_PATTERNS)
    candidate_tags = candidate.evidence_tags
    required_tools = _present_tags(text, TOOL_PATTERNS)
    required_languages = _present_tags(text, LANGUAGE_PATTERNS)
    specification = job.requirements or {}
    responsibility_tags = specification.get("responsibility_tags", job_tags)
    domain_tags = specification.get("domain_tags", job_tags & {"strategy", "technology", "finance", "operations"})
    required_tools = specification.get("required_tools", required_tools)
    required_languages = specification.get("required_languages", required_languages)
    core_checks = specification.get("core_checks", {"business_degree", "english"} if "english" in required_languages else {"business_degree"})
    if any(_contains_term(text, phrase) for phrase in ("computer science degree", "computer science major", "software engineering degree", "computer engineering degree")):
        core_checks = set(core_checks) | {"computer_science_degree"}
    if any(_contains_term(text, phrase) for phrase in ("accounting degree", "accounting major")):
        core_checks = set(core_checks) | {"accounting_degree"}

    blockers: list[str] = []
    for language in ("japanese", "chinese"):
        if language in required_languages and language not in candidate.languages:
            blockers.append(f"Required language missing: {language.title()}")

    passed_checks = _passed_core_checks(candidate, core_checks)
    qualification_score = _score_coverage(core_checks, passed_checks, 30)

    breakdown = {
        "Role responsibilities": _score_coverage(responsibility_tags, candidate_tags, 35),
        "Core qualifications": qualification_score,
        "Tools": _score_coverage(required_tools, candidate.tools, 10),
        "Domain alignment": _score_coverage(domain_tags, candidate_tags, 15),
        "Evidence strength": 10 if len(candidate.evidence_tags) >= 6 else 7,
    }
    score = sum(breakdown.values())
    if blockers:
        score = min(score, 55)

    strengths = sorted(responsibility_tags & candidate_tags)
    gaps = sorted((responsibility_tags - candidate_tags) | (required_tools - candidate.tools))
    gaps.extend(f"missing qualification: {check}" for check in sorted(core_checks - passed_checks))
    evidence = []
    for tag in strengths:
        evidence.extend(candidate.evidence.get(tag, [])[:1])
    return FitResult(
        score=score,
        grade=_grade(score),
        recommendation=_recommendation(score, blockers),
        eligibility="Risk" if blockers else "Pass",
        blockers=blockers,
        strengths=strengths,
        gaps=gaps,
        breakdown=breakdown,
        evidence=evidence[:5],
    )
