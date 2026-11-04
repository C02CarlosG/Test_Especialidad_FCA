-- Agrega el semestre a la tabla de alumnos (instalaciones que ya tenían datos).
-- Ejecutar en Supabase (SQL Editor) ANTES de desplegar la versión que lo pide; es seguro repetirlo.
alter table public.alumnos
    add column if not exists semestre smallint check (semestre between 1 and 8);
