"""Páginas de la app (alumno y docente) con sus dependencias inyectadas, para poder probarlas
sin Supabase. app.py solo las conecta con la configuración real."""
from __future__ import annotations

import logging
from typing import Callable

import streamlit as st

from views import admin, alumno

log = logging.getLogger(__name__)


def pagina_alumno(cargar: Callable, aviso_md: str, secreto: Callable, cliente_ip: str) -> None:
    """`cargar()` devuelve (tests, repo) o lanza si la configuración está incompleta."""
    try:
        tests, repo = cargar()
    except Exception:
        log.exception("Configuración incompleta")
        st.title("Evaluación Diagnóstica FCA")
        st.error("El test no está disponible por el momento. Avisa a tu docente.")
        return
    # El alumno ve y descarga sus resultados al terminar, salvo que [app] MOSTRAR_RESULTADO_AL_ALUMNO sea false.
    mostrar = secreto("app", "MOSTRAR_RESULTADO_AL_ALUMNO", True)
    mostrar = mostrar if isinstance(mostrar, bool) else str(mostrar).strip().lower() not in ("false", "no", "0")
    alumno.render(repo, tests, aviso_md, cliente_ip, mostrar)


def pagina_admin(cargar: Callable, secreto: Callable, cliente_ip: str) -> None:
    try:
        tests, repo = cargar()
    except Exception:
        # Sin sesión no se muestra ningún detalle (rutas del servidor, errores de los archivos, secretos):
        # cualquiera puede abrir /admin. El detalle queda en los registros de la app.
        log.exception("Configuración incompleta (panel del docente)")
        st.title("Panel del docente")
        st.error("El panel no está disponible por un problema de configuración. "
                 "Revisa los registros de la app.")
        return
    admin.render(repo, tests, secreto("admin", "password"), cliente_ip, secreto("app", "public_url"))
