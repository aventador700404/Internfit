# InternFit analysis records

These records support manual review of matching mistakes. They do not train
the provider model automatically, and a score change is not proof of improved
accuracy. Review whether requirements, evidence classifications, and CV advice
are correct before changing weights or prompts.

## Where to look

- Render → InternFit → Logs → search `analysis_completed` or an `analysis_id`.
- Supabase → Table Editor → `analysis_events` → expand `payload`.
- The result screen shows the reference and whether evidence was saved.

Events remain `analysis_completed`, `analysis_blocked`, and `analysis_error`.
Each has an ID, UTC timestamp, and derived request metadata. `storage_status`
in Render confirms whether the DB accepted the event; `failed_or_disabled`
means no successful write was confirmed. DB failures never block scoring.

## Always recorded: derived fields only

- CV format/size, detected tags, languages/tools, education/graduation flags.
- Job source, hostname only, extraction status, text/title character counts.
- Score, grade, decision, component breakdown, penalties, blockers, strengths/gaps.
- LLM status/model, token counts, conservative budget reservation amount.
- `rule_only_score`, `rule_only_breakdown`, `llm_score_delta`, `breakdown_delta`.
- `scoring_diagnostics.rule_only` and `.final`: requirements actually used,
  core checks and passes, per-tag evidence strengths, subtotal, penalties,
  domain/eligibility caps and whether each cap reduced the score.
- `llm_candidate_tags`, `llm_added_candidate_tags`, and `llm_job_overlay`.
- `llm_validation`: accepted/rejected candidate evidence, matches and gaps,
  with section/index/tag/strength and rejection reason, never rejected quotes.
- `llm_response_status`, `llm_incomplete_reason`, `llm_failure_stage`, and
  `llm_failure_reason`: distinguish provider truncation (including
  `max_output_tokens`), API/network failure, empty/refusal output, JSON parse
  failure, and semantic validation failure. These fields contain only bounded
  status/code labels, not provider messages or response text.
- `llm_validation_summary`: per-section received/accepted/rejected counts and
  rejection-reason counts for candidate evidence, matches, and CV edits. This
  reveals evidence-check failures even when another valid part of the semantic
  response was still used.
- `cv_advice_source`, `llm_gap_count`, `llm_gap_rejected_count`, `llm_gap_status`:
  whether CV advice came from the LLM and whether suggestions were accepted,
  partly rejected, all rejected, absent, or unavailable. Gap validation includes
  known source IDs and edit type, but no source text in stdout.
- Engine source fingerprint, prompt/schema fingerprint, validator/trace version,
  deployment commit when available, and whether the LLM input was truncated.

The baseline and final score use the **same parsed CV and job**. The baseline
is a second deterministic calculation, not another LLM request. If the LLM is
unavailable, both scores are equal. Scoring weights and caps are unchanged.

Evidence strength is `0 = missing`, `1 = supporting`, `2 = direct`.
Candidate evidence and matches use source-quote checks. From v0.4.3, CV-edit
suggestions use server-owned source IDs resolved to the exact sections sent
to the model. Unknown/wrong-document references are rejected. Neither method
proves semantic correctness: the chosen source can still be irrelevant or its
meaning overstated. Job overlay tags are enum-filtered classifications, not
quote-validated claims.

## Cache observations

`llm_cache_status` records `miss` (computed), `hit` (reused), `shared` (joined
an in-flight computation), or `bypass` (AI disabled). `llm_cache_age_seconds`
is the age since the reused computation completed. A reused successful result
has `llm_status=cached` and `llm_used=true`: AI informed the result, but this
request did not call the provider. Its input/output token counts, character
counts, and estimated budget reservation are zero; only the original request
records those usage amounts. Cache digests and source text never enter stdout.

Every request gets a new `analysis_id` and a separate derived telemetry row.
The current request's sharing checkbox alone controls its private evidence
trace, including on cache hits. Cache state never carries that choice forward.
For model-quality comparisons, exclude `hit`/`shared` rows to avoid counting
the same AI output repeatedly. A shared failure retains its failure status
and is not saved in the cache for future requests.

## Optional: short evidence excerpts

The upload screen has a **Share evidence to improve matching** checkbox that
is checked by default on each page load. The notice explains the default and
how to turn sharing off before analysis. A user's choice stays unchanged when
another CV is selected in the same page; the choice is not saved in browser
storage. Analysis works with the checkbox off.

The submitted setting uses notice version `evidence-v2-default-on`, so these
records can be distinguished from the earlier default-off `evidence-v1`
records. A checked default is not recorded as a separate affirmative opt-in.
The server still requires an explicit true field and the current notice
version; unchecked, missing, or outdated settings never store excerpts.

With sharing enabled, the same private DB row includes `payload.analysis_trace`:

- job title/company for identifying the case;
- deduplicated `excerpts` with `cv-*` and `job-*` reference IDs;
- `tag_evidence`: rule-derived CV quotes versus accepted LLM quotes,
  requirement groups, final strength, and selected job keyword context;
- accepted LLM match/gap explanations and source-excerpt references;
- gap `edit_type`, `job_source_id`, and `cv_source_id` to trace each editing
  suggestion to the source sections shown to the model;
- selected education excerpts and the explanations displayed to the user.

Limits: 24 unique CV and 24 job excerpts, 280 characters each (plus an ellipsis),
and two selected quotes per tag/source. Omitted counts and per-tag evidence
counts make selection limits visible. Job keyword context helps manual review;
it is **not** asserted to be the sentence the LLM used. This bounded diagnostic
record cannot reconstruct full documents or replay arbitrary future parsers.
Generated CV-edit explanations are separately bounded to 400 characters.

Obvious emails, phone-like numbers, and links are masked best-effort. Names,
workplaces, and other personal details may remain: excerpts are **not anonymous**.
The UI says the owner can review them. File bytes, full documents, filenames,
full URLs, raw prompts, and raw model responses are not retained. Excerpts are
never printed to Render, even if storage fails.

The checkbox governs durable evidence storage. When AI is enabled, extracted
CV/job text is still sent to OpenAI for analysis; the UI discloses this separately.
Unchecking does not delete previously shared records.

## Database setup and review

The existing `analysis_events.payload` JSONB column accepts these fields.
**No migration or additional environment variable is required.** For a new
installation, run [`supabase/schema.sql`](../supabase/schema.sql). The server
uses `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (or `SUPABASE_SECRET_KEY`).
Keys stay on the server. The table has RLS and no browser-facing `anon` or
`authenticated` access. There is no public log endpoint.

In SQL Editor, find shared evidence records:

```sql
select analysis_id, occurred_at,
       payload->>'score' as final_score,
       payload->>'rule_only_score' as rule_score,
       payload->>'llm_score_delta' as llm_delta,
       payload->'analysis_trace' as evidence
from public.analysis_events
where payload ? 'analysis_trace'
order by occurred_at desc
limit 30;
```

For a deletion request, delete only the specified `analysis_id` from
`analysis_events` in Table Editor or SQL Editor. Do not delete `llm_usage`:
it holds budget accounting, not evidence. Records currently remain until the
owner deletes them; there is no automatic expiry job. Review retention as the
friend beta grows.

`llm_usage.estimated_cost_usd` is a conservative reservation, not an invoice.
Evidence storage uses the existing DB request and no additional LLM call.
