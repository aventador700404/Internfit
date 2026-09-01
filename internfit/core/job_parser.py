from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import re
from urllib.parse import urlparse


IGNORED_TAGS = {"script", "style", "noscript", "template", "svg", "canvas"}


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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._ignored_tags:
            if tag in IGNORED_TAGS:
                self._ignored_tags.append(tag)
            return
        if tag in IGNORED_TAGS:
            self._ignored_tags.append(tag)
            return
        if tag == "meta":
            attributes = {key.lower(): value or "" for key, value in attrs}
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "").strip()
            if key in {"og:title", "og:site_name", "application-name", "twitter:title"} and content:
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
            html = response.read().decode("utf-8", errors="ignore")
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
    text = normalize_text("".join(parser.parts))
    title = normalize_text(parser.meta.get("og:title", "") or parser.job_heading or parser.title or parser.h1) or "Untitled job posting"
    company = (
        normalize_text(parser.meta.get("og:site_name", ""))
        or _company_from_title(title)
        or _company_from_url(url)
    )
    if company == "Unknown":
        company = _company_from_url(url)
    return JobPosting(title=title, company=company, url=url, text=text)


def job_from_text(title: str, company: str, text: str, url: str = "") -> JobPosting:
    return JobPosting(title=title or "Pasted job posting", company=company or "Unknown", url=url, text=normalize_text(text))
