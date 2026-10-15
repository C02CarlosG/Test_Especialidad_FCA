-- Esquema del test vocacional. Ejecutar en Supabase: SQL Editor.
create extension if not exists "pgcrypto";

create table if not exists public.alumnos (
    id                uuid primary key default gen_random_uuid(),
    apellido_paterno  text not null,
    apellido_materno  text not null,
    nombres           text not null,
    matricula         text not null unique check (matricula ~ '^[0-9]{6}$'),
    edad              smallint not null check (edad between 18 and 99),
    tutor             text not null,   -- nombre del tutor / orientador
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
    valor       integer,          -- NULL = "SE" (sin experiencia): dato faltante, no es 0
    unique (alumno_id, test_id, pregunta_id)
);

-- Un resultado por alumno y por test. La comparación entre tests se calcula al vuelo.
create table if not exists public.resultados (
    alumno_id               uuid not null references public.alumnos(id) on delete cascade,
    test_id                 text not null,
    puntajes                jsonb not null,
    afinidad                jsonb not null,
    -- NULL si el test no alcanzó a tener al menos 2 afinidades con datos (muchas respuestas "SE")
    especialidad_principal  text,
    especialidad_secundaria text,
    calculado_en            timestamptz not null default now(),
    unique (alumno_id, test_id)
);

-- Intentos fallidos persistentes (acceso con matrícula ajena / admin), para limitar fuerza bruta
-- aunque Streamlit reinicie la sesión.
create table if not exists public.intentos_fallidos (
    id        bigserial primary key,
    tipo      text not null check (tipo in ('acceso', 'admin')),
    clave     text not null,           -- matrícula o identificador de cliente
    creado_en timestamptz not null default now()
);

-- Índices
create index if not exists idx_alumnos_estado     on public.alumnos(estado);
create index if not exists idx_respuestas_alumno  on public.respuestas(alumno_id, test_id);
create index if not exists idx_progreso_alumno    on public.progreso_tests(alumno_id);
create index if not exists idx_intentos_busqueda  on public.intentos_fallidos(tipo, clave, creado_en desc);
