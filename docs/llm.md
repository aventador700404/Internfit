# Optional Luna semantic layer

InternFit works without an LLM. When `OPENAI_API_KEY` is absent, the server
uses the deterministic parser and scorer exactly as before.

When the key is present, one bounded Luna call runs after CV and job text have
been extracted. Luna may normalize paraphrases, classify core versus preferred
job signals, and write more specific match/gap text. The Python engine still
owns the final arithmetic, eligibility blockers for language and degree, role
specific penalties, and score caps.

## Temporary analysis cache

Successful, validated Luna responses are reused for **30 minutes from
completion**, without extending expiry on a hit. The process-local cache
keeps only a digest key, validated semantic output (including selected short
source evidence), validation diagnostics, and timestamps. It does not retain
uploaded bytes, parsed CV/job objects, full source text, raw provider output,
or request metadata such as analysis IDs, filenames, application URLs, and
evidence-sharing choices. Selected evidence may still contain personal details.

The key covers exact extracted CV text, job title/body, model, engine version,
prompt/schema version, validator version, and model input/output limits. Each
request still parses its CV and reads the current job page (or supplied text)
before lookup. A changed page at the same URL therefore gets a fresh analysis.
Changing only a filename or tracking URL can reuse the same AI output. Current
request metadata and scoring are always reconstructed, so another request's
filename, application link, reference, or sharing choice cannot be replayed.

One in-flight computation per key serves concurrent identical requests. Reuse
does not call the model or reserve budget; its token/cost fields are zero.
Failed, disabled, budget-exhausted, or invalid responses are not retained for
later requests. Current waiters share a failure instead of triggering a retry
storm; a later request can retry normally. Removing the API key bypasses AI
reuse as well as new provider calls.

Bounds: 100 entries, 4 MiB serialized payload total, 64 KiB per entry, 32 unique
in-flight keys, and a 30-second duplicate wait. A full pending table or wait
timeout returns a retryable 503 instead of launching extra model requests.
The HTTP server loop sweeps expired entries even when no new analyses arrive.
A restart/deploy clears the cache; multiple processes would have independent
caches. This is not a per-user quota or a replacement for broader abuse/load
controls; CV parsing, OCR, URL fetching, scoring, and logging still occur.
No new service, migration, or paid cache is required.

## Evaluation perspective and feedback language

The system prompt asks Luna to adopt the perspective of a recruiter with
10 years of internship hiring and CV review experience. Its evaluation rubric
prioritizes actual work and personal contribution over keyword overlap,
distinguishes required from preferred qualifications, recognizes defensible
transferable experience, and treats missing CV evidence as unverified rather
than proof of inability. Expectations are calibrated to the internship role,
without aiming for a predetermined score or predicting hiring outcomes.
This is a prompt instruction, not model training or a guarantee of accuracy.

Both **Why it matches** and **Make the CV sharper** use the job posting's
language for LLM-generated feedback: Korean duties/qualifications produce
Korean explanations; English ones produce English explanations, regardless
of the CV language. For bilingual postings the prompt selects the predominant
language of the substantive duties and qualifications; a balanced posting
uses its first substantive section. English technical terms or an English
title within Korean job prose do not override that choice.

Source quotes stay in their original language for validation. UI labels and
existing deterministic guidance, including hard-requirement reminders and
provider-failure fallbacks, retain their current language. Language selection
and the evaluation rubric run inside the same single model request. The
content-derived `prompt_version` in telemetry changes with these instructions.

## CV editing advice

The same model call also powers **Make the CV sharper**. Bounded CV/job text
is split into contiguous sections up to 260 characters, labeled `C001`, `J001`,
etc. The gap schema permits only reference IDs from that request. The server
resolves selected IDs back to the original source slices; the model does not
have to reproduce punctuation or whitespace in a job quote.

Each of up to four suggestions includes a job reference, an optional CV
reference, an `edit_type`, and a specific editing action:

- `clarify_existing` requires a CV reference and asks how to make an existing
  activity, method, contribution, or outcome clearer.
- `evidence_to_add` can omit the CV reference when no related evidence appears.
  The prompt requires conditional wording and prohibits invented achievements,
  tools, figures, or claims that rewriting fixes a missing qualification.

Known IDs verify source provenance, not the correctness of the model's
interpretation or every claim in its suggestion. The private trace links
advice to those sections for review. Invalid references are rejected per item;
valid suggestions remain usable. Existing candidate evidence and match
explanations still undergo source-quote matching.

The UI labels accepted advice **AI-assisted guidance**. Hard-requirement
reminders remain in the result. When there are no valid suggestions or the
provider is unavailable, it labels the fallback **Rule-based guidance**.
There is no retry or second model call for editing advice. Prompt/schema
length and output can affect per-request cost; the existing budget guard and
1,800-output-token limit remain active.

## Render settings

Add these environment variables to the Render service:

```text
OPENAI_API_KEY=your-server-side-key
OPENAI_MODEL=gpt-5.6-luna
LLM_BUDGET_USD=1.00
```

Do not put the key in the browser, GitHub, or a chat message. It is read only
by the Python server.

## Supabase budget migration

Run [`supabase/llm_budget.sql`](../supabase/llm_budget.sql) once in the
Supabase SQL Editor. This creates an atomic server-side reservation function
and keeps the `$1.00` budget across Render restarts. Until this migration is
run, the application uses a process-local best-effort guard.

The existing `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` variables are
reused. No browser Supabase client is needed for the LLM call.

## Fallback behavior

The analysis remains available when the key is missing, the budget is
exhausted, the provider times out, or the response fails validation. The
result exposes `analysis_mode` and `llm_status` so the owner can tell whether
the semantic layer was used.

Telemetry records status, token counts, budget reservations, and a same-input
rule-only versus LLM-assisted score comparison. Source-validation outcomes are
logged without source text. When the optional sharing setting is enabled, bounded CV/job
excerpts and selected match/gap explanations are saved privately in Supabase
for manual review; they never enter Render stdout. Full documents, uploaded
files, raw prompts, and raw model responses are not retained. See
[`telemetry.md`](telemetry.md) for fields, limits, consent, and deletion.
