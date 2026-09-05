# InternFit Decision Log

This document records important product and engineering decisions. It answers “why is the project built this way?” rather than listing every code change.

## D-001 — Use deterministic scoring before adding an LLM

- **Date:** 2026-08-30
- **Decision:** Keep the first public beta rule-based and explainable. Defer LLM analysis.
- **Reason:** The score should be auditable, CV data should not be sent to an external model by default, and the project should be testable without API costs.
- **Consequence:** The engine is predictable and free, but it can miss semantic equivalence between differently worded experiences. LLM-assisted explanations may be considered later as a separate layer.

## D-002 — Treat the score as a prioritization signal, not a hiring prediction

- **Date:** 2026-08-30
- **Decision:** Present the output as application priority and eligibility guidance: apply, apply after CV edits, low probability, or pass.
- **Reason:** A CV-to-posting keyword overlap cannot estimate an employer’s actual hiring decision.
- **Consequence:** The UI must show evidence, gaps, blockers, and limitations instead of presenting the number as objective truth.

## D-003 — Use Python + Docker + Render for the first public beta

- **Date:** 2026-09-01
- **Decision:** Keep the existing Python backend and deploy it as a Docker web service on Render.
- **Reason:** The parser and OCR dependencies are already Python-based, and this path required minimal restructuring for a friend-testable public URL.
- **Trade-off:** The free service can sleep after inactivity, so the first request may be slow. A Vercel/Supabase or another always-on architecture can be reconsidered if usage justifies migration.

## D-004 — Do not persist uploaded CV files

- **Date:** 2026-09-01
- **Decision:** Parse uploaded CV bytes in memory and do not save the original file as part of the beta flow.
- **Reason:** CVs contain personal information, and persistent storage is not required for one-off analysis.
- **Consequence:** A new session requires a new upload. Persistent accounts or saved analyses would require an explicit privacy and storage design first.

## D-005 — Add Korean support through extraction and lexicon layers

- **Date:** 2026-09-03
- **Decision:** Extend the existing parser and rule set with Korean headings, terms, required/preferred cues, Hangul matching, and common Korean encodings rather than training a separate model.
- **Reason:** The initial problem is language coverage, not a need for a new scoring model. A lexicon-based layer is cheaper, inspectable, and easier to test.
- **Consequence:** Coverage improves for ordinary Korean and mixed-language documents, but slang, unusual wording, and deeper semantic equivalence remain limited.

## D-006 — Use a layered PDF extraction fallback

- **Date:** 2026-09-04
- **Decision:** Try normal PDF text extraction first, then PDFMiner/PyMuPDF-compatible fallbacks, and finally bounded OCR for image-based PDFs.
- **Reason:** Most exported Word-to-PDF resumes contain selectable text and should be fast; OCR is slower and less reliable, especially on the free Render instance.
- **Consequence:** Ordinary scanned/image PDFs are supported, while PDFs made from vector text outlines may still be treated as unsupported edge cases.

## D-007 — Reject unsafe job URLs before server-side fetching

- **Date:** 2026-09-05
- **Decision:** Accept only public HTTP(S) job URLs, resolve hostnames before fetching, block non-public addresses, and revalidate redirects.
- **Reason:** The public server fetches a URL supplied by an anonymous user. Without validation, that endpoint could be abused to access local services or cloud metadata endpoints.
- **Consequence:** Unusual but non-public URLs and non-standard ports are rejected. Users can still use the pasted-job-text fallback when a legitimate page cannot be fetched.

## D-008 — Do not score pages with unreliable job content

- **Date:** 2026-09-05
- **Decision:** Run a lightweight content-quality gate after fetching and extracting a job page. If the result is empty, blocked, boilerplate-only, too short, or lacks job-related signals, stop before scoring and request pasted job text.
- **Reason:** A successful HTTP response does not guarantee that the response contains the job description. Login shells, JavaScript blockers, and company pages can otherwise produce misleading scores.
- **Consequence:** Some unusual short postings may require the paste fallback, but the system avoids presenting a fabricated score when the source is not reliable enough.

## D-009 — Collect derived scoring telemetry, not source documents

- **Date:** 2026-09-05
- **Decision:** Emit JSON analysis events to the Render service logs after explicit owner approval. Record derived fields such as detected tags, score breakdown, blockers, extraction status, and latency; never record CV text, job text, filenames, or full URLs.
- **Reason:** Engine calibration needs real input/output distributions, but storing source documents would create unnecessary privacy and retention risk.
- **Consequence:** Render logs can support early calibration and debugging. An optional Supabase table now supports durable beta calibration, while raw documents remain excluded. User-facing notice, retention period, and deletion flow remain required before using the dataset beyond beta calibration.

## D-010 — Make Supabase persistence optional and server-side

- **Date:** 2026-09-05
- **Decision:** Use Supabase's REST Data API only when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are configured on Render. Keep stdout logging as the fallback, and make database failures non-fatal to analysis.
- **Reason:** The beta needs durable rows for calibration, but it should remain deployable without credentials, additional Python dependencies, or an LLM provider. A server-only key also prevents the browser from writing directly to the telemetry table.
- **Consequence:** The owner must create the Supabase project, run the schema once, and add two Render environment variables. If the project is paused or unavailable, analyses still work and remain visible in Render logs.

## D-011 — Add Luna as a bounded semantic overlay

- **Date:** 2026-09-05
- **Decision:** Use Luna only to normalize meaning across Korean, English, and mixed-language CVs and job postings, while keeping the final score, eligibility gates, penalties, and caps in Python.
- **Reason:** Exact keyword matching misses equivalent wording and produces repetitive generic explanations. A semantic layer can improve recall and explanation quality without making the score opaque or allowing the model to waive hard requirements.
- **Consequence:** When the owner enables the API key, CV text and job text are sent to the provider for one bounded call. Exact-source validation, a default $1 budget, `store:false`, and deterministic fallback limit the cost and failure surface. The LLM output is still an assistive signal, not a hiring prediction.

## Open decisions

- Calibrate score bands with a small, diverse set of CVs and postings before making the scoring language stronger.
- Decide whether an LLM is worth the cost and privacy trade-off after the deterministic engine has stable evaluation cases.
- Consider HWP/HWPX support only after the common DOCX/PDF/OCR paths are reliable.
