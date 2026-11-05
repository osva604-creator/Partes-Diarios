alter table public.report_revisions
  add column if not exists correction_key uuid;
create unique index if not exists report_revisions_correction_key_idx
  on public.report_revisions(report_id,correction_key) where correction_key is not null;

create or replace function private.correct_daily_report(
  p_report_id uuid,
  p_correction_key uuid,
  p_report_date date,
  p_service_order text,
  p_tasks jsonb
)
returns integer language plpgsql security definer set search_path = '' as $$
declare
  v_report public.daily_reports%rowtype;
  v_version integer;
  v_task jsonb;
  v_task_id uuid;
  v_cycle_id uuid;
  v_operation_code text;
  v_operation public.operations%rowtype;
  v_unit text;
  v_task_quantity numeric;
  v_allocation jsonb;
  v_input jsonb;
  v_total numeric;
  v_personnel_code text;
  v_machine_code text;
begin
  if auth.uid() is null or public.current_app_role() is null or not public.is_app_admin() then
    raise exception 'Solo administracion puede corregir partes' using errcode = '42501';
  end if;
  if p_correction_key is null or p_report_date is null or jsonb_typeof(p_tasks) <> 'array' or jsonb_array_length(p_tasks)=0 then
    raise exception 'Datos incompletos para corregir el parte';
  end if;
  v_report := (select r from public.daily_reports r where r.id=p_report_id for update);
  if v_report.id is null then raise exception 'No se encontro el parte'; end if;
  if exists(select 1 from public.report_revisions where report_id=p_report_id and correction_key=p_correction_key) then
    return v_report.pdf_version;
  end if;
  if v_report.document_status='Borrador' then
    raise exception 'Los borradores sin revision no requieren correccion';
  end if;
  if (select count(*) from public.report_tasks where report_id=p_report_id) <> jsonb_array_length(p_tasks)
     or exists(select 1 from jsonb_to_recordset(p_tasks) as x(task_id uuid) group by x.task_id having count(*)>1)
     or exists(select 1 from jsonb_to_recordset(p_tasks) as x(task_id uuid) where not exists(select 1 from public.report_tasks t where t.id=x.task_id and t.report_id=p_report_id)) then
    raise exception 'La correccion debe conservar las tareas del parte; no se permiten lineas agregadas o quitadas';
  end if;

  -- Preserve the complete document before changing any live row.
  insert into public.report_revisions(report_id,saved_by,was_sent,snapshot,correction_key)
  select r.id,auth.uid(),r.sent_at is not null,
    jsonb_build_object('report',to_jsonb(r),'tasks',coalesce((
      select jsonb_agg(jsonb_build_object('task',to_jsonb(t),
        'allocations',coalesce((select jsonb_agg(to_jsonb(a)) from public.allocations a where a.report_task_id=t.id),'[]'::jsonb),
        'inputs',coalesce((select jsonb_agg(to_jsonb(i)) from public.part_inputs i where i.report_task_id=t.id),'[]'::jsonb)) order by t.line_no)
      from public.report_tasks t where t.report_id=r.id),'[]'::jsonb)),p_correction_key
  from public.daily_reports r where r.id=p_report_id;

  for v_task in select value from jsonb_array_elements(p_tasks) loop
    v_task_id := (v_task->>'task_id')::uuid;
    v_task_quantity := (v_task->>'quantity')::numeric;
    v_cycle_id := (select t.work_cycle_id from public.report_tasks t where t.id=v_task_id and t.report_id=p_report_id for update);
    v_operation_code := (select t.operation_code from public.report_tasks t where t.id=v_task_id and t.report_id=p_report_id);
    if v_cycle_id is null or v_task_quantity<=0 or coalesce(jsonb_typeof(v_task->'cost_center_context'),'null') not in ('object','null') then
      raise exception 'Tarea corregida incompleta o con cantidad no valida';
    end if;
    v_operation := (select o from public.operations o where o.operation_code=v_operation_code and o.active);
    if v_operation.operation_code is null then raise exception 'La operacion de una tarea ya no esta activa'; end if;
    v_unit := (select c.unit from public.work_cycles c where c.id=v_cycle_id);
    if jsonb_typeof(v_task->'allocations')<>'array'
       or (select count(*) from public.allocations a where a.report_task_id=v_task_id) <> jsonb_array_length(v_task->'allocations')
       or exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(allocation_id uuid) group by a.allocation_id having count(*)>1)
       or exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(allocation_id uuid) where not exists(select 1 from public.allocations old where old.id=a.allocation_id and old.report_task_id=v_task_id)) then
      raise exception 'La correccion debe conservar las asignaciones existentes de cada tarea';
    end if;
    if jsonb_typeof(coalesce(v_task->'inputs','[]'::jsonb))<>'array'
       or (select count(*) from public.part_inputs i where i.report_task_id=v_task_id) <> jsonb_array_length(coalesce(v_task->'inputs','[]'::jsonb))
       or exists(select 1 from jsonb_to_recordset(coalesce(v_task->'inputs','[]'::jsonb)) as i(input_id uuid) group by i.input_id having count(*)>1)
       or exists(select 1 from jsonb_to_recordset(coalesce(v_task->'inputs','[]'::jsonb)) as i(input_id uuid) where not exists(select 1 from public.part_inputs old where old.id=i.input_id and old.report_task_id=v_task_id)) then
      raise exception 'La correccion debe conservar los insumos existentes de cada tarea';
    end if;
    if exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(personnel_code text) group by a.personnel_code having count(*)>1) then
      raise exception 'Una persona no puede repetirse en la tarea corregida';
    end if;
    v_total := (select coalesce(sum(a.quantity),0) from jsonb_to_recordset(v_task->'allocations') as a(quantity numeric));
    if abs(v_total-v_task_quantity)>0.001 then raise exception 'Las asignaciones no coinciden con la cantidad de la tarea'; end if;
    if upper(trim(v_unit))='SC' and (v_task_quantity<>trunc(v_task_quantity)
       or exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(quantity numeric) where a.quantity<>trunc(a.quantity))) then
      raise exception 'Las cantidades en surcos deben ser enteras';
    end if;
    if v_operation.task_type='Manual' and exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(machine_code text) where nullif(a.machine_code,'') is not null) then
      raise exception 'Una tarea manual no admite maquinaria';
    end if;
    if cardinality(v_operation.machine_groups)>0 and not exists(select 1 from jsonb_to_recordset(v_task->'allocations') as a(machine_code text,attendance text) where nullif(a.machine_code,'') is not null and coalesce(a.attendance,'Presente')<>'Ausente') then
      raise exception 'La tarea requiere maquinaria compatible';
    end if;

    update public.report_tasks set part_date=p_report_date,quantity=v_task_quantity,
      crop=coalesce(v_task->>'crop',''),notes=coalesce(v_task->>'notes',''),
      cost_center_context=coalesce(v_task->'cost_center_context','{}'::jsonb)
      where id=v_task_id and report_id=p_report_id;
    for v_allocation in select value from jsonb_array_elements(v_task->'allocations') loop
      v_personnel_code := v_allocation->>'personnel_code';
      v_machine_code := nullif(v_allocation->>'machine_code','');
      if not exists(select 1 from public.personnel p where p.employee_code=v_personnel_code and p.active)
         or (nullif(v_allocation->>'replacement_code','') is not null and not exists(select 1 from public.personnel p where p.employee_code=v_allocation->>'replacement_code' and p.active)) then
        raise exception 'El legajo o reemplazo no existe o esta inactivo';
      end if;
      if v_machine_code is not null and (not exists(select 1 from public.machines m where m.machine_code=v_machine_code and m.active)
        or (exists(select 1 from public.operation_machines om where om.operation_code=v_operation_code)
          and not exists(select 1 from public.operation_machines om where om.operation_code=v_operation_code and om.machine_code=v_machine_code))
        or (not exists(select 1 from public.operation_machines om where om.operation_code=v_operation_code) and cardinality(v_operation.machine_groups)>0
          and not exists(select 1 from public.machines m where m.machine_code=v_machine_code and exists(select 1 from unnest(v_operation.machine_groups) g where upper(trim(g))=upper(trim(m.operational_group)))))) then
        raise exception 'La maquinaria no existe, esta inactiva o no es compatible con la tarea';
      end if;
      update public.allocations set personnel_code=v_allocation->>'personnel_code',
        machine_code=nullif(v_allocation->>'machine_code',''),attendance=coalesce(v_allocation->>'attendance','Presente'),
        quantity=coalesce((v_allocation->>'quantity')::numeric,0),replacement_code=nullif(v_allocation->>'replacement_code',''),
        front_id=nullif(v_allocation->>'front_id','')::uuid,machine_start_time=(v_allocation->>'machine_start_time')::integer,
        machine_end_time=(v_allocation->>'machine_end_time')::integer,person_hours=coalesce((v_allocation->>'person_hours')::numeric,12)
        where id=(v_allocation->>'allocation_id')::uuid and report_task_id=v_task_id;
    end loop;
    for v_input in select value from jsonb_array_elements(coalesce(v_task->'inputs','[]'::jsonb)) loop
      if not exists(select 1 from public.inputs i where i.input_code=v_input->>'input_code' and i.active) then
        raise exception 'El insumo no existe o esta inactivo';
      end if;
      update public.part_inputs set input_code=v_input->>'input_code',dose=coalesce((v_input->>'dose')::numeric,0),
        quantity=coalesce((v_input->>'quantity')::numeric,0),unit=coalesce(v_input->>'unit','')
        where id=(v_input->>'input_id')::uuid and report_task_id=v_task_id;
    end loop;
  end loop;

  update public.daily_reports set report_date=p_report_date,service_order=coalesce(p_service_order,''),
    document_status='Corregido',reviewed_by=null,reviewed_at=null,sent_by=null,sent_at=null,sent_to='',sent_via='',
    pdf_version=pdf_version+1,modified_at=now()
    where id=p_report_id;
  v_version := (select r.pdf_version from public.daily_reports r where r.id=p_report_id);
  return v_version;
end; $$;
revoke all on function private.correct_daily_report(uuid,uuid,date,text,jsonb) from public,anon,authenticated;
grant execute on function private.correct_daily_report(uuid,uuid,date,text,jsonb) to authenticated;

create or replace function public.correct_daily_report(
  p_report_id uuid,
  p_correction_key uuid,
  p_report_date date,
  p_service_order text,
  p_tasks jsonb
)
returns integer language sql security invoker set search_path = '' as $$
  select private.correct_daily_report(p_report_id,p_correction_key,p_report_date,p_service_order,p_tasks);
$$;
revoke all on function public.correct_daily_report(uuid,uuid,date,text,jsonb) from public,anon;
grant execute on function public.correct_daily_report(uuid,uuid,date,text,jsonb) to authenticated;
