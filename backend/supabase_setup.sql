-- REVIVE Supabase bootstrap script
-- Run this in Supabase SQL Editor.
-- This script sets up auth profile sync, role model, core app tables,
-- RAG-ready pgvector tables/functions, and RLS policies.

create extension if not exists pgcrypto;
create extension if not exists vector;

-- Role enum
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'app_role') THEN
    CREATE TYPE public.app_role AS ENUM ('admin', 'user');
  END IF;
END
$$;

-- Generic trigger for updated_at columns
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- Profiles table linked to auth.users
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text unique not null,
  full_name text,
  role public.app_role not null default 'user',
  is_approved boolean not null default false,
  approved_at timestamptz,
  approved_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.profiles
  add column if not exists is_approved boolean not null default false;

alter table public.profiles
  add column if not exists approved_at timestamptz;

alter table public.profiles
  add column if not exists approved_by uuid references auth.users(id);

-- Auto-create profile row on new auth user
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, role, is_approved)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    'user',
    false
  )
  on conflict (id) do update
  set email = excluded.email,
      updated_at = now();
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- Core app domain tables
create table if not exists public.patients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  age int,
  notes text,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.vitals (
  id bigserial primary key,
  patient_id uuid references public.patients(id) on delete set null,
  hr int not null check (hr >= 0),
  spo2 int not null check (spo2 between 0 and 100),
  movement int not null check (movement >= 0),
  status text not null check (status in ('Normal','Warning','Critical')),
  trend text not null check (trend in ('stable','declining','critical')),
  scenario text,
  source text not null default 'simulator',
  ts timestamptz not null default now()
);

create table if not exists public.ai_guidance (
  id bigserial primary key,
  vital_id bigint references public.vitals(id) on delete cascade,
  instant_action text,
  detailed_steps jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

-- RAG documents and chunk embeddings
create table if not exists public.rag_documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  protocol_type text not null,
  body text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- NOTE: vector(768) assumes your embedding model outputs 768 dims.
create table if not exists public.rag_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.rag_documents(id) on delete cascade,
  chunk_index int not null,
  chunk_text text not null,
  embedding vector(768) not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.rag_chunks
  alter column embedding drop not null;

-- Indexes
create index if not exists idx_vitals_ts on public.vitals(ts desc);
create index if not exists idx_vitals_status on public.vitals(status);
create index if not exists idx_rag_chunks_document_id on public.rag_chunks(document_id);
create index if not exists idx_rag_chunks_text_fts on public.rag_chunks using gin (to_tsvector('english', chunk_text));
create unique index if not exists idx_rag_documents_title on public.rag_documents(title);
create unique index if not exists idx_rag_chunks_document_chunk on public.rag_chunks(document_id, chunk_index);

-- Vector similarity index
create index if not exists idx_rag_chunks_embedding
on public.rag_chunks
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

-- Retrieval function for RAG
create or replace function public.match_rag_chunks(
  query_embedding vector(768),
  match_count int default 5,
  filter jsonb default '{}'::jsonb
)
returns table (
  id uuid,
  document_id uuid,
  chunk_text text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    c.id,
    c.document_id,
    c.chunk_text,
    c.metadata,
    1 - (c.embedding <=> query_embedding) as similarity
  from public.rag_chunks c
  where c.embedding is not null
    and c.metadata @> filter
  order by c.embedding <=> query_embedding
  limit match_count;
$$;

create or replace function public.search_rag_chunks_text(
  query_text text,
  match_count int default 5
)
returns table (
  id uuid,
  document_id uuid,
  chunk_text text,
  metadata jsonb,
  rank real
)
language sql
stable
as $$
  select
    c.id,
    c.document_id,
    c.chunk_text,
    c.metadata,
    ts_rank_cd(to_tsvector('english', c.chunk_text), plainto_tsquery('english', query_text)) as rank
  from public.rag_chunks c
  where to_tsvector('english', c.chunk_text) @@ plainto_tsquery('english', query_text)
  order by rank desc
  limit match_count;
$$;

-- RBAC helper
create or replace function public.is_admin(user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists(
    select 1
    from public.profiles p
    where p.id = user_id and p.role = 'admin' and p.is_approved = true
  );
$$;

create or replace function public.is_approved(user_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists(
    select 1
    from public.profiles p
    where p.id = user_id and p.is_approved = true
  );
$$;

create or replace function public.bootstrap_first_admin(target_user_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  caller_id uuid := auth.uid();
  approved_admin_count bigint;
begin
  if caller_id is null or caller_id <> target_user_id then
    return false;
  end if;

  perform pg_advisory_xact_lock(hashtext('revive.bootstrap_first_admin'));

  select count(*)
    into approved_admin_count
  from public.profiles
  where role = 'admin' and is_approved = true;

  if approved_admin_count > 0 then
    return false;
  end if;

  update public.profiles
  set role = 'admin',
      is_approved = true,
      approved_at = now(),
      approved_by = target_user_id
  where id = target_user_id
    and is_approved = false;

  return found;
end;
$$;

revoke all on function public.bootstrap_first_admin(uuid) from public;
grant execute on function public.bootstrap_first_admin(uuid) to authenticated;

-- Seed fallback RAG corpus so retrieval is never empty.
insert into public.rag_documents (title, protocol_type, body, metadata)
values
  (
    'Hypoxia Immediate Response',
    'respiratory',
    'Assess airway, provide oxygen, monitor SpO2 continuously, and escalate if SpO2 stays below 90%.',
    '{"source":"bootstrap"}'::jsonb
  ),
  (
    'Cardiac Arrest Immediate Response',
    'cardiac',
    'Check responsiveness and pulse, start CPR immediately, activate emergency response team, and continue ACLS sequence.',
    '{"source":"bootstrap"}'::jsonb
  ),
  (
    'Tachycardia Stabilization',
    'cardiac',
    'Monitor heart rhythm, assess symptoms, maintain oxygenation, and prepare escalation for sustained instability.',
    '{"source":"bootstrap"}'::jsonb
  )
on conflict (title) do nothing;

insert into public.rag_chunks (document_id, chunk_index, chunk_text, embedding, metadata)
select d.id, s.chunk_index, s.chunk_text, null, '{"source":"bootstrap"}'::jsonb
from public.rag_documents d
join (
  values
    ('Hypoxia Immediate Response', 0, 'Open airway and position patient to optimize breathing.'),
    ('Hypoxia Immediate Response', 1, 'Start supplemental oxygen and track oxygen saturation every minute.'),
    ('Hypoxia Immediate Response', 2, 'Escalate urgently if SpO2 remains below 90% despite support.'),
    ('Cardiac Arrest Immediate Response', 0, 'Confirm unresponsiveness and check pulse immediately.'),
    ('Cardiac Arrest Immediate Response', 1, 'Start high-quality chest compressions and maintain airway support.'),
    ('Cardiac Arrest Immediate Response', 2, 'Continue ACLS protocol and prepare defibrillation if indicated.'),
    ('Tachycardia Stabilization', 0, 'Reassess heart rate trend and evaluate chest pain or breathlessness.'),
    ('Tachycardia Stabilization', 1, 'Maintain oxygenation and continuous rhythm monitoring.'),
    ('Tachycardia Stabilization', 2, 'Escalate to advanced cardiac support if instability worsens.')
) as s(title, chunk_index, chunk_text)
  on s.title = d.title
on conflict (document_id, chunk_index) do nothing;

-- updated_at triggers
DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
create trigger trg_profiles_updated_at
before update on public.profiles
for each row execute procedure public.set_updated_at();

DROP TRIGGER IF EXISTS trg_patients_updated_at ON public.patients;
create trigger trg_patients_updated_at
before update on public.patients
for each row execute procedure public.set_updated_at();

DROP TRIGGER IF EXISTS trg_rag_documents_updated_at ON public.rag_documents;
create trigger trg_rag_documents_updated_at
before update on public.rag_documents
for each row execute procedure public.set_updated_at();

-- RLS
alter table public.profiles enable row level security;
alter table public.patients enable row level security;
alter table public.vitals enable row level security;
alter table public.ai_guidance enable row level security;
alter table public.rag_documents enable row level security;
alter table public.rag_chunks enable row level security;

DROP POLICY IF EXISTS profiles_select_self_or_admin ON public.profiles;
create policy profiles_select_self_or_admin
  on public.profiles
  for select
  to authenticated
  using (id = auth.uid() or public.is_admin(auth.uid()));

DROP POLICY IF EXISTS profiles_insert_self ON public.profiles;
create policy profiles_insert_self
  on public.profiles
  for insert
  to authenticated
  with check (id = auth.uid());

DROP POLICY IF EXISTS profiles_update_admin_only ON public.profiles;
create policy profiles_update_admin_only
  on public.profiles
  for update
  to authenticated
  using (public.is_admin(auth.uid()))
  with check (public.is_admin(auth.uid()));

DROP POLICY IF EXISTS vitals_read_all_auth ON public.vitals;
create policy vitals_read_all_auth
  on public.vitals
  for select
  to authenticated
  using (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS vitals_insert_all_auth ON public.vitals;
create policy vitals_insert_all_auth
  on public.vitals
  for insert
  to authenticated
  with check (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS ai_guidance_read_all_auth ON public.ai_guidance;
create policy ai_guidance_read_all_auth
  on public.ai_guidance
  for select
  to authenticated
  using (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS ai_guidance_insert_all_auth ON public.ai_guidance;
create policy ai_guidance_insert_all_auth
  on public.ai_guidance
  for insert
  to authenticated
  with check (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS patients_read_all_auth ON public.patients;
create policy patients_read_all_auth
  on public.patients
  for select
  to authenticated
  using (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS patients_insert_all_auth ON public.patients;
create policy patients_insert_all_auth
  on public.patients
  for insert
  to authenticated
  with check (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS rag_documents_read_all_auth ON public.rag_documents;
create policy rag_documents_read_all_auth
  on public.rag_documents
  for select
  to authenticated
  using (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS rag_documents_admin_write ON public.rag_documents;
create policy rag_documents_admin_write
  on public.rag_documents
  for all
  to authenticated
  using (public.is_admin(auth.uid()))
  with check (public.is_admin(auth.uid()));

DROP POLICY IF EXISTS rag_chunks_read_all_auth ON public.rag_chunks;
create policy rag_chunks_read_all_auth
  on public.rag_chunks
  for select
  to authenticated
  using (public.is_approved(auth.uid()));

DROP POLICY IF EXISTS rag_chunks_admin_write ON public.rag_chunks;
create policy rag_chunks_admin_write
  on public.rag_chunks
  for all
  to authenticated
  using (public.is_admin(auth.uid()))
  with check (public.is_admin(auth.uid()));

-- ----------------------------------------------------------------------
-- User role assignment after creating users in Supabase Auth UI
-- ----------------------------------------------------------------------
-- Admins are simply rows in public.profiles where role = 'admin'.
-- You can promote/demote users directly in the table editor or with SQL.
--
-- Promote one or more users to admin:
-- update public.profiles
-- set role = 'admin'
--   , is_approved = true
--   , approved_at = now()
-- where email in ('admin@revive.com', 'admin2@revive.com');
--
-- Demote admin back to normal user:
-- update public.profiles
-- set role = 'user'
-- where email = 'admin2@revive.com';
--
-- update public.profiles
-- set role = 'user'
--   , is_approved = true
--   , approved_at = now()
-- where email in ('user@revive.com');

-- ----------------------------------------------------------------------
-- Demo-friendly approval model
-- ----------------------------------------------------------------------
-- Signup inserts into auth.users and the trigger creates public.profiles
-- with is_approved = false by default.
-- Admins simply approve users by updating public.profiles.is_approved = true.
