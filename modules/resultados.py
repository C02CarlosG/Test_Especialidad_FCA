"""Resultados finales de un alumno: califica sus respuestas guardadas, test por test."""
from __future__ import annotations

from typing import Protocol, Sequence

from modules.acceso import Alumno
from modules.config_loader import TestConfig
from modules.scoring import ResultadoTest, calificar


class RepositorioRespuestas(Protocol):
    def obtener_respuestas(self, alumno_id: str, test_id: str) -> dict[str, int | None]: ...


def resultados_del_alumno(repo: RepositorioRespuestas, alumno: Alumno,
                          tests: Sequence[TestConfig]) -> list[ResultadoTest]:
    """Un resultado por test, en el orden de `tests`. Lanza ErrorDeCalificacion si falta algo."""
    return [calificar(t, repo.obtener_respuestas(alumno.id, t.id)) for t in tests]
