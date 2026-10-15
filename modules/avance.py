"""Avance del alumno por los tests: en qué test y bloque va, guardado por bloque y cierre.

Reglas:
- Los tests se contestan en el orden de `tests` (orden alfabético de archivo).
- Un bloque se guarda completo o no se guarda: hay que contestar todas sus preguntas.
  "SE" (sin experiencia) cuenta como respuesta y se guarda como NULL.
- Un test se marca terminado cuando todas sus preguntas tienen respuesta; el alumno
  queda terminado cuando terminó todos los tests.
- El avance vive en la BD, no en la sesión del navegador: si recarga la página y vuelve
  a entrar con su matrícula y nombre, continúa en el primer bloque sin contestar.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Protocol, Sequence

from modules.acceso import Alumno
from modules.config_loader import TestConfig

SIN_EXPERIENCIA = None  # valor guardado para la opción "SE"


@dataclass(frozen=True)
class ProgresoTest:
    estado: str  # en_curso | terminado
    version_test: str


class RepositorioAvance(Protocol):
    def obtener_progreso(self, alumno_id: str) -> dict[str, ProgresoTest]: ...
    def iniciar_test(self, alumno_id: str, test_id: str, version: str, ahora: datetime) -> None: ...
    def obtener_respuestas(self, alumno_id: str, test_id: str) -> dict[str, int | None]: ...
    def guardar_respuestas(self, alumno_id: str, test_id: str,
                           respuestas: Mapping[str, int | None]) -> None: ...
    def terminar_test(self, alumno_id: str, test_id: str, ahora: datetime) -> None: ...
    def terminar_alumno(self, alumno_id: str) -> None: ...


class AvanceError(Exception):
    """Error mostrable al alumno."""

    def __init__(self, mensaje: str) -> None:
        self.mensaje = mensaje
        super().__init__(mensaje)


class CambioDeTest(AvanceError):
    def __init__(self) -> None:
        super().__init__("El test cambió mientras lo contestabas. Avisa a tu tutor.")


class BloqueIncompleto(AvanceError):
    def __init__(self, faltan: int) -> None:
        super().__init__(f"Te faltan {faltan} pregunta(s) por contestar en este bloque.")


class RespuestaInvalida(AvanceError):
    def __init__(self) -> None:
        super().__init__("Hay una respuesta no válida. Recarga la página e inténtalo de nuevo.")


@dataclass(frozen=True)
class Posicion:
    """Dónde va el alumno. `bloque` es el siguiente bloque sin contestar."""
    numero_test: int  # 1-based
    total_tests: int
    test: TestConfig
    bloque: int
    numero_bloque: int  # 1-based, dentro del test
    total_bloques: int
    contestadas: int  # preguntas ya guardadas en este test


def calcular_posicion(repo: RepositorioAvance, alumno: Alumno, tests: Sequence[TestConfig],
                      ahora: datetime | None = None) -> Posicion | None:
    """Siguiente bloque por contestar, o None si el alumno ya terminó todo.

    Inicia el registro de progreso del test en curso la primera vez que lo ve.
    """
    ahora = ahora or datetime.now(timezone.utc)
    progreso = repo.obtener_progreso(alumno.id)
    for n, test in enumerate(tests, start=1):
        previo = progreso.get(test.id)
        if previo is not None and previo.estado == "terminado":
            continue
        if previo is None:
            repo.iniciar_test(alumno.id, test.id, test.version, ahora)
        elif previo.version_test != test.version:
            raise CambioDeTest()
        respuestas = repo.obtener_respuestas(alumno.id, test.id)
        for i, bloque in enumerate(test.bloques, start=1):
            if any(p.id not in respuestas for p in test.preguntas_de_bloque(bloque)):
                return Posicion(n, len(tests), test, bloque, i, len(test.bloques), len(respuestas))
        # Todas contestadas pero sin cerrar (p. ej. se cayó la conexión al terminar).
        repo.terminar_test(alumno.id, test.id, ahora)
    repo.terminar_alumno(alumno.id)
    return None


def guardar_bloque(repo: RepositorioAvance, alumno: Alumno, tests: Sequence[TestConfig],
                   test: TestConfig, bloque: int, respuestas: Mapping[str, int | None],
                   ahora: datetime | None = None) -> None:
    """Guarda un bloque completo. `respuestas` solo incluye las preguntas contestadas;
    el valor None significa "SE" y solo se admite si el test la tiene."""
    ahora = ahora or datetime.now(timezone.utc)
    ids_bloque = [p.id for p in test.preguntas_de_bloque(bloque)]
    if not ids_bloque or set(respuestas) - set(ids_bloque):
        raise RespuestaInvalida()
    if faltan := [i for i in ids_bloque if i not in respuestas]:
        raise BloqueIncompleto(len(faltan))
    validos = {o.valor for o in test.escala}
    for valor in respuestas.values():
        if valor is None:
            if test.sin_experiencia is None:
                raise RespuestaInvalida()
        elif valor not in validos:
            raise RespuestaInvalida()

    repo.iniciar_test(alumno.id, test.id, test.version, ahora)  # idempotente
    repo.guardar_respuestas(alumno.id, test.id, dict(respuestas))
    if len(repo.obtener_respuestas(alumno.id, test.id)) >= len(test.preguntas):
        repo.terminar_test(alumno.id, test.id, ahora)
        if all(t.id == test.id or _terminado(repo, alumno, t) for t in tests):
            repo.terminar_alumno(alumno.id)


def _terminado(repo: RepositorioAvance, alumno: Alumno, test: TestConfig) -> bool:
    p = repo.obtener_progreso(alumno.id).get(test.id)
    return p is not None and p.estado == "terminado"
