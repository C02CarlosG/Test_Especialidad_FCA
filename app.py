"""Entrada de la app. Fase 2: ruteo hacia la vista del alumno.

La vista de admin se conecta en la Fase 5.
"""
import logging
from pathlib import Path

import streamlit as st

from modules.config_loader import ConfigError, load_all_tests
from modules.db import DBConfigError, SupabaseRepo, crear_cliente
from views import alumno

RAIZ = Path(__file__).parent
log = logging.getLogger(__name__)

st.set_page_config(page_title="Evaluación Diagnóstica FCA", page_icon="🎓", layout="centered")


@st.cache_resource
def _tests():
    return load_all_tests(RAIZ / "config" / "tests")


@st.cache_resource
def _repo():
    return SupabaseRepo(crear_cliente(st.secrets))


def _cliente_ip() -> str:
    """IP del cliente según el proxy de Streamlit Cloud; 'desconocido' si no hay cabecera."""
    try:
        xff = st.context.headers.get("X-Forwarded-For", "")
    except Exception:
        xff = ""
    return xff.split(",")[0].strip() or "desconocido"


try:
    tests, repo = _tests(), _repo()
except (ConfigError, DBConfigError, FileNotFoundError):
    log.exception("Configuración incompleta")
    st.title("Evaluación Diagnóstica FCA")
    st.error("El test no está disponible por el momento. Avisa a tu docente.")
else:
    aviso = (RAIZ / "config" / "aviso_privacidad.md").read_text(encoding="utf-8")
    alumno.render(repo, tests, aviso, _cliente_ip())
