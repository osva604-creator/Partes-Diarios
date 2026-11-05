-- Keep read access and administrator writes in separate policies. A single
-- FOR ALL policy is also permissive for SELECT and duplicates each read rule.
do $$ declare t text; begin
  foreach t in array array['cost_centers','operation_groups','cost_center_operation_groups','operation_group_operations','operation_machines','operation_inputs'] loop
    execute format('drop policy if exists %I on public.%I', t || '_admin_write', t);
    execute format('drop policy if exists %I on public.%I', t || '_admin_insert', t);
    execute format('drop policy if exists %I on public.%I', t || '_admin_update', t);
    execute format('drop policy if exists %I on public.%I', t || '_admin_delete', t);
    execute format('create policy %I on public.%I for insert to authenticated with check ((select public.is_app_admin()))', t || '_admin_insert', t);
    execute format('create policy %I on public.%I for update to authenticated using ((select public.is_app_admin())) with check ((select public.is_app_admin()))', t || '_admin_update', t);
    execute format('create policy %I on public.%I for delete to authenticated using ((select public.is_app_admin()))', t || '_admin_delete', t);
  end loop;
end $$;
