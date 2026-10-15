"""Acceso a Supabase. Única capa que habla con la base de datos.

Usa la service_role key, que solo existe en el servidor (st.secrets);
nunca se envía al navegador. RLS bloquea cualquier otro acceso.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from postgrest.exceptions import APIError
from supabase import Client, create_client

from modules.acceso import Alumno, MatriculaDuplicada


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
    """Lanza excepción si no se puede consultar la tabla `alumnos`."""
    client.table("alumnos").select("id").limit(1).execute()


def _alumno(fila: dict[str, Any]) -> Alumno:
    return Alumno(id=fila["id"], apellido_paterno=fila["apellido_paterno"],
                  apellido_materno=fila["apellido_materno"], nombres=fila["nombres"],
                  matricula=fila["matricula"], edad=fila["edad"], tutor=fila["tutor"],
                  estado=fila["estado"])


_COLS_ALUMNO = "id,apellido_paterno,apellido_materno,nombres,matricula,edad,tutor,estado"


class SupabaseRepo:
    """Implementa `modules.acceso.Repositorio` sobre Supabase."""

    def __init__(self, client: Client) -> None:
        self._c = client

    def contar_intentos(self, tipo: str, clave: str, desde: datetime) -> int:
        r = (self._c.table("intentos_fallidos").select("id", count="exact")
             .eq("tipo", tipo).eq("clave", clave).gte("creado_en", desde.isoformat())
             .execute())
        return r.count or 0

    def registrar_intento(self, tipo: str, clave: str) -> None:
        self._c.table("intentos_fallidos").insert({"tipo": tipo, "clave": clave}).execute()

    def obtener_alumno_por_matricula(self, matricula: str) -> Alumno | None:
        r = (self._c.table("alumnos").select(_COLS_ALUMNO)
             .eq("matricula", matricula).limit(1).execute())
        return _alumno(r.data[0]) if r.data else None

    def crear_alumno(self, apellido_paterno: str, apellido_materno: str, nombres: str,
                     matricula: str, edad: int, tutor: str,
                     acepto_en: datetime) -> Alumno:
        try:
            r = self._c.table("alumnos").insert({
                "apellido_paterno": apellido_paterno, "apellido_materno": apellido_materno,
                "nombres": nombres, "matricula": matricula, "edad": edad, "tutor": tutor,
                "acepto_privacidad": True,
                "acepto_en": acepto_en.isoformat(),
            }).execute()
        except APIError as exc:
            if exc.json().get("code") == "23505":  # unique_violation
                raise MatriculaDuplicada() from exc
            raise
        return _alumno(r.data[0])
