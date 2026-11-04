"""Entrada de la app: la vista del alumno en "/" y el panel del docente en la ruta oculta "/admin"."""
from pathlib import Path

import streamlit as st

from modules.config_loader import load_all_tests
from modules.db import SupabaseRepo, crear_cliente
from views import paginas

RAIZ = Path(__file__).parent

st.set_page_config(page_title="Evaluación Diagnóstica FCA", page_icon="🎓", layout="centered")


@st.cache_resource
def _tests():
    return load_all_tests(RAIZ / "config" / "tests")


@st.cache_resource
def _repo():
    return SupabaseRepo(crear_cliente(st.secrets))


def _cargar():
    return _tests(), _repo()


def _cliente_ip() -> str:
    """IP del cliente según el proxy de Streamlit Cloud; 'desconocido' si no hay cabecera."""
    try:
        xff = st.context.headers.get("X-Forwarded-For", "")
    except Exception:
        xff = ""
    return xff.split(",")[0].strip() or "desconocido"


def _secreto(seccion: str, clave: str, defecto=None):
    try:
        return st.secrets[seccion][clave]
    except Exception:
        return defecto


def pagina_alumno() -> None:
    aviso = (RAIZ / "config" / "aviso_privacidad.md").read_text(encoding="utf-8")
    paginas.pagina_alumno(_cargar, aviso, _secreto, _cliente_ip())


def pagina_admin() -> None:
    paginas.pagina_admin(_cargar, _secreto, _cliente_ip())


navegacion = st.navigation(
    [st.Page(pagina_alumno, title="Evaluación", url_path="", default=True),
     st.Page(pagina_admin, title="Docente", url_path="admin")],
    position="hidden")
navegacion.run()
