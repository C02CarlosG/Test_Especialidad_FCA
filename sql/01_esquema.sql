-- Esquema del test vocacional. Ejecutar en Supabase: SQL Editor.
create extension if not exists "pgcrypto";

create table if not exists public.grupos (
    id            uuid primary key default gen_random_uuid(),
    codigo_acceso text not null unique,
    nombre        text not null,
    activo        boolean not null default true,
    expira_en     timestamptz,
    -- ids de test habilitados para el grupo (nombre de archivo sin .xlsx); null = todos
    tests_habilitados text[],
    creado_en     timestamptz not null default now()
);

create table if not exists public.alumnos (
    id                uuid primary key default gen_random_uuid(),
    nombre            text not null,
    matricula         text not null unique,
    correo            text not null,
    grupo_id          uuid not null references public.grupos(id),
    acepto_privacidad boolean not null default false,
    acepto_en         timestamptz,
    estado            text not null default 'en_curso'
                      check (estado in ('en_curso', 'terminado')),
    creado_en         timestamptz not null default now(),
    constraint acepto_requerido check (acepto_privacidad and acepto_en is not null)
);

-- Avance del alumno en cada test. El alumno los contesta en orden fijo.
create table if not exists public.progreso_tests (
    alumno_id    uuid not null references public.alumnos(id) on delete cascade,
    test_id      text not null,
    estado       text not null default 'en_curso' check (estado in ('en_curso', 'terminado')),
    version_test text not null,           -- hash del .xlsx con el que respondió
    iniciado_en  timestamptz not null default now(),
    terminado_en timestamptz,
    primary key (alumno_id, test_id)
);

create table if not exists public.respuestas (
    alumno_id   uuid not null references public.alumnos(id) on delete cascade,
    test_id     text not null,
    pregunta_id text not null,
    valor       integer not null,
    unique (alumno_id, test_id, pregunta_id)
);

-- Un resultado por alumno y por test. La comparación entre tests se calcula al vuelo.
create table if not exists public.resultados (
    alumno_id               uuid not null references public.alumnos(id) on delete cascade,
    test_id                 text not null,
    puntajes                jsonb not null,
    afinidad                jsonb not null,
    especialidad_principal  text not null,
    especialidad_secundaria text,
    calculado_en            timestamptz not null default now(),
    unique (alumno_id, test_id)
);

-- Intentos fallidos persistentes (código de grupo / admin), para limitar fuerza bruta
-- aunque Streamlit reinicie la sesión.
create table if not exists public.intentos_fallidos (
    id        bigserial primary key,
    tipo      text not null check (tipo in ('codigo_grupo', 'admin')),
    clave     text not null,           -- matrícula o identificador de cliente
    creado_en timestamptz not null default now()
);

-- Índices
create index if not exists idx_alumnos_grupo      on public.alumnos(grupo_id);
create index if not exists idx_alumnos_estado     on public.alumnos(estado);
create index if not exists idx_respuestas_alumno  on public.respuestas(alumno_id, test_id);
create index if not exists idx_progreso_alumno    on public.progreso_tests(alumno_id);
create index if not exists idx_intentos_busqueda  on public.intentos_fallidos(tipo, clave, creado_en desc);
