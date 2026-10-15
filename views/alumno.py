"""Vista del alumno, Fase 2: registro en una sola pantalla (datos, aviso de privacidad
y consentimiento).

Al registrarse (o reanudar) el alumno pasa a views.test.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence
from zoneinfo import ZoneInfo

import streamlit as st

from modules.acceso import AccesoError, DatosAcceso, DatosInvalidos, Repositorio, iniciar_acceso
from views import test

log = logging.getLogger(__name__)

TITULO = "Evaluación Diagnóstica FCA"
SUBTITULO = "Test Big Five & Orientación Vocacional en Administración"
ZONA = ZoneInfo("America/Mexico_City")


def _encabezado() -> None:
    st.title(TITULO)
    st.caption(SUBTITULO)


def _registro(repo: Repositorio, aviso_md: str, cliente_ip: str) -> None:
    _encabezado()
    st.subheader("Registro del estudiante")
    with st.form("registro"):
        c1, c2, c3 = st.columns(3)
        paterno = c1.text_input("Apellido paterno *", max_chars=80, autocomplete="family-name")
        materno = c2.text_input("Apellido materno *", max_chars=80)
        nombres = c3.text_input("Nombre(s) *", max_chars=80, autocomplete="given-name")
        c4, c5, c6 = st.columns(3)
        matricula = c4.text_input("Matrícula *", max_chars=6, placeholder="6 números")
        edad = c5.number_input("Edad *", min_value=0, max_value=120, value=None, step=1,
                               placeholder="Años cumplidos")
        c6.text_input("Fecha de aplicación", value=datetime.now(ZONA).strftime("%d/%m/%Y"),
                      disabled=True)
        tutor = st.text_input("Nombre del tutor / orientador *", max_chars=80)
        with st.container(border=True):
            st.markdown(aviso_md)
            acepto = st.checkbox("Acepto el aviso de privacidad y declaro ser mayor de edad.")
        enviar = st.form_submit_button("Iniciar evaluación →", type="primary",
                                       width="stretch")
    if not enviar:
        return
    datos = DatosAcceso(paterno, materno, nombres, matricula,
                        int(edad) if edad is not None else None, tutor, acepto)
    try:
        res = iniciar_acceso(repo, datos, cliente_ip)
    except DatosInvalidos as exc:
        for msg in exc.errores.values():
            st.error(msg)
    except AccesoError as exc:
        st.error(exc.mensaje)
    except Exception:  # BD caída, red, etc.: no mostrar detalles al alumno
        log.exception("Error inesperado en el acceso del alumno")
        st.error("No pudimos registrar tu acceso. Intenta de nuevo en un momento.")
    else:
        st.session_state["alumno"] = res.alumno
        st.session_state["reanudado"] = res.reanudado
        st.session_state["etapa"] = "listo"
        st.rerun()


def render(repo, tests: Sequence, aviso_md: str, cliente_ip: str, mostrar_resultados: bool = True) -> None:
    etapa = st.session_state.setdefault("etapa", "registro")
    if etapa == "listo" and "alumno" in st.session_state:
        test.render(repo, st.session_state["alumno"], tests, mostrar_resultados)
    else:
        st.session_state["etapa"] = "registro"
        _registro(repo, aviso_md, cliente_ip)
