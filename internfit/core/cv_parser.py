from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
from typing import BinaryIO
from typing import Iterable
import re

from docx import Document
from pypdf import PdfReader


EVIDENCE_RULES = {
    "strategy": ("strategy", "strategic", "portfolio", "bcg matrix", "five forces", "vrio"),
    "research": ("research", "screened", "market", "consumer", "interview", "insight"),
    "operations": ("operations", "operation", "planning", "execution", "coordination", "logistics"),
    "stakeholder": ("stakeholder", "partnered", "communication", "community", "cross-cultural"),
    "data_analysis": ("data", "analytics", "analysis", "quantitative", "excel", "financial"),
    "technology": ("technology", "information systems", "digital", "platform", "ai", "generative ai"),
    "finance": ("finance", "fintech", "investment", "financial", "m&a", "acquisition"),
    "event_management": ("event", "recruitment", "onboarding", "training", "member"),
    "marketing": ("marketing", "social media", "campaign", "influencer", "content strategy", "brand"),
    "sales": ("sales", "business development", "lead generation", "account management"),
    # Keep generic credentials such as "SQL Developer" from turning a business
    # candidate into a software engineer.  A real engineering signal should be
    # an engineering role, a programming deliverable, or a concrete stack.
    "software_engineering": ("software engineer", "software engineering", "backend", "frontend", "api", "programming language", "programming project", "software developer", "coding"),
    "accounting": ("accounting", "audit", "journal entries", "reconciliation", "monthly close", "bookkeeping"),
}

LANGUAGE_RULES = {
    "korean": ("korean (native)", "korean"),
    "english": ("english (cefr c1", "toefl", "english"),
    "german": ("german (cefr a2", "german"),
    "japanese": ("japanese",),
    "chinese": ("chinese", "mandarin"),
}

TOOL_RULES = {
    "excel": ("excel",),
    "powerpoint": ("powerpoint",),
    "word": ("word",),
    "sql": ("sqld", "sql"),
    "ai_tools": ("generative ai", "ai tools", "rapid prototyping"),
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


@dataclass
class CandidateProfile:
    source_name: str
    raw_text: str
    evidence: dict[str, list[str]]
    languages: set[str]
    tools: set[str]
    graduation: str | None
    education: list[str]

    @property
    def evidence_tags(self) -> set[str]:
        return {tag for tag, lines in self.evidence.items() if lines}


def extract_docx_text(file_path: str | Path) -> list[str]:
    document = Document(file_path)
    lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            row_text = " ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                lines.append(row_text)
    return lines


def extract_docx_bytes(data: bytes | BinaryIO) -> list[str]:
    """Extract visible DOCX text without persisting the uploaded file."""
    document = Document(BytesIO(data) if isinstance(data, bytes) else data)
    lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            row_text = " ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                lines.append(row_text)
    return lines


def extract_pdf_bytes(data: bytes) -> list[str]:
    """Extract selectable PDF text without persisting the uploaded file."""
    try:
        reader = PdfReader(BytesIO(data))
        lines: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            lines.extend(line.strip() for line in text.splitlines() if line.strip())
        return lines
    except Exception as exc:
        raise ValueError("Could not read this PDF. Please upload a text-based PDF.") from exc


def parse_pdf_bytes(data: bytes, source_name: str = "uploaded_cv.pdf") -> CandidateProfile:
    lines = extract_pdf_bytes(data)
    if not lines:
        raise ValueError(
            "No selectable text found in this PDF. Please upload a text-based PDF instead of a scanned image."
        )
    return _profile_from_lines(lines, source_name)


def _matching_lines(lines: Iterable[str], needles: tuple[str, ...]) -> list[str]:
    return [line for line in lines if any(_contains_term(line, needle) for needle in needles)]


def _contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term.lower().strip()).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()))


def parse_cv(file_path: str | Path) -> CandidateProfile:
    lines = extract_docx_text(file_path)
    return _profile_from_lines(lines, Path(file_path).name)


def parse_cv_bytes(data: bytes, source_name: str = "uploaded_cv.docx") -> CandidateProfile:
    return _profile_from_lines(extract_docx_bytes(data), source_name)


def _profile_from_lines(lines: list[str], source_name: str) -> CandidateProfile:
    raw_text = "\n".join(lines)
    evidence = {tag: _matching_lines(lines, needles) for tag, needles in EVIDENCE_RULES.items()}
    languages = {
        language
        for language, needles in LANGUAGE_RULES.items()
        if any(_contains_term(raw_text, needle) for needle in needles)
    }
    tools = {
        tool
        for tool, needles in TOOL_RULES.items()
        if any(_contains_term(raw_text, needle) for needle in needles)
    }
    graduation = next((line for line in lines if "B.B.A. Candidate" in line), None)
    education = [line for line in lines if "University" in line or "Student" in line]
    return CandidateProfile(
        source_name=source_name,
        raw_text=raw_text,
        evidence=evidence,
        languages=languages,
        tools=tools,
        graduation=graduation,
        education=education,
    )
