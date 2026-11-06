-- Lista de alumnos autorizados a contestar el test (5.º semestre). Solo la matrícula decide el acceso;
-- el resto de las columnas es informativo. Ejecutar en Supabase (SQL Editor); es seguro repetirlo.
-- La lista se carga con scripts/importar_alumnos_autorizados.py (no se escribe a mano).
create table if not exists public.alumnos_autorizados (
    matricula text primary key check (matricula ~ '^[0-9]{6}$'),
    nombre    text not null,
    sexo      text,
    estatus   text,                         -- REGULAR | IRREGULAR, tal como viene en la lista
    cargado_en timestamptz not null default now()
);

alter table public.alumnos_autorizados enable row level security;
alter table public.alumnos_autorizados force row level security;
revoke all on public.alumnos_autorizados from anon, authenticated;
