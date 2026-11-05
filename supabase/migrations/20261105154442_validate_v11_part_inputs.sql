create or replace function private.enforce_part_input_compatibility()
returns trigger language plpgsql security invoker set search_path = '' as $$
declare v_operation text;
begin
  select t.operation_code into v_operation from public.report_tasks t where t.id=new.report_task_id;
  if not exists(select 1 from public.operations o where o.operation_code=v_operation and o.allows_inputs) then
    raise exception 'La tarea no admite insumos';
  end if;
  if exists(select 1 from public.operation_inputs oi where oi.operation_code=v_operation)
     and not exists(select 1 from public.operation_inputs oi where oi.operation_code=v_operation and oi.input_code=new.input_code) then
    raise exception 'El insumo no es compatible con la tarea %',v_operation;
  end if;
  return new;
end; $$;
revoke all on function private.enforce_part_input_compatibility() from public, anon, authenticated;

create trigger part_inputs_operation_compatibility
  before insert or update of report_task_id,input_code on public.part_inputs
  for each row execute function private.enforce_part_input_compatibility();
