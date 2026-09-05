-- Run this once in the Supabase SQL Editor.
-- The table stores derived calibration telemetry only; it never receives CV
-- bytes, CV text, job text, filenames, contact details, or full URLs.

create table if not exists public.analysis_events (
  event_id text primary key,
  analysis_id text not null,
  event text not null check (event in ('analysis_completed', 'analysis_blocked', 'analysis_error')),
  occurred_at timestamptz not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists analysis_events_occurred_at_idx
  on public.analysis_events (occurred_at desc);

create index if not exists analysis_events_event_idx
  on public.analysis_events (event);

alter table public.analysis_events enable row level security;

-- Only the server-side service_role may append telemetry. The browser-facing
-- anon/authenticated roles receive no table access.
revoke all on table public.analysis_events from anon, authenticated;
grant insert on table public.analysis_events to service_role;

