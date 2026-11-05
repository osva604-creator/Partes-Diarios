-- Rebuild operation-to-machine compatibility from the verified catalog groups.
-- Operacion_Maquinaria.csv uses "COSECHADORAS" while Maquinaria.csv uses
-- "MAQUINAS COSECHADORAS"; normalize that known alias and ignore inactive
-- equipment and manual operations.
with expected as materialized (
  select distinct o.operation_code, m.machine_code
  from public.operations o
  cross join lateral unnest(o.machine_groups) as g(group_name)
  join public.machines m
    on m.active
   and upper(trim(m.operational_group)) = case
     when upper(trim(g.group_name)) = 'COSECHADORAS' then 'MAQUINAS COSECHADORAS'
     else upper(trim(g.group_name))
   end
  where o.active and o.task_type <> 'Manual'
)
delete from public.operation_machines om
where not exists (
  select 1 from expected e
  where e.operation_code = om.operation_code and e.machine_code = om.machine_code
);

with expected as materialized (
  select distinct o.operation_code, m.machine_code
  from public.operations o
  cross join lateral unnest(o.machine_groups) as g(group_name)
  join public.machines m
    on m.active
   and upper(trim(m.operational_group)) = case
     when upper(trim(g.group_name)) = 'COSECHADORAS' then 'MAQUINAS COSECHADORAS'
     else upper(trim(g.group_name))
   end
  where o.active and o.task_type <> 'Manual'
)
insert into public.operation_machines(operation_code, machine_code)
select operation_code, machine_code from expected
on conflict (operation_code, machine_code) do nothing;

-- Keep front setup validation aligned with the report compatibility checks.
create or replace function public.replace_front_task_members(p_front_id uuid, p_front_name text, p_members jsonb)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if auth.uid() is null or public.current_app_role() is null then
    raise exception 'Cuenta inactiva o sesión requerida' using errcode = '42501';
  end if;
  if p_front_id is null or nullif(trim(p_front_name), '') is null or jsonb_typeof(p_members) <> 'array' then
    raise exception 'Datos de integrantes incompletos';
  end if;
  if not exists (
    select 1 from public.fronts f
    where f.id = p_front_id and (f.created_by = auth.uid() or public.is_app_admin())
  ) then
    raise exception 'No tenés permiso para administrar este frente' using errcode = '42501';
  end if;
  update public.fronts set name = trim(p_front_name) where id = p_front_id;
  if exists (
    select 1 from jsonb_to_recordset(p_members) as m(operation_code text, personnel_code text)
    group by m.operation_code, m.personnel_code
    having count(*) > 1
  ) then
    raise exception 'Una persona no puede repetirse en la misma tarea del frente';
  end if;
  if exists (
    select 1
    from jsonb_to_recordset(p_members) as m(operation_code text, personnel_code text, machine_code text)
    left join public.operations o on o.operation_code = m.operation_code and o.active
    left join public.personnel p on p.employee_code = m.personnel_code and p.active
    left join public.machines v on v.machine_code = nullif(m.machine_code, '') and v.active
    where m.operation_code is null or m.personnel_code is null or o.operation_code is null or p.employee_code is null
       or (nullif(m.machine_code, '') is not null and (
         v.machine_code is null or o.task_type = 'Manual'
         or (exists (
           select 1 from public.operation_machines om where om.operation_code = m.operation_code
         ) and not exists (
           select 1 from public.operation_machines om
           where om.operation_code = m.operation_code and om.machine_code = m.machine_code
         ))
         or (not exists (
           select 1 from public.operation_machines om where om.operation_code = m.operation_code
         ) and cardinality(o.machine_groups) > 0 and not exists (
           select 1 from unnest(o.machine_groups) as g(group_name)
           where upper(trim(v.operational_group)) = case
             when upper(trim(g.group_name)) = 'COSECHADORAS' then 'MAQUINAS COSECHADORAS'
             else upper(trim(g.group_name))
           end
         ))
       ))
  ) then
    raise exception 'La tarea, persona o máquina no está activa o la máquina no es compatible';
  end if;

  delete from public.front_task_members where front_id = p_front_id;
  insert into public.front_task_members(front_id, operation_code, personnel_code, machine_code)
  select p_front_id, m.operation_code, m.personnel_code, nullif(m.machine_code, '')
  from jsonb_to_recordset(p_members) as m(operation_code text, personnel_code text, machine_code text);
end;
$$;
revoke all on function public.replace_front_task_members(uuid,text,jsonb) from public, anon;
grant execute on function public.replace_front_task_members(uuid,text,jsonb) to authenticated;
