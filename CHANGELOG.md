# Changelog

This file records user-visible changes to InternFit. Technical rationale is kept in [`docs/decisions.md`](docs/decisions.md).

## [0.4.6] — 2026-09-29

### Added

- Reused validated AI results for identical CV/job content and analysis configuration for 30 minutes in bounded server memory.
- Joined concurrent identical analyses into one model call; failed and fallback results remain retryable.
- Kept current job-page fetching, scoring, filenames, application links, analysis references, and evidence-sharing choices independent of cached AI output.
- Logged cache hits and ages with zero additional tokens or budget reservation on reused requests, and indicated reuse in the analysis status text.
- Added expiry, memory bounds, concurrency, configuration-change, usage-accounting, and per-request sharing regression coverage.

## [0.4.5] — 2026-09-29

### Changed

- Checked optional evidence sharing by default on page load, with an explicit default-on notice and an available opt-out.
- Preserved a user's sharing choice when changing CVs within the same page.
- Versioned the default-on notice in stored records; unchecked, missing, or outdated settings still prevent evidence storage.
- Reduced the evidence-sharing label and helper text to 12 px and 11 px for a more compact upload card.

## [0.4.4] — 2026-09-29

### Improved

- Added an internship-recruiter evaluation perspective emphasizing actual contribution, transferable experience, required versus preferred qualifications, and evidence-calibrated judgments.
- Made both LLM match explanations and CV editing suggestions follow the job posting's language, independent of the CV language.
- Clarified mixed-language posting behavior while retaining original-language evidence quotes, existing UI labels, and deterministic guidance.
- Kept one Luna call per analysis and the existing scoring, budget, and source-validation paths.

## [0.4.3] — 2026-09-29

### Improved

- Made Luna CV-edit advice refer to server-labeled CV/job source sections instead of retyping job quotes that could fail exact matching.
- Constrained reference IDs to the actual text sent in that analysis and rejected unknown or wrong-document references individually.
- Asked for specific edits tied to job requirements, distinguishing clarification of existing experience from conditional suggestions for missing evidence.
- Added an AI-assisted/rule-based guidance label and accepted/rejected suggestion counts in telemetry.
- Preserved one model request per analysis, the existing output token limit, scoring weights, budget guard, and consent-based evidence storage.
- Added mixed-language source-reference, invalid-reference, conditional-advice, fallback, and single-call regression coverage.

## [0.4.2] — 2026-09-29

### Added

- Added optional, versioned consent to save short CV/job excerpts and explanations privately in Supabase for engine review.
- Recorded rule-only and LLM-assisted scores for the same input, component differences, requirements, evidence strengths, penalties, and caps without another model call.
- Recorded source-validation acceptance/rejection reasons and engine/prompt versions, without retaining rejected quotes or raw model responses.
- Kept excerpts out of Render logs and updated privacy copy to describe owner review and OpenAI processing accurately.
- Displayed each analysis reference and whether evidence storage succeeded; DB failure leaves the analysis usable.
- Added consent, source-linkage, masking, storage-failure, and multipart integration coverage. Scoring weights and the mobile layout remain unchanged.

## [0.4.1] — 2026-09-27

### Fixed

- Restored mobile layouts by removing a literal escaped newline that caused the responsive media query to be discarded.
- Kept upload, job-posting, and result cards in a single column at widths up to 780px.
- Prevented long CV filenames, job titles, result URLs, and evidence from widening the page.
- Improved score-label spacing and mobile pasted-description input sizing.

## [0.4.0] — 2026-09-05

### Added

- Added optional Luna semantic analysis for Korean, English, and mixed-language paraphrases.
- Kept final scoring, eligibility blockers, and score caps in the deterministic Python engine.
- Added exact-source quote validation for LLM evidence, matches, and CV-edit suggestions.
- Added a default server-side $1.00 Luna budget guard with Supabase-backed reservations when configured.
- Added provider failure, missing-key, invalid-output, and exhausted-budget fallbacks to rule-based scoring.

### Privacy and cost

- Only extracted CV/job text is sent to the provider when `OPENAI_API_KEY` is configured; uploaded bytes are not sent.
- Responses API storage is disabled for these calls, and raw prompts/responses are excluded from telemetry.
- The LLM path is off by default until the owner adds the server-side key.

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
