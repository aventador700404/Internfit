# InternFit Analysis Telemetry

InternFit emits one JSON object per analysis event to standard output. Render captures these lines in the service logs.

## Events

- `analysis_completed`: a CV and job posting were scored.
- `analysis_blocked`: the request stopped because the job page could not be safely fetched or reliably extracted.
- `analysis_error`: the request failed while parsing or processing.

## Recorded fields

- request metadata: `analysis_id`, UTC `timestamp`, `duration_ms`;
- CV metadata: file format, byte size, detected evidence tags, languages, tools, education/graduation indicators;
- job metadata: source type, safe hostname only, extraction status, text/title character counts;
- scoring output: score, grade, recommendation, decision, eligibility, category breakdown, penalties, blockers, strengths, and gaps.

## Excluded fields

- original CV bytes or extracted CV text;
- original job-page or pasted job text;
- filenames, full URLs, URL query parameters, contact details, or exception messages.

## Use for calibration

Telemetry shows how the engine behaves, not whether its judgment is correct. Calibration should combine these logs with a separate human label such as “score too high,” “appropriate,” or “score too low.”

## Optional durable storage

The current implementation continues to emit Render logs. If both server-only
environment variables below are configured, the same allowlisted event is also
appended to Supabase through its REST Data API:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

No extra Python package or LLM/API provider is needed. Without these variables,
the app stays on Render logs and analysis behavior is unchanged. The service
role key must exist only in Render environment variables; it must never be
committed or sent to the browser.

To enable the table, run [`supabase/schema.sql`](../supabase/schema.sql) once
in the Supabase SQL Editor. The table is append-only from the application side
and has no browser-facing `anon` or `authenticated` access.

For the public beta, show users a short notice that anonymized derived analysis
signals are collected for engine calibration. Set a retention period and a
deletion process before using the data beyond beta calibration.
