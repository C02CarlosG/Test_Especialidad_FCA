"""Hoja de resultados del alumno (pantalla): resumen de convergencia, gráficas, diagnóstico y cierre.

Lee todo de modules.interpretacion.Informe (el mismo que usan el PDF y el Excel). Cada texto que viene de datos se
escapa; las gráficas son PNG de modules.graficas.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Sequence

import streamlit as st

from modules.acceso import Alumno
from modules.graficas import grafica_campos, grafica_convergencia, grafica_ocean
from modules.interpretacion import ALCANCE, SUBTITULO_CIERRE, TITULO_CIERRE, Campo, Informe
from modules.reports import pct
from views import tema


def _pp(x) -> str:
    return pct(x).replace(" %", " %")


def _caja(clase: str, html: str) -> None:
    st.html(f'<section class="inf {clase}">{html}</section>')


def _titulo(texto: str, sub: str = "") -> None:
    s = f'<p class="inf-sub">{escape(sub)}</p>' if sub else ""
    st.html(f'<h2 class="inf-h2">{escape(texto)}</h2>{s}')


def _lista(items: Sequence[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def _campo_pts(c: Campo) -> str:
    return f"{c.puntos} / {c.maximo} pts en el test de competencias" if c.puntos is not None else "Sin datos en el test de competencias"


def mostrar(alumno: Alumno, informe: Informe, fecha: datetime, cache: dict) -> None:
    """`cache`: dict de la sesión donde se guardan las gráficas (matplotlib tarda y la página se redibuja a menudo)."""
    def grafica(clave, fn):
        if clave not in cache:
            cache[clave] = fn(informe)
        return cache[clave]

    dom, com = informe.dominante, informe.complementario
    _caja("cab", f'<h1>Reporte de Evaluación Integral</h1>'
                 f'<p class="datos">{escape(alumno.nombre_completo)} · Matrícula {escape(alumno.matricula)} · '
                 f'Tutor: {escape(alumno.tutor)}</p><p class="folio">Fecha: {fecha.strftime("%d/%m/%Y")}</p>'
                 f'<div class="alcance"><b>Alcance del instrumento:</b> {escape(ALCANCE)}</div>')

    _titulo("Resumen de convergencia", "Une los dos tests: cómo eres y lo que ya sabes hacer.")
    requeridos = "".join(
        f'<div class="comp"><b>{escape(r.nombre)}</b> {escape(pct(r.porcentaje))} {tema.chip(r.nivel)}</div>'
        for r in informe.requeridos) or "<span class=et>Este campo no define rasgos.</span>"
    indice = f'{round(float(informe.indice) * 100)} % · {escape(informe.etiqueta_indice)}' if informe.indice is not None else "—"
    explica = (f'{sum(r.alto for r in informe.requeridos)} de {len(informe.requeridos)} rasgos requeridos están en el nivel más alto.'
               if informe.requeridos else "")
    complementario = (f'<div class="gr">{escape(com.nombre)}</div><div class="et">{escape(_campo_pts(com))}</div>'
                      if com else '<div class="gr">—</div>')
    chip_conf = {"alta": "alto", "buena": "alto", "moderada": "medio"}[informe.confianza]
    _caja("resumen", f'<div class="r4"><div><div class="et">Perfil vocacional dominante</div>'
                     f'<div class="gr">{escape(dom.nombre)}</div><div class="et">{escape(_campo_pts(dom))}</div></div>'
                     f'<div><div class="et">Campo formativo complementario</div>{complementario}</div>'
                     f'<div><div class="et">Rasgos Big Five requeridos vs. obtenidos</div>{requeridos}</div>'
                     f'<div><div class="et">Índice de alineación</div><div class="gr az">{indice}</div>'
                     f'<div class="et">{escape(explica)}</div></div></div>'
                     f'<div class="conf"><span class="chip {chip_conf}">Confianza {informe.confianza}</span>'
                     f'<div>{" ".join(escape(m) for m in informe.motivos_confianza)}</div></div>')
    for n in informe.notas:
        st.html(f'<div class="inf nota"><b>Nota:</b> {escape(n)}</div>')

    c1, c2 = st.columns(2)
    for col, titulo, png, pie in (
            (c1, "Resultados Big Five (OCEAN)", grafica('g_ocean', grafica_ocean),
             "Tus factores más altos son fortalezas conductuales; los más bajos, áreas con espacio para crecer."),
            (c2, "Orientación por campo formativo", grafica('g_campos', grafica_campos),
             "Un puntaje alto indica que realizas esas actividades con más autonomía. Es una guía orientativa, no determinista.")):
        with col:
            st.html(f'<h3 class="inf-h3">{escape(titulo)}</h3>')
            if png:
                st.image(png)
            st.html(f'<div class="inf pie">{escape(pie)}</div>')

    _titulo("Cómo se ven tus rasgos", "No hay rasgos buenos ni malos: describen cómo sueles desempeñarte.")
    tema.tabla(["Rasgo", "Porcentaje", "Nivel", "Qué significa"],
               [[escape(r.nombre), tema.porcentaje(r.porcentaje), tema.chip(r.nivel), escape(r.descripcion)]
                for r in informe.rasgos], numericas=[1])

    _titulo("Dónde coinciden tus dos tests",
            "Si los puntos están cerca, la señal es más sólida; el número es el promedio de ambos tests.")
    png = grafica('g_conv', grafica_convergencia)
    if png:
        st.image(png)
    if informe.lectura:
        st.html(f'<div class="inf pie">{escape(informe.lectura)}</div>')

    _titulo("Diagnóstico orientativo del campo formativo")
    _caja("diag", f'<h3>Análisis de afinidad y competencias</h3><p>{escape(informe.analisis)}</p>'
                  f'<h4 class="verde">Fortalezas proyectadas</h4>{_lista(informe.fortalezas)}'
                  f'<h4 class="naranja">Áreas de desarrollo sugeridas</h4>{_lista(informe.desarrollo)}')

    _titulo("Tus rutas para explorar", "Dos caminos con sentido para ti y una tercera opción para ampliar horizontes.")
    rutas = [(dom, "Opción A" if informe.empate else "1.ª opción", "principal")]
    if com:
        rutas.append((com, "Opción B" if informe.empate else "2.ª opción", "secundaria"))
    if informe.tercero:
        rutas.append((informe.tercero, "Para explorar", "otra"))
    tarjetas = "".join(
        f'<div class="ruta {clase}"><span class="chip {"alto" if clase == "principal" else "bajo"}">{escape(tag)}</span>'
        f'<h3>{escape(c.nombre)} · {escape(pct(c.promedio))}</h3>'
        f'<p>{escape(c.descripcion)}</p><p class="et">{escape(c.descripcion_competencias)}</p></div>'
        for c, tag, clase in rutas)
    st.html(f'<div class="inf rutas">{tarjetas}</div>')

    st.html(f'<div class="inf cierre"><h2>{escape(TITULO_CIERRE)}</h2><p>{escape(SUBTITULO_CIERRE)}</p></div>')
