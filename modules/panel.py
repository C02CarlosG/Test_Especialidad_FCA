"""Datos del panel del docente: todos los alumnos juntos, su avance y sus resultados.

Los resultados se calculan siempre desde las respuestas guardadas (la fuente de verdad); la
tabla `resultados` es una copia para consultas externas y se refresca con `sincronizar_resultados`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from modules.acceso import Alumno
from modules.avance import ProgresoTest
from modules.config_loader import TestConfig
from modules.scoring import ErrorDeCalificacion, ResultadoTest, calificar


class RepositorioPanel(Protocol):
    def listar_alumnos(self) -> list[Alumno]: ...
    def obtener_progreso_todos(self) -> dict[str, dict[str, ProgresoTest]]: ...
    def obtener_respuestas_de_test(self, test_id: str) -> dict[str, dict[str, int | None]]: ...
    def guardar_resultado(self, alumno_id: str, resultado: ResultadoTest, ahora: datetime) -> None: ...


@dataclass(frozen=True)
class FilaAlumno:
    alumno: Alumno
    estado_tests: tuple[str, ...]  # por test: sin_iniciar | en_curso | terminado
    contestadas: tuple[int, ...]  # respuestas guardadas por test
    resultados: tuple[ResultadoTest | None, ...]  # None si el test no está terminado o no se pudo calificar

    @property
    def completo(self) -> bool:
        return all(r is not None for r in self.resultados)


@dataclass(frozen=True)
class PanelDatos:
    tests: tuple[TestConfig, ...]
    filas: tuple[FilaAlumno, ...]
    respuestas: dict[str, dict[str, dict[str, int | None]]]  # test_id -> alumno_id -> pregunta_id -> valor
    problemas: tuple[str, ...]  # avisos para el docente (versiones distintas, respuestas incompletas)

    @property
    def terminados(self) -> int:
        return sum(1 for f in self.filas if f.alumno.estado == "terminado")


def cargar_panel(repo: RepositorioPanel, tests: Sequence[TestConfig]) -> PanelDatos:
    alumnos = repo.listar_alumnos()
    progreso = repo.obtener_progreso_todos()
    respuestas = {t.id: repo.obtener_respuestas_de_test(t.id) for t in tests}
    problemas: list[str] = []
    filas = []
    for a in alumnos:
        estados, conteos, resultados = [], [], []
        for t in tests:
            p = progreso.get(a.id, {}).get(t.id)
            resp = respuestas[t.id].get(a.id, {})
            estados.append(p.estado if p else "sin_iniciar")
            conteos.append(len(resp))
            resultado = None
            if p is not None and p.estado == "terminado":
                if p.version_test != t.version:
                    problemas.append(f"{a.matricula}: contestó '{t.titulo}' con una versión anterior del test; "
                                     "no se califica con la actual.")
                else:
                    try:
                        resultado = calificar(t, resp)
                    except ErrorDeCalificacion as exc:
                        problemas.append(f"{a.matricula}: no se pudo calificar '{t.titulo}' ({exc}).")
            resultados.append(resultado)
        filas.append(FilaAlumno(a, tuple(estados), tuple(conteos), tuple(resultados)))
    return PanelDatos(tuple(tests), tuple(filas), respuestas, tuple(problemas))


def sincronizar_resultados(repo: RepositorioPanel, panel: PanelDatos, ahora: datetime) -> int:
    """Guarda en la tabla `resultados` todos los resultados calculados. Devuelve cuántos."""
    n = 0
    for fila in panel.filas:
        for r in fila.resultados:
            if r is not None:
                repo.guardar_resultado(fila.alumno.id, r, ahora)
                n += 1
    return n
