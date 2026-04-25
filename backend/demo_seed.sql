-- REVIVE demo seed data for Supabase SQL Editor
-- Prerequisite: run backend/supabase_setup.sql first.
--
-- Manual Supabase Auth setup (must be done in dashboard UI):
-- 1) Open Supabase Dashboard -> Authentication -> Users.
-- 2) Click "Add user" and create at least:
--    - admin@revive.com
--    - admin2@revive.com
--    - user@revive.com
--    - pending.user@revive.com
-- 3) Confirm both users.
-- 4) After users are created, run the SQL statements below.

-- ----------------------------------------------------------------------
-- Role assignment
-- ----------------------------------------------------------------------
update public.profiles
set role = 'admin'
  , is_approved = true
  , approved_at = now()
where email in ('admin@revive.com', 'admin2@revive.com');

update public.profiles
set role = 'user'
  , is_approved = true
  , approved_at = now()
where email = 'user@revive.com';

update public.profiles
set role = 'user'
  , is_approved = false
  , approved_at = null
where email = 'pending.user@revive.com';

-- ----------------------------------------------------------------------
-- Demo patients (at least 3)
-- ----------------------------------------------------------------------
insert into public.patients (name, age, notes, created_by)
values
  (
    'John Carter',
    67,
    'Post-op monitoring with mild COPD history.',
    (select id from public.profiles where email = 'admin@revive.com' limit 1)
  ),
  (
    'Meera Nair',
    54,
    'High-risk respiratory distress follow-up.',
    (select id from public.profiles where email = 'admin@revive.com' limit 1)
  ),
  (
    'Aarav Menon',
    72,
    'Cardiac rehab observation and continuous telemetry.',
    (select id from public.profiles where email = 'admin@revive.com' limit 1)
  );

-- ----------------------------------------------------------------------
-- Demo vitals (2-3 rows)
-- ----------------------------------------------------------------------
insert into public.vitals (
  patient_id,
  hr,
  spo2,
  movement,
  status,
  trend,
  scenario,
  source,
  ts
)
values
  (
    (select id from public.patients where name = 'John Carter' order by created_at desc limit 1),
    78,
    98,
    7,
    'Normal',
    'stable',
    'Normal',
    'seed',
    now() - interval '3 minutes'
  ),
  (
    (select id from public.patients where name = 'Meera Nair' order by created_at desc limit 1),
    128,
    85,
    15,
    'Critical',
    'critical',
    'Hypoxia',
    'seed',
    now() - interval '2 minutes'
  ),
  (
    (select id from public.patients where name = 'Aarav Menon' order by created_at desc limit 1),
    0,
    61,
    0,
    'Critical',
    'critical',
    'Cardiac Arrest',
    'seed',
    now() - interval '1 minutes'
  );

-- ----------------------------------------------------------------------
-- AI guidance linked to seeded vitals
-- ----------------------------------------------------------------------
insert into public.ai_guidance (vital_id, instant_action, detailed_steps)
values
  (
    (
      select id
      from public.vitals
      where source = 'seed' and scenario = 'Hypoxia'
      order by ts desc
      limit 1
    ),
    'Begin oxygen support and prepare urgent escalation.',
    '[
      "Check airway patency and breathing effort immediately.",
      "Administer supplemental oxygen and monitor SpO2 continuously.",
      "Escalate to emergency team if saturation remains below 90%."
    ]'::jsonb
  ),
  (
    (
      select id
      from public.vitals
      where source = 'seed' and scenario = 'Cardiac Arrest'
      order by ts desc
      limit 1
    ),
    'Start CPR protocol now and call code team.',
    '[
      "Confirm unresponsiveness and absence of pulse.",
      "Start chest compressions and maintain airway support.",
      "Continue ACLS protocol until advanced team arrives."
    ]'::jsonb
  );
