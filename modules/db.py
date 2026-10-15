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
from modules.avance import ProgresoTest
from modules.scoring import ResultadoTest


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
                  estado=fila["estado"], creado_en=_fecha(fila.get("creado_en")))


def _fecha(valor: str | None) -> datetime | None:
    return datetime.fromisoformat(valor) if valor else None


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

    def liberar_intento(self, tipo: str, clave: str) -> None:
        """Borra el intento más reciente de esa clave (devuelve una reserva)."""
        r = (self._c.table("intentos_fallidos").select("id").eq("tipo", tipo).eq("clave", clave)
             .order("id", desc=True).limit(1).execute())
        if r.data:
            self._c.table("intentos_fallidos").delete().eq("id", r.data[0]["id"]).execute()

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

    # --- avance en los tests (modules.avance.RepositorioAvance) ---

    def obtener_progreso(self, alumno_id: str) -> dict[str, ProgresoTest]:
        r = (self._c.table("progreso_tests").select("test_id,estado,version_test")
             .eq("alumno_id", alumno_id).execute())
        return {f["test_id"]: ProgresoTest(f["estado"], f["version_test"]) for f in r.data}

    def iniciar_test(self, alumno_id: str, test_id: str, version: str, ahora: datetime) -> None:
        self._c.table("progreso_tests").upsert(
            {"alumno_id": alumno_id, "test_id": test_id, "version_test": version,
             "iniciado_en": ahora.isoformat()},
            on_conflict="alumno_id,test_id", ignore_duplicates=True).execute()

    def obtener_respuestas(self, alumno_id: str, test_id: str) -> dict[str, int | None]:
        r = (self._c.table("respuestas").select("pregunta_id,valor")
             .eq("alumno_id", alumno_id).eq("test_id", test_id).execute())
        return {f["pregunta_id"]: f["valor"] for f in r.data}

    def guardar_respuestas(self, alumno_id: str, test_id: str,
                           respuestas: Mapping[str, int | None]) -> None:
        filas = [{"alumno_id": alumno_id, "test_id": test_id, "pregunta_id": pid, "valor": v}
                 for pid, v in respuestas.items()]
        self._c.table("respuestas").upsert(
            filas, on_conflict="alumno_id,test_id,pregunta_id").execute()

    def terminar_test(self, alumno_id: str, test_id: str, ahora: datetime) -> None:
        (self._c.table("progreso_tests")
         .update({"estado": "terminado", "terminado_en": ahora.isoformat()})
         .eq("alumno_id", alumno_id).eq("test_id", test_id).execute())

    def terminar_alumno(self, alumno_id: str) -> None:
        self._c.table("alumnos").update({"estado": "terminado"}).eq("id", alumno_id).execute()

    # --- panel del docente (modules.panel.RepositorioPanel) ---
    # PostgREST devuelve como máximo ~1000 filas por consulta: se pagina con orden estable.

    def _todas(self, tabla: str, columnas: str, orden: tuple[str, ...], pagina: int = 1000) -> list[dict[str, Any]]:
        filas: list[dict[str, Any]] = []
        while True:
            consulta = self._c.table(tabla).select(columnas)
            for col in orden:
                consulta = consulta.order(col)
            lote = consulta.range(len(filas), len(filas) + pagina - 1).execute().data
            filas.extend(lote)
            if len(lote) < pagina:
                return filas

    def listar_alumnos(self) -> list[Alumno]:
        return [_alumno(f) for f in self._todas("alumnos", _COLS_ALUMNO + ",creado_en", ("creado_en", "id"))]

    def obtener_progreso_todos(self) -> dict[str, dict[str, ProgresoTest]]:
        por_alumno: dict[str, dict[str, ProgresoTest]] = {}
        for f in self._todas("progreso_tests", "alumno_id,test_id,estado,version_test", ("alumno_id", "test_id")):
            por_alumno.setdefault(f["alumno_id"], {})[f["test_id"]] = ProgresoTest(f["estado"], f["version_test"])
        return por_alumno

    def obtener_respuestas_todas(self) -> dict[str, dict[str, dict[str, int | None]]]:
        """test_id -> alumno_id -> pregunta_id -> valor, de TODOS los tests (incluso los retirados)."""
        por_test: dict[str, dict[str, dict[str, int | None]]] = {}
        for f in self._todas("respuestas", "test_id,alumno_id,pregunta_id,valor",
                             ("test_id", "alumno_id", "pregunta_id")):
            por_test.setdefault(f["test_id"], {}).setdefault(f["alumno_id"], {})[f["pregunta_id"]] = f["valor"]
        return por_test

    def guardar_resultado(self, alumno_id: str, resultado: ResultadoTest, ahora: datetime) -> None:
        puntajes, afinidad = resultado.a_json()
        self._c.table("resultados").upsert(
            {"alumno_id": alumno_id, "test_id": resultado.test_id, "puntajes": puntajes, "afinidad": afinidad,
             "especialidad_principal": resultado.principal, "especialidad_secundaria": resultado.secundaria,
             "calculado_en": ahora.isoformat()},
            on_conflict="alumno_id,test_id").execute()
