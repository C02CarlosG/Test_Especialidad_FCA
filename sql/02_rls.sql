-- Row Level Security: activo en TODAS las tablas y SIN políticas.
-- Con RLS activo y sin políticas, los roles `anon` y `authenticated`
-- (clave pública) no pueden leer ni escribir nada.
-- La app usa la service_role key desde el servidor; ese rol omite RLS.
alter table public.grupos            enable row level security;
alter table public.alumnos           enable row level security;
alter table public.respuestas        enable row level security;
alter table public.resultados        enable row level security;
alter table public.intentos_fallidos enable row level security;

alter table public.grupos            force row level security;
alter table public.alumnos           force row level security;
alter table public.respuestas        force row level security;
alter table public.resultados        force row level security;
alter table public.intentos_fallidos force row level security;

-- Defensa en profundidad: quitar privilegios directos a roles públicos.
revoke all on public.grupos, public.alumnos, public.respuestas,
              public.resultados, public.intentos_fallidos from anon, authenticated;
revoke all on sequence public.intentos_fallidos_id_seq from anon, authenticated;
