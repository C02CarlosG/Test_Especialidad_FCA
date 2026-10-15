"""Calificación de un test. Lógica pura: no toca la BD ni Streamlit.

Reglas (replican las calculadoras de Excel de docs/referencia, salvo donde se indica):
- Cada especialidad (o dimensión) del test suma sus respuestas. Una pregunta invertida vale
  `valor_min + valor_max - respuesta`.
- El puntaje máximo de una especialidad es `respuestas contestadas x valor_max`. El porcentaje es
  `obtenido / máximo` (con escala 1-5 el mínimo posible es 20 %, no 0 %, igual que en la calculadora).
- "SE" (sin experiencia) es un dato faltante: no suma al puntaje ni al máximo. Con 2 o más "SE" en
  una especialidad se marca `requiere_exploracion`. Si todas sus respuestas son "SE" no hay dato
  (`porcentaje` None) y la especialidad queda fuera del ranking.
- Si el test define afinidades derivadas (hoja `afinidad`), el porcentaje de cada una es la suma
  de los puntajes de sus componentes entre la suma de sus máximos, y el ranking se hace sobre ellas.
  Si no, el ranking se hace sobre las propias especialidades.
- Ranking: mayor porcentaje; el empate se rompe por mayor puntaje bruto y luego por el orden en
  que aparecen en el Excel. (La calculadora usa solo el orden y, en un empate de los dos primeros,
  repite la misma especialidad como 2ª opción; aquí no ocurre.)
- Principal y secundaria solo existen si al menos 2 afinidades tienen dato.
- `empate_tecnico`: las dos primeras difieren 5 puntos porcentuales o menos.

Los porcentajes son `Fraction` (comparaciones exactas con los umbrales de la hoja `niveles`).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping

from modules.config_loader import Nivel, TestConfig

SE_EXPLORACION = 2  # "SE" en una especialidad a partir de los cuales se pide explorar
UMBRAL_EMPATE = Fraction(5, 100)


class ErrorDeCalificacion(ValueError):
    """Las respuestas no corresponden al test o están incompletas."""


@dataclass(frozen=True)
class PuntajeEspecialidad:
    codigo: str
    nombre: str
    obtenido: int
    maximo: int
    porcentaje: Fraction | None  # None = sin datos (todas "SE")
    nivel: str | None
    respondidas: int  # con valor numérico
    sin_experiencia: int
    requiere_exploracion: bool

    @property
    def sin_datos(self) -> bool:
        return self.porcentaje is None


@dataclass(frozen=True)
class Afinidad:
    codigo: str
    nombre: str
    obtenido: int
    maximo: int
    porcentaje: Fraction | None
    nivel: str | None

    @property
    def sin_datos(self) -> bool:
        return self.porcentaje is None


@dataclass(frozen=True)
class ResultadoTest:
    test_id: str
    version: str
    especialidades: tuple[PuntajeEspecialidad, ...]  # en el orden del Excel
    afinidades: tuple[Afinidad, ...]  # en el orden del Excel
    ranking: tuple[Afinidad, ...]  # solo con datos, de mayor a menor
    principal: str | None
    secundaria: str | None
    empate_tecnico: bool

    def a_json(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """(puntajes, afinidad) listos para las columnas jsonb de `resultados`."""
        puntajes = {e.codigo: {
            "obtenido": e.obtenido, "maximo": e.maximo, "porcentaje": _flotante(e.porcentaje),
            "nivel": e.nivel, "respondidas": e.respondidas, "sin_experiencia": e.sin_experiencia,
            "requiere_exploracion": e.requiere_exploracion} for e in self.especialidades}
        afinidad = {a.codigo: {
            "obtenido": a.obtenido, "maximo": a.maximo, "porcentaje": _flotante(a.porcentaje),
            "nivel": a.nivel} for a in self.afinidades}
        return puntajes, afinidad


def _flotante(f: Fraction | None) -> float | None:
    return None if f is None else float(f)


def _nivel(niveles: tuple[Nivel, ...], porcentaje: Fraction | None) -> str | None:
    if porcentaje is None:
        return None
    # `niveles` viene de mayor a menor mínimo; el primero que se alcanza es el nivel.
    return next((n.etiqueta for n in niveles if porcentaje >= n.minimo), None)


def _validar(test: TestConfig, respuestas: Mapping[str, int | None]) -> None:
    ids = {p.id for p in test.preguntas}
    if extra := sorted(set(respuestas) - ids):
        raise ErrorDeCalificacion(f"Respuestas a preguntas que no existen en el test: {', '.join(extra)}.")
    if faltan := sorted(ids - set(respuestas)):
        raise ErrorDeCalificacion(f"Faltan {len(faltan)} respuesta(s): {', '.join(faltan[:5])}"
                                  f"{'…' if len(faltan) > 5 else ''}.")
    validos = {o.valor for o in test.escala}
    for pid, valor in respuestas.items():
        if valor is None:
            if test.sin_experiencia is None:
                raise ErrorDeCalificacion(f"La pregunta {pid} no admite 'sin experiencia'.")
        elif isinstance(valor, bool) or valor not in validos:
            raise ErrorDeCalificacion(f"Valor fuera de la escala en {pid}: {valor!r}.")


def calificar(test: TestConfig, respuestas: Mapping[str, int | None]) -> ResultadoTest:
    """Califica un test completo. `respuestas`: pregunta_id -> valor (None = "SE")."""
    _validar(test, respuestas)
    vmin, vmax = test.valor_min, test.valor_max

    especialidades: list[PuntajeEspecialidad] = []
    for esp in test.especialidades:
        obtenido = maximo = respondidas = se = 0
        for p in test.preguntas:
            if p.especialidad_codigo != esp.codigo:
                continue
            valor = respuestas[p.id]
            if valor is None:
                se += 1
                continue
            obtenido += (vmin + vmax - valor) if p.invertida else valor
            maximo += vmax
            respondidas += 1
        porcentaje = Fraction(obtenido, maximo) if maximo else None
        especialidades.append(PuntajeEspecialidad(
            esp.codigo, esp.nombre, obtenido, maximo, porcentaje,
            _nivel(test.niveles_categoria, porcentaje), respondidas, se, se >= SE_EXPLORACION))

    if test.afinidades:
        por_codigo = {e.codigo: e for e in especialidades}
        afinidades = []
        for d in test.afinidades:
            comps = [por_codigo[c] for c in d.componentes]
            obtenido, maximo = sum(c.obtenido for c in comps), sum(c.maximo for c in comps)
            porcentaje = Fraction(obtenido, maximo) if maximo else None
            afinidades.append(Afinidad(d.codigo, d.nombre, obtenido, maximo, porcentaje,
                                       _nivel(test.niveles_afinidad, porcentaje)))
    else:
        afinidades = [Afinidad(e.codigo, e.nombre, e.obtenido, e.maximo, e.porcentaje, e.nivel)
                      for e in especialidades]

    # sorted(reverse=True) es estable: a igualdad de porcentaje y puntaje manda el orden del Excel.
    ranking = tuple(sorted((a for a in afinidades if a.porcentaje is not None),
                           key=lambda a: (a.porcentaje, a.obtenido), reverse=True))
    hay_dos = len(ranking) >= 2
    return ResultadoTest(
        test_id=test.id, version=test.version,
        especialidades=tuple(especialidades), afinidades=tuple(afinidades), ranking=ranking,
        principal=ranking[0].codigo if hay_dos else None,
        secundaria=ranking[1].codigo if hay_dos else None,
        empate_tecnico=hay_dos and ranking[0].porcentaje - ranking[1].porcentaje <= UMBRAL_EMPATE,
    )
