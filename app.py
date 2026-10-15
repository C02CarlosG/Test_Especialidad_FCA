"""Entrada de la app: la vista del alumno en "/" y el panel del docente en la ruta oculta "/admin"."""
import logging
from pathlib import Path

import streamlit as st

from modules.config_loader import ConfigError, load_all_tests
from modules.db import DBConfigError, SupabaseRepo, crear_cliente
from views import admin, alumno

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


def _secreto(seccion: str, clave: str, defecto=None):
    try:
        return st.secrets[seccion][clave]
    except Exception:
        return defecto


def pagina_alumno() -> None:
    try:
        tests, repo = _tests(), _repo()
    except (ConfigError, DBConfigError, FileNotFoundError):
        log.exception("Configuración incompleta")
        st.title("Evaluación Diagnóstica FCA")
        st.error("El test no está disponible por el momento. Avisa a tu docente.")
        return
    aviso = (RAIZ / "config" / "aviso_privacidad.md").read_text(encoding="utf-8")
    # El alumno ve y descarga sus resultados al terminar, salvo que [app] MOSTRAR_RESULTADO_AL_ALUMNO sea false.
    mostrar = _secreto("app", "MOSTRAR_RESULTADO_AL_ALUMNO", True)
    mostrar = mostrar if isinstance(mostrar, bool) else str(mostrar).strip().lower() not in ("false", "no", "0")
    alumno.render(repo, tests, aviso, _cliente_ip(), mostrar)


def pagina_admin() -> None:
    try:
        tests, repo = _tests(), _repo()
    except ConfigError as exc:  # el docente sí ve el detalle de los archivos de tests
        st.title("Panel del docente")
        st.error("Los archivos de config/tests no son válidos:")
        for e in exc.errores:
            st.write(f"- {e}")
        return
    except (DBConfigError, FileNotFoundError) as exc:
        st.title("Panel del docente")
        st.error(f"Supabase sin configurar: {exc}")
        return
    admin.render(repo, tests, _secreto("admin", "password"), _cliente_ip(), _secreto("app", "public_url"))


navegacion = st.navigation(
    [st.Page(pagina_alumno, title="Evaluación", url_path="", default=True),
     st.Page(pagina_admin, title="Docente", url_path="admin")],
    position="hidden")
navegacion.run()
