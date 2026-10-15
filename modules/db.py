"""Acceso a Supabase. Única capa que habla con la base de datos.

Usa la service_role key, que solo existe en el servidor (st.secrets);
nunca se envía al navegador. RLS bloquea cualquier otro acceso.
"""
from __future__ import annotations

from typing import Any, Mapping

from supabase import Client, create_client


class DBConfigError(Exception):
    """Faltan o son inválidos los secretos de Supabase."""


def crear_cliente(secrets: Mapping[str, Any]) -> Client:
    try:
        cfg = secrets["supabase"]
        url, key = str(cfg["url"]).strip(), str(cfg["service_role_key"]).strip()
    except (KeyError, TypeError) as exc:
        raise DBConfigError("Falta la sección [supabase] (url, service_role_key) en secrets.toml.") from exc
    if not url.startswith("https://") or not key or key == "REEMPLAZAR":
        raise DBConfigError("Los secretos de Supabase no están configurados.")
    return create_client(url, key)


def verificar_conexion(client: Client) -> None:
    """Lanza excepción si no se puede consultar la tabla `grupos`."""
    client.table("grupos").select("id").limit(1).execute()
