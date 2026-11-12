-- Correo del alumno y estado del envío de su reporte en PDF. Ejecutar en Supabase (SQL Editor) ANTES de
-- desplegar la versión que lo pide; es seguro repetirlo.
alter table public.alumnos add column if not exists correo text;
alter table public.alumnos add column if not exists reporte_estado text not null default 'pendiente';
alter table public.alumnos add column if not exists reporte_enviado_en timestamptz;
alter table public.alumnos add column if not exists reporte_reservado_en timestamptz;  -- cuándo se tomó la reserva del envío
alter table public.alumnos add column if not exists reporte_error text;

alter table public.alumnos drop constraint if exists alumnos_reporte_estado_check;
alter table public.alumnos add constraint alumnos_reporte_estado_check
    check (reporte_estado in ('pendiente', 'enviando', 'enviado', 'error'));

alter table public.alumnos drop constraint if exists alumnos_correo_formato;
alter table public.alumnos add constraint alumnos_correo_formato
    check (correo is null or correo ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$');
