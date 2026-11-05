create or replace function private.validate_v11_allocation_fields()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if new.attendance not in ('Presente','Ausente','Cantidad fija') then
    raise exception 'Estado de asistencia no válido';
  end if;
  if new.quantity < 0 or new.person_hours < 0 or new.person_hours > 24 then
    raise exception 'Cantidad y horas deben ser valores no negativos y las horas no pueden superar 24';
  end if;
  if new.attendance='Ausente' and new.quantity<>0 then
    raise exception 'Una persona ausente no puede recibir cantidad';
  end if;
  if (new.machine_start_time is null) <> (new.machine_end_time is null)
     or (new.machine_start_time is not null and new.machine_end_time < new.machine_start_time) then
    raise exception 'Las lecturas de máquina deben informarse juntas y el fin no puede ser menor al inicio';
  end if;
  if new.replacement_code is not null and not exists(select 1 from public.personnel p where p.employee_code=new.replacement_code and p.active) then
    raise exception 'El reemplazo no existe o está inactivo';
  end if;
  return new;
end; $$;
revoke all on function private.validate_v11_allocation_fields() from public, anon, authenticated;

create trigger allocations_v11_field_validation_insert
  before insert on public.allocations for each row execute function private.validate_v11_allocation_fields();
create trigger allocations_v11_field_validation_update
  before update of attendance,quantity,replacement_code,machine_start_time,machine_end_time,person_hours
  on public.allocations for each row execute function private.validate_v11_allocation_fields();
