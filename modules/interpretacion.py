"""Interpretación conjunta de los resultados: lo que cuentan los dos tests juntos.

Lógica pura (no toca la BD ni Streamlit). La pantalla, el PDF y el Excel leen de aquí el mismo
informe, así que dicen lo mismo. Aplica cuando hay un test de rasgos (con hoja `afinidad`, p. ej. el
Big Five) y un test de competencias que comparten los códigos de las especialidades. Si no, `construir`
devuelve None y los reportes usan su versión genérica.

Reglas:
- Promedio de un campo = promedio de la afinidad por rasgos (test 1) y del porcentaje de competencias
  (test 2). Sin dato en alguno, el campo queda fuera del ranking.
- Dominante = mayor promedio; complementario = el siguiente. Empate técnico: 5 puntos o menos.
- Índice de alineación = parte de los rasgos que pide el campo dominante que están en el nivel más alto.
  75 % o más: alta; 50 % o más: moderada; menos: baja. Es una lectura orientativa, no un puntaje oficial.
- Confianza: «alta» con 15 puntos o más de margen y tests que coinciden; «moderada» con empate técnico
  o con «sin experiencia» en el campo dominante; «buena» en el resto.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Sequence

from modules.config_loader import TestConfig
from modules.scoring import ResultadoTest, UMBRAL_EMPATE

TITULO_CIERRE = "El desafío de la elección: más allá del interés"
SUBTITULO_CIERRE = ("Confía en lo que descubriste sobre ti. Esta elección es el primer paso para construir "
                    "un futuro que te inspire.")
ALCANCE = ("Los resultados de esta evaluación tienen fines exclusivamente educativos y orientativos. No "
           "constituyen un diagnóstico psicológico, clínico, laboral o médico, ni sustituyen la valoración "
           "realizada por profesionales especializados. La elección de un campo formativo debe considerar, "
           "además de estos resultados, los intereses, experiencias, habilidades, circunstancias personales y "
           "objetivos académicos del estudiante. Se recomienda revisar el reporte con el tutor u orientador "
           "correspondiente.")
MARGEN_ALTO = Fraction(15, 100)


@dataclass(frozen=True)
class Rasgo:
    codigo: str
    nombre: str
    porcentaje: Fraction | None
    nivel: str | None
    descripcion: str
    alto: bool  # está en el nivel más alto de la hoja `niveles`


@dataclass(frozen=True)
class Campo:
    codigo: str
    nombre: str
    por_rasgos: Fraction | None  # afinidad del test de rasgos
    por_competencias: Fraction | None
    puntos: int | None  # puntos obtenidos en el test de competencias
    maximo: int | None
    nivel_competencias: str | None
    promedio: Fraction | None
    componentes: tuple[str, ...]  # códigos de los rasgos que pide
    descripcion: str  # texto de la afinidad (test de rasgos)
    descripcion_competencias: str
    requisito: str
    sin_experiencia: int
    requiere_exploracion: bool

    @property
    def distancia(self) -> Fraction | None:
        if self.por_rasgos is None or self.por_competencias is None:
            return None
        return abs(self.por_rasgos - self.por_competencias)


@dataclass(frozen=True)
class Informe:
    rasgos: tuple[Rasgo, ...]
    campos: tuple[Campo, ...]  # en el orden del Excel
    ranking: tuple[Campo, ...]  # solo con promedio, de mayor a menor
    dominante: Campo
    complementario: Campo | None
    tercero: Campo | None
    requeridos: tuple[Rasgo, ...]  # rasgos que pide el campo dominante
    indice: Fraction | None  # alineación (None si el campo no pide rasgos)
    etiqueta_indice: str
    margen: Fraction | None  # promedio 1.º - promedio 2.º
    empate: bool
    coinciden: bool  # el test de rasgos y el de competencias señalan el mismo campo
    confianza: str  # alta | buena | moderada
    motivos_confianza: tuple[str, ...]
    analisis: str
    fortalezas: tuple[str, ...]
    desarrollo: tuple[str, ...]
    lectura: str  # qué dicen los dos tests juntos
    notas: tuple[str, ...]  # requisitos y avisos para el alumno
    titulos: tuple[str, str]  # (test de rasgos, test de competencias)


def _p(x: Fraction | None) -> str:
    from modules.reports import pct
    return pct(x)


def _lista(items: Sequence[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def etiqueta_indice(indice: Fraction | None) -> str:
    if indice is None:
        return "Sin datos"
    return "Alineación alta" if indice >= Fraction(3, 4) else "Alineación moderada" if indice >= Fraction(1, 2) else "Alineación baja"


def construir(tests: Sequence[TestConfig], resultados: Sequence[ResultadoTest]) -> Informe | None:
    if len(tests) < 2 or len(tests) != len(resultados):
        return None
    ir = next((i for i, t in enumerate(tests) if t.afinidades), None)
    if ir is None:
        return None
    ic = next((i for i in range(len(tests)) if i != ir and not tests[i].afinidades), None)
    if ic is None:
        return None
    t_r, t_c, r_r, r_c = tests[ir], tests[ic], resultados[ir], resultados[ic]
    alto = t_r.niveles_categoria[0] if t_r.niveles_categoria else None
    rasgos = tuple(Rasgo(e.codigo, e.nombre, e.porcentaje, e.nivel, t_r.especialidad(e.codigo).descripcion,
                         alto is not None and e.porcentaje is not None and e.porcentaje >= alto.minimo)
                   for e in r_r.especialidades)
    por_rasgo = {r.codigo: r for r in rasgos}
    comp = {e.codigo: e for e in r_c.especialidades}
    campos = []
    for d in t_r.afinidades:
        a = next(x for x in r_r.afinidades if x.codigo == d.codigo)
        c = comp.get(d.codigo)
        if c is None:
            continue
        prom = (a.porcentaje + c.porcentaje) / 2 if a.porcentaje is not None and c.porcentaje is not None else None
        esp_c = next((e for e in t_c.especialidades if e.codigo == d.codigo), None)
        campos.append(Campo(
            d.codigo, d.nombre, a.porcentaje, c.porcentaje, None if c.sin_datos else c.obtenido,
            None if c.sin_datos else c.maximo, c.nivel, prom, d.componentes, d.descripcion,
            esp_c.descripcion if esp_c else "", esp_c.requisito if esp_c else "", c.sin_experiencia,
            c.requiere_exploracion))
    ranking = tuple(sorted((c for c in campos if c.promedio is not None), key=lambda c: c.promedio, reverse=True))
    if not ranking:
        return None
    dom = ranking[0]
    comple = ranking[1] if len(ranking) > 1 else None
    tercero = ranking[2] if len(ranking) > 2 else None
    margen = dom.promedio - comple.promedio if comple else None
    empate = margen is not None and margen <= UMBRAL_EMPATE
    con_dato_r = [c for c in campos if c.por_rasgos is not None]
    con_dato_c = [c for c in campos if c.por_competencias is not None]
    top_r = max(con_dato_r, key=lambda c: c.por_rasgos) if con_dato_r else None
    top_c = max(con_dato_c, key=lambda c: c.por_competencias) if con_dato_c else None
    coinciden = top_r is not None and top_c is not None and top_r.codigo == top_c.codigo

    requeridos = tuple(por_rasgo[c] for c in dom.componentes if c in por_rasgo and por_rasgo[c].porcentaje is not None)
    indice = Fraction(sum(r.alto for r in requeridos), len(requeridos)) if requeridos else None
    altos = [r for r in requeridos if r.alto]
    por_fortalecer = [r for r in requeridos if not r.alto]

    motivos = []
    if empate:
        motivos.append(f"Empate técnico: {dom.nombre} y {comple.nombre} están a 5 puntos porcentuales o menos.")
    elif margen is not None:
        motivos.append(f"Margen de {round(float(margen) * 100)} puntos entre tu 1.ª y tu 2.ª opción.")
    motivos.append("Los dos tests coinciden en la primera opción." if coinciden
                   else "Los dos tests no coinciden en la primera opción: tómalos como dos miradas distintas.")
    if dom.requiere_exploracion:
        motivos.append(f"Contestaste «sin experiencia» en {dom.sin_experiencia} actividades de {dom.nombre}.")
    if empate or dom.requiere_exploracion:
        confianza = "moderada"
    elif margen is not None and margen >= MARGEN_ALTO and coinciden:
        confianza = "alta"
    else:
        confianza = "buena"

    nivel_c = f" Tu nivel en el test de competencias es {dom.nivel_competencias} ({dom.puntos} de {dom.maximo} puntos)." \
        if dom.puntos is not None else ""
    analisis = (f"El resultado sugiere afinidad con {dom.nombre}." +
                (f" La diferencia con el segundo campo ({comple.nombre}) es de {_diferencia_puntos(dom, comple)}." if comple else "") +
                (f" Las competencias asociadas incluyen: {dom.descripcion[0].lower() + dom.descripcion[1:].rstrip('.')}."
                 if dom.descripcion else "") +
                nivel_c +
                (f" Su alineación con tus rasgos conductuales es {etiqueta_indice(indice).replace('Alineación ', '')}: "
                 f"{len(altos)} de {len(requeridos)} rasgos que pide este campo están en nivel {alto.etiqueta if alto else 'alto'}."
                 if indice is not None else ""))
    fortalezas = [f"Tu {r.nombre.lower()} ({_p(r.porcentaje)}) es una fortaleza para este campo." for r in altos]
    if dom.puntos is not None:
        fortalezas.append(f"En el test de competencias, tu nivel en {dom.nombre} es {dom.nivel_competencias}.")
    if not altos and not dom.puntos:
        fortalezas.append("Todavía no hay rasgos destacados para este campo; revisa el resto de tu informe.")
    desarrollo = [f"Fortalecer {r.nombre.lower()} ({_p(r.porcentaje)}): talleres, prácticas supervisadas o "
                  "proyectos con retroalimentación." for r in por_fortalecer]
    if not desarrollo:
        desarrollo = ["Los rasgos que pide este campo están en nivel alto; el reto es mantenerlos con práctica."]

    if coinciden:
        lectura = (f"Tus dos tests apuntan a {top_r.nombre}. Es la señal más sólida que dan estos instrumentos.")
    elif top_r and top_c:
        lectura = (f"Tus tests no apuntan al mismo campo. Por personalidad destaca {top_r.nombre} ({_p(top_r.por_rasgos)}) "
                   f"y por competencias actuales {top_c.nombre} ({_p(top_c.por_competencias)}). No es una contradicción: "
                   "tu forma de ser encaja con uno y ya practicaste más el otro.")
    else:
        lectura = ""
    distancias = [c for c in campos if c.distancia is not None]
    if distancias and coinciden:
        mayor = max(distancias, key=lambda c: c.distancia)
        lectura += (f" La mayor distancia entre tests está en {mayor.nombre} ({_p(mayor.distancia)}): ahí tu forma de ser "
                    "y tus competencias actuales cuentan historias distintas.")

    notas = []
    for c in (dom, comple):
        if c is not None and c.requisito and c.nombre not in " ".join(notas):
            notas.append(f"Para {c.nombre} se requiere {c.requisito}; si es una opción para ti, conviene fortalecerlo.")
    for e in r_c.especialidades:
        if e.sin_datos:
            notas.append(f"{e.nombre}: contestaste «sin experiencia» en todo, no hay dato para compararla.")
        elif e.requiere_exploracion:
            notas.append(f"{e.nombre}: contestaste «sin experiencia» en {e.sin_experiencia} actividades; "
                         "conviene explorar esta área antes de descartarla.")
    return Informe(rasgos, tuple(campos), ranking, dom, comple, tercero, requeridos, indice, etiqueta_indice(indice),
                   margen, empate, coinciden, confianza, tuple(motivos), analisis, tuple(fortalezas),
                   tuple(desarrollo), lectura.strip(), tuple(notas), (t_r.titulo, t_c.titulo))


def _diferencia_puntos(a: Campo, b: Campo) -> str:
    if a.puntos is not None and b.puntos is not None:
        d = a.puntos - b.puntos
        return f"{d} {'punto' if d == 1 else 'puntos'} en el test de competencias"
    return f"{_p(a.promedio - b.promedio)} en el promedio"
