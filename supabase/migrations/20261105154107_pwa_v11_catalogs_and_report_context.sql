-- V1.1 catalog model and immutable per-task context. This migration is additive:
-- historical lots and report rows remain addressable by their existing keys.
alter table public.lots
  add column if not exists selectable boolean not null default true,
  add column if not exists agronomic_data_available boolean not null default true,
  add column if not exists totvs_location_id text not null default '',
  add column if not exists suggested_cost_center_id text not null default '',
  add column if not exists suggested_cost_center_name text not null default '';

alter table public.report_tasks
  add column if not exists cost_center_context jsonb not null default '{}'::jsonb,
  add column if not exists catalog_snapshot jsonb not null default '{}'::jsonb;
alter table public.work_cycles
  add column if not exists target_available boolean not null default true;
create index if not exists report_idempotency_report_id_idx
  on public.report_idempotency(report_id);

create table if not exists public.cost_centers (
  cost_center_id text primary key,
  name text not null,
  active boolean not null default true,
  source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.operation_groups (
  group_code text primary key,
  name text not null,
  active boolean not null default true,
  source_data jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.cost_center_operation_groups (
  cost_center_id text not null references public.cost_centers(cost_center_id),
  group_code text not null references public.operation_groups(group_code),
  primary key (cost_center_id, group_code)
);
create table if not exists public.operation_group_operations (
  group_code text not null references public.operation_groups(group_code),
  operation_code text not null references public.operations(operation_code),
  primary key (group_code, operation_code)
);
create table if not exists public.operation_machines (
  operation_code text not null references public.operations(operation_code),
  machine_code text not null references public.machines(machine_code),
  primary key (operation_code, machine_code)
);
create table if not exists public.operation_inputs (
  operation_code text not null references public.operations(operation_code),
  input_code text not null references public.inputs(input_code),
  primary key (operation_code, input_code)
);

-- The composite primary keys cover lookups by their first column. Index the
-- reverse foreign-key paths too, so catalog deletes/updates and selectors do
-- not scan the full relationship tables.
create index if not exists cost_center_operation_groups_group_idx
  on public.cost_center_operation_groups(group_code);
create index if not exists operation_group_operations_operation_idx
  on public.operation_group_operations(operation_code);
create index if not exists operation_machines_machine_idx
  on public.operation_machines(machine_code);
create index if not exists operation_inputs_input_idx
  on public.operation_inputs(input_code);

create or replace function private.enforce_part_input_compatibility()
returns trigger language plpgsql security invoker set search_path = '' as $$
declare v_operation text;
begin
  select t.operation_code into v_operation from public.report_tasks t where t.id=new.report_task_id;
  if exists(select 1 from public.operation_inputs oi where oi.operation_code=v_operation)
     and not exists(select 1 from public.operation_inputs oi where oi.operation_code=v_operation and oi.input_code=new.input_code) then
    raise exception 'El insumo no es compatible con la tarea %',v_operation;
  end if;
  return new;
end; $$;
create trigger part_inputs_operation_compatibility
  before insert or update of report_task_id,input_code on public.part_inputs
  for each row execute function private.enforce_part_input_compatibility();

do $$ declare t text; begin
  foreach t in array array['cost_centers','operation_groups','cost_center_operation_groups','operation_group_operations','operation_machines','operation_inputs'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('create policy %I on public.%I for select to authenticated using ((select public.current_app_role()) is not null)', t || '_read', t);
    execute format('create policy %I on public.%I for insert to authenticated with check ((select public.is_app_admin()))', t || '_admin_insert', t);
    execute format('create policy %I on public.%I for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()))', t || '_admin_update', t);
    execute format('create policy %I on public.%I for delete to authenticated using ((select public.is_app_admin()))', t || '_admin_delete', t);
  end loop;
end $$;
grant select, insert, update, delete on public.cost_centers, public.operation_groups,
  public.cost_center_operation_groups, public.operation_group_operations,
  public.operation_machines, public.operation_inputs to authenticated;

create or replace function public.create_daily_report(
  p_idempotency_key uuid, p_report_date date, p_service_order text, p_tasks jsonb
)
returns table(report_id uuid, report_code text, report_sequence bigint, replayed boolean)
language plpgsql security invoker set search_path = '' as $$
declare
  v_user uuid := auth.uid(); v_existing uuid; v_sequence bigint; v_report_id uuid;
  v_report_code text; v_task jsonb; v_task_id uuid; v_cycle_id uuid; v_cycle_no integer;
  v_lot_id text; v_operation text; v_quantity numeric; v_total numeric; v_fixed numeric;
  v_dynamic_count integer; v_alloc jsonb; v_input jsonb; v_line integer := 0;
  v_seen text[] := '{}'; v_context jsonb; v_lot public.lots%rowtype; v_op public.operations%rowtype;
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
    return query select v_existing, v_report_code, v_sequence, true; return;
  end if;

  -- Reject duplicate lot + operation before any document rows are written.
  if exists (
    select 1 from jsonb_to_recordset(p_tasks) as x(lot_id text, operation_code text)
    group by x.lot_id, x.operation_code having count(*) > 1
  ) then raise exception 'No se puede repetir lote y operación en el mismo parte'; end if;

  v_sequence := private.next_report_sequence();
  v_report_code := 'pd-' || left(replace(v_user::text,'-',''),8) || '-' || lpad(v_sequence::text,6,'0');
  insert into public.daily_reports(report_code,report_sequence,report_date,service_order,created_by)
    values (v_report_code,v_sequence,p_report_date,coalesce(p_service_order,''),v_user) returning id into v_report_id;

  for v_task in select value from jsonb_array_elements(p_tasks) loop
    v_line := v_line + 1; v_lot_id := v_task->>'lot_id'; v_operation := v_task->>'operation_code';
    v_quantity := (v_task->>'quantity')::numeric;
    if v_quantity <= 0 or v_lot_id is null or v_operation is null or v_task->>'front_id' is null then raise exception 'Tarea % incompleta o con cantidad no válida', v_line; end if;
    select * into v_lot from public.lots l where l.id=v_lot_id and l.active and l.selectable;
    if not found then raise exception 'El lote % no está disponible para nuevas cargas', v_lot_id; end if;
    select * into v_op from public.operations o where o.operation_code=v_operation and o.active;
    if not found then raise exception 'La tarea % no existe o está inactiva', v_operation; end if;
    if not exists(select 1 from public.fronts f where f.id=(v_task->>'front_id')::uuid and f.active) then raise exception 'El frente de la tarea % no existe o está inactivo', v_line; end if;
    if (v_task->>'allocation_mode') not in ('Total a repartir','Cantidad individual') then raise exception 'Modo de cantidad inválido'; end if;
    if (v_task->>'allocation_mode') = 'Total a repartir' and (v_task->>'target_quantity') is null then raise exception 'El objetivo debe especificarse explícitamente; no se completa con la cantidad del parte'; end if;

    select c.id into v_cycle_id from public.work_cycles c where c.lot_id=v_lot_id and c.operation_code=v_operation and c.status='Abierto' order by c.cycle_no desc limit 1 for update;
    if v_cycle_id is null then
      select coalesce(max(c.cycle_no),0)+1 into v_cycle_no from public.work_cycles c where c.lot_id=v_lot_id and c.operation_code=v_operation;
      insert into public.work_cycles(lot_id,operation_code,cycle_no,target_quantity,target_available,unit,allocation_mode,status,started_on,created_by)
      values(v_lot_id,v_operation,v_cycle_no,case when coalesce((v_task->>'target_available')::boolean,true) then greatest(coalesce((v_task->>'target_quantity')::numeric,0),0) else 0 end,coalesce((v_task->>'target_available')::boolean,true),coalesce(v_task->>'unit',''),coalesce(v_task->>'allocation_mode','Total a repartir'),'Abierto',p_report_date,v_user) returning id into v_cycle_id;
    end if;
    v_context := coalesce(v_task->'cost_center_context','{}'::jsonb);
    insert into public.report_tasks(report_id,line_no,work_cycle_id,front_id,lot_id,operation_code,part_date,quantity,crop,notes,cost_center_context,catalog_snapshot)
      values(v_report_id,v_line,v_cycle_id,(v_task->>'front_id')::uuid,v_lot_id,v_operation,p_report_date,v_quantity,coalesce(v_task->>'crop',''),coalesce(v_task->>'notes',''),v_context,
        jsonb_build_object('lot',jsonb_build_object('id',v_lot.id,'farm_id',v_lot.farm_id,'code',v_lot.lot_code,'name',v_lot.lot_name,'crop',v_lot.crop,'variety',v_lot.variety),
          'operation',jsonb_build_object('code',v_op.operation_code,'name',v_op.name,'unit',v_op.unit,'task_type',v_op.task_type,'machine_groups',to_jsonb(v_op.machine_groups)))) returning id into v_task_id;
    if coalesce(jsonb_typeof(v_task->'allocations'),'null') <> 'array' or jsonb_array_length(coalesce(v_task->'allocations','[]'::jsonb))=0 then raise exception 'La tarea % necesita al menos una persona asignada',v_line; end if;
    if exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(personnel_code text) group by a.personnel_code having count(*)>1) then
      raise exception 'Una persona no puede repetirse en la tarea %',v_line;
    end if;
    v_total:=0; v_fixed:=0; v_dynamic_count:=0;
    for v_alloc in select value from jsonb_array_elements(v_task->'allocations') loop
      if not exists(select 1 from public.personnel p where p.employee_code=v_alloc->>'personnel_code' and p.active) then raise exception 'Legajo inexistente o inactivo: %',v_alloc->>'personnel_code'; end if;
      if coalesce(v_alloc->>'machine_code','')<>'' and not exists(select 1 from public.machines m where m.machine_code=v_alloc->>'machine_code' and m.active) then raise exception 'Maquinaria inexistente o inactiva: %',v_alloc->>'machine_code'; end if;
      if v_op.task_type='Manual' and coalesce(v_alloc->>'machine_code','')<>'' then raise exception 'La tarea manual % no admite maquinaria',v_operation; end if;
      if coalesce(v_alloc->>'machine_code','')<>'' and (
        (exists(select 1 from public.operation_machines om where om.operation_code=v_operation)
          and not exists(select 1 from public.operation_machines om where om.operation_code=v_operation and om.machine_code=v_alloc->>'machine_code'))
        or (not exists(select 1 from public.operation_machines om where om.operation_code=v_operation) and cardinality(v_op.machine_groups)>0
          and not exists(select 1 from public.machines m where m.machine_code=v_alloc->>'machine_code' and exists(select 1 from unnest(v_op.machine_groups) g where upper(trim(g))=upper(trim(m.operational_group)))))
      ) then raise exception 'La maquinaria no es compatible con la tarea %',v_operation; end if;
      if coalesce(v_alloc->>'attendance','Presente')='Ausente' and coalesce((v_alloc->>'quantity')::numeric,0)<>0 then raise exception 'Las personas ausentes no reciben cantidad'; end if;
      v_total:=v_total+coalesce((v_alloc->>'quantity')::numeric,0);
      if coalesce(v_alloc->>'attendance','Presente')='Cantidad fija' then v_fixed:=v_fixed+coalesce((v_alloc->>'quantity')::numeric,0); elsif coalesce(v_alloc->>'attendance','Presente')<>'Ausente' then v_dynamic_count:=v_dynamic_count+1; end if;
      insert into public.allocations(report_task_id,personnel_code,machine_code,attendance,quantity,replacement_code,front_id,machine_start_time,machine_end_time,person_hours)
      values(v_task_id,v_alloc->>'personnel_code',nullif(v_alloc->>'machine_code',''),coalesce(v_alloc->>'attendance','Presente'),coalesce((v_alloc->>'quantity')::numeric,0),nullif(v_alloc->>'replacement_code',''),coalesce((v_alloc->>'front_id')::uuid,(v_task->>'front_id')::uuid),(v_alloc->>'machine_start_time')::integer,(v_alloc->>'machine_end_time')::integer,coalesce((v_alloc->>'person_hours')::numeric,12));
    end loop;
    if (v_task->>'allocation_mode')='Total a repartir' and (abs(v_total-v_quantity)>0.001 or (v_dynamic_count>0 and v_fixed>v_quantity)) then raise exception 'La distribución de la tarea % no coincide con el total',v_line; end if;
    if (v_task->>'allocation_mode')='Cantidad individual' and abs(v_total-v_quantity)>0.001 then raise exception 'El total de la tarea % debe coincidir con la suma individual',v_line; end if;
    if upper(trim(coalesce(v_task->>'unit','')))='SC' and (v_quantity<>trunc(v_quantity) or exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(quantity numeric) where a.quantity<>trunc(a.quantity))) then
      raise exception 'Las cantidades en surcos deben ser enteras';
    end if;
    if cardinality(v_op.machine_groups)>0 and not exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(machine_code text) where nullif(a.machine_code,'') is not null) then
      raise exception 'La tarea % requiere maquinaria compatible',v_operation;
    end if;
    for v_input in select value from jsonb_array_elements(coalesce(v_task->'inputs','[]'::jsonb)) loop
      if not exists(select 1 from public.inputs i where i.input_code=v_input->>'input_code' and i.active) then raise exception 'Insumo inexistente o inactivo: %',v_input->>'input_code'; end if;
      insert into public.part_inputs(report_task_id,input_code,dose,quantity,unit) values(v_task_id,v_input->>'input_code',coalesce((v_input->>'dose')::numeric,0),coalesce((v_input->>'quantity')::numeric,0),coalesce(v_input->>'unit',''));
    end loop;
  end loop;
  insert into public.report_idempotency(user_id,idempotency_key,report_id) values(v_user,p_idempotency_key,v_report_id);
  return query select v_report_id,v_report_code,v_sequence,false;
end; $$;
revoke all on function public.create_daily_report(uuid,date,text,jsonb) from public, anon;
grant execute on function public.create_daily_report(uuid,date,text,jsonb) to authenticated;

-- Review is an explicit, administrator-only snapshot transition. PDF creation is
-- still a client action; every review increments pdf_version to identify it.
create or replace function public.review_daily_report(p_report_id uuid)
returns integer language plpgsql security invoker set search_path = '' as $$
declare v_version integer;
begin
  if auth.uid() is null or not public.is_app_admin() then
    raise exception 'Solo administración puede revisar partes' using errcode = '42501';
  end if;
  perform 1 from public.daily_reports where id = p_report_id for update;
  if not found then raise exception 'No se encontró el parte'; end if;
  if exists(select 1 from public.daily_reports where id=p_report_id and document_status='Enviado') then
    raise exception 'Un parte enviado requiere corrección y una nueva revisión';
  end if;
  insert into public.report_revisions(report_id,saved_by,was_sent,snapshot)
  select r.id, auth.uid(), r.sent_at is not null,
    jsonb_build_object('report',to_jsonb(r),'tasks',coalesce((
      select jsonb_agg(jsonb_build_object('task',to_jsonb(t),'allocations',coalesce((select jsonb_agg(to_jsonb(a)) from public.allocations a where a.report_task_id=t.id),'[]'::jsonb),'inputs',coalesce((select jsonb_agg(to_jsonb(i)) from public.part_inputs i where i.report_task_id=t.id),'[]'::jsonb)) order by t.line_no)
      from public.report_tasks t where t.report_id=r.id),'[]'::jsonb))
  from public.daily_reports r where r.id=p_report_id;
  update public.daily_reports set document_status='Revisado',reviewed_by=auth.uid(),reviewed_at=now(),pdf_version=pdf_version+1 where id=p_report_id returning pdf_version into v_version;
  return v_version;
end; $$;
revoke all on function public.review_daily_report(uuid) from public, anon;
grant execute on function public.review_daily_report(uuid) to authenticated;

-- Keep the narrowly privileged write in the unexposed private schema. The
-- public RPC wrapper remains invoker and the private function verifies the
-- JWT user and owner/admin relationship before changing the document state.
create or replace function private.confirm_daily_report_sent(p_report_id uuid,p_sent_to text,p_sent_via text)
returns void language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or public.current_app_role() is null then
    raise exception 'Cuenta inactiva o sesión requerida' using errcode = '42501';
  end if;
  if nullif(trim(p_sent_via),'') is null then raise exception 'Indicá el canal de envío'; end if;
  perform 1 from public.daily_reports r where r.id=p_report_id and (r.created_by=auth.uid() or public.is_app_admin()) for update;
  if not found then raise exception 'No tenés permiso para confirmar el envío' using errcode = '42501'; end if;
  if not exists(select 1 from public.daily_reports where id=p_report_id and document_status='Revisado') then
    raise exception 'El parte debe estar revisado antes de confirmar el envío';
  end if;
  update public.daily_reports set document_status='Enviado',sent_by=auth.uid(),sent_at=now(),sent_to=coalesce(trim(p_sent_to),''),sent_via=trim(p_sent_via) where id=p_report_id;
end; $$;
revoke all on function private.confirm_daily_report_sent(uuid,text,text) from public, anon, authenticated;
grant execute on function private.confirm_daily_report_sent(uuid,text,text) to authenticated;

create or replace function public.confirm_daily_report_sent(p_report_id uuid,p_sent_to text,p_sent_via text)
returns void language sql security invoker set search_path = '' as $$
  select private.confirm_daily_report_sent(p_report_id,p_sent_to,p_sent_via);
$$;
revoke all on function public.confirm_daily_report_sent(uuid,text,text) from public, anon;
grant execute on function public.confirm_daily_report_sent(uuid,text,text) to authenticated;
