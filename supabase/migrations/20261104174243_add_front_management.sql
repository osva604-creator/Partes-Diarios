-- Only the owner of a front or an administrator may change its membership.
drop policy front_members_insert on public.front_members;
drop policy front_members_update on public.front_members;
drop policy front_members_delete on public.front_members;
create policy front_members_insert on public.front_members for insert to authenticated
with check ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
));
create policy front_members_update on public.front_members for update to authenticated
using ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
))
with check ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
));
create policy front_members_delete on public.front_members for delete to authenticated
using ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
));

drop policy front_task_members_insert on public.front_task_members;
drop policy front_task_members_update on public.front_task_members;
drop policy front_task_members_delete on public.front_task_members;
create policy front_task_members_insert on public.front_task_members for insert to authenticated
with check ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
));
create policy front_task_members_update on public.front_task_members for update to authenticated
using ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
))
with check ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
));
create policy front_task_members_delete on public.front_task_members for delete to authenticated
using ((select public.current_app_role()) is not null and exists (
  select 1 from public.fronts f where f.id = front_id and (f.created_by = (select auth.uid()) or (select public.is_app_admin()))
));

drop policy fronts_update on public.fronts;
create policy fronts_update on public.fronts for update to authenticated
using ((select public.current_app_role()) is not null and (created_by = (select auth.uid()) or (select public.is_app_admin())))
with check ((select public.current_app_role()) is not null and (created_by = (select auth.uid()) or (select public.is_app_admin())));

-- Replace membership as one transaction so a failed insert cannot erase the prior team.
create or replace function public.replace_front_members(p_front_id uuid, p_members jsonb)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if auth.uid() is null or public.current_app_role() is null then
    raise exception 'Cuenta inactiva o sesión requerida' using errcode = '42501';
  end if;
  if p_front_id is null or jsonb_typeof(p_members) <> 'array' then
    raise exception 'Datos de integrantes incompletos';
  end if;
  if not exists (
    select 1 from public.fronts f where f.id = p_front_id and (f.created_by = auth.uid() or public.is_app_admin())
  ) then
    raise exception 'No tenés permiso para administrar este frente' using errcode = '42501';
  end if;
  delete from public.front_members where front_id = p_front_id;
  insert into public.front_members(front_id, personnel_code, machine_code)
  select p_front_id, m.personnel_code, nullif(m.machine_code, '')
  from jsonb_to_recordset(p_members) as m(personnel_code text, machine_code text);
end;
$$;
revoke all on function public.replace_front_members(uuid,jsonb) from public, anon;
grant execute on function public.replace_front_members(uuid,jsonb) to authenticated;
