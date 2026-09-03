from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import re
from urllib.parse import urlparse


IGNORED_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# Career pages frequently place the actual role beside company marketing,
# related jobs, and legal copy. These headings are useful across career-site
# vendors and let the scorer focus on role-specific content.
JOB_CONTENT_HEADINGS = (
    "role overview",
    "job overview",
    "about the role",
    "the opportunity",
    "responsibilities",
    "job responsibilities",
    "what you'll do",
    "what you will do",
    "what we're looking for",
    "what we are looking for",
    "minimum qualification",
    "minimum qualifications",
    "basic qualification",
    "basic qualifications",
    "required qualification",
    "required qualifications",
    "preferred qualification",
    "preferred qualifications",
    "requirements",
    "qualifications",
    "skills",
    "주요업무",
    "담당업무",
    "수행업무",
    "업무내용",
    "모집분야",
    "모집부문",
    "직무내용",
    "자격요건",
    "지원자격",
    "필수요건",
    "필수자격",
    "자격조건",
    "요구사항",
    "기본요건",
    "우대사항",
    "우대조건",
    "우대요건",
)

JOB_FOOTER_HEADINGS = (
    "about the company",
    "company overview",
    "about qualcomm",
    "qualcomm overview",
    "join us",
    "our culture",
    "benefits",
    "perks",
    "similar jobs",
    "similar positions",
    "equal employment",
    "equal opportunity",
    "privacy",
    "accessibility",
    "share this job",
    "apply now",
    "전형절차",
    "채용절차",
    "채용전형",
    "근무조건",
    "근무환경",
    "복리후생",
    "혜택 및 복지",
    "기타사항",
    "유의사항",
    "접수방법",
    "제출서류",
    "회사소개",
    "인재상",
    "문의처",
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.in_title = False
        self.title = ""
        self.in_h1 = False
        self.h1 = ""
        self.in_job_heading = False
        self.job_heading = ""
        self.meta: dict[str, str] = {}
        self._ignored_tags: list[str] = []
        self._main_depth = 0
        self.main_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._ignored_tags:
            if tag in IGNORED_TAGS:
                self._ignored_tags.append(tag)
            return
        if tag in IGNORED_TAGS:
            self._ignored_tags.append(tag)
            return
        if tag == "main":
            self._main_depth += 1
        if tag == "meta":
            attributes = {key.lower(): value or "" for key, value in attrs}
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "").strip()
            if key in {
                "og:title",
                "og:site_name",
                "application-name",
                "twitter:title",
                "description",
                "og:description",
                "twitter:description",
            } and content:
                self.meta[key] = content
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.in_h1 = True
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag in {"h1", "h2", "h3"} and "title" in attributes.get("class", "").lower().split():
            self.in_job_heading = True
        if tag in {"p", "br", "li", "h1", "h2", "h3", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._ignored_tags:
            if tag == self._ignored_tags[-1]:
                self._ignored_tags.pop()
            return
        if tag == "main":
            self._main_depth = max(0, self._main_depth - 1)
        if tag == "title":
            self.in_title = False
        if tag == "h1":
            self.in_h1 = False
        if tag in {"h1", "h2", "h3"} and self.in_job_heading:
            self.in_job_heading = False
        if tag in {"p", "li", "h1", "h2", "h3", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_tags:
            return
        clean = data.strip()
        if clean:
            self.parts.append(clean + " ")
            if self._main_depth:
                self.main_parts.append(clean + " ")
            if self.in_title:
                self.title += clean + " "
            if self.in_h1:
                self.h1 += clean + " "
            if self.in_job_heading:
                self.job_heading += clean + " "


@dataclass
class JobPosting:
    title: str
    company: str
    url: str
    text: str
    source_status: str = "ok"
    requirements: dict[str, Any] | None = None


def normalize_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _declared_charset(content_type: str) -> str | None:
    match = re.search(r"charset\s*=\s*[\"']?\s*([\w.-]+)", content_type or "", flags=re.IGNORECASE)
    return match.group(1) if match else None


def _meta_charset(body: bytes) -> str | None:
    header = body[:4096].decode("latin-1", errors="ignore")
    match = re.search(r"<meta[^>]+charset\s*=\s*[\"']?\s*([\w.-]+)", header, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(
        r"<meta[^>]+content\s*=\s*[\"'][^\"']*charset\s*=\s*([\w.-]+)",
        header,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else None


def _decode_response_body(body: bytes, content_type: str = "") -> str:
    """Decode common career-page encodings without silently dropping Korean."""
    declared = _declared_charset(content_type) or _meta_charset(body)
    candidates = [declared, "utf-8", "cp949", "euc-kr"]
    encodings: list[str] = []
    for encoding in candidates:
        if not encoding:
            continue
        try:
            normalized = encoding.lower().replace("_", "-")
            if normalized not in {item.lower().replace("_", "-") for item in encodings}:
                encodings.append(encoding)
        except AttributeError:
            continue

    decoded: list[tuple[int, str]] = []
    for index, encoding in enumerate(encodings):
        try:
            value = body.decode(encoding, errors="replace")
        except (LookupError, UnicodeError):
            continue
        replacement_count = value.count("\ufffd")
        control_count = sum(1 for char in value if ord(char) < 9 or 13 < ord(char) < 32)
        hangul_count = sum(1 for char in value if "가" <= char <= "힣")
        # Prefer declared/UTF-8 when quality is tied, but penalize replacement
        # and control characters heavily so CP949 pages are recovered.
        score = hangul_count * 3 - replacement_count * 40 - control_count * 10 - index
        decoded.append((score, value))
    if not decoded:
        return body.decode("utf-8", errors="replace")
    return max(decoded, key=lambda item: item[0])[1]


def _extract_jobposting_jsonld(html: str) -> dict[str, str]:
    """Read the structured JobPosting payload used by client-rendered sites."""
    script_pattern = re.compile(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def find_job_posting(value: Any) -> dict[str, Any] | None:
        if isinstance(value, list):
            for item in value:
                found = find_job_posting(item)
                if found:
                    return found
            return None
        if not isinstance(value, dict):
            return None
        type_value = value.get("@type", "")
        types = type_value if isinstance(type_value, list) else [type_value]
        if any(str(item).casefold() == "jobposting" for item in types):
            return value
        for key in ("@graph", "mainEntity", "item"):
            found = find_job_posting(value.get(key))
            if found:
                return found
        return None

    for match in script_pattern.finditer(html):
        try:
            payload = json.loads(unescape(match.group(1).strip()))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        posting = find_job_posting(payload)
        if not posting:
            continue
        organization = posting.get("hiringOrganization")
        company = organization.get("name", "") if isinstance(organization, dict) else ""
        return {
            "title": str(posting.get("title", "")).strip(),
            "description": str(posting.get("description", "")).strip(),
            "company": str(company).strip(),
        }
    return {}


def _heading_matches(line: str, headings: tuple[str, ...]) -> bool:
    """Match a section heading without treating a normal sentence as one."""
    lowered = normalize_text(line).casefold()
    # Korean recruiting pages commonly decorate headings as
    # "■ 자격요건", "[우대사항]", or "▶ 주요업무".
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


def focus_job_content(text: str) -> str:
    """Remove common career-page boilerplate while preserving role sections.

    If a page has recognizable job-section headings, keep content from the
    first such heading until the company/footer sections begin. Pages without
    those headings are returned unchanged so unusual job boards still work.
    """
    lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
    if not lines:
        return text

    start_index = next(
        (index for index, line in enumerate(lines) if _heading_matches(line, JOB_CONTENT_HEADINGS)),
        None,
    )
    if start_index is None:
        return text

    focused: list[str] = []
    for line in lines[start_index:]:
        if focused and _heading_matches(line, JOB_FOOTER_HEADINGS):
            break
        focused.append(line)

    result = normalize_text("\n".join(focused))
    # A false-positive heading should not discard a substantial description.
    return result if len(result) >= 120 or len(focused) >= 3 else text


def _company_from_title(title: str) -> str:
    """Infer a company label from common career-page title formats."""
    for separator in ("|", " — ", " – ", " - "):
        pieces = [piece.strip() for piece in title.split(separator) if piece.strip()]
        if len(pieces) < 2:
            continue
        for piece in reversed(pieces[1:]):
            cleaned = re.sub(r"\b(job details|job detail|careers?|jobs?|share)\b", "", piece, flags=re.I)
            cleaned = normalize_text(cleaned).strip(" -–—|")
            if cleaned and cleaned.lower() not in {"job posting", "open positions"}:
                return cleaned
    return "Unknown"


def _company_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    known_hosts = {
        "careers.linecorp.com": "LINE",
        "jobs.sap.com": "SAP",
        "careers.bcg.com": "BCG",
        "careers.feverup.com": "Fever",
        "team.emma-sleep.com": "Emma – The Sleep Company",
    }
    if host in known_hosts:
        return known_hosts[host]
    if host.endswith(".lever.co"):
        slug = (urlparse(url).path.strip("/").split("/") or [""])[0]
        if slug:
            return slug.replace("-", " ").title()
    return "Unknown"


def fetch_job_posting(url: str, timeout: int = 12) -> JobPosting:
    request = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; InternFit/0.1; +https://github.com/)"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES)
            headers = getattr(response, "headers", {})
            content_type = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
            html = _decode_response_body(body, content_type)
    except (HTTPError, URLError, TimeoutError) as exc:
        return JobPosting(
            title="Could not fetch this job page",
            company="Unknown",
            url=url,
            text="",
            source_status=f"fetch_failed: {exc.__class__.__name__}",
        )

    parser = _TextExtractor()
    parser.feed(html)
    full_text = normalize_text("".join(parser.parts))
    main_text = normalize_text("".join(parser.main_parts))
    structured_job = _extract_jobposting_jsonld(html)
    structured_description = normalize_text(structured_job.get("description", ""))
    metadata_description = normalize_text(
        parser.meta.get("og:description", "")
        or parser.meta.get("description", "")
        or parser.meta.get("twitter:description", "")
    )
    title = normalize_text(
        structured_job.get("title", "")
        or parser.meta.get("og:title", "")
        or parser.job_heading
        or parser.title
        or parser.h1
    ) or "Untitled job posting"
    # Navigation, related jobs, and legal footers can contain many unrelated
    # keywords. Prefer semantic <main> content when it is substantial and
    # actually looks like a job description. Application-form pages sometimes
    # put only the form controls in <main>, so those still use the full page.
    main_markers = (
        "responsibilities",
        "qualifications",
        "requirements",
        "what you'll do",
        "what we’re looking for",
        "who we're looking for",
        "job overview",
        "about the role",
        "job responsibilities",
        "profile",
        "주요업무",
        "담당업무",
        "자격요건",
        "지원자격",
        "우대사항",
    )
    parsed_path = urlparse(url).path.casefold()
    title_lower = title.casefold()
    is_application_form = (
        "/embed/job_app" in parsed_path
        or title_lower.startswith("job application for")
        or "application form" in title_lower
    )
    use_main = (
        not is_application_form
        and len(main_text) >= 180
        and any(marker in main_text.casefold() for marker in main_markers)
    )
    if structured_description:
        # JSON-LD is usually the canonical description on React/client-
        # rendered career pages, where visible body text may be absent to
        # urllib even though a browser can render it.
        text = structured_description
    elif use_main:
        text = main_text
    elif len(metadata_description) >= 180 and not full_text:
        text = metadata_description
    else:
        text = full_text
    text = focus_job_content(text)
    company = (
        structured_job.get("company", "")
        or normalize_text(parser.meta.get("og:site_name", ""))
        or _company_from_title(title)
        or _company_from_url(url)
    )
    if company == "Unknown":
        company = _company_from_url(url)
    return JobPosting(title=title, company=company, url=url, text=text)


def job_from_text(title: str, company: str, text: str, url: str = "") -> JobPosting:
    return JobPosting(title=title or "Pasted job posting", company=company or "Unknown", url=url, text=normalize_text(text))
