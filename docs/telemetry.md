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

The current implementation uses Render logs for beta diagnostics. Moving telemetry to Supabase or another durable store requires an explicit retention period, user-facing notice/consent, and a deletion policy.
