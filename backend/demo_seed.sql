-- REVIVE extended demo seed
-- Run this after users are created in Supabase Auth.
--
-- DEMO ADMINS
--   admin@revive.com
--   admin2@revive.com
-- DEMO USERS
--   user1@revive.com   (approved)
--   user2@revive.com   (approved)
--   user3@revive.com   (pending)

-- ----------------------------------------------------------------------
-- Ensure profiles exist for the target demo users
-- ----------------------------------------------------------------------
insert into public.profiles (id, email, full_name, role, is_approved)
select
  u.id,
  lower(u.email),
  coalesce(u.raw_user_meta_data->>'full_name', split_part(u.email, '@', 1)),
  'user'::public.app_role,
  false
from auth.users u
where lower(u.email) in (
  'admin@revive.com',
  'admin2@revive.com',
  'user1@revive.com',
  'user2@revive.com',
  'user3@revive.com'
)
on conflict (id) do update
set email = excluded.email,
    full_name = excluded.full_name,
    updated_at = now();

-- ----------------------------------------------------------------------
-- Role and approval setup
-- ----------------------------------------------------------------------
update public.profiles
set role = 'admin',
    is_approved = true,
    approved_at = now(),
    approved_by = id
where lower(email) in ('admin@revive.com', 'admin2@revive.com');

update public.profiles
set role = 'user',
    is_approved = true,
    approved_at = now(),
    approved_by = (select id from public.profiles where lower(email) = 'admin@revive.com' limit 1)
where lower(email) in ('user1@revive.com', 'user2@revive.com');

update public.profiles
set role = 'user',
    is_approved = false,
    approved_at = null,
    approved_by = null
where lower(email) = 'user3@revive.com';

-- ----------------------------------------------------------------------
-- Demo patients
-- ----------------------------------------------------------------------
insert into public.patients (name, age, notes, created_by)
values
  ('John Carter', 67, 'Post-op respiratory watch with periodic desaturation.', (select id from public.profiles where lower(email) = 'admin@revive.com' limit 1)),
  ('Meera Nair', 54, 'Acute hypoxia follow-up and oxygen titration.', (select id from public.profiles where lower(email) = 'admin@revive.com' limit 1)),
  ('Aarav Menon', 72, 'Cardiac telemetry and rehab monitoring.', (select id from public.profiles where lower(email) = 'admin2@revive.com' limit 1)),
  ('Sophia Reed', 45, 'Post-anesthesia recovery observation.', (select id from public.profiles where lower(email) = 'admin2@revive.com' limit 1)),
  ('Daniel Kim', 61, 'COPD exacerbation early-warning tracking.', (select id from public.profiles where lower(email) = 'admin@revive.com' limit 1)),
  ('Fatima Ali', 39, 'General ward vitals baseline trend capture.', (select id from public.profiles where lower(email) = 'admin@revive.com' limit 1));

-- ----------------------------------------------------------------------
-- Demo vitals timeline (multiple samples)
-- ----------------------------------------------------------------------
insert into public.vitals (patient_id, hr, spo2, movement, status, trend, scenario, source, ts)
values
  ((select id from public.patients where name = 'John Carter' order by created_at desc limit 1), 84, 96, 8,  'Normal',   'stable',    'Normal',         'seed', now() - interval '14 minutes'),
  ((select id from public.patients where name = 'John Carter' order by created_at desc limit 1), 92, 94, 10, 'Warning',  'declining', 'Tachycardia',    'seed', now() - interval '12 minutes'),
  ((select id from public.patients where name = 'Meera Nair' order by created_at desc limit 1),   118, 89, 14, 'Critical', 'critical',  'Hypoxia',        'seed', now() - interval '10 minutes'),
  ((select id from public.patients where name = 'Meera Nair' order by created_at desc limit 1),   126, 85, 17, 'Critical', 'critical',  'Hypoxia',        'seed', now() - interval '8 minutes'),
  ((select id from public.patients where name = 'Aarav Menon' order by created_at desc limit 1),  0,   62, 0,  'Critical', 'critical',  'Cardiac Arrest', 'seed', now() - interval '6 minutes'),
  ((select id from public.patients where name = 'Sophia Reed' order by created_at desc limit 1),  77,  98, 6,  'Normal',   'stable',    'Normal',         'seed', now() - interval '5 minutes'),
  ((select id from public.patients where name = 'Daniel Kim' order by created_at desc limit 1),   104, 92, 12, 'Warning',  'declining', 'Hypoxia',        'seed', now() - interval '3 minutes'),
  ((select id from public.patients where name = 'Fatima Ali' order by created_at desc limit 1),   88,  97, 7,  'Normal',   'stable',    'Normal',         'seed', now() - interval '2 minutes');

-- ----------------------------------------------------------------------
-- AI guidance linked to critical seed rows
-- ----------------------------------------------------------------------
insert into public.ai_guidance (vital_id, instant_action, detailed_steps)
values
  (
    (select id from public.vitals where source = 'seed' and scenario = 'Hypoxia' order by ts desc limit 1),
    'Start oxygen support now and escalate to rapid response if saturation remains below target.',
    '[
      "Assess airway patency and breathing effort immediately.",
      "Apply supplemental oxygen and trend SpO2 every minute.",
      "Escalate immediately if saturation fails to improve."
    ]'::jsonb
  ),
  (
    (select id from public.vitals where source = 'seed' and scenario = 'Cardiac Arrest' order by ts desc limit 1),
    'Initiate CPR immediately and activate emergency code response.',
    '[
      "Confirm unresponsiveness and absence of pulse.",
      "Begin high-quality chest compressions and airway support.",
      "Continue ACLS protocol while preparing defibrillation readiness."
    ]'::jsonb
  );

-- ----------------------------------------------------------------------
-- Extended RAG document corpus
-- ----------------------------------------------------------------------
insert into public.rag_documents (title, protocol_type, body, metadata)
values
  ('Hypoxia Early Intervention', 'respiratory', 'Structured oxygen escalation protocol for declining saturation and respiratory distress.', '{"source":"demo_seed","tier":"core"}'::jsonb),
  ('Cardiac Arrest Primary Response', 'cardiac', 'Immediate BLS and ACLS-aligned response sequence for pulseless patients.', '{"source":"demo_seed","tier":"core"}'::jsonb),
  ('Tachycardia Stabilization Pathway', 'cardiac', 'Rate and perfusion stabilization pathway with escalation checkpoints.', '{"source":"demo_seed","tier":"core"}'::jsonb),
  ('Post-op Respiratory Monitoring', 'respiratory', 'Post-operative respiratory deterioration watchlist and intervention ladder.', '{"source":"demo_seed","tier":"support"}'::jsonb),
  ('Golden Hour Reassessment Framework', 'general', 'Two-minute reassessment framework for high-risk instability windows.', '{"source":"demo_seed","tier":"support"}'::jsonb),
  ('Low Movement Clinical Correlation', 'general', 'Interpretation guidance when movement drops with abnormal perfusion indicators.', '{"source":"demo_seed","tier":"support"}'::jsonb),
  ('Severe Desaturation Escalation', 'respiratory', 'Escalation protocol for persistent desaturation despite oxygen therapy.', '{"source":"demo_seed","tier":"critical"}'::jsonb),
  ('Telemetry Alert Playbook', 'cardiac', 'Response checklist for rhythm and hemodynamic telemetry alerts.', '{"source":"demo_seed","tier":"support"}'::jsonb),
  ('Airway-Breathing-Circulation Recheck', 'general', 'Rapid ABC recheck script for bedside teams.', '{"source":"demo_seed","tier":"core"}'::jsonb),
  ('Emergency Team Handoff Template', 'general', 'High-signal handoff format during clinical escalation.', '{"source":"demo_seed","tier":"support"}'::jsonb)
on conflict (title) do update
set protocol_type = excluded.protocol_type,
    body = excluded.body,
    metadata = excluded.metadata,
    updated_at = now();

-- ----------------------------------------------------------------------
-- Extended RAG chunks (40)
-- ----------------------------------------------------------------------
insert into public.rag_chunks (document_id, chunk_index, chunk_text, embedding, metadata)
select d.id, c.chunk_index, c.chunk_text, null, c.metadata
from public.rag_documents d
join (
  values
    ('Hypoxia Early Intervention', 0, 'Reposition patient, clear airway, and evaluate respiratory effort within 30 seconds.', '{"source":"demo_seed"}'::jsonb),
    ('Hypoxia Early Intervention', 1, 'Start oxygen and verify pulse oximeter placement before trend interpretation.', '{"source":"demo_seed"}'::jsonb),
    ('Hypoxia Early Intervention', 2, 'Escalate if SpO2 remains below 90% despite first-line oxygen support.', '{"source":"demo_seed"}'::jsonb),
    ('Hypoxia Early Intervention', 3, 'Document intervention timing and response trend at one-minute intervals.', '{"source":"demo_seed"}'::jsonb),

    ('Cardiac Arrest Primary Response', 0, 'Check responsiveness, breathing, and pulse with no delay.', '{"source":"demo_seed"}'::jsonb),
    ('Cardiac Arrest Primary Response', 1, 'Begin compressions at guideline depth and rate immediately.', '{"source":"demo_seed"}'::jsonb),
    ('Cardiac Arrest Primary Response', 2, 'Rotate compressor roles regularly to maintain CPR quality.', '{"source":"demo_seed"}'::jsonb),
    ('Cardiac Arrest Primary Response', 3, 'Prepare defibrillator and continue rhythm checks per protocol.', '{"source":"demo_seed"}'::jsonb),

    ('Tachycardia Stabilization Pathway', 0, 'Assess chest pain, dyspnea, perfusion, and mental status early.', '{"source":"demo_seed"}'::jsonb),
    ('Tachycardia Stabilization Pathway', 1, 'Maintain oxygenation and continuous ECG trend observation.', '{"source":"demo_seed"}'::jsonb),
    ('Tachycardia Stabilization Pathway', 2, 'Escalate when sustained tachycardia coexists with instability signs.', '{"source":"demo_seed"}'::jsonb),
    ('Tachycardia Stabilization Pathway', 3, 'Record intervention responses to support rapid clinical decisions.', '{"source":"demo_seed"}'::jsonb),

    ('Post-op Respiratory Monitoring', 0, 'Screen for shallow breathing, sedation burden, and secretion retention.', '{"source":"demo_seed"}'::jsonb),
    ('Post-op Respiratory Monitoring', 1, 'Use frequent SpO2 and movement trends to detect early decline.', '{"source":"demo_seed"}'::jsonb),
    ('Post-op Respiratory Monitoring', 2, 'Escalate quickly when respiratory pattern changes persist.', '{"source":"demo_seed"}'::jsonb),
    ('Post-op Respiratory Monitoring', 3, 'Coordinate analgesia review if respiratory depression is suspected.', '{"source":"demo_seed"}'::jsonb),

    ('Golden Hour Reassessment Framework', 0, 'Reassess airway, breathing, circulation, and mental status every two minutes.', '{"source":"demo_seed"}'::jsonb),
    ('Golden Hour Reassessment Framework', 1, 'Track whether interventions are improving objective vital trends.', '{"source":"demo_seed"}'::jsonb),
    ('Golden Hour Reassessment Framework', 2, 'Trigger escalation if trend remains flat or deteriorates.', '{"source":"demo_seed"}'::jsonb),
    ('Golden Hour Reassessment Framework', 3, 'Use concise team updates to reduce handoff delay.', '{"source":"demo_seed"}'::jsonb),

    ('Low Movement Clinical Correlation', 0, 'Low movement with hypoxia may indicate reduced responsiveness.', '{"source":"demo_seed"}'::jsonb),
    ('Low Movement Clinical Correlation', 1, 'Correlate movement with perfusion markers before concluding stabilization.', '{"source":"demo_seed"}'::jsonb),
    ('Low Movement Clinical Correlation', 2, 'Escalate when movement drops alongside worsening vital signs.', '{"source":"demo_seed"}'::jsonb),
    ('Low Movement Clinical Correlation', 3, 'Repeat neuro and perfusion checks at short intervals.', '{"source":"demo_seed"}'::jsonb),

    ('Severe Desaturation Escalation', 0, 'Confirm severe desaturation and check waveform reliability immediately.', '{"source":"demo_seed"}'::jsonb),
    ('Severe Desaturation Escalation', 1, 'Escalate oxygen delivery strategy and summon additional support.', '{"source":"demo_seed"}'::jsonb),
    ('Severe Desaturation Escalation', 2, 'Prepare advanced airway support for refractory oxygen failure.', '{"source":"demo_seed"}'::jsonb),
    ('Severe Desaturation Escalation', 3, 'Maintain continuous documentation and timing of interventions.', '{"source":"demo_seed"}'::jsonb),

    ('Telemetry Alert Playbook', 0, 'Validate telemetry signal quality before acting on arrhythmia alerts.', '{"source":"demo_seed"}'::jsonb),
    ('Telemetry Alert Playbook', 1, 'Cross-check rhythm alerts with BP, perfusion, and symptoms.', '{"source":"demo_seed"}'::jsonb),
    ('Telemetry Alert Playbook', 2, 'Escalate promptly for unstable rhythm and deteriorating perfusion.', '{"source":"demo_seed"}'::jsonb),
    ('Telemetry Alert Playbook', 3, 'Capture event window details for clinical handoff clarity.', '{"source":"demo_seed"}'::jsonb),

    ('Airway-Breathing-Circulation Recheck', 0, 'Airway: ensure patency and obstruction clearance.', '{"source":"demo_seed"}'::jsonb),
    ('Airway-Breathing-Circulation Recheck', 1, 'Breathing: evaluate rate, effort, and oxygen response.', '{"source":"demo_seed"}'::jsonb),
    ('Airway-Breathing-Circulation Recheck', 2, 'Circulation: inspect pulse quality, skin signs, and pressure trend.', '{"source":"demo_seed"}'::jsonb),
    ('Airway-Breathing-Circulation Recheck', 3, 'Repeat the ABC cycle after each major intervention.', '{"source":"demo_seed"}'::jsonb),

    ('Emergency Team Handoff Template', 0, 'State current status, trend direction, and immediate risk level.', '{"source":"demo_seed"}'::jsonb),
    ('Emergency Team Handoff Template', 1, 'Summarize key vitals and interventions already attempted.', '{"source":"demo_seed"}'::jsonb),
    ('Emergency Team Handoff Template', 2, 'Highlight pending actions and expected next reassessment time.', '{"source":"demo_seed"}'::jsonb),
    ('Emergency Team Handoff Template', 3, 'Use concise language and avoid duplicate narrative detail.', '{"source":"demo_seed"}'::jsonb)
) as c(title, chunk_index, chunk_text, metadata)
  on c.title = d.title
on conflict (document_id, chunk_index) do update
set chunk_text = excluded.chunk_text,
    metadata = excluded.metadata;
