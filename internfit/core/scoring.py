from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
import re

from .cv_parser import CandidateProfile
from .job_parser import (
    JOB_CONTENT_HEADINGS,
    JOB_FOOTER_HEADINGS,
    JobPosting,
    focus_job_content,
)


TAG_PATTERNS = {
    "strategy": ("strategy", "strategic", "planning", "portfolio", "전략", "전략기획", "사업전략", "경영전략", "기획"),
    "research": ("research", "market", "analysis", "insight", "report", "리서치", "시장조사", "시장 분석", "시장분석", "분석", "보고서"),
    "operations": ("operation", "execution", "workflow", "process", "logistics", "coordination", "운영", "운영관리", "프로세스", "업무개선", "실행", "조율"),
    "stakeholder": ("stakeholder", "communication", "ecosystem", "partner", "event", "workshop", "이해관계자", "유관부서", "파트너", "커뮤니케이션", "협업", "행사", "워크숍"),
    "data_analysis": ("data analysis", "data analytics", "quantitative", "analytics", "dashboard", "analyze data", "데이터 분석", "데이터분석", "데이터", "정량분석", "통계", "대시보드"),
    "technology": ("technology", "digital", "ai", "robotics", "systems", "deep tech", "기술", "디지털", "인공지능", "생성형 ai", "로보틱스", "시스템", "자동화"),
    "finance": ("finance", "financial", "capital markets", "bond", "debt", "investment", "금융", "재무", "자본시장", "채권", "부채", "투자", "인수합병"),
    "event_management": (
        "event planning",
        "event management",
        "event coordination",
        "event logistics",
        "organize events",
        "organise events",
        "workshop planning",
        "workshop coordination",
        "training coordination",
        "행사기획",
        "행사 운영",
        "이벤트 운영",
        "교육 운영",
    ),
    "marketing": ("marketing", "social media", "campaign", "influencer", "content strategy", "brand", "마케팅", "소셜미디어", "캠페인", "인플루언서", "콘텐츠", "브랜딩"),
    "sales": ("business development", "lead generation", "account management", "sales growth", "sales target", "영업", "사업개발", "리드 발굴", "고객관리"),
    "software_engineering": ("software engineer", "software engineering", "backend", "frontend", "api", "programming language", "programming project", "developer", "coding", "소프트웨어 개발", "백엔드", "프론트엔드", "애플리케이션 개발", "프로그래밍", "코딩", "개발 프로젝트"),
    "mcp_integration": ("mcp", "model context protocol", "rest api", "api integration", "mcp server", "mcp client", "모델 컨텍스트 프로토콜", "api 연동", "시스템 연동"),
    "accounting": ("accounting", "audit", "journal entries", "reconciliation", "monthly close", "bookkeeping", "회계", "감사", "분개", "조정", "월말 마감", "장부"),
    "capital_markets": ("capital markets", "bond", "debt capital", "dc m", "자본시장", "채권발행", "채권", "부채자본"),
    "market_monitoring": ("market monitoring", "financial markets", "trading", "시장 모니터링", "금융시장", "시장 동향", "트레이딩"),
    "pitch_materials": ("pitch", "marketing material", "investor presentation", "피치", "마케팅 자료", "투자자 프레젠테이션", "제안서"),
    "robotics_data": ("robotics", "3d scanning", "data labeling", "sensor", "robot learning", "로보틱스", "3d 스캐닝", "데이터 라벨링", "센서", "로봇 학습"),
    "financial_modeling": ("financial model", "financial modeling", "valuation", "valuations", "merger consequences", "재무 모델", "재무 모델링", "밸류에이션", "기업가치평가"),
    "due_diligence": ("due diligence", "diligence", "실사", "기업실사"),
}

TOOL_PATTERNS = {
    "excel": ("excel", "엑셀"),
    "powerpoint": ("powerpoint", "파워포인트", "ppt", "피피티"),
    "word": ("word", "워드"),
    "sql": ("sql", "sqld", "에스큐엘"),
    "ai_tools": ("ai tool", "ai collaboration", "generative ai", "artificial intelligence", "생성형 ai", "생성형 인공지능", "프롬프트", "llm"),
    "python": ("python", "파이썬"),
    "java": ("java", "자바"),
    "javascript": ("javascript", "typescript", "자바스크립트", "타입스크립트"),
    "git": ("git", "github"),
    "docker": ("docker", "도커"),
    "kubernetes": ("kubernetes", "쿠버네티스"),
    "power_bi": ("power bi", "파워 bi"),
    "notion": ("notion", "노션"),
    "asana": ("asana", "아사나"),
    "sap": ("sap",),
    "erp": ("erp", "전사적 자원관리"),
    "figma": ("figma", "피그마"),
}

LANGUAGE_PATTERNS = {
    "japanese": ("japanese", "일본어", "jlpt"),
    "chinese": ("chinese", "mandarin", "중국어", "만다린", "hsk"),
    "english": ("english", "영어", "토익", "토플", "토스", "오픽", "teps"),
    "korean": ("korean", "한국어", "국어", "모국어"),
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
    "mcp_integration",
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
    "mcp_integration": 12,
}

STRICT_DOMAIN_TAGS = {
    "strategy",
    "operations",
    "technology",
    "finance",
    "marketing",
    "sales",
    "capital_markets",
    "market_monitoring",
    "accounting",
    "software_engineering",
    "robotics_data",
    "financial_modeling",
    "due_diligence",
    "mcp_integration",
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
    "mcp_integration": "MCP and API integration",
}

EXPLANATION_TEMPLATES = {
    "strategy": "Planning fit: {snippet} — relevant to the role's strategy and decision work.",
    "research": "Research overlap: {snippet} — supports the posting's market or company-analysis needs.",
    "operations": "Execution evidence: {snippet} — relevant to this role's process and delivery work.",
    "stakeholder": "Collaboration evidence: {snippet} — maps to the role's stakeholder-facing work.",
    "data_analysis": "Analytical evidence: {snippet} — supports the posting's data-driven tasks.",
    "technology": "Technology overlap: {snippet} — connects to the role's digital or systems scope.",
    "finance": "Finance relevance: {snippet} — gives the application a basis for the role's financial work.",
    "event_management": "Program-delivery evidence: {snippet} — matches the role's event or coordination needs.",
    "marketing": "Marketing overlap: {snippet} — supports the role's brand or customer-facing work.",
    "sales": "Commercial evidence: {snippet} — relates to the role's sales or business-development goals.",
    "software_engineering": "Engineering proof: {snippet} — relevant to the role's software-development scope.",
    "accounting": "Accounting proof: {snippet} — maps to the role's controls and reporting work.",
    "capital_markets": "Transaction relevance: {snippet} — connects to the role's funding and markets work.",
    "market_monitoring": "Markets overlap: {snippet} — supports the posting's monitoring and analysis tasks.",
    "pitch_materials": "Presentation proof: {snippet} — relevant to the role's pitch and client-material needs.",
    "robotics_data": "Technical-data overlap: {snippet} — connects to the role's robotics and collection work.",
    "financial_modeling": "Modeling relevance: {snippet} — supports the posting's valuation or forecast work.",
    "due_diligence": "Diligence overlap: {snippet} — relevant to the role's transaction-review needs.",
    "mcp_integration": "Integration proof: {snippet} — relevant to the role's MCP/API integration scope.",
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
    "graduate_technical_degree": "This role's minimum qualification is a currently enrolled graduate degree in a technical field; a business bachelor's degree does not satisfy it.",
    "mcp_integration": "Show a real MCP, REST API, server/client, or systems-integration deliverable; generic AI interest is not equivalent.",
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
    "summary:",
    "professional summary:",
    "academic focus:",
    "skills:",
    "technical skills:",
    "core competencies:",
    "tools:",
    "certifications:",
    "languages:",
    "research & business skills:",
    "selected analytical methods:",
    "interests:",
    "프로필",
    "요약:",
    "경력 요약:",
    "학력:",
    "교육:",
    "기술:",
    "보유 기술:",
    "자격증:",
    "언어:",
    "역량:",
    "관심 분야:",
)

OPTIONAL_CUES = (
    "preferred",
    "preferably",
    "nice to have",
    "nice-to-have",
    "a plus",
    "bonus",
    "advantage",
    "desired",
    "ideally",
    "not required",
    "optional",
    "우대",
    "우대함",
    "우대합니다",
    "있으면 좋음",
    "있으시면",
    "플러스",
    "가산점",
    "선호",
    "무방",
    "관계없음",
    "무관",
    "필수 아님",
    "권장",
)

PREFERRED_SECTION_HEADINGS = (
    "preferred qualification",
    "preferred qualifications",
    "nice to have",
    "nice-to-have",
    "desired qualification",
    "desired qualifications",
    "bonus qualification",
    "bonus qualifications",
    "additional qualification",
    "additional qualifications",
    "우대사항",
    "우대조건",
    "우대요건",
    "이런 분이면 더 좋아요",
    "이런 경험이 있으면 좋아요",
    "플러스 요인",
    "있으면 좋은 경험",
)

REQUIRED_CUES = (
    "required",
    "must",
    "minimum",
    "need to",
    "you have",
    "requirements",
    "qualifications",
    "proficient",
    "proficiency",
    "fluent",
    "strong command",
    "ability to",
    "you will",
    "필수",
    "반드시",
    "가능자",
    "가능하신",
    "능숙",
    "능통",
    "숙련",
    "보유자",
    "보유하신",
    "경험자",
    "유경험자",
    "자격",
    "요건",
    "조건",
    "해당자",
)


@dataclass
class FitResult:
    score: int
    grade: str
    recommendation: str
    decision: str
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


def _heading_matches(line: str, headings: tuple[str, ...]) -> bool:
    """Match a short section heading without treating a sentence as one."""
    lowered = _normalise_line(line).casefold()
    lowered = re.sub(r"^[\s\[\]■▶●◆※·*#▸•\-–—]+", "", lowered)
    lowered = re.sub(r"[\s\[\]■▶●◆※·*#▸•\-–—]+$", "", lowered)
    lowered = lowered.strip(" :–—-")
    if not lowered or len(lowered) > 90:
        return False
    return any(
        lowered == heading
        or lowered.startswith(f"{heading}:")
        for heading in headings
    )


def _split_preferred_text(text: str) -> tuple[str, str]:
    """Keep preferred-only lines out of required/core scoring signals."""
    lines = [_normalise_line(line) for line in text.splitlines() if _normalise_line(line)]
    if not lines:
        return text, ""

    core: list[str] = []
    preferred: list[str] = []
    in_preferred = False
    for line in lines:
        if preferred and _heading_matches(line, JOB_FOOTER_HEADINGS):
            break
        if _heading_matches(line, PREFERRED_SECTION_HEADINGS):
            in_preferred = True
            preferred.append(line)
            continue
        if _heading_matches(line, JOB_CONTENT_HEADINGS):
            in_preferred = False

        if in_preferred:
            preferred.append(line)
            continue

        lowered = line.casefold()
        has_optional_cue = any(cue in lowered for cue in OPTIONAL_CUES)
        has_required_cue = any(cue in lowered for cue in REQUIRED_CUES)
        if has_optional_cue and not has_required_cue:
            preferred.append(line)
        else:
            core.append(line)

    return "\n".join(core), "\n".join(preferred)


def _text_units(text: str) -> list[str]:
    """Break prose into small enough units to classify nearby cues."""
    units: list[str] = []
    for line in text.splitlines():
        clean = _normalise_line(line)
        if not clean:
            continue
        units.extend(
            piece.strip()
            for piece in re.split(r"(?<=[.!?。！？])\s+|[;•]", clean)
            if piece.strip()
        )
    return units or [_normalise_line(text)]


def _cue_positions(text: str, cues: Iterable[str]) -> list[int]:
    lowered = text.casefold()
    positions: list[int] = []
    for cue in cues:
        start = 0
        needle = cue.casefold()
        while True:
            position = lowered.find(needle, start)
            if position < 0:
                break
            positions.append(position)
            start = position + max(1, len(needle))
    return positions


def _term_is_preferred_in_unit(unit: str, terms: Iterable[str]) -> bool:
    lowered = unit.casefold()
    optional_positions = _cue_positions(lowered, OPTIONAL_CUES)
    required_positions = _cue_positions(lowered, REQUIRED_CUES)
    if not optional_positions:
        return False
    for term in terms:
        escaped = re.escape(term.casefold().strip()).replace(r"\ ", r"\s+")
        for match in re.finditer(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", lowered):
            optional_distance = min(abs(position - match.start()) for position in optional_positions)
            required_distance = (
                min(abs(position - match.start()) for position in required_positions)
                if required_positions
                else float("inf")
            )
            if optional_distance <= 120 and optional_distance < required_distance:
                return True
    return False


def _classify_tag_contexts(
    text: str,
    patterns: dict[str, tuple[str, ...]],
) -> tuple[set[str], set[str]]:
    """Return (core tags, preferred-only tags) for inline job-posting prose."""
    present = _present_tags(text, patterns)
    core: set[str] = set()
    preferred: set[str] = set()
    units = _text_units(text)
    for tag in present:
        matching_units = [
            unit
            for unit in units
            if any(_contains_term(unit, term) for term in patterns.get(tag, ()))
        ]
        if not matching_units:
            core.add(tag)
            continue
        if any(_term_is_preferred_in_unit(unit, patterns[tag]) for unit in matching_units):
            preferred.add(tag)
        if any(not _term_is_preferred_in_unit(unit, patterns[tag]) for unit in matching_units):
            core.add(tag)
    return core, preferred


def _present_tags(text: str, patterns: dict[str, tuple[str, ...]]) -> set[str]:
    lowered = text.lower()
    tags = {tag for tag, words in patterns.items() if any(_contains_term(lowered, word) for word in words)}
    # A career-page footer often mentions "events" or a "speaker series".
    # Count event management only when an action is tied to the event itself.
    if re.search(
        r"\b(?:coordinate|coordinates|coordinating|manage|manages|managing|plan|plans|planning|organize|organise|deliver|delivers|own|owns)\w*\s+(?:[a-z]+\s+){0,2}events?\b",
        lowered,
    ):
        tags.add("event_management")
    return tags


def _contains_term(text: str, term: str) -> bool:
    """Match a whole word/phrase so short terms do not hit substrings."""
    normalized_text = re.sub(r"\s+", " ", text.casefold()).strip()
    normalized_term = re.sub(r"\s+", " ", term.casefold()).strip()
    if re.search(r"[가-힣]", normalized_term):
        return re.sub(r"\s+", "", normalized_term) in re.sub(r"\s+", "", normalized_text)
    escaped = re.escape(normalized_term).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", normalized_text))


def _mention_contexts(text: str, terms: Iterable[str], window: int = 180) -> list[str]:
    lowered = text.casefold()
    contexts: list[str] = []
    for term in terms:
        escaped = re.escape(term.casefold().strip()).replace(r"\ ", r"\s+")
        for match in re.finditer(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", lowered):
            start = max(0, match.start() - window)
            end = min(len(lowered), match.end() + window)
            contexts.append(lowered[start:end])
    return contexts


def _is_required_mention(text: str, terms: Iterable[str]) -> bool:
    contexts = _mention_contexts(text, terms)
    if not contexts:
        return False
    for context in contexts:
        if any(cue in context for cue in OPTIONAL_CUES):
            continue
        if any(cue in context for cue in REQUIRED_CUES):
            return True
    return False


def _required_tags(text: str, patterns: dict[str, tuple[str, ...]]) -> set[str]:
    present = _present_tags(text, patterns)
    return {
        tag
        for tag in present
        if _is_required_mention(text, patterns[tag])
    }


def _score_coverage(required: set[str], candidate: set[str], weight: int) -> int:
    if not required:
        return weight // 2
    return round(weight * len(required & candidate) / len(required))


def _set_coverage(required: set[str], candidate: set[str], weight: int) -> int:
    """Coverage for literal tools, where a tool is not an evidence tag."""
    if not required:
        return weight // 2
    return round(weight * len(required & candidate) / len(required))


def _preferred_alignment_bonus(
    candidate: CandidateProfile,
    preferred_tags: set[str],
    preferred_tools: set[str],
    preferred_languages: set[str],
) -> int:
    """Reward explicit preferred-fit evidence without letting it dominate.

    Preferred qualifications are a differentiator, not a substitute for a
    required qualification. The entire bonus is deliberately capped at five
    points so a long preferred section cannot inflate a weak application.
    """
    points = 0.0
    for tag in preferred_tags:
        strength = _candidate_tag_strength(candidate, tag)
        points += {0: 0.0, 1: 0.75, 2: 1.5}.get(strength, 0.0)
    points += 0.75 * len(preferred_tools & candidate.tools)
    points += 1.5 * len(preferred_languages & candidate.languages)
    return min(5, round(points))


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
    lowered = re.sub(r"^[\s\[\]■▶●◆※·*#▸•\-–—]+", "", lowered)
    lowered = re.sub(r"[\s\[\]■▶●◆※·*#▸•\-–—]+$", "", lowered)
    lowered = lowered.strip(" :–—-")
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
        "프로필",
        "요약",
        "경력 요약",
        "학력",
        "교육",
        "기술",
        "보유 기술",
        "자격증",
        "언어",
        "역량",
        "관심 분야",
        "경력사항",
        "주요 프로젝트",
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
    direct_tags = {
        tag
        for tag, lines in candidate.evidence.items()
        if any(not _is_metadata_line(line) for line in lines)
    }
    count = len(direct_lines)
    breadth = len(direct_tags)
    # Do not let a long CV earn a perfect evidence score from repeated bullets
    # in one area. Breadth and distinct proof both matter.
    if count >= 10 and breadth >= 5:
        return 10
    if count >= 6 and breadth >= 3:
        return 8
    if count >= 3 and breadth >= 2:
        return 6
    if count:
        return 4
    return 2


def _has_business_degree(candidate: CandidateProfile) -> bool:
    degree_markers = (
        "b.b.a",
        "bba",
        "bachelor",
        "bachelor's",
        "b.a.",
        "b.s.",
        "bsc",
        "mba",
        "master",
        "m.a.",
        "m.s.",
        "msc",
        "degree",
        "major",
        "candidate",
        "university",
        "college",
        "학사",
        "석사",
        "박사",
        "전공",
        "재학",
        "대학교",
        "대학",
    )
    business_fields = (
        "business administration",
        "business management",
        "business analytics",
        "management",
        "commerce",
        "economics",
        "finance",
        "marketing",
        "b.b.a",
        "bba",
        "경영학",
        "경영학과",
        "경영학부",
        "글로벌경영",
        "경제학",
        "상경계열",
        "경상계열",
        "무역학",
        "국제통상",
        "경영정보학",
    )
    return any(
        any(_contains_term(line, marker) for marker in degree_markers)
        and any(_contains_term(line, field) for field in business_fields)
        for line in candidate.raw_text.splitlines()
    )


GRADUATE_DEGREE_RE = re.compile(
    r"(?<![a-z0-9])(?:ms|m\.s\.|master(?:'s)?|ph\.?d\.?|doctoral)(?![a-z0-9])|석사|박사",
    re.IGNORECASE,
)
TECHNICAL_DEGREE_RE = re.compile(
    r"\b(?:computer science|computer engineering|electrical engineering|software engineering)\b|컴퓨터\s*공학|전기전자공학|전자공학|소프트웨어학(?:과)?|전산학|인공지능학(?:과)?",
    re.IGNORECASE,
)


def _has_required_graduate_technical_degree(text: str) -> bool:
    """Detect an explicit minimum/current graduate technical-degree gate."""
    segments = [segment.strip() for segment in re.split(r"\n|(?<=[.!?])\s+", text) if segment.strip()]
    for index, segment in enumerate(segments):
        context = " ".join(segments[max(0, index - 1): index + 2]).casefold()
        if not GRADUATE_DEGREE_RE.search(context) or not TECHNICAL_DEGREE_RE.search(context):
            continue
        hard_signal = any(
            cue in context
            for cue in (
                "minimum qualification",
                "minimum qualifications",
                "basic qualification",
                "basic qualifications",
                "required qualification",
                "required qualifications",
                "currently enrolled",
                "must be enrolled",
                "degree program",
                "필수",
                "자격요건",
                "지원자격",
                "학위 과정",
                "재학 중",
                "석사 이상",
                "박사 이상",
            )
        )
        optional_only = any(cue in context for cue in OPTIONAL_CUES) and not any(
            cue in context
            for cue in (
                "minimum",
                "required",
                "currently enrolled",
                "must be enrolled",
            )
        )
        if hard_signal and not optional_only:
            return True
    return False


def _has_graduate_technical_degree(candidate: CandidateProfile) -> bool:
    """Require graduate level and technical field in nearby CV evidence."""
    lines = [line.strip() for line in candidate.raw_text.splitlines() if line.strip()]
    for index, _line in enumerate(lines):
        context = " ".join(lines[max(0, index - 1): index + 2])
        if GRADUATE_DEGREE_RE.search(context) and TECHNICAL_DEGREE_RE.search(context):
            return True
    return False


def _has_technical_degree(candidate: CandidateProfile) -> bool:
    """Require a technical field to appear in actual education context."""
    degree_signal = re.compile(
        r"\b(?:degree|bachelor|master|ph\.?d|doctoral|major|candidate|university|college)\b|학위|학사|석사|박사|전공|대학교|대학",
        re.IGNORECASE,
    )
    lines = [line.strip() for line in candidate.raw_text.splitlines() if line.strip()]
    for index, _line in enumerate(lines):
        context = " ".join(lines[max(0, index - 1): index + 2])
        if TECHNICAL_DEGREE_RE.search(context) and degree_signal.search(context):
            return True
    return False


def _passed_core_checks(candidate: CandidateProfile, checks: set[str]) -> set[str]:
    passed: set[str] = set()
    lowered = candidate.raw_text.lower()
    if "business_degree" in checks and _has_business_degree(candidate):
        passed.add("business_degree")
    if "english" in checks and "english" in candidate.languages:
        passed.add("english")
    if "student" in checks and candidate.graduation:
        passed.add("student")
    if "japanese" in checks and "japanese" in candidate.languages:
        passed.add("japanese")
    if "chinese" in checks and "chinese" in candidate.languages:
        passed.add("chinese")
    if "capital_markets_knowledge" in checks and any(
        _contains_term(lowered, phrase)
        for phrase in ("capital markets", "자본시장", "채권", "채권발행")
    ):
        passed.add("capital_markets_knowledge")
    if "computer_science_degree" in checks and _has_technical_degree(candidate):
        passed.add("computer_science_degree")
    if "accounting_degree" in checks and any(
        _contains_term(lowered, phrase)
        for phrase in ("accounting", "회계", "회계학")
    ):
        passed.add("accounting_degree")
    if "graduate_technical_degree" in checks and _has_graduate_technical_degree(candidate):
        passed.add("graduate_technical_degree")
    return passed


def _infer_core_checks(text: str, required_languages: set[str], specification: dict[str, object]) -> set[str]:
    if "core_checks" in specification:
        return set(specification["core_checks"] or set())
    checks: set[str] = set()
    if "english" in required_languages or _is_required_mention(text, LANGUAGE_PATTERNS["english"]):
        checks.add("english")
    if any(
        _contains_term(text, phrase)
        for phrase in ("intern", "undergraduate", "student", "graduating", "인턴", "재학생", "졸업예정", "재학 중")
    ):
        checks.add("student")
    if any(
        _is_required_mention(text, (phrase,))
        for phrase in (
            "business administration",
            "business degree",
            "business major",
            "경영학",
            "경영학과",
            "상경계열",
            "경상계열",
            "무역학",
            "국제통상",
        )
    ):
        checks.add("business_degree")
    if _has_required_graduate_technical_degree(text):
        checks.add("graduate_technical_degree")
    elif any(
        _is_required_mention(text, (phrase,))
        for phrase in (
            "computer science degree",
            "computer engineering degree",
            "software engineering degree",
            "컴퓨터공학 전공",
            "컴퓨터공학과",
            "전자공학과",
            "소프트웨어학과",
            "전기전자공학",
        )
    ):
        checks.add("computer_science_degree")
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


def _recommendation(score: int, blockers: Iterable[str], penalty_points: int = 0) -> str:
    if blockers:
        return "Hold — eligibility gap"
    if score >= 85:
        return "Apply now"
    if score >= 65:
        return "Apply after targeted CV edits"
    return "Lower priority"


def _decision(score: int, blockers: Iterable[str]) -> str:
    """Map the internal score to a simple application-priority label."""
    if blockers or score < 40:
        return "Skip"
    if score >= 85:
        return "Apply now"
    if score >= 65:
        return "Apply after CV edits"
    return "Low probability"


def _shorten(text: str, limit: int = 175) -> str:
    clean = _normalise_line(text).strip(" .")
    if len(clean) <= limit:
        return clean
    shortened = clean[: limit - 3].rsplit(" ", 1)[0]
    return shortened.rstrip(" ,;:") + "..."


STOPWORDS = {
    "about", "after", "also", "and", "are", "been", "being", "from", "have", "into", "more",
    "that", "their", "this", "through", "with", "will", "your", "role", "work", "what", "where",
    "which", "such", "than", "then", "they", "them", "those", "these", "using", "including",
    "그리고", "또는", "관련", "업무", "담당", "경험", "능력", "가능", "대한", "통한", "위한", "기타", "이상", "우대",
}


def _line_quality(line: str, job_words: set[str] | None = None) -> tuple[int, int, int, int]:
    clean = _normalise_line(line)
    lowered = clean.casefold()
    action_words = (
        "led", "conducted", "screened", "designed", "developed", "managed", "translated",
        "interpreted", "assessed", "evaluated", "founded", "attracted", "built", "supported",
        "주도", "수행", "분석", "개발", "기획", "운영", "개선", "달성", "구축", "설계", "담당", "참여",
    )
    action_score = sum(1 for word in action_words if _contains_term(lowered, word))
    number_score = 1 if re.search(r"\d", clean) else 0
    line_words = set(re.findall(r"[a-z]{4,}|[가-힣]{2,}", lowered)) - STOPWORDS
    overlap = len(line_words & (job_words or set()))
    return (0 if _is_metadata_line(clean) else 1, overlap, action_score + number_score, len(clean))


def _best_evidence_line(
    candidate: CandidateProfile,
    tag: str,
    used: set[str] | None = None,
    job_text: str = "",
) -> str | None:
    lines = _unique_lines(candidate.evidence.get(tag, []))
    used = used or set()
    available = [
        line
        for line in lines
        if line.casefold() not in used and not _is_metadata_line(line)
    ]
    if not available:
        return None
    job_words = set(re.findall(r"[a-z]{4,}|[가-힣]{2,}", job_text.casefold())) - STOPWORDS
    return max(available, key=lambda line: _line_quality(line, job_words))


def _ordered_tags(tags: set[str], candidate: CandidateProfile) -> list[str]:
    return sorted(tags, key=lambda tag: (-_candidate_tag_strength(candidate, tag), TAG_LABELS.get(tag, tag)))


def _build_explanations(candidate: CandidateProfile, strengths: set[str], job_text: str) -> list[str]:
    explanations: list[str] = []
    used: set[str] = set()
    for tag in _ordered_tags(strengths, candidate):
        line = _best_evidence_line(candidate, tag, used, job_text)
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


def _build_evidence(candidate: CandidateProfile, strengths: set[str], job_text: str) -> list[str]:
    evidence: list[str] = []
    used: set[str] = set()
    for tag in _ordered_tags(strengths, candidate):
        line = _best_evidence_line(candidate, tag, used, job_text)
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
            detail = f"Evidence gap: {label}. Add one CV bullet with a specific action, tool, and result."
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
            "degree program in computer science",
            "degree program in computer engineering",
            "degree program in electrical engineering",
            "컴퓨터공학 전공",
            "컴퓨터공학과",
            "전자공학과",
            "소프트웨어학과",
            "전기전자공학",
        )
    )
    if engineering_degree_language:
        has_adjacent_degree = any(
            _contains_term(candidate.raw_text, phrase)
            for phrase in (
                "computer science",
                "computer engineering",
                "software engineering",
                "컴퓨터공학",
                "전자공학",
                "소프트웨어학",
                "전기전자공학",
            )
        )
        if not has_adjacent_degree:
            points += 6
            reasons.append("Preferred engineering/CS degree is not evidenced (-6)")
        elif _candidate_tag_strength(candidate, "software_engineering") == 0:
            points += 3
            reasons.append("Adjacent degree but no direct programming evidence (-3)")
    return points, reasons


def _domain_score_cap(
    candidate: CandidateProfile,
    domain_tags: set[str],
) -> tuple[int | None, str | None]:
    strict_tags = sorted(domain_tags & STRICT_DOMAIN_TAGS)
    missing = [
        tag
        for tag in strict_tags
        if _candidate_tag_strength(candidate, tag) == 0
    ]
    if not missing:
        return None, None
    supporting = [
        tag
        for tag in strict_tags
        if _candidate_tag_strength(candidate, tag) == 1
    ]
    if len(missing) >= 2:
        cap = 64
    elif supporting:
        cap = 78
    else:
        cap = 72
    labels = ", ".join(TAG_LABELS.get(tag, tag) for tag in missing)
    return cap, f"Missing direct role-specific evidence ({labels}); score capped at {cap}."


def assess_fit(candidate: CandidateProfile, job: JobPosting) -> FitResult:
    # The title is usually the cleanest role signal; the body is cleaned by
    # the job parser before it reaches this function.
    focused_body = focus_job_content(job.text)
    core_body, preferred_body = _split_preferred_text(focused_body)
    text = "\n".join(part for part in (job.title, core_body) if part).casefold()
    preferred_text = preferred_body.casefold()
    core_job_tags, inline_preferred_tags = _classify_tag_contexts(text, TAG_PATTERNS)
    _, inline_preferred_tools = _classify_tag_contexts(text, TOOL_PATTERNS)
    _, inline_preferred_languages = _classify_tag_contexts(text, LANGUAGE_PATTERNS)
    preferred_body_tags = _present_tags(preferred_text, TAG_PATTERNS)
    candidate_tags = candidate.evidence_tags
    specification = job.requirements or {}

    responsibility_tags = set(specification.get("responsibility_tags", core_job_tags))
    domain_tags = set(specification.get("domain_tags", core_job_tags & DOMAIN_TAGS))
    preferred_tags = (
        set(specification.get("preferred_tags") or set())
        | preferred_body_tags
        | inline_preferred_tags
    )
    preferred_domain_tags = (
        set(specification.get("preferred_domain_tags") or set())
        | (preferred_tags & DOMAIN_TAGS)
    )
    preferred_tools = (
        set(specification.get("preferred_tools") or set())
        | _present_tags(preferred_text, TOOL_PATTERNS)
        | inline_preferred_tools
    )
    preferred_languages = (
        set(specification.get("preferred_languages") or set())
        | _present_tags(preferred_text, LANGUAGE_PATTERNS)
        | inline_preferred_languages
    )
    required_tools = (
        set(specification["required_tools"])
        if "required_tools" in specification
        else _required_tags(text, TOOL_PATTERNS)
    )
    required_languages = (
        set(specification["required_languages"])
        if "required_languages" in specification
        else _required_tags(text, LANGUAGE_PATTERNS)
    )
    core_checks = _infer_core_checks(text, required_languages, specification)

    # Explicit degree requirements are checked separately so a preferred
    # degree lowers the score without incorrectly turning into a hard blocker.
    if any(
        _contains_term(text, phrase)
        for phrase in ("accounting degree", "accounting major", "회계학과", "회계 전공")
    ):
        core_checks.add("accounting_degree")

    blockers: list[str] = []
    for language in ("japanese", "chinese"):
        if language in required_languages and language not in candidate.languages:
            blockers.append(f"Required language missing: {language.title()}")

    passed_checks = _passed_core_checks(candidate, core_checks)
    if "graduate_technical_degree" in core_checks and "graduate_technical_degree" not in passed_checks:
        blockers.append("Required graduate technical degree missing")
    elif "computer_science_degree" in core_checks and "computer_science_degree" not in passed_checks:
        blockers.append("Required technical degree missing")
    qualification_score = _score_coverage(core_checks, passed_checks, 25)
    breakdown = {
        "Role responsibilities": _weighted_coverage(responsibility_tags, candidate, 30),
        "Core qualifications": qualification_score,
        "Tools": _set_coverage(required_tools, candidate.tools, 15),
        "Domain alignment": _weighted_coverage(domain_tags, candidate, 15),
        "Evidence strength": _evidence_score(candidate),
        "Preferred alignment": _preferred_alignment_bonus(
            candidate,
            preferred_domain_tags,
            preferred_tools,
            preferred_languages,
        ),
    }

    penalty_points, penalty_reasons = _specificity_penalties(candidate, domain_tags, text)
    score = max(0, min(100, sum(breakdown.values()) - penalty_points))
    domain_cap, domain_cap_reason = _domain_score_cap(candidate, domain_tags)
    if domain_cap is not None and score > domain_cap:
        penalty_points += score - domain_cap
        score = domain_cap
        if domain_cap_reason:
            penalty_reasons.append(domain_cap_reason)
    if "Required graduate technical degree missing" in blockers:
        # A missing minimum-degree gate is materially different from a soft
        # skill gap; it should never look like an apply-now match.
        score = min(score, 45)
    elif "Required technical degree missing" in blockers:
        score = min(score, 45)
    elif blockers:
        # Eligibility is a separate gate: a strong-looking keyword match must
        # not wash out an explicit language requirement.
        score = min(score, 55)

    strengths_set = {
        tag
        for tag in responsibility_tags
        if tag in candidate_tags and _candidate_tag_strength(candidate, tag) > 0
    }
    strength_list = _ordered_tags(strengths_set, candidate)
    evidenced_tags = {
        tag
        for tag in responsibility_tags | domain_tags
        if _candidate_tag_strength(candidate, tag) == 2
    }
    gap_tags = sorted(
        (responsibility_tags | domain_tags) - evidenced_tags
        | (required_tools - candidate.tools)
    )
    gaps = list(gap_tags)
    gaps.extend(f"missing qualification: {check}" for check in sorted(core_checks - passed_checks))

    return FitResult(
        score=score,
        grade=_grade(score),
        recommendation=_recommendation(score, blockers, penalty_points),
        decision=_decision(score, blockers),
        eligibility="Risk" if blockers else "Pass",
        blockers=blockers,
        strengths=strength_list,
        gaps=gaps,
        breakdown=breakdown,
        evidence=_build_evidence(candidate, strengths_set, text),
        match_explanations=_build_explanations(candidate, strengths_set, text),
        gap_details=_build_gap_details(gap_tags, core_checks - passed_checks, blockers),
        penalty_points=penalty_points,
        penalty_reasons=penalty_reasons,
    )
