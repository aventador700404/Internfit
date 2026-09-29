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
- Engine source fingerprint, prompt/schema fingerprint, validator/trace version,
  deployment commit when available, and whether the LLM input was truncated.

The baseline and final score use the **same parsed CV and job**. The baseline
is a second deterministic calculation, not another LLM request. If the LLM is
unavailable, both scores are equal. Scoring weights and caps are unchanged.

Evidence strength is `0 = missing`, `1 = supporting`, `2 = direct`.
Validation confirms source-quote checks, not semantic correctness. An accepted
quote may still have the wrong tag or strength. Job overlay tags are enum-filtered
classifications, not quote-validated claims.

## Optional: short evidence excerpts

The upload screen has an unchecked **Share evidence to improve matching**
checkbox. Consent is sent with the current notice version, is not restored
from browser storage, and resets when another CV is selected. Analysis works
with the checkbox off. Old clients without consent never store excerpts.

With consent, the same private DB row includes `payload.analysis_trace`:

- job title/company for identifying the case;
- deduplicated `excerpts` with `cv-*` and `job-*` reference IDs;
- `tag_evidence`: rule-derived CV quotes versus accepted LLM quotes,
  requirement groups, final strength, and selected job keyword context;
- accepted LLM match/gap explanations and source-excerpt references;
- selected education excerpts and the explanations displayed to the user.

Limits: 24 unique CV and 24 job excerpts, 280 characters each (plus an ellipsis),
and two selected quotes per tag/source. Omitted counts and per-tag evidence
counts make selection limits visible. Job keyword context helps manual review;
it is **not** asserted to be the sentence the LLM used. This bounded diagnostic
record cannot reconstruct full documents or replay arbitrary future parsers.

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

In SQL Editor, find consented records:

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
