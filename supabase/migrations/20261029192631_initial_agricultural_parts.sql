-- Initial agricultural operations schema for Partes Diarios.
-- Apply this migration before 20261029192647_tighten_part_permissions.sql.
create extension if not exists pgcrypto with schema extensions;

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '',
  role text not null default 'usuario' check (role in ('administrador', 'usuario')),
  active boolean not null default true,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create or replace function public.current_app_role() returns text language sql stable security invoker set search_path = '' as $$ select p.role from public.profiles p where p.user_id = (select auth.uid()) and p.active; $$;
create or replace function public.is_app_admin() returns boolean language sql stable security invoker set search_path = '' as $$ select coalesce((select public.current_app_role()) = 'administrador', false); $$;
create or replace function public.touch_updated_at() returns trigger language plpgsql set search_path = '' as $$ begin new.updated_at := now(); return new; end; $$;

create table public.farms (
  id text primary key, name text not null, active boolean not null default true,
  source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.lots (
  id text primary key, farm_id text not null references public.farms(id) on update cascade,
  lot_code text not null, lot_name text not null default '', crop text not null default '',
  variety text not null default '', gross_area numeric(14,3), net_area numeric(14,3),
  furrows integer, planting_year integer, planting_distance numeric(10,3), active boolean not null default true,
  source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (farm_id, lot_code)
);
create table public.personnel (
  employee_code text primary key, full_name text not null, hire_date date,
  cost_center_id text, cost_center_name text not null default '', active boolean not null default true,
  source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.machines (
  equipment_code text primary key, machine_code text not null unique, operational_group text not null default '',
  acquisition_date date, brand text not null default '', model text not null default '', plate text not null default '',
  active boolean not null default true, source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index machines_machine_code_idx on public.machines(machine_code);
create index machines_group_idx on public.machines(operational_group);
create table public.inputs (
  input_code text primary key, description text not null, unit text not null default '',
  group_code text not null default '', group_name text not null default '', active boolean not null default true,
  source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table public.operations (
  operation_code text primary key, name text not null, unit text not null default '',
  task_type text not null default '' check (task_type in ('', 'Manual', 'Mecanizada')),
  unit_description text not null default '', machine_groups text[] not null default '{}',
  allows_inputs boolean not null default false, default_target numeric(14,3), active boolean not null default true,
  source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table public.fronts (
  id uuid primary key default gen_random_uuid(), name text not null unique, active boolean not null default true,
  created_by uuid not null default auth.uid() references auth.users(id),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  check (length(trim(name)) between 1 and 120)
);
create table public.front_members (
  id uuid primary key default gen_random_uuid(), front_id uuid not null references public.fronts(id) on delete cascade,
  personnel_code text not null references public.personnel(employee_code),
  machine_code text references public.machines(machine_code), created_at timestamptz not null default now(),
  unique (front_id, personnel_code)
);
create table public.front_task_members (
  id uuid primary key default gen_random_uuid(), front_id uuid not null references public.fronts(id) on delete cascade,
  operation_code text not null references public.operations(operation_code),
  personnel_code text not null references public.personnel(employee_code),
  machine_code text references public.machines(machine_code), created_at timestamptz not null default now(),
  unique (front_id, operation_code, personnel_code)
);

create table public.work_cycles (
  id uuid primary key default gen_random_uuid(), lot_id text not null references public.lots(id),
  operation_code text not null references public.operations(operation_code), cycle_no integer not null check (cycle_no > 0),
  target_quantity numeric(14,3) not null default 0 check (target_quantity >= 0), unit text not null,
  allocation_mode text not null check (allocation_mode in ('Total a repartir', 'Cantidad individual')),
  status text not null default 'Abierto' check (status in ('Abierto', 'Cerrado')),
  started_on date not null, closed_on date, created_by uuid not null default auth.uid() references auth.users(id),
  created_at timestamptz not null default now(), unique (lot_id, operation_code, cycle_no),
  check ((status = 'Abierto' and closed_on is null) or (status = 'Cerrado' and closed_on is not null))
);
create index work_cycles_open_lookup_idx on public.work_cycles(lot_id, operation_code, id desc) where status = 'Abierto';
create table public.daily_reports (
  id uuid primary key default gen_random_uuid(), report_code text not null unique, report_sequence bigint not null,
  report_date date not null, service_order text not null default '',
  document_status text not null default 'Borrador' check (document_status in ('Borrador', 'Corregido', 'Revisado', 'Enviado')),
  created_by uuid not null default auth.uid() references auth.users(id),
  reviewed_by uuid references auth.users(id), reviewed_at timestamptz,
  sent_by uuid references auth.users(id), sent_at timestamptz, sent_to text not null default '', sent_via text not null default '',
  pdf_version integer not null default 0 check (pdf_version >= 0), modified_at timestamptz,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (created_by, report_sequence)
);
create index daily_reports_owner_date_idx on public.daily_reports(created_by, report_date desc, id desc);
create table public.report_tasks (
  id uuid primary key default gen_random_uuid(), report_id uuid not null references public.daily_reports(id) on delete cascade,
  line_no integer not null check (line_no > 0), work_cycle_id uuid not null references public.work_cycles(id),
  front_id uuid not null references public.fronts(id), lot_id text not null references public.lots(id),
  operation_code text not null references public.operations(operation_code), part_date date not null,
  quantity numeric(14,3) not null check (quantity > 0), crop text not null default '', notes text not null default '',
  created_at timestamptz not null default now(), unique (report_id, line_no)
);
create index report_tasks_cycle_idx on public.report_tasks(work_cycle_id);
create table public.allocations (
  id uuid primary key default gen_random_uuid(), report_task_id uuid not null references public.report_tasks(id) on delete cascade,
  personnel_code text not null references public.personnel(employee_code), machine_code text references public.machines(machine_code),
  attendance text not null default 'Presente' check (attendance in ('Presente', 'Ausente', 'Cantidad fija')),
  quantity numeric(14,3) not null default 0 check (quantity >= 0),
  replacement_code text references public.personnel(employee_code), front_id uuid references public.fronts(id),
  machine_start_time integer, machine_end_time integer,
  person_hours numeric(8,2) not null default 12 check (person_hours >= 0 and person_hours <= 48),
  created_at timestamptz not null default now(),
  check ((machine_start_time is null and machine_end_time is null) or (machine_start_time >= 0 and machine_end_time >= machine_start_time))
);
create table public.part_inputs (
  id uuid primary key default gen_random_uuid(), report_task_id uuid not null references public.report_tasks(id) on delete cascade,
  input_code text not null references public.inputs(input_code), dose numeric(14,5) not null default 0 check (dose >= 0),
  quantity numeric(14,3) not null default 0 check (quantity >= 0), unit text not null default '',
  created_at timestamptz not null default now()
);
create table public.user_preferences (
  user_id uuid primary key default auth.uid() references auth.users(id) on delete cascade,
  default_front_id uuid references public.fronts(id) on delete set null,
  default_person_hours numeric(8,2) not null default 12 check (default_person_hours >= 0 and default_person_hours <= 48),
  whatsapp_number text not null default '', whatsapp_message text not null default 'Parte diario {id} - {fecha}',
  updated_at timestamptz not null default now()
);
create table public.report_revisions (
  id uuid primary key default gen_random_uuid(), report_id uuid not null references public.daily_reports(id) on delete cascade,
  saved_by uuid not null default auth.uid() references auth.users(id), was_sent boolean not null default false,
  snapshot jsonb not null check (jsonb_typeof(snapshot) = 'object'), created_at timestamptz not null default now()
);
create index report_revisions_report_idx on public.report_revisions(report_id, created_at desc);
create table public.report_sequences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  last_sequence bigint not null default 0 check (last_sequence >= 0)
);

create trigger profiles_touch_updated_at before update on public.profiles for each row execute function public.touch_updated_at();
create trigger farms_touch_updated_at before update on public.farms for each row execute function public.touch_updated_at();
create trigger lots_touch_updated_at before update on public.lots for each row execute function public.touch_updated_at();
create trigger personnel_touch_updated_at before update on public.personnel for each row execute function public.touch_updated_at();
create trigger machines_touch_updated_at before update on public.machines for each row execute function public.touch_updated_at();
create trigger inputs_touch_updated_at before update on public.inputs for each row execute function public.touch_updated_at();
create trigger operations_touch_updated_at before update on public.operations for each row execute function public.touch_updated_at();
create trigger fronts_touch_updated_at before update on public.fronts for each row execute function public.touch_updated_at();
create trigger daily_reports_touch_updated_at before update on public.daily_reports for each row execute function public.touch_updated_at();
create trigger user_preferences_touch_updated_at before update on public.user_preferences for each row execute function public.touch_updated_at();

create or replace function public.handle_new_auth_user() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles(user_id, display_name, role)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', ''), 'usuario')
  on conflict (user_id) do nothing;
  return new;
end; $$;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_auth_user();
create or replace function public.bootstrap_report_sequence() returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  insert into public.report_sequences(user_id, last_sequence) values (new.user_id, 0) on conflict (user_id) do nothing;
  return new;
end; $$;
create trigger profile_bootstrap_sequence after insert on public.profiles for each row execute function public.bootstrap_report_sequence();

do $$ declare table_name text; begin
  foreach table_name in array array['profiles','farms','lots','personnel','machines','inputs','operations','fronts','front_members','front_task_members','work_cycles','daily_reports','report_tasks','allocations','part_inputs','user_preferences','report_revisions','report_sequences'] loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('alter table public.%I force row level security', table_name);
  end loop;
end $$;
create policy profile_self_read on public.profiles for select to authenticated using (user_id = (select auth.uid()) or (select public.is_app_admin()));
create policy profile_admin_update on public.profiles for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
do $$ declare table_name text; begin
  foreach table_name in array array['farms','lots','personnel','machines','inputs','operations'] loop
    execute format('create policy %I on public.%I for select to authenticated using ((select public.current_app_role()) is not null)', table_name || '_authenticated_read', table_name);
    execute format('create policy %I on public.%I for all to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()))', table_name || '_admin_write', table_name);
  end loop;
end $$;
create policy fronts_read on public.fronts for select to authenticated using ((select public.current_app_role()) is not null);
create policy fronts_insert on public.fronts for insert to authenticated with check ((select public.current_app_role()) is not null and created_by = (select auth.uid()));
create policy fronts_update on public.fronts for update to authenticated using ((select public.current_app_role()) is not null and created_by = (select auth.uid())) with check ((select public.current_app_role()) is not null and created_by = (select auth.uid()));
create policy fronts_admin_delete on public.fronts for delete to authenticated using ((select public.is_app_admin()));
create policy front_members_read on public.front_members for select to authenticated using ((select public.current_app_role()) is not null);
create policy front_members_write on public.front_members for all to authenticated using ((select public.current_app_role()) is not null) with check ((select public.current_app_role()) is not null);
create policy front_task_members_read on public.front_task_members for select to authenticated using ((select public.current_app_role()) is not null);
create policy front_task_members_write on public.front_task_members for all to authenticated using ((select public.current_app_role()) is not null) with check ((select public.current_app_role()) is not null);
create policy cycles_read on public.work_cycles for select to authenticated using ((select public.current_app_role()) is not null);
create policy cycles_insert on public.work_cycles for insert to authenticated with check ((select public.current_app_role()) is not null and created_by = (select auth.uid()));
create policy cycles_admin_update on public.work_cycles for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy cycles_admin_delete on public.work_cycles for delete to authenticated using ((select public.is_app_admin()));
create policy reports_read on public.daily_reports for select to authenticated using ((select public.current_app_role()) is not null);
create policy reports_insert on public.daily_reports for insert to authenticated with check ((select public.current_app_role()) is not null and created_by = (select auth.uid()));
create policy reports_admin_update on public.daily_reports for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy reports_admin_delete on public.daily_reports for delete to authenticated using ((select public.is_app_admin()));
create policy report_tasks_read on public.report_tasks for select to authenticated using ((select public.current_app_role()) is not null);
create policy report_tasks_insert on public.report_tasks for insert to authenticated with check ((select public.current_app_role()) is not null and exists (select 1 from public.daily_reports r where r.id = report_id and r.created_by = (select auth.uid())));
create policy report_tasks_admin_update on public.report_tasks for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy report_tasks_admin_delete on public.report_tasks for delete to authenticated using ((select public.is_app_admin()));
create policy allocations_read on public.allocations for select to authenticated using ((select public.current_app_role()) is not null);
create policy allocations_insert on public.allocations for insert to authenticated with check ((select public.current_app_role()) is not null and exists (select 1 from public.report_tasks t join public.daily_reports r on r.id = t.report_id where t.id = report_task_id and r.created_by = (select auth.uid())));
create policy allocations_admin_update on public.allocations for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy allocations_admin_delete on public.allocations for delete to authenticated using ((select public.is_app_admin()));
create policy part_inputs_read on public.part_inputs for select to authenticated using ((select public.current_app_role()) is not null);
create policy part_inputs_insert on public.part_inputs for insert to authenticated with check ((select public.current_app_role()) is not null and exists (select 1 from public.report_tasks t join public.daily_reports r on r.id = t.report_id where t.id = report_task_id and r.created_by = (select auth.uid())));
create policy part_inputs_admin_update on public.part_inputs for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy part_inputs_admin_delete on public.part_inputs for delete to authenticated using ((select public.is_app_admin()));
create policy preferences_self_read on public.user_preferences for select to authenticated using (user_id = (select auth.uid()) or (select public.is_app_admin()));
create policy preferences_self_insert on public.user_preferences for insert to authenticated with check (user_id = (select auth.uid()));
create policy preferences_self_update on public.user_preferences for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy revisions_read on public.report_revisions for select to authenticated using ((select public.current_app_role()) is not null);
create policy revisions_admin_write on public.report_revisions for all to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy sequences_self_read on public.report_sequences for select to authenticated using (user_id = (select auth.uid()) or (select public.is_app_admin()));
create policy sequences_self_insert on public.report_sequences for insert to authenticated with check (user_id = (select auth.uid()));
create policy sequences_self_update on public.report_sequences for update to authenticated using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

grant select, update on public.profiles to authenticated;
grant select, insert, update, delete on public.farms, public.lots, public.personnel, public.machines, public.inputs, public.operations to authenticated;
grant select, insert, update, delete on public.fronts, public.front_members, public.front_task_members to authenticated;
grant select, insert, update, delete on public.work_cycles, public.daily_reports, public.report_tasks, public.allocations, public.part_inputs, public.user_preferences, public.report_revisions, public.report_sequences to authenticated;
grant execute on function public.current_app_role() to authenticated;
grant execute on function public.is_app_admin() to authenticated;
