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

-- Optional durable guard for the Luna MVP budget. The server calls this RPC
-- with the server-only service_role key before each provider request.
create table if not exists public.llm_usage (
  usage_id text primary key,
  budget_key text not null,
  analysis_id text not null,
  model text not null,
  estimated_cost_usd numeric(12,6) not null check (estimated_cost_usd > 0),
  created_at timestamptz not null default now(),
  unique (budget_key, analysis_id)
);

create index if not exists llm_usage_budget_created_idx
  on public.llm_usage (budget_key, created_at desc);

alter table public.llm_usage enable row level security;
revoke all on table public.llm_usage from anon, authenticated;
grant insert on table public.llm_usage to service_role;

create or replace function public.reserve_llm_budget(
  p_budget_key text,
  p_analysis_id text,
  p_model text,
  p_estimated_cost_usd numeric,
  p_budget_limit_usd numeric
) returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  current_total numeric;
begin
  perform pg_advisory_xact_lock(hashtext(p_budget_key));

  if exists (
    select 1
    from public.llm_usage
    where budget_key = p_budget_key and analysis_id = p_analysis_id
  ) then
    return true;
  end if;

  select coalesce(sum(estimated_cost_usd), 0)
    into current_total
    from public.llm_usage
   where budget_key = p_budget_key;

  if p_estimated_cost_usd <= 0
     or current_total + p_estimated_cost_usd > p_budget_limit_usd then
    return false;
  end if;

  insert into public.llm_usage (
    usage_id, budget_key, analysis_id, model, estimated_cost_usd
  ) values (
    md5(random()::text || clock_timestamp()::text),
    p_budget_key,
    p_analysis_id,
    p_model,
    p_estimated_cost_usd
  );
  return true;
end;
$$;

revoke all on function public.reserve_llm_budget(text, text, text, numeric, numeric)
  from public, anon, authenticated;
grant execute on function public.reserve_llm_budget(text, text, text, numeric, numeric)
  to service_role;
