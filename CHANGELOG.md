# Changelog

This file records user-visible changes to InternFit. Technical rationale is kept in [`docs/decisions.md`](docs/decisions.md).

## [0.3.0] — 2026-09-05

### Security

- Added server-side validation for job-posting URLs.
- Only public HTTP(S) URLs on standard web ports are accepted.
- Blocked local, private, loopback, link-local, reserved, and metadata-service addresses.
- Revalidated redirect targets to prevent a public URL from redirecting into a private network.

### Reliability

- Added regression coverage for unsafe URL schemes, private IPs, credentials, non-standard ports, and unsafe redirects.
- Added a job-content quality gate so empty, blocked, boilerplate-only, or non-job pages are not scored.
- Added privacy-conscious JSON analysis events for engine calibration; raw CV and job text are excluded.
- Added optional Supabase persistence for the same derived telemetry; database outages do not block analysis.
- Kept job-page responses bounded to prevent unexpectedly large downloads.

## [0.2.0] — 2026-09-04

### Added

- Connected CV upload and job-posting URL analysis to the web interface.
- Added `.docx` and PDF CV parsing, including a bounded OCR fallback for ordinary image-based PDFs.
- Added Korean and mixed Korean-English CV/job-posting support.
- Added pasted job-description fallback for login-protected or bot-blocked pages.
- Added dynamic company/title metadata and an `Apply now` link to the submitted posting.

### Changed

- Replaced the hard-coded demo result with deterministic rule-based scoring.
- Added eligibility bands, required-language checks, preferred-qualification handling, and role-specific penalties.
- Improved mobile result-page layout and page-state handling.

### Known limitations

- Some PDFs whose text is converted into vector outlines rather than normal text or raster images may still be unreadable.
- Login walls, anti-bot pages, and heavily client-rendered pages may require pasted job text.
- The score is a transparent reference signal, not a hiring prediction.

## [0.1.0] — 2026-08-30

### Added

- Created the first InternFit web prototype.
- Added CV upload, job URL input, result cards, fit score, evidence, gaps, and application-link flow.
- Established the no-LLM, explainable scoring direction for the initial public beta.
