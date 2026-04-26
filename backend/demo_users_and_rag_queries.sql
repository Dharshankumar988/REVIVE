-- REVIVE demo users + advanced RAG SQL
-- Run in Supabase SQL Editor after running backend/supabase_setup.sql.
-- This script creates 3 demo auth users, syncs profiles, and adds practical RAG implementation pieces.

create extension if not exists pgcrypto;
create extension if not exists vector;

-- ---------------------------------------------------------------------
-- 1) Demo account bootstrap (auth.users + auth.identities + profiles)
-- ---------------------------------------------------------------------
create or replace function public.create_or_update_demo_user(
  p_email text,
  p_password text,
  p_full_name text,
  p_role public.app_role,
  p_is_approved boolean
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid;
begin
  select u.id
    into v_user_id
  from auth.users u
  where lower(u.email) = lower(p_email)
  limit 1;

  if v_user_id is null then
    v_user_id := gen_random_uuid();

    insert into auth.users (
      instance_id,
      id,
      aud,
      role,
      email,
      encrypted_password,
      email_confirmed_at,
      raw_app_meta_data,
      raw_user_meta_data,
      created_at,
      updated_at,
      confirmation_token,
      recovery_token,
      email_change_token_new,
      email_change
    )
    values (
      '00000000-0000-0000-0000-000000000000',
      v_user_id,
      'authenticated',
      'authenticated',
      lower(p_email),
      extensions.crypt(p_password, extensions.gen_salt('bf')),
      now(),
      jsonb_build_object('provider', 'email', 'providers', array['email']),
      jsonb_build_object('full_name', p_full_name),
      now(),
      now(),
      '',
      '',
      '',
      ''
    );
  else
    update auth.users
    set email = lower(p_email),
        encrypted_password = extensions.crypt(p_password, extensions.gen_salt('bf')),
        raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb) || jsonb_build_object('full_name', p_full_name),
        email_confirmed_at = coalesce(email_confirmed_at, now()),
        updated_at = now()
    where id = v_user_id;
  end if;

  insert into auth.identities (
    id,
    user_id,
    identity_data,
    provider,
    provider_id,
    last_sign_in_at,
    created_at,
    updated_at
  )
  values (
    gen_random_uuid(),
    v_user_id,
    jsonb_build_object('sub', v_user_id::text, 'email', lower(p_email)),
    'email',
    v_user_id::text,
    now(),
    now(),
    now()
  )
  on conflict (provider, provider_id)
  do update
  set identity_data = excluded.identity_data,
      updated_at = now();

  insert into public.profiles (id, email, full_name, role, is_approved, approved_at, approved_by)
  values (
    v_user_id,
    lower(p_email),
    p_full_name,
    p_role,
    p_is_approved,
    case when p_is_approved then now() else null end,
    case when p_is_approved then v_user_id else null end
  )
  on conflict (id)
  do update
  set email = excluded.email,
      full_name = excluded.full_name,
      role = excluded.role,
      is_approved = excluded.is_approved,
      approved_at = case when excluded.is_approved then coalesce(public.profiles.approved_at, now()) else null end,
      approved_by = case when excluded.is_approved then coalesce(public.profiles.approved_by, excluded.id) else null end,
      updated_at = now();

  return v_user_id;
end;
$$;

-- Shared demo password used by login-page quick sign-in:
--   123456
select public.create_or_update_demo_user(
  'john@revive.com',
  '123456',
  'John Smith',
  'admin',
  true
);

select public.create_or_update_demo_user(
  'jane@revive.com',
  '123456',
  'Jane Doe',
  'user',
  true
);

select public.create_or_update_demo_user(
  'alex@revive.com',
  '123456',
  'Alex Brown',
  'user',
  false
);

-- Ensure password stays consistent for jane in case of a prior seed typo.
update auth.users
set encrypted_password = extensions.crypt('123456', extensions.gen_salt('bf')),
    updated_at = now()
where lower(email) = 'jane@revive.com';

-- ---------------------------------------------------------------------
-- 2) RAG corpus expansion from known emergency procedures (summarized)
-- ---------------------------------------------------------------------
insert into public.rag_documents (title, protocol_type, body, metadata)
values
  (
    'AHA BLS Adult Cardiac Arrest Quick Flow',
    'cardiac',
    'Summary of high-level adult BLS actions for immediate arrest response, compressions, and AED readiness.',
    '{"source":"AHA Guidelines 2020","topic":"BLS","authority":"AHA"}'::jsonb
  ),
  (
    'WHO Oxygen Therapy Escalation (Acute Hypoxemia)',
    'respiratory',
    'Summary of oxygen titration and reassessment priorities for low saturation and respiratory compromise.',
    '{"source":"WHO Clinical Guidance","topic":"Oxygen Therapy","authority":"WHO"}'::jsonb
  ),
  (
    'Rapid ABCDE Deterioration Assessment',
    'general',
    'Summary framework for structured airway, breathing, circulation, disability, exposure reassessment.',
    '{"source":"Emergency Medicine Practice","topic":"ABCDE","authority":"Clinical Practice"}'::jsonb
  ),
  (
    'Sepsis First-Hour Response Checklist',
    'general',
    'Summary checklist for early sepsis suspicion, perfusion checks, and urgent escalation tasks.',
    '{"source":"Surviving Sepsis Campaign","topic":"Sepsis","authority":"SSC"}'::jsonb
  ),
  (
    'Tachyarrhythmia Initial Stabilization',
    'cardiac',
    'Summary of instability recognition and immediate stabilization checks in tachyarrhythmia patterns.',
    '{"source":"ACLS-aligned practice","topic":"Tachyarrhythmia","authority":"AHA/ACLS"}'::jsonb
  )
on conflict (title) do update
set protocol_type = excluded.protocol_type,
    body = excluded.body,
    metadata = excluded.metadata,
    updated_at = now();

insert into public.rag_chunks (document_id, chunk_index, chunk_text, embedding, metadata)
select d.id, c.chunk_index, c.chunk_text, null, c.metadata
from public.rag_documents d
join (
  values
    ('AHA BLS Adult Cardiac Arrest Quick Flow', 0, 'Confirm unresponsiveness and absent normal breathing, then activate emergency response pathway immediately.', '{"source":"AHA 2020 summary"}'::jsonb),
    ('AHA BLS Adult Cardiac Arrest Quick Flow', 1, 'Start high-quality chest compressions without delay and minimize interruptions during cycles.', '{"source":"AHA 2020 summary"}'::jsonb),
    ('AHA BLS Adult Cardiac Arrest Quick Flow', 2, 'Use AED or defibrillator as soon as available while CPR continues between rhythm checks.', '{"source":"AHA 2020 summary"}'::jsonb),

    ('WHO Oxygen Therapy Escalation (Acute Hypoxemia)', 0, 'Verify pulse oximetry reliability, patient positioning, and airway patency before trend interpretation.', '{"source":"WHO oxygen summary"}'::jsonb),
    ('WHO Oxygen Therapy Escalation (Acute Hypoxemia)', 1, 'Start supplemental oxygen and reassess saturation and work of breathing at short intervals.', '{"source":"WHO oxygen summary"}'::jsonb),
    ('WHO Oxygen Therapy Escalation (Acute Hypoxemia)', 2, 'Escalate support if severe desaturation persists despite first-line oxygen delivery.', '{"source":"WHO oxygen summary"}'::jsonb),

    ('Rapid ABCDE Deterioration Assessment', 0, 'Airway: ensure patency and protect against obstruction before moving to next step.', '{"source":"ABCDE summary"}'::jsonb),
    ('Rapid ABCDE Deterioration Assessment', 1, 'Breathing and circulation: identify oxygenation failure, perfusion deficits, and trend deterioration quickly.', '{"source":"ABCDE summary"}'::jsonb),
    ('Rapid ABCDE Deterioration Assessment', 2, 'Disability and exposure: reassess neuro status and hidden causes while continuing vitals surveillance.', '{"source":"ABCDE summary"}'::jsonb),

    ('Sepsis First-Hour Response Checklist', 0, 'Recognize possible sepsis early using perfusion signs, infection context, and hemodynamic instability.', '{"source":"SSC summary"}'::jsonb),
    ('Sepsis First-Hour Response Checklist', 1, 'Prioritize urgent escalation, hemodynamic monitoring, and rapid treatment workflows per local protocol.', '{"source":"SSC summary"}'::jsonb),
    ('Sepsis First-Hour Response Checklist', 2, 'Track response to interventions and trigger higher-level support if deterioration continues.', '{"source":"SSC summary"}'::jsonb),

    ('Tachyarrhythmia Initial Stabilization', 0, 'Assess instability markers such as chest pain, hypotension, altered mentation, and poor perfusion.', '{"source":"ACLS summary"}'::jsonb),
    ('Tachyarrhythmia Initial Stabilization', 1, 'Maintain oxygenation and continuous rhythm monitoring while preparing escalation.', '{"source":"ACLS summary"}'::jsonb),
    ('Tachyarrhythmia Initial Stabilization', 2, 'Escalate urgently when sustained high rate coexists with instability signs.', '{"source":"ACLS summary"}'::jsonb)
) as c(title, chunk_index, chunk_text, metadata)
  on c.title = d.title
on conflict (document_id, chunk_index) do update
set chunk_text = excluded.chunk_text,
    metadata = excluded.metadata;

-- ---------------------------------------------------------------------
-- 2b) Web-researched protocol additions (source-attributed summaries)
-- ---------------------------------------------------------------------
insert into public.rag_documents (title, protocol_type, body, metadata)
values
  (
    'SSC 2026 Sepsis Immediate Priorities',
    'general',
    'Source-attributed summary of early sepsis priorities: rapid recognition, immediate treatment, hemodynamic support, and source control timing.',
    '{"source":"Surviving Sepsis Campaign Adult Guidelines 2026","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines","evidence_type":"guideline_summary"}'::jsonb
  ),
  (
    'WHO Clinical Oxygen Escalation Principles',
    'respiratory',
    'Source-attributed summary of oxygen monitoring and escalation principles from WHO clinical management guidance.',
    '{"source":"WHO Clinical Management Guidance","source_url":"https://www.who.int/publications/i/item/WHO-2019-nCoV-Clinical-2021-2","evidence_type":"guideline_summary"}'::jsonb
  ),
  (
    'Emergency Team Handoff and Reassessment Triggers',
    'general',
    'Source-attributed summary emphasizing serial reassessment, rapid handoff, and escalation triggers in unstable patients.',
    '{"source":"SCCM Sepsis Guidance + bedside escalation practice","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines","evidence_type":"workflow_summary"}'::jsonb
  )
on conflict (title) do update
set protocol_type = excluded.protocol_type,
    body = excluded.body,
    metadata = excluded.metadata,
    updated_at = now();

insert into public.rag_chunks (document_id, chunk_index, chunk_text, embedding, metadata)
select d.id, c.chunk_index, c.chunk_text, null, c.metadata
from public.rag_documents d
join (
  values
    (
      'SSC 2026 Sepsis Immediate Priorities',
      0,
      'Sepsis and septic shock should be treated as medical emergencies with treatment and resuscitation started immediately.',
      '{"source":"SSC 2026","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines"}'::jsonb
    ),
    (
      'SSC 2026 Sepsis Immediate Priorities',
      1,
      'Collect blood cultures as soon as possible and ideally before antimicrobial administration when this does not cause harmful delay.',
      '{"source":"SSC 2026","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines"}'::jsonb
    ),
    (
      'SSC 2026 Sepsis Immediate Priorities',
      2,
      'For probable or definite septic shock, antimicrobial therapy is recommended immediately, ideally within one hour of recognition.',
      '{"source":"SSC 2026","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines"}'::jsonb
    ),
    (
      'SSC 2026 Sepsis Immediate Priorities',
      3,
      'For septic shock, target MAP around 65 mmHg, use crystalloids first-line, and escalate vasopressors when hypotension persists.',
      '{"source":"SSC 2026","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines"}'::jsonb
    ),

    (
      'WHO Clinical Oxygen Escalation Principles',
      0,
      'Assess oxygenation using pulse oximetry together with clinical examination and patient work-of-breathing patterns.',
      '{"source":"WHO clinical guidance","source_url":"https://www.who.int/publications/i/item/WHO-2019-nCoV-Clinical-2021-2"}'::jsonb
    ),
    (
      'WHO Clinical Oxygen Escalation Principles',
      1,
      'Escalate oxygen support in a stepwise manner when hypoxemia persists and continuously reassess response after each intervention.',
      '{"source":"WHO clinical guidance","source_url":"https://www.who.int/publications/i/item/WHO-2019-nCoV-Clinical-2021-2"}'::jsonb
    ),
    (
      'WHO Clinical Oxygen Escalation Principles',
      2,
      'When severe hypoxemia continues despite standard oxygen, prepare advanced respiratory support and urgent escalation pathways.',
      '{"source":"WHO clinical guidance","source_url":"https://www.who.int/publications/i/item/WHO-2019-nCoV-Clinical-2021-2"}'::jsonb
    ),

    (
      'Emergency Team Handoff and Reassessment Triggers',
      0,
      'During instability, use short reassessment loops focused on airway, breathing, circulation, perfusion, and mental status.',
      '{"source":"workflow summary","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines"}'::jsonb
    ),
    (
      'Emergency Team Handoff and Reassessment Triggers',
      1,
      'Handoff should include trend direction, interventions completed, pending actions, and explicit reassessment timing.',
      '{"source":"workflow summary","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines"}'::jsonb
    ),
    (
      'Emergency Team Handoff and Reassessment Triggers',
      2,
      'Escalate early when objective deterioration persists despite initial interventions, rather than waiting for complete failure.',
      '{"source":"workflow summary","source_url":"https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines"}'::jsonb
    )
) as c(title, chunk_index, chunk_text, metadata)
  on c.title = d.title
on conflict (document_id, chunk_index) do update
set chunk_text = excluded.chunk_text,
    metadata = excluded.metadata;

-- ---------------------------------------------------------------------
-- 3) Hybrid retrieval and observability helpers for production-style RAG
-- ---------------------------------------------------------------------
create table if not exists public.rag_query_log (
  id bigserial primary key,
  query_text text not null,
  query_metadata jsonb not null default '{}'::jsonb,
  result_count int not null default 0,
  latency_ms int,
  created_at timestamptz not null default now()
);

create index if not exists idx_rag_query_log_created_at on public.rag_query_log(created_at desc);

create or replace function public.log_rag_query(
  p_query_text text,
  p_query_metadata jsonb default '{}'::jsonb,
  p_result_count int default 0,
  p_latency_ms int default null
)
returns void
language sql
security definer
set search_path = public
as $$
  insert into public.rag_query_log(query_text, query_metadata, result_count, latency_ms)
  values (p_query_text, coalesce(p_query_metadata, '{}'::jsonb), greatest(p_result_count, 0), p_latency_ms);
$$;

create or replace function public.hybrid_match_rag_chunks(
  query_text text,
  query_embedding vector(768),
  match_count int default 6,
  filter jsonb default '{}'::jsonb
)
returns table (
  id uuid,
  document_id uuid,
  chunk_text text,
  metadata jsonb,
  vector_similarity float,
  text_rank float,
  hybrid_score float
)
language sql
stable
as $$
  with vector_hits as (
    select
      c.id,
      c.document_id,
      c.chunk_text,
      c.metadata,
      1 - (c.embedding <=> query_embedding) as vector_similarity,
      row_number() over (order by c.embedding <=> query_embedding) as vector_rank
    from public.rag_chunks c
    where query_embedding is not null
      and c.embedding is not null
      and c.metadata @> filter
    limit greatest(match_count * 4, 12)
  ),
  text_hits as (
    select
      c.id,
      c.document_id,
      c.chunk_text,
      c.metadata,
      ts_rank_cd(to_tsvector('english', c.chunk_text), plainto_tsquery('english', query_text))::float as text_rank,
      row_number() over (
        order by ts_rank_cd(to_tsvector('english', c.chunk_text), plainto_tsquery('english', query_text)) desc
      ) as text_rank_order
    from public.rag_chunks c
    where c.metadata @> filter
      and to_tsvector('english', c.chunk_text) @@ plainto_tsquery('english', query_text)
    limit greatest(match_count * 4, 12)
  ),
  merged as (
    select
      coalesce(v.id, t.id) as id,
      coalesce(v.document_id, t.document_id) as document_id,
      coalesce(v.chunk_text, t.chunk_text) as chunk_text,
      coalesce(v.metadata, t.metadata) as metadata,
      coalesce(v.vector_similarity, 0)::float as vector_similarity,
      coalesce(t.text_rank, 0)::float as text_rank,
      (
        coalesce(1.0 / (60 + v.vector_rank), 0)
        + coalesce(1.0 / (60 + t.text_rank_order), 0)
      )::float as hybrid_score
    from vector_hits v
    full outer join text_hits t on t.id = v.id
  )
  select
    m.id,
    m.document_id,
    m.chunk_text,
    m.metadata,
    m.vector_similarity,
    m.text_rank,
    m.hybrid_score
  from merged m
  order by m.hybrid_score desc, m.vector_similarity desc, m.text_rank desc
  limit greatest(match_count, 1);
$$;

-- Optional: if you use this function from frontend directly, keep RLS in mind.
-- You can keep this restricted to backend/service role execution.
