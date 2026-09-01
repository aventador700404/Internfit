from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import re


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        if tag in {"p", "br", "li", "h1", "h2", "h3", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in {"p", "li", "h1", "h2", "h3", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if clean:
            self.parts.append(clean + " ")
            if self.in_title:
                self.title += clean + " "


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
    title = normalize_text(parser.title) or "Untitled job posting"
    return JobPosting(title=title, company="Unknown", url=url, text=text)


def job_from_text(title: str, company: str, text: str, url: str = "") -> JobPosting:
    return JobPosting(title=title or "Pasted job posting", company=company or "Unknown", url=url, text=normalize_text(text))
