"""Identidad visual: hoja de estilos y componentes HTML pequeños (camino de pasos, chips, tablas).

Todo el texto que viene de datos (títulos, nombres de especialidades) se escapa. Las tipografías (Fraunces y
Plus Jakarta Sans) van autoalojadas en ./static/fonts: no se carga nada de servidores de terceros.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Sequence

import streamlit as st

INSTITUCION = "Facultad de Contaduría y Administración"
UNIVERSIDAD = "Universidad Autónoma Benito Juárez de Oaxaca"
# Los logos viven en ./static y se sirven con enableStaticServing (config.toml): el navegador los
# guarda en caché y no se reenvían en cada recarga de la página.
LOGO_FCA = ("/app/static/logo_fca.png", 165, 240, "Facultad de Contaduría y Administración, Calidad Académica")
LOGO_UABJO = ("/app/static/logo_uabjo.png", 204, 240, "Universidad Autónoma Benito Juárez de Oaxaca, 1955, Ciencia, Arte, Libertad")


@lru_cache(maxsize=1)
def _css() -> str:
    return (Path(__file__).with_name("tema.css")).read_text(encoding="utf-8")


def aplicar() -> None:
    """Inyecta la hoja de estilos. Se llama al inicio de cada página."""
    st.html(f"<style>{_css()}</style>")


def _logo(clase: str, logo: tuple) -> str:
    url, ancho, alto, alt = logo
    return f'<img class="logo {clase}" src="{url}" width="{ancho}" height="{alto}" alt="{escape(alt)}">'


def _marca() -> str:
    """Un logo a cada lado y el nombre de la facultad al centro."""
    return (f'<div class="marca">{_logo("fca", LOGO_FCA)}'
            f'<span class="inst"><span class="kicker">{UNIVERSIDAD}</span><span class="nombre">{INSTITUCION}</span></span>'
            f'{_logo("uabjo", LOGO_UABJO)}</div>')


def _corto(titulo: str) -> str:
    """'Test 1: The Big Five' -> 'Test 1' (rótulo del paso)."""
    return titulo.split(":")[0].strip() if ":" in titulo else titulo


def cabecera(tests: Sequence, paso: int) -> None:
    """Marca de la facultad y camino de pasos: Registro, un paso por test y Resultados.
    `paso` 0 = registro, 1..N = test n, N+1 = resultados."""
    rotulos = ["Registro", *[_corto(t.titulo) for t in tests], "Resultados"]
    items = []
    for i, r in enumerate(rotulos):
        estado = "hecho" if i < paso else "actual" if i == paso else "pendiente"
        marca = "✓" if estado == "hecho" else ""
        actual = ' aria-current="step"' if estado == "actual" else ""
        items.append(f'<li class="{estado}"{actual}><span class="punto" aria-hidden="true">{marca}</span>'
                     f'<span class="rotulo">{escape(r)}</span></li>')
    st.html(f'<nav class="camino" aria-label="Progreso de la evaluación">{_marca()}'
            f'<ol>{"".join(items)}</ol></nav>')


def marca() -> None:
    """Solo la marca de la facultad (sin camino de pasos): panel del docente."""
    st.html(f'<nav class="camino" aria-label="Facultad">{_marca()}</nav>')


def pregunta(numero: int, texto: str, primera: bool = False) -> None:
    clase = "pregunta primera" if primera else "pregunta"
    st.html(f'<div class="{clase}"><span class="num">{numero}</span><p>{escape(texto)}</p></div>')


# ---------------------------------------------------------------- resultados

def _tono(nivel: str | None) -> str:
    n = (nivel or "").lower()
    return "alto" if "alt" in n else "medio" if "medi" in n else "bajo"


def chip(nivel: str | None) -> str:
    return f'<span class="chip {_tono(nivel)}">{escape(nivel)}</span>' if nivel else "—"


def porcentaje(valor: Fraction | None) -> str:
    """'64.0 %' con barra; el redondeo es el mismo que usan el PDF y el Excel."""
    from modules.reports import pct
    if valor is None:
        return "Sin datos"
    ancho = min(100.0, float(valor) * 100)
    return f'<span class="barra"><i style="width:{ancho:.1f}%"></i></span>{escape(pct(valor))}'


def tabla(cabeceras: Sequence[str], filas: Sequence[Sequence[str]], numericas: Sequence[int] = ()) -> None:
    """Tabla HTML. Cada celda ya debe venir como HTML seguro (usa `escape`, `chip` o `porcentaje`)."""
    cab = "".join(f'<th scope="col"{" class=num" if i in numericas else ""}>{escape(c)}</th>' for i, c in enumerate(cabeceras))
    cuerpo = "".join("<tr>" + "".join(f'<td{" class=num" if i in numericas else ""}>{c}</td>'
                                       for i, c in enumerate(fila)) + "</tr>" for fila in filas)
    st.html(f'<div class="tabla-w"><table class="tabla"><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table></div>')


def tarjetas_resumen(items: Sequence[dict]) -> None:
    """Una tarjeta por test con su 1ª y 2ª opción. items: titulo, primera, segunda, nota (opcional)."""
    tarjetas = []
    for it in items:
        segunda = f'<p class="segunda">2ª opción: <b>{escape(it["segunda"])}</b></p>' if it.get("segunda") else ""
        nota = f'<p class="nota">{escape(it["nota"])}</p>' if it.get("nota") else ""
        tarjetas.append(f'<section><p class="test">{escape(it["titulo"])}</p>'
                        f'<p class="primera"><span class="rol">1ª opción</span>{escape(it["primera"])}</p>{segunda}{nota}</section>')
    st.html(f'<div class="resumen">{"".join(tarjetas)}</div>')
