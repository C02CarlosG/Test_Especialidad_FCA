-- Quita el largo fijo de 6 dígitos de la matrícula (hay alumnos con 5): ahora son 1 a 10 dígitos.
-- Ejecutar en Supabase (SQL Editor) en las bases que ya existían; es seguro repetirlo.
alter table public.alumnos drop constraint if exists alumnos_matricula_check;
alter table public.alumnos drop constraint if exists alumnos_matricula_6_digitos;  -- nombre que tiene en algunas bases
alter table public.alumnos add constraint alumnos_matricula_check check (matricula ~ '^[0-9]{1,10}$');
alter table public.alumnos_autorizados drop constraint if exists alumnos_autorizados_matricula_check;
alter table public.alumnos_autorizados add constraint alumnos_autorizados_matricula_check check (matricula ~ '^[0-9]{1,10}$');
