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


@dataclass(frozen=True)
class Autorizado:
    matricula: str
    nombre: str
    estatus: str  # REGULAR | IRREGULAR | PRUEBA, tal como viene en la lista


class RepositorioPanel(Protocol):
    def listar_alumnos(self) -> list[Alumno]: ...
    def listar_autorizados(self) -> list[Autorizado]: ...
    def reiniciar_alumno(self, alumno_id: str, test_ids: Sequence[str], borrar_registro: bool) -> None: ...
    def obtener_progreso_todos(self) -> dict[str, dict[str, ProgresoTest]]: ...
    def obtener_respuestas_todas(self) -> dict[str, dict[str, dict[str, int | None]]]: ...
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
    # test_id -> alumno_id -> pregunta_id -> valor. Incluye tests y preguntas que ya no están en la
    # configuración: es el respaldo de la BD y no debe perder nada.
    respuestas: dict[str, dict[str, dict[str, int | None]]]
    problemas: tuple[str, ...]  # avisos para el docente (versiones distintas, respuestas incompletas)
    autorizados: tuple[Autorizado, ...] = ()  # la lista de alumnos con acceso, registrados o no

    @property
    def terminados(self) -> int:
        return sum(1 for f in self.filas if f.alumno.estado == "terminado")


def cargar_panel(repo: RepositorioPanel, tests: Sequence[TestConfig]) -> PanelDatos:
    alumnos = repo.listar_alumnos()
    progreso = repo.obtener_progreso_todos()
    todas = repo.obtener_respuestas_todas()
    respuestas = {**todas, **{t.id: todas.get(t.id, {}) for t in tests}}
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
    return PanelDatos(tuple(tests), tuple(filas), respuestas, tuple(problemas),
                      tuple(repo.listar_autorizados()))


@dataclass(frozen=True)
class FilaLista:
    """Una línea de la lista de alumnos: alguien de la lista autorizada (registrado o no) o, si ya se
    había registrado y no está en la lista, un registro huérfano."""
    matricula: str
    nombre: str
    estatus: str
    fila: FilaAlumno | None  # None = todavía no se registra
    en_lista: bool


def lista_de_alumnos(panel: PanelDatos) -> list[FilaLista]:
    """Toda la lista autorizada con el avance de quien ya entró, y al final los registrados que no están en ella."""
    registrados = {f.alumno.matricula: f for f in panel.filas}
    lista = [FilaLista(a.matricula, a.nombre, a.estatus or "", registrados.get(a.matricula), True)
             for a in panel.autorizados]
    en_lista = {a.matricula for a in panel.autorizados}
    lista += [FilaLista(f.alumno.matricula, f.alumno.nombre_completo, "", f, False)
              for f in panel.filas if f.alumno.matricula not in en_lista]
    return lista


def reiniciar(repo: RepositorioPanel, alumno: Alumno, tests: Sequence[TestConfig], desde: int,
              borrar_registro: bool = False) -> None:
    """Borra las respuestas del test número `desde` (0 = el primero) y de los que le siguen, para que el
    alumno los conteste de nuevo; el orden de los tests es fijo, así que no puede quedar uno terminado
    después de uno borrado. Con `borrar_registro` se elimina además al alumno, que tendrá que registrarse otra vez."""
    ids = [t.id for t in (tests if borrar_registro else tests[desde:])]
    repo.reiniciar_alumno(alumno.id, ids, borrar_registro)


def sincronizar_resultados(repo: RepositorioPanel, panel: PanelDatos, ahora: datetime) -> int:
    """Guarda en la tabla `resultados` todos los resultados calculados. Devuelve cuántos."""
    n = 0
    for fila in panel.filas:
        for r in fila.resultados:
            if r is not None:
                repo.guardar_resultado(fila.alumno.id, r, ahora)
                n += 1
    return n
