from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "internfit"))

from core.cv_parser import parse_cv_bytes, parse_pdf_bytes  # noqa: E402
from core.job_parser import fetch_job_posting, job_from_text  # noqa: E402
from core.scoring import assess_fit  # noqa: E402
from core.telemetry import emit_analysis_event, new_analysis_id, safe_url_domain  # noqa: E402


MAX_REQUEST_BYTES = 8 * 1024 * 1024


def _parse_multipart(body: bytes, content_type: str) -> dict[str, dict[str, str | bytes]]:
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type)
    if not match:
        raise ValueError("multipart boundary missing")
    boundary = (match.group(1) or match.group(2)).encode()
    fields: dict[str, dict[str, str | bytes]] = {}
    for raw_part in body.split(b"--" + boundary)[1:]:
        if raw_part in {b"--", b"--\r\n", b"", b"\r\n"}:
            continue
        raw_part = raw_part.strip(b"\r\n-")
        if b"\r\n\r\n" not in raw_part:
            continue
        header_bytes, value = raw_part.split(b"\r\n\r\n", 1)
        headers = header_bytes.decode("utf-8", errors="ignore")
        disposition = re.search(r'Content-Disposition:[^\r\n]*?\bname="([^"]+)"', headers, re.I)
        if not disposition:
            continue
        name = disposition.group(1)
        filename_match = re.search(r'filename="([^"]*)"', headers, re.I)
        fields[name] = {"data": value.rstrip(b"\r\n"), "filename": filename_match.group(1) if filename_match else ""}
    return fields


def _text_field(fields: dict[str, dict[str, str | bytes]], name: str) -> str:
    value = fields.get(name, {}).get("data", b"")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip()
    return str(value).strip()


def _candidate_log_fields(candidate, cv_size: int, cv_format: str) -> dict[str, object]:
    return {
        "cv_format": cv_format,
        "cv_size_bytes": cv_size,
        "candidate_tags": sorted(candidate.evidence_tags),
        "candidate_languages": sorted(candidate.languages),
        "candidate_tools": sorted(candidate.tools),
        "candidate_evidence_tag_count": len(candidate.evidence_tags),
        "education_detected": bool(candidate.education),
        "graduation_detected": bool(candidate.graduation),
    }


def _job_log_fields(job, job_url: str, analysis_source: str, job_fetch_status: str) -> dict[str, object]:
    # Store only derived metadata. Never log the URL path/query or job text.
    domain = safe_url_domain(job_url or job.url) if job_fetch_status == "ok" else ""
    return {
        "analysis_source": analysis_source,
        "job_fetch_status": job_fetch_status,
        "job_domain": domain,
        "job_text_chars": len(job.text),
        "job_title_chars": len(job.title),
        "company_known": bool(job.company and job.company != "Unknown"),
    }


def _result_log_fields(result) -> dict[str, object]:
    return {
        "score": result.score,
        "grade": result.grade,
        "recommendation": result.recommendation,
        "decision": result.decision,
        "eligibility": result.eligibility,
        "breakdown": result.breakdown,
        "penalty_points": result.penalty_points,
        "penalty_reasons": result.penalty_reasons,
        "strengths": result.strengths,
        "gaps": result.gaps,
        "blockers": result.blockers,
    }


class AppHandler(BaseHTTPRequestHandler):
    server_version = "InternFit/0.2"

    def _send(self, status: int, payload: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, value: dict) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._json(200, {"status": "ok", "service": "InternFit", "version": "0.2"})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/analyze":
            self._json(404, {"error": "not_found"})
            return

        analysis_id = new_analysis_id()
        started_at = time.perf_counter()
        cv = b""
        cv_format = ""
        job_url = ""
        job_fetch_status = "not_requested"
        try:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > MAX_REQUEST_BYTES:
                emit_analysis_event(
                    "analysis_error",
                    analysis_id,
                    error_type="RequestSizeError",
                    status=413,
                    duration_ms=round((time.perf_counter() - started_at) * 1000),
                )
                self._json(413, {"error": "CV upload is empty or exceeds the 8 MB limit."})
                return

            fields = _parse_multipart(self.rfile.read(length), self.headers.get("Content-Type", ""))
            cv = fields.get("cv", {}).get("data", b"")
            filename = str(fields.get("cv", {}).get("filename", "uploaded_cv.docx"))
            if not isinstance(cv, bytes) or not cv:
                raise ValueError("CV file is required")
            suffix = Path(filename).suffix.casefold()
            cv_format = suffix.lstrip(".")
            if suffix == ".pdf":
                candidate = parse_pdf_bytes(cv, filename)
            elif suffix == ".docx":
                candidate = parse_cv_bytes(cv, filename)
            else:
                raise ValueError("Please upload a .docx or .pdf CV.")

            job_url = _text_field(fields, "job_url")
            job_text = _text_field(fields, "job_text")
            analysis_source = "job_url"
            if job_url:
                job = fetch_job_posting(job_url)
                job_fetch_status = job.source_status
                if job.source_status != "ok" or not job.text:
                    if job_text:
                        job = job_from_text(
                            _text_field(fields, "job_title"),
                            _text_field(fields, "job_company"),
                            job_text,
                            url=job_url,
                        )
                        analysis_source = "pasted_text_fallback"
                    else:
                        emit_analysis_event(
                            "analysis_blocked",
                            analysis_id,
                            **_candidate_log_fields(candidate, len(cv), cv_format),
                            **_job_log_fields(job, job_url, analysis_source, job_fetch_status),
                            reason=job_fetch_status,
                            duration_ms=round((time.perf_counter() - started_at) * 1000),
                        )
                        self._json(422, {
                            "error": "This job page could not be read. Paste the job description instead.",
                            "source_status": job.source_status,
                            "fallback_required": True,
                        })
                        return
            elif job_text:
                job = job_from_text(_text_field(fields, "job_title"), _text_field(fields, "job_company"), job_text)
                analysis_source = "pasted_text"
            else:
                self._json(400, {"error": "A job URL or job description is required."})
                return

            result = assess_fit(candidate, job)
            emit_analysis_event(
                "analysis_completed",
                analysis_id,
                **_candidate_log_fields(candidate, len(cv), cv_format),
                **_job_log_fields(job, job_url, analysis_source, job_fetch_status),
                **_result_log_fields(result),
                duration_ms=round((time.perf_counter() - started_at) * 1000),
            )
            response = asdict(result)
            response.update({
                "job_title": job.title,
                "company": job.company,
                "apply_url": job.url or job_url,
                "cv_name": candidate.source_name,
                "analysis_source": analysis_source,
            })
            self._json(200, response)
        except (ValueError, KeyError) as exc:
            emit_analysis_event(
                "analysis_error",
                analysis_id,
                error_type=type(exc).__name__,
                status=400,
                cv_format=cv_format,
                cv_size_bytes=len(cv),
                job_domain=safe_url_domain(job_url) if job_url else "",
                duration_ms=round((time.perf_counter() - started_at) * 1000),
            )
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            emit_analysis_event(
                "analysis_error",
                analysis_id,
                error_type=type(exc).__name__,
                status=500,
                cv_format=cv_format,
                cv_size_bytes=len(cv),
                job_domain=safe_url_domain(job_url) if job_url else "",
                duration_ms=round((time.perf_counter() - started_at) * 1000),
            )
            self._json(500, {"error": "The analysis could not be completed."})

    def log_message(self, format: str, *args: object) -> None:
        # Keep local development output useful without logging CV contents.
        print(f"[InternFit] {self.address_string()} - {format % args}")


def main() -> None:
    requested_port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    port = int(os.environ.get("PORT", requested_port))
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    server = ThreadingHTTPServer((host, port), AppHandler)
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    print(f"InternFit running at http://{display_host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
