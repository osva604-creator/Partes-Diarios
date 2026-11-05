-- V1.1's operational key is `Equipo` (machines.machine_code), which remains
-- unique and continues to back all existing foreign keys. Its source catalog
-- allows duplicate ID_Equipo values, so equipment_code cannot remain the PK.
-- Add a surrogate PK while preserving all machine_code constraints and rows.
alter table public.machines add column machine_id uuid not null default gen_random_uuid();
alter table public.machines drop constraint machines_pkey;
alter table public.machines add constraint machines_pkey primary key (machine_id);
