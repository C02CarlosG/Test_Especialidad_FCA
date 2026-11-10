"""Identidad visual: hoja de estilos y componentes HTML pequeños (camino de pasos, chips, tablas).

Todo el texto que viene de datos (títulos, nombres de especialidades) se escapa. Las tipografías (Fraunces y
Plus Jakarta Sans) van autoalojadas en ./static/fonts: no se carga nada de servidores de terceros.
"""
from __future__ import annotations

import base64
from fractions import Fraction
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Sequence

import streamlit as st

from modules.institucion import COORDINACION, CUERPO_ACADEMICO, FACULTAD

_FACULTAD_HTML = FACULTAD.replace(" - ", "\u00a0- ")  # el guion se queda pegado a la palabra anterior al partir la línea
# Los logos (./static) van incrustados en el HTML como data URI: así se ven igual en local, en Streamlit
# Cloud (donde la app corre bajo una ruta distinta y una ruta absoluta hacia la carpeta static da 404) y detrás de
# cualquier proxy. Pesan ~21 KB en total.
RAIZ = Path(__file__).resolve().parent.parent
LOGO_FCA = ("logo_fca.png", 165, 240, "Facultad de Contaduría y Administración, Calidad Académica")
LOGO_GESTION = ("logo_gestion.png", 240, 240, "Gestión e Innovación de las Organizaciones, Cuerpo Académico FCA UABJO")


@lru_cache(maxsize=1)
def _css() -> str:
    return (Path(__file__).with_name("tema.css")).read_text(encoding="utf-8")


def aplicar() -> None:
    """Inyecta la hoja de estilos. Se llama al inicio de cada página."""
    st.html(f"<style>{_css()}</style>")


@lru_cache(maxsize=None)
def _data_uri(archivo: str) -> str:
    return "data:image/png;base64," + base64.b64encode((RAIZ / "static" / archivo).read_bytes()).decode()


def _logo(clase: str, logo: tuple) -> str:
    archivo, ancho, alto, alt = logo
    return f'<img class="logo {clase}" src="{_data_uri(archivo)}" width="{ancho}" height="{alto}" alt="{escape(alt)}">'


def _marca() -> str:
    """Un logo a cada lado y, al centro, la facultad, la coordinación y el cuerpo académico (tres líneas)."""
    return (f'<div class="marca">{_logo("fca", LOGO_FCA)}'
            f'<span class="inst"><span class="nombre">{_FACULTAD_HTML}</span><span class="coord">{COORDINACION}</span>'
            f'<span class="area">{CUERPO_ACADEMICO}</span></span>'
            f'{_logo("gestion", LOGO_GESTION)}</div>')


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
    compacta = " compacta" if 1 <= paso <= len(tests) else ""  # mientras contesta, en celular, la marca ocupa menos
    st.html(f'<nav class="camino{compacta}" aria-label="Progreso de la evaluación">{_marca()}'
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


def tarjetas_resumen(items: Sequence[dict], mejor: str | None = None, segunda: str | None = None,
                     aviso: str | None = None) -> None:
    """Una tarjeta de recomendación (`mejor`, `segunda`, `aviso`) y, debajo, un sello por test con su
    1ª y 2ª opción. items: titulo, primera, segunda, nota (opcional). Con un solo test y sin `mejor`,
    la tarjeta toma la opción de ese test."""
    if mejor is None and len(items) == 1:
        mejor, segunda = items[0]["primera"], items[0].get("segunda")
    hero = ""
    if mejor is not None:
        seg = f'<p class="segunda">2ª opción: <b>{escape(segunda)}</b></p>' if segunda else ""
        av = f'<p class="nota">{escape(aviso)}</p>' if aviso else ""
        hero = (f'<section class="mejor"><p class="rol">Tu mejor opción</p><p class="nombre">{escape(mejor)}</p>'
                f'{seg}{av}</section>')
    sellos = []
    for it in items:
        seg = f'<span class="seg">2ª: {escape(it["segunda"])}</span>' if it.get("segunda") else ""
        nota = f'<span class="nota">{escape(it["nota"])}</span>' if it.get("nota") else ""
        sellos.append(f'<div class="sello"><span class="test">{escape(it["titulo"])}</span>'
                      f'<span class="opcion">{escape(it["primera"])}</span>{seg}{nota}</div>')
    st.html(f'<div class="resumen">{hero}<div class="sellos">{"".join(sellos)}</div></div>')


def frase_avance(registrados: int, terminaron: int, en_curso: int) -> None:
    """Resumen del grupo en una frase grande, sin tarjetas."""
    def parte(n: int, uno: str, varios: str) -> str:
        return f'<b>{n}</b> {uno if n == 1 else varios}'
    st.html('<p class="frase">' + '<span class="sep" aria-hidden="true">·</span>'.join([
        parte(registrados, "alumno registrado", "alumnos registrados"),
        parte(terminaron, "terminó", "terminaron"),
        parte(en_curso, "en curso", "en curso")]) + '</p>')


def _nombre_legible(nombre: str) -> str:
    """La lista trae los nombres en MAYÚSCULAS; en pantalla se leen mejor con inicial mayúscula."""
    return nombre.title() if nombre.isupper() else nombre


def _mini_barra(hechas: int, total: int) -> str:
    ancho = 100 * hechas / total if total else 0
    clase = "completa" if total and hechas >= total else ""
    return (f'<span class="mini {clase}" role="img" aria-label="{hechas} de {total}"><i style="width:{ancho:.0f}%"></i></span>'
            f'<span class="cuenta">{hechas}<span class="de">/{total}</span></span>')


def cabecera_lista(titulos_tests: Sequence[str]) -> None:
    celdas = "".join(f"<span>{escape(t)}</span>" for t in titulos_tests)
    st.html(f'<div class="al-grid al-cab" style="--tests:{len(titulos_tests)}"><span>Matrícula</span><span>Alumno</span>'
            f'<span>Estado</span>{celdas}</div>')


def fila_lista(matricula: str, nombre: str, estado: str, tono: str, tests: Sequence[tuple[int, int]] | None,
               nota: str = "", n_tests: int = 2) -> None:
    """Una fila de la lista de alumnos. `tests` = (contestadas, total) por test, o None si no se ha registrado."""
    nota_html = f'<small class="{"alerta" if nota.startswith("Fuera") else ""}">{escape(nota)}</small>' if nota else ""
    celdas = "".join(f'<span class="al-test">{_mini_barra(h, t)}</span>' for h, t in tests) if tests else \
        '<span class="al-test vacio">—</span>' * n_tests
    st.html(f'<div class="al-grid" style="--tests:{n_tests}"><span class="al-mat">{escape(matricula)}</span>'
            f'<span class="al-nombre"><b>{escape(_nombre_legible(nombre))}</b>{nota_html}</span>'
            f'<span><span class="chip {tono}">{escape(estado)}</span></span>{celdas}</div>')


def ficha_reinicio(matricula: str, nombre: str, detalle: str, tests: Sequence[tuple[str, int, int]]) -> None:
    """Encabezado del cuadro de reinicio: quién es y en qué va. tests = (título, contestadas, total)."""
    filas = "".join(f'<li><span>{escape(t)}</span><span class="cuenta">{h}<span class="de">/{n}</span></span></li>' for t, h, n in tests)
    st.html(f'<div class="rei-ficha"><p class="quien"><b>{escape(_nombre_legible(nombre))}</b><span>{escape(matricula)}</span></p>'
            f'<p class="detalle">{escape(detalle)}</p><ul>{filas}</ul></div>')
