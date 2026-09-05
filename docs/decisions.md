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

## Open decisions

- Calibrate score bands with a small, diverse set of CVs and postings before making the scoring language stronger.
- Decide whether an LLM is worth the cost and privacy trade-off after the deterministic engine has stable evaluation cases.
- Consider HWP/HWPX support only after the common DOCX/PDF/OCR paths are reliable.
