from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
import re

from .cv_parser import CandidateProfile
from .job_parser import JobPosting


TAG_PATTERNS = {
    "strategy": ("strategy", "strategic", "planning", "portfolio"),
    "research": ("research", "market", "analysis", "insight", "report"),
    "operations": ("operation", "execution", "workflow", "process", "logistics", "coordination"),
    "stakeholder": ("stakeholder", "communication", "ecosystem", "partner", "event", "workshop"),
    "data_analysis": ("data analysis", "data analytics", "quantitative", "analytics", "dashboard", "analyze data"),
    "technology": ("technology", "digital", "ai", "robotics", "systems", "deep tech"),
    "finance": ("finance", "financial", "capital markets", "bond", "debt", "investment"),
    "event_management": ("event", "workshop", "training", "logistics", "coordination"),
    "marketing": ("marketing", "social media", "campaign", "influencer", "content strategy", "brand"),
    "sales": ("business development", "lead generation", "account management", "sales growth", "sales target"),
    "software_engineering": ("software engineer", "software engineering", "backend", "frontend", "api", "programming language", "programming project", "developer", "coding"),
    "accounting": ("accounting", "audit", "journal entries", "reconciliation", "monthly close", "bookkeeping"),
    "capital_markets": ("capital markets", "bond", "debt capital", "dc m"),
    "market_monitoring": ("market monitoring", "financial markets", "trading"),
    "pitch_materials": ("pitch", "marketing material", "investor presentation"),
    "robotics_data": ("robotics", "3d scanning", "data labeling", "sensor", "robot learning"),
    "financial_modeling": ("financial model", "financial modeling", "valuation", "valuations", "merger consequences"),
    "due_diligence": ("due diligence", "diligence"),
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


# Broad skills such as research and communication are useful, but a missing
# role-specific domain should matter more than a few generic keyword hits.
DOMAIN_TAGS = {
    "strategy",
    "technology",
    "finance",
    "operations",
    "capital_markets",
    "market_monitoring",
    "accounting",
    "software_engineering",
    "robotics_data",
    "financial_modeling",
    "due_diligence",
    "marketing",
    "sales",
}
SPECIFIC_DOMAIN_PENALTIES = {
    "capital_markets": 8,
    "market_monitoring": 5,
    "accounting": 7,
    "software_engineering": 10,
    "robotics_data": 10,
    "financial_modeling": 9,
    "due_diligence": 4,
    "finance": 4,
    "technology": 3,
    "marketing": 3,
    "sales": 3,
}

TAG_LABELS = {
    "strategy": "strategy and planning",
    "research": "market and company research",
    "operations": "operations and execution",
    "stakeholder": "stakeholder communication",
    "data_analysis": "data analysis",
    "technology": "technology and digital work",
    "finance": "finance-related analysis",
    "event_management": "event and program delivery",
    "marketing": "marketing and brand work",
    "sales": "sales and business development",
    "software_engineering": "software engineering",
    "accounting": "accounting and controls",
    "capital_markets": "capital-markets work",
    "market_monitoring": "financial-market monitoring",
    "pitch_materials": "pitch and client materials",
    "robotics_data": "robotics and data-collection work",
    "financial_modeling": "financial modeling and valuation",
    "due_diligence": "due-diligence work",
}

EXPLANATION_TEMPLATES = {
    "strategy": "Your strategy experience ({snippet}) maps to this role's planning and decision work.",
    "research": "Your research track record ({snippet}) matches the posting's market and company-analysis work.",
    "operations": "Your operations experience ({snippet}) supports the role's execution and coordination needs.",
    "stakeholder": "Your stakeholder work ({snippet}) fits the role's collaboration and communication demands.",
    "data_analysis": "Your analytical evidence ({snippet}) supports the role's data-driven work.",
    "technology": "Your technology exposure ({snippet}) connects to the role's digital or technology scope.",
    "finance": "Your finance-related evidence ({snippet}) is relevant to the role's financial work.",
    "event_management": "Your program-delivery experience ({snippet}) matches the role's event or coordination work.",
    "marketing": "Your marketing experience ({snippet}) supports the role's brand and customer-facing work.",
    "sales": "Your commercial experience ({snippet}) maps to the role's sales or business-development work.",
    "software_engineering": "Your programming evidence ({snippet}) is relevant to the role's engineering scope.",
    "accounting": "Your accounting evidence ({snippet}) maps to the role's controls and reporting work.",
    "capital_markets": "Your capital-markets evidence ({snippet}) matches the role's transaction and funding work.",
    "market_monitoring": "Your market-monitoring evidence ({snippet}) supports the role's financial-market work.",
    "pitch_materials": "Your presentation work ({snippet}) is relevant to the role's pitch and client-material needs.",
    "robotics_data": "Your robotics/data evidence ({snippet}) connects to the role's technical data-collection work.",
    "financial_modeling": "Your modeling evidence ({snippet}) is relevant to the role's valuation and financial-model work.",
    "due_diligence": "Your diligence experience ({snippet}) supports the role's transaction-review work.",
}

GAP_GUIDANCE = {
    "strategy": "Add the decision, framework, and measurable outcome behind one strategy project.",
    "research": "Add a concrete research example with the question, method, and decision it informed.",
    "operations": "Add an operations example showing the process you changed, your ownership, and the result.",
    "stakeholder": "Name the stakeholders you aligned, the conflict or objective, and the outcome.",
    "data_analysis": "Show what data you analyzed, which tool or method you used, and what changed because of it.",
    "technology": "Make the technology angle concrete by naming the system, product, or workflow you delivered.",
    "finance": "Add finance-specific work with the instrument, model, or transaction—not just general financial exposure.",
    "event_management": "Quantify an event or program you delivered, including scale, ownership, and result.",
    "marketing": "Add a campaign or growth example with audience, channel, and measurable outcome.",
    "sales": "Add a measurable commercial result such as pipeline, conversion, revenue, or accounts managed.",
    "software_engineering": "Surface a real programming deliverable with language, project/repository, and outcome; the current CV is mainly business-focused.",
    "accounting": "Add hands-on accounting evidence such as reconciliation, journal entries, month-end close, or variance analysis.",
    "capital_markets": "Name any debt/equity, IPO, bond, or capital-markets work you actually completed and what you analyzed.",
    "market_monitoring": "Add a market-monitoring example: what data you tracked, how often, and which decision it informed.",
    "pitch_materials": "Add a client or investor pitch example with audience, material produced, and outcome.",
    "robotics_data": "Add robotics evidence with sensors, 3D scanning, data labeling, or robot-learning datasets if you have it.",
    "financial_modeling": "Add a financial-model or valuation example with the assumptions, analysis, and decision it supported.",
    "due_diligence": "Add a diligence example showing the questions investigated, evidence reviewed, and recommendation made.",
    "power_bi": "If you have used Power BI, name the dashboard and decision it supported; otherwise leave this as a genuine gap.",
    "python": "For a technical role, show a shipped Python project rather than listing Python as a skill.",
    "java": "For a technical role, show a shipped Java project rather than listing Java as a skill.",
    "javascript": "For a technical role, show a shipped JavaScript/TypeScript project rather than listing it as a skill.",
    "git": "Link or describe a project where Git was used in a real delivery workflow.",
    "docker": "Name the project where you built or deployed a Docker image and why it was needed.",
    "accounting_degree": "The posting asks for accounting background; surface relevant coursework or accounting experience if you have it.",
    "computer_science_degree": "This posting prefers an engineering/CS degree; do not imply one—counterbalance it with a concrete programming project.",
    "business_degree": "Make the relevant degree and expected graduation date easy to find near the top.",
    "english": "State English proficiency and one example of working or presenting in English.",
    "student": "Show current enrollment and expected graduation date clearly.",
    "capital_markets_knowledge": "Add coursework or a project showing debt/equity, bonds, IPOs, or transaction analysis.",
}

LANGUAGE_GAP_GUIDANCE = {
    "chinese": "Chinese/Mandarin is an eligibility gate for this role; only claim it if you can work professionally in it.",
    "japanese": "Japanese is an eligibility gate for this role; only claim it if you can work professionally in it.",
}

METADATA_PREFIXES = (
    "profile",
    "academic focus:",
    "tools:",
    "certifications:",
    "languages:",
    "research & business skills:",
    "selected analytical methods:",
    "interests:",
)


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
    match_explanations: list[str] = field(default_factory=list)
    gap_details: list[str] = field(default_factory=list)
    penalty_points: int = 0
    penalty_reasons: list[str] = field(default_factory=list)


def _present_tags(text: str, patterns: dict[str, tuple[str, ...]]) -> set[str]:
    lowered = text.lower()
    return {tag for tag, words in patterns.items() if any(_contains_term(lowered, word) for word in words)}


def _contains_term(text: str, term: str) -> bool:
    """Match a whole word/phrase so short terms do not hit substrings."""
    escaped = re.escape(term.lower().strip()).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))


def _score_coverage(required: set[str], candidate: set[str], weight: int) -> int:
    if not required:
        return weight // 2
    return round(weight * len(required & candidate) / len(required))


def _set_coverage(required: set[str], candidate: set[str], weight: int) -> int:
    """Coverage for literal tools, where a tool is not an evidence tag."""
    if not required:
        return weight // 2
    return round(weight * len(required & candidate) / len(required))


def _normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _unique_lines(lines: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for line in lines:
        clean = _normalise_line(line)
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            unique.append(clean)
    return unique


def _is_metadata_line(line: str) -> bool:
    lowered = _normalise_line(line).casefold()
    if lowered.startswith(tuple(prefix.casefold() for prefix in METADATA_PREFIXES)):
        return True
    if lowered.startswith("global business administration b.b.a. candidate"):
        return True
    if lowered in {
        "education",
        "professional experience",
        "leadership & community building",
        "selected strategy, innovation & digital projects",
        "selected projects (continued)",
        "additional capabilities",
    }:
        return True
    return False


def _candidate_tag_strength(candidate: CandidateProfile, tag: str) -> int:
    """Return 0=missing, 1=only a supporting mention, 2=direct evidence."""
    lines = _unique_lines(candidate.evidence.get(tag, []))
    if not lines:
        return 0
    # SQL Developer is a database certification, not proof of software
    # engineering. The CV parser no longer tags it, but this guard protects
    # manually constructed CandidateProfile objects too.
    if tag == "software_engineering" and all(_contains_term(line, "sql developer") for line in lines):
        return 0
    direct = [line for line in lines if not _is_metadata_line(line)]
    return 2 if direct else 1


def _strength_fraction(strength: int) -> float:
    return {0: 0.0, 1: 0.45, 2: 1.0}.get(strength, 0.0)


def _tag_importance(tag: str) -> float:
    return 1.5 if tag in SPECIFIC_DOMAIN_PENALTIES else 1.0


def _weighted_coverage(required: set[str], candidate: CandidateProfile, weight: int) -> int:
    if not required:
        return weight // 2
    denominator = sum(_tag_importance(tag) for tag in required)
    numerator = sum(_tag_importance(tag) * _strength_fraction(_candidate_tag_strength(candidate, tag)) for tag in required)
    return round(weight * numerator / denominator) if denominator else weight // 2


def _evidence_score(candidate: CandidateProfile) -> int:
    direct_lines = {
        _normalise_line(line).casefold()
        for lines in candidate.evidence.values()
        for line in lines
        if not _is_metadata_line(line)
    }
    count = len(direct_lines)
    if count >= 10:
        return 10
    if count >= 6:
        return 8
    if count >= 3:
        return 6
    if count:
        return 4
    return 2


def _passed_core_checks(candidate: CandidateProfile, checks: set[str]) -> set[str]:
    passed: set[str] = set()
    lowered = candidate.raw_text.lower()
    if "business_degree" in checks and "b.b.a" in lowered:
        passed.add("business_degree")
    if "english" in checks and "english" in candidate.languages:
        passed.add("english")
    if "student" in checks and candidate.graduation:
        passed.add("student")
    if "japanese" in checks and "japanese" in candidate.languages:
        passed.add("japanese")
    if "chinese" in checks and "chinese" in candidate.languages:
        passed.add("chinese")
    if "capital_markets_knowledge" in checks and "capital markets" in lowered:
        passed.add("capital_markets_knowledge")
    if "computer_science_degree" in checks and any(
        _contains_term(lowered, phrase)
        for phrase in ("computer science", "computer engineering", "software engineering")
    ):
        passed.add("computer_science_degree")
    if "accounting_degree" in checks and _contains_term(lowered, "accounting"):
        passed.add("accounting_degree")
    return passed


def _infer_core_checks(text: str, required_languages: set[str], specification: dict[str, object]) -> set[str]:
    if "core_checks" in specification:
        return set(specification["core_checks"] or set())
    checks: set[str] = set()
    if "english" in required_languages or _contains_term(text, "english"):
        checks.add("english")
    if any(_contains_term(text, phrase) for phrase in ("intern", "undergraduate", "student", "graduating")):
        checks.add("student")
    if any(_contains_term(text, phrase) for phrase in ("business administration", "business degree", "business major")):
        checks.add("business_degree")
    return checks


def _grade(score: int) -> str:
    # S is reserved for a genuinely strong fit after penalties, not merely a
    # page containing a lot of generic business vocabulary.
    if score >= 90:
        return "S"
    if score >= 78:
        return "A"
    if score >= 62:
        return "B"
    return "C"


def _recommendation(score: int, blockers: Iterable[str]) -> str:
    if blockers:
        return "Hold — eligibility gap"
    if score >= 85:
        return "Apply now"
    if score >= 50:
        return "Apply after targeted CV edits"
    return "Lower priority"


def _shorten(text: str, limit: int = 175) -> str:
    clean = _normalise_line(text).strip(" .")
    if len(clean) <= limit:
        return clean
    shortened = clean[: limit - 3].rsplit(" ", 1)[0]
    return shortened.rstrip(" ,;:") + "..."


def _line_quality(line: str) -> tuple[int, int, int]:
    clean = _normalise_line(line)
    lowered = clean.casefold()
    action_words = (
        "led", "conducted", "screened", "designed", "developed", "managed", "translated",
        "interpreted", "assessed", "evaluated", "founded", "attracted", "built", "supported",
    )
    action_score = sum(1 for word in action_words if _contains_term(lowered, word))
    number_score = 1 if re.search(r"\d", clean) else 0
    return (0 if _is_metadata_line(clean) else 1, action_score + number_score, len(clean))


def _best_evidence_line(candidate: CandidateProfile, tag: str, used: set[str] | None = None) -> str | None:
    lines = _unique_lines(candidate.evidence.get(tag, []))
    used = used or set()
    available = [line for line in lines if line.casefold() not in used]
    if not available:
        return None
    return max(available, key=_line_quality)


def _ordered_tags(tags: set[str], candidate: CandidateProfile) -> list[str]:
    return sorted(tags, key=lambda tag: (-_candidate_tag_strength(candidate, tag), TAG_LABELS.get(tag, tag)))


def _build_explanations(candidate: CandidateProfile, strengths: set[str]) -> list[str]:
    explanations: list[str] = []
    used: set[str] = set()
    for tag in _ordered_tags(strengths, candidate):
        line = _best_evidence_line(candidate, tag, used)
        if not line:
            continue
        used.add(line.casefold())
        template = EXPLANATION_TEMPLATES.get(
            tag,
            "Your CV contains relevant evidence ({snippet}) for this role.",
        )
        explanations.append(template.format(snippet=_shorten(line)))
        if len(explanations) >= 4:
            break
    return explanations


def _build_evidence(candidate: CandidateProfile, strengths: set[str]) -> list[str]:
    evidence: list[str] = []
    used: set[str] = set()
    for tag in _ordered_tags(strengths, candidate):
        line = _best_evidence_line(candidate, tag, used)
        if not line:
            continue
        used.add(line.casefold())
        evidence.append(line)
        if len(evidence) >= 5:
            break
    return evidence


def _build_gap_details(
    gap_tags: Iterable[str],
    missing_checks: Iterable[str],
    blockers: Iterable[str] = (),
) -> list[str]:
    details: list[str] = []
    seen: set[str] = set()
    keys = list(gap_tags) + [check for check in sorted(missing_checks) if check not in {"japanese", "chinese"}]
    for key in keys:
        detail = GAP_GUIDANCE.get(key)
        if not detail:
            label = TAG_LABELS.get(key, key.replace("_", " "))
            detail = f"Add one bullet proving {label} with a specific action, tool, and result."
        if detail.casefold() not in seen:
            seen.add(detail.casefold())
            details.append(detail)
    for blocker in blockers:
        lowered = blocker.casefold()
        for language, detail in LANGUAGE_GAP_GUIDANCE.items():
            if language in lowered and detail.casefold() not in seen:
                seen.add(detail.casefold())
                details.append(detail)
    return details[:6]


def _specificity_penalties(
    candidate: CandidateProfile,
    domain_tags: set[str],
    job_text: str,
) -> tuple[int, list[str]]:
    points = 0
    reasons: list[str] = []
    for tag in sorted(domain_tags & set(SPECIFIC_DOMAIN_PENALTIES)):
        strength = _candidate_tag_strength(candidate, tag)
        maximum = SPECIFIC_DOMAIN_PENALTIES[tag]
        if strength == 0:
            points += maximum
            reasons.append(f"Missing direct {TAG_LABELS.get(tag, tag)} evidence (-{maximum})")
        elif strength == 1:
            penalty = max(1, round(maximum * 0.4))
            points += penalty
            reasons.append(f"Only supporting {TAG_LABELS.get(tag, tag)} evidence (-{penalty})")

    # A preferred engineering degree is not an eligibility blocker, but it
    # should prevent a business CV with no code deliverable from scoring like a
    # software-engineering candidate.
    engineering_degree_language = any(
        _contains_term(job_text, phrase)
        for phrase in (
            "engineering degree",
            "computer science degree",
            "computer engineering degree",
            "software engineering degree",
            "degree in computer science",
        )
    )
    if engineering_degree_language:
        has_adjacent_degree = any(
            _contains_term(candidate.raw_text, phrase)
            for phrase in ("computer science", "computer engineering", "software engineering", "business informatics")
        )
        if not has_adjacent_degree:
            points += 6
            reasons.append("Preferred engineering/CS degree is not evidenced (-6)")
        elif _candidate_tag_strength(candidate, "software_engineering") == 0:
            points += 3
            reasons.append("Adjacent degree but no direct programming evidence (-3)")
    return points, reasons


def assess_fit(candidate: CandidateProfile, job: JobPosting) -> FitResult:
    text = job.text.lower()
    job_tags = _present_tags(text, TAG_PATTERNS)
    candidate_tags = candidate.evidence_tags
    all_tools = _present_tags(text, TOOL_PATTERNS)
    required_languages = _present_tags(text, LANGUAGE_PATTERNS)
    specification = job.requirements or {}

    responsibility_tags = set(specification.get("responsibility_tags", job_tags))
    domain_tags = set(specification.get("domain_tags", job_tags & DOMAIN_TAGS))
    required_tools = set(specification.get("required_tools", all_tools))
    required_languages = set(specification.get("required_languages", required_languages))
    core_checks = _infer_core_checks(text, required_languages, specification)

    # Explicit degree requirements are checked separately so a preferred
    # degree lowers the score without incorrectly turning into a hard blocker.
    if any(
        _contains_term(text, phrase)
        for phrase in ("accounting degree", "accounting major")
    ):
        core_checks.add("accounting_degree")

    blockers: list[str] = []
    for language in ("japanese", "chinese"):
        if language in required_languages and language not in candidate.languages:
            blockers.append(f"Required language missing: {language.title()}")

    passed_checks = _passed_core_checks(candidate, core_checks)
    qualification_score = _score_coverage(core_checks, passed_checks, 25)
    breakdown = {
        "Role responsibilities": _weighted_coverage(responsibility_tags, candidate, 30),
        "Core qualifications": qualification_score,
        "Tools": _set_coverage(required_tools, candidate.tools, 15),
        "Domain alignment": _weighted_coverage(domain_tags, candidate, 20),
        "Evidence strength": _evidence_score(candidate),
    }

    penalty_points, penalty_reasons = _specificity_penalties(candidate, domain_tags, text)
    score = max(0, min(95, sum(breakdown.values()) - penalty_points))
    if blockers:
        # Eligibility is a separate gate: a strong-looking keyword match must
        # not wash out an explicit language requirement.
        score = min(score, 55)

    strengths_set = responsibility_tags & candidate_tags
    strength_list = _ordered_tags(strengths_set, candidate)
    gap_tags = sorted(
        (responsibility_tags - candidate_tags)
        | (domain_tags - candidate_tags)
        | (required_tools - candidate.tools)
    )
    gaps = list(gap_tags)
    gaps.extend(f"missing qualification: {check}" for check in sorted(core_checks - passed_checks))

    return FitResult(
        score=score,
        grade=_grade(score),
        recommendation=_recommendation(score, blockers),
        eligibility="Risk" if blockers else "Pass",
        blockers=blockers,
        strengths=strength_list,
        gaps=gaps,
        breakdown=breakdown,
        evidence=_build_evidence(candidate, strengths_set),
        match_explanations=_build_explanations(candidate, strengths_set),
        gap_details=_build_gap_details(gap_tags, core_checks - passed_checks, blockers),
        penalty_points=penalty_points,
        penalty_reasons=penalty_reasons,
    )
