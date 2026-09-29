# Optional Luna semantic layer

InternFit works without an LLM. When `OPENAI_API_KEY` is absent, the server
uses the deterministic parser and scorer exactly as before.

When the key is present, one bounded Luna call runs after CV and job text have
been extracted. Luna may normalize paraphrases, classify core versus preferred
job signals, and write more specific match/gap text. The Python engine still
owns the final arithmetic, eligibility blockers for language and degree, role
specific penalties, and score caps.

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
logged without source text. If a user explicitly opts in, bounded CV/job
excerpts and selected match/gap explanations are saved privately in Supabase
for manual review; they never enter Render stdout. Full documents, uploaded
files, raw prompts, and raw model responses are not retained. See
[`telemetry.md`](telemetry.md) for fields, limits, consent, and deletion.
