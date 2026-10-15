"""Vista del test, Fase 3: preguntas por bloque, barra de avance y guardado por bloque.

Una columna y botones grandes para el celular. Todas las preguntas son obligatorias; el
avance se guarda en la BD al terminar cada bloque (ver modules.avance).
"""
from __future__ import annotations

import logging
from typing import Sequence

import streamlit as st

from modules.acceso import Alumno
from modules.avance import (AvanceError, Posicion, RepositorioAvance, calcular_posicion,
                            guardar_bloque)
from modules.config_loader import TestConfig

log = logging.getLogger(__name__)

# Áreas de toque de al menos 44 px para contestar con el dedo en el celular.
_CSS = """
<style>
label[data-testid="stRadioOption"] { min-height: 44px; padding: .5rem .75rem; margin-bottom: .4rem;
  border: 1px solid rgba(128,128,128,.35); border-radius: .6rem; width: 100%; }
label[data-testid="stRadioOption"]:has(input:checked) { border-color: #f5c400; background: rgba(245,196,0,.12); }
</style>
"""

# Tras guardar un bloque la página nueva debe empezar arriba, no donde estaba el botón.
_SUBIR = "<script>document.querySelector('[data-testid=\"stMain\"]')?.scrollTo(0, 0);</script>"

_SE = "SE"  # clave interna de la opción "sin experiencia" en el radio (se guarda como NULL)


def _opciones(test: TestConfig) -> tuple[list, dict]:
    """Opciones del radio y su texto. Se usan claves str para no mezclar None con números."""
    etiquetas = {str(o.valor): f"{o.valor} – {o.etiqueta}" for o in test.escala}
    if test.sin_experiencia:
        etiquetas[_SE] = test.sin_experiencia
    return list(etiquetas), etiquetas


def _encabezado(pos: Posicion) -> None:
    test = pos.test
    st.title("Evaluación Diagnóstica FCA")
    st.caption(f"Test {pos.numero_test} de {pos.total_tests} · {test.titulo}")
    st.progress(pos.contestadas / len(test.preguntas),
                text=f"Bloque {pos.numero_bloque} de {pos.total_bloques} · "
                     f"{pos.contestadas} de {len(test.preguntas)} preguntas contestadas")
    if test.instrucciones:
        with st.expander("Instrucciones", expanded=pos.contestadas == 0):
            st.write(test.instrucciones)


def _fin() -> None:
    st.title("Evaluación Diagnóstica FCA")
    st.success("¡Terminaste! Tus respuestas quedaron guardadas.")
    st.write("Gracias por tu participación. Tu tutor u orientador te compartirá los "
             "resultados. Ya puedes cerrar esta página.")


def render(repo: RepositorioAvance, alumno: Alumno, tests: Sequence[TestConfig]) -> None:
    try:
        pos = calcular_posicion(repo, alumno, tests)
    except AvanceError as exc:
        st.error(exc.mensaje)
        return
    except Exception:
        log.exception("Error al calcular el avance del alumno")
        st.error("No pudimos cargar tu avance. Recarga la página e inténtalo de nuevo.")
        return
    if pos is None:
        _fin()
        return

    if st.session_state.pop("reanudado", False):
        st.success("Te damos la bienvenida de nuevo. Continúas donde te quedaste.")
    st.html(_CSS)
    if st.session_state.pop("subir", False):
        st.html(_SUBIR, unsafe_allow_javascript=True)
    _encabezado(pos)

    test = pos.test
    claves, etiquetas = _opciones(test)
    numero = {p.id: n for n, p in enumerate(test.preguntas, start=1)}
    with st.form(f"bloque-{test.id}-{pos.bloque}"):
        for p in test.preguntas_de_bloque(pos.bloque):
            st.markdown(f"**{numero[p.id]}. {p.texto}**")
            st.radio(p.texto, claves, index=None, format_func=etiquetas.get,
                     key=f"r-{test.id}-{p.id}", label_visibility="collapsed")
        ultimo = pos.numero_bloque == pos.total_bloques
        enviar = st.form_submit_button(
            "Terminar este test" if ultimo else "Guardar y continuar",
            type="primary", use_container_width=True)
    if not enviar:
        return

    elegidas = {p.id: st.session_state.get(f"r-{test.id}-{p.id}")
                for p in test.preguntas_de_bloque(pos.bloque)}
    respuestas = {pid: (None if c == _SE else int(c)) for pid, c in elegidas.items() if c is not None}
    try:
        guardar_bloque(repo, alumno, tests, test, pos.bloque, respuestas)
    except AvanceError as exc:
        st.error(exc.mensaje)
    except Exception:
        log.exception("Error al guardar el bloque")
        st.error("No pudimos guardar tus respuestas. Inténtalo de nuevo.")
    else:
        st.session_state["subir"] = True
        st.rerun()
