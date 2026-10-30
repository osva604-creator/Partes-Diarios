revoke execute on function public.handle_new_auth_user() from public, anon, authenticated;
grant execute on function public.handle_new_auth_user() to service_role;

drop policy farms_admin_write on public.farms;
create policy farms_admin_write on public.farms for insert to authenticated with check ((select public.is_app_admin()));
create policy farms_admin_update on public.farms for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy farms_admin_delete on public.farms for delete to authenticated using ((select public.is_app_admin()));
drop policy lots_admin_write on public.lots;
create policy lots_admin_insert on public.lots for insert to authenticated with check ((select public.is_app_admin()));
create policy lots_admin_update on public.lots for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy lots_admin_delete on public.lots for delete to authenticated using ((select public.is_app_admin()));
drop policy personnel_admin_write on public.personnel;
create policy personnel_admin_insert on public.personnel for insert to authenticated with check ((select public.is_app_admin()));
create policy personnel_admin_update on public.personnel for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy personnel_admin_delete on public.personnel for delete to authenticated using ((select public.is_app_admin()));
drop policy machines_admin_write on public.machines;
create policy machines_admin_insert on public.machines for insert to authenticated with check ((select public.is_app_admin()));
create policy machines_admin_update on public.machines for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy machines_admin_delete on public.machines for delete to authenticated using ((select public.is_app_admin()));
drop policy inputs_admin_write on public.inputs;
create policy inputs_admin_insert on public.inputs for insert to authenticated with check ((select public.is_app_admin()));
create policy inputs_admin_update on public.inputs for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy inputs_admin_delete on public.inputs for delete to authenticated using ((select public.is_app_admin()));
drop policy operations_admin_write on public.operations;
create policy operations_admin_insert on public.operations for insert to authenticated with check ((select public.is_app_admin()));
create policy operations_admin_update on public.operations for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy operations_admin_delete on public.operations for delete to authenticated using ((select public.is_app_admin()));

drop policy front_members_write on public.front_members;
create policy front_members_insert on public.front_members for insert to authenticated with check ((select public.current_app_role()) is not null);
create policy front_members_update on public.front_members for update to authenticated using ((select public.current_app_role()) is not null) with check ((select public.current_app_role()) is not null);
create policy front_members_delete on public.front_members for delete to authenticated using ((select public.current_app_role()) is not null);
drop policy front_task_members_write on public.front_task_members;
create policy front_task_members_insert on public.front_task_members for insert to authenticated with check ((select public.current_app_role()) is not null);
create policy front_task_members_update on public.front_task_members for update to authenticated using ((select public.current_app_role()) is not null) with check ((select public.current_app_role()) is not null);
create policy front_task_members_delete on public.front_task_members for delete to authenticated using ((select public.current_app_role()) is not null);
drop policy revisions_admin_write on public.report_revisions;
create policy revisions_admin_insert on public.report_revisions for insert to authenticated with check ((select public.is_app_admin()));
create policy revisions_admin_update on public.report_revisions for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()));
create policy revisions_admin_delete on public.report_revisions for delete to authenticated using ((select public.is_app_admin()));

drop policy reports_admin_update on public.daily_reports;
create policy reports_admin_update on public.daily_reports for update to authenticated
using ((select public.is_app_admin()) or (created_by = (select auth.uid()) and document_status in ('Borrador','Corregido')))
with check ((select public.is_app_admin()) or (created_by = (select auth.uid()) and document_status in ('Borrador','Corregido')));

create index if not exists allocations_task_idx on public.allocations(report_task_id);
create index if not exists allocations_personnel_idx on public.allocations(personnel_code);
create index if not exists allocations_machine_idx on public.allocations(machine_code);
create index if not exists allocations_replacement_idx on public.allocations(replacement_code);
create index if not exists allocations_front_idx on public.allocations(front_id);
create index if not exists daily_reports_reviewed_by_idx on public.daily_reports(reviewed_by);
create index if not exists daily_reports_sent_by_idx on public.daily_reports(sent_by);
create index if not exists front_members_personnel_idx on public.front_members(personnel_code);
create index if not exists front_members_machine_idx on public.front_members(machine_code);
create index if not exists front_task_members_operation_idx on public.front_task_members(operation_code);
create index if not exists front_task_members_personnel_idx on public.front_task_members(personnel_code);
create index if not exists front_task_members_machine_idx on public.front_task_members(machine_code);
create index if not exists part_inputs_input_idx on public.part_inputs(input_code);
create index if not exists part_inputs_task_idx on public.part_inputs(report_task_id);
create index if not exists report_tasks_front_idx on public.report_tasks(front_id);
create index if not exists report_tasks_lot_idx on public.report_tasks(lot_id);
create index if not exists report_tasks_operation_idx on public.report_tasks(operation_code);
create index if not exists report_revisions_saved_by_idx on public.report_revisions(saved_by);
create index if not exists user_preferences_front_idx on public.user_preferences(default_front_id);
create index if not exists work_cycles_created_by_idx on public.work_cycles(created_by);
create index if not exists work_cycles_operation_idx on public.work_cycles(operation_code);
create index if not exists fronts_created_by_idx on public.fronts(created_by);

-- Atomic report creation. The idempotency key is generated by the PWA before
-- enqueueing offline work, so retries cannot create duplicate reports.
create table public.report_idempotency (
  user_id uuid not null references auth.users(id) on delete cascade,
  idempotency_key uuid not null,
  report_id uuid not null references public.daily_reports(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, idempotency_key)
);
alter table public.report_idempotency enable row level security;
alter table public.report_idempotency force row level security;
grant select, insert on public.report_idempotency to authenticated;
create policy report_idempotency_self_read on public.report_idempotency for select to authenticated
using (user_id = (select auth.uid()));
create policy report_idempotency_self_insert on public.report_idempotency for insert to authenticated
with check (user_id = (select auth.uid()));

create or replace function public.create_daily_report(
  p_idempotency_key uuid,
  p_report_date date,
  p_service_order text,
  p_tasks jsonb
)
returns table(report_id uuid, report_code text, report_sequence bigint, replayed boolean)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_existing uuid;
  v_sequence bigint;
  v_report_id uuid;
  v_report_code text;
  v_task jsonb;
  v_task_id uuid;
  v_cycle_id uuid;
  v_cycle_no integer;
  v_lot_id text;
  v_operation text;
  v_quantity numeric;
  v_total numeric;
  v_fixed numeric;
  v_dynamic_count integer;
  v_alloc jsonb;
  v_input jsonb;
  v_line integer := 0;
begin
  if v_user is null or public.current_app_role() is null then
    raise exception 'Cuenta inactiva o sesión requerida' using errcode = '42501';
  end if;
  if p_idempotency_key is null or p_report_date is null or jsonb_typeof(p_tasks) <> 'array' or jsonb_array_length(p_tasks) = 0 then
    raise exception 'Datos incompletos del parte';
  end if;
  select i.report_id into v_existing from public.report_idempotency i
    where i.user_id = v_user and i.idempotency_key = p_idempotency_key;
  if v_existing is not null then
    select r.report_code, r.report_sequence into v_report_code, v_sequence from public.daily_reports r where r.id = v_existing;
    return query select v_existing, v_report_code, v_sequence, true;
    return;
  end if;

  insert into public.report_sequences(user_id,last_sequence) values (v_user,0) on conflict (user_id) do nothing;
  select s.last_sequence + 1 into v_sequence from public.report_sequences s where s.user_id = v_user for update;
  update public.report_sequences set last_sequence = v_sequence where user_id = v_user;
  v_report_code := 'pd-' || left(replace(v_user::text,'-',''),8) || '-' || lpad(v_sequence::text,6,'0');
  insert into public.daily_reports(report_code,report_sequence,report_date,service_order,created_by)
    values (v_report_code,v_sequence,p_report_date,coalesce(p_service_order,''),v_user) returning id into v_report_id;

  for v_task in select value from jsonb_array_elements(p_tasks) loop
    v_line := v_line + 1;
    v_lot_id := v_task->>'lot_id';
    v_operation := v_task->>'operation_code';
    v_quantity := (v_task->>'quantity')::numeric;
    if v_quantity <= 0 or v_lot_id is null or v_operation is null or v_task->>'front_id' is null then
      raise exception 'Tarea % incompleta o con cantidad no válida', v_line;
    end if;
    if not exists(select 1 from public.operations o where o.operation_code=v_operation and o.active) then
      raise exception 'La tarea % no existe o está inactiva', v_operation;
    end if;
    if not exists(select 1 from public.lots l where l.id=v_lot_id and l.active) then
      raise exception 'El lote % no existe o está inactivo', v_lot_id;
    end if;
    if not exists(select 1 from public.fronts f where f.id=(v_task->>'front_id')::uuid and f.active) then
      raise exception 'El frente de la tarea % no existe o está inactivo', v_line;
    end if;

    select c.id into v_cycle_id from public.work_cycles c
      where c.lot_id=v_lot_id and c.operation_code=v_operation and c.status='Abierto'
      order by c.cycle_no desc limit 1 for update;
    if v_cycle_id is null then
      select coalesce(max(c.cycle_no),0)+1 into v_cycle_no from public.work_cycles c
        where c.lot_id=v_lot_id and c.operation_code=v_operation;
      insert into public.work_cycles(lot_id,operation_code,cycle_no,target_quantity,unit,allocation_mode,started_on,created_by)
      values(v_lot_id,v_operation,v_cycle_no,greatest(coalesce((v_task->>'target_quantity')::numeric,0),0),
        coalesce(v_task->>'unit',''),coalesce(v_task->>'allocation_mode','Total a repartir'),p_report_date,v_user)
      returning id into v_cycle_id;
    end if;
    insert into public.report_tasks(report_id,line_no,work_cycle_id,front_id,lot_id,operation_code,part_date,quantity,crop,notes)
    values(v_report_id,v_line,v_cycle_id,(v_task->>'front_id')::uuid,v_lot_id,v_operation,p_report_date,v_quantity,
      coalesce(v_task->>'crop',''),coalesce(v_task->>'notes','')) returning id into v_task_id;

    if jsonb_typeof(v_task->'allocations') <> 'array' or jsonb_array_length(v_task->'allocations') = 0 then
      raise exception 'La tarea % necesita al menos una persona asignada',v_line;
    end if;
    v_total := 0; v_fixed := 0; v_dynamic_count := 0;
    for v_alloc in select value from jsonb_array_elements(v_task->'allocations') loop
      if not exists(select 1 from public.personnel p where p.employee_code=v_alloc->>'personnel_code' and p.active) then
        raise exception 'Legajo inexistente o inactivo: %',v_alloc->>'personnel_code';
      end if;
      if coalesce(v_alloc->>'machine_code','') <> '' and not exists(select 1 from public.machines m where m.machine_code=v_alloc->>'machine_code' and m.active) then
        raise exception 'Maquinaria inexistente o inactiva: %',v_alloc->>'machine_code';
      end if;
      if exists(select 1 from public.operations o where o.operation_code=v_operation and o.task_type='Manual') and coalesce(v_alloc->>'machine_code','') <> '' then
        raise exception 'La tarea manual % no admite maquinaria',v_operation;
      end if;
      if coalesce(v_alloc->>'attendance','Presente')='Ausente' and coalesce((v_alloc->>'quantity')::numeric,0) <> 0 then
        raise exception 'Las personas ausentes no reciben cantidad';
      end if;
      v_total := v_total + coalesce((v_alloc->>'quantity')::numeric,0);
      if coalesce(v_alloc->>'attendance','Presente')='Cantidad fija' then v_fixed := v_fixed + coalesce((v_alloc->>'quantity')::numeric,0);
      elsif coalesce(v_alloc->>'attendance','Presente') <> 'Ausente' then v_dynamic_count := v_dynamic_count + 1; end if;
      insert into public.allocations(report_task_id,personnel_code,machine_code,attendance,quantity,replacement_code,front_id,machine_start_time,machine_end_time,person_hours)
      values(v_task_id,v_alloc->>'personnel_code',nullif(v_alloc->>'machine_code',''),coalesce(v_alloc->>'attendance','Presente'),
        coalesce((v_alloc->>'quantity')::numeric,0),nullif(v_alloc->>'replacement_code',''),
        coalesce((v_alloc->>'front_id')::uuid,(v_task->>'front_id')::uuid),(v_alloc->>'machine_start_time')::integer,
        (v_alloc->>'machine_end_time')::integer,coalesce((v_alloc->>'person_hours')::numeric,12));
    end loop;
    if coalesce(v_task->>'allocation_mode','Total a repartir')='Total a repartir'
       and (abs(v_total-v_quantity)>0.01 or (v_dynamic_count>0 and v_fixed>v_quantity)) then
      raise exception 'La distribución de la tarea % no coincide con el total',v_line;
    end if;

    for v_input in select value from jsonb_array_elements(coalesce(v_task->'inputs','[]'::jsonb)) loop
      if not exists(select 1 from public.inputs i where i.input_code=v_input->>'input_code' and i.active) then
        raise exception 'Insumo inexistente o inactivo: %',v_input->>'input_code';
      end if;
      insert into public.part_inputs(report_task_id,input_code,dose,quantity,unit)
      values(v_task_id,v_input->>'input_code',coalesce((v_input->>'dose')::numeric,0),
        coalesce((v_input->>'quantity')::numeric,0),coalesce(v_input->>'unit',''));
    end loop;
  end loop;
  insert into public.report_idempotency(user_id,idempotency_key,report_id) values(v_user,p_idempotency_key,v_report_id);
  return query select v_report_id,v_report_code,v_sequence,false;
end;
$$;
grant execute on function public.create_daily_report(uuid,date,text,jsonb) to authenticated;

