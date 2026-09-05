# Optional Luna semantic layer

InternFit works without an LLM. When `OPENAI_API_KEY` is absent, the server
uses the deterministic parser and scorer exactly as before.

When the key is present, one bounded Luna call runs after CV and job text have
been extracted. Luna may normalize paraphrases, classify core versus preferred
job signals, and write more specific match/gap text. The Python engine still
owns the final arithmetic, eligibility blockers for language and degree, role
specific penalties, and score caps.

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

Telemetry stores status, token counts, estimated cost, and score outputs. It
does not store raw CV text, job text, uploaded files, prompts, or model output.
