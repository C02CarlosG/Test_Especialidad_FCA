"""Panel del docente: login, avance de todos los alumnos, descargas y código QR.

Se llega por la ruta oculta /admin (no aparece en ningún menú del alumno).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Sequence
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from modules import admin_auth
from modules.config_loader import TestConfig
from modules.panel import PanelDatos, cargar_panel, sincronizar_resultados
from modules.qr_utils import UrlInvalida, qr_png, validar_url
from modules.reports import excel_individual, pdf_individual
from modules.reports_admin import ESTADOS, excel_concentrado, nombre_pdf, zip_pdfs

log = logging.getLogger(__name__)
ZONA = ZoneInfo("America/Mexico_City")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
URL_EJEMPLO = "https://tu-app.streamlit.app"
# La app usa diseño centrado (pensado para el celular del alumno); el panel necesita más ancho.
_ANCHO = '<style>[data-testid="stMainBlockContainer"] { max-width: 1200px; }</style>'


def _sesion_activa() -> bool:
    hasta = st.session_state.get("admin_hasta")
    if hasta is None or time.time() > hasta:
        st.session_state.pop("admin_hasta", None)
        st.session_state.pop("panel", None)  # no dejar datos de alumnos en memoria de una sesión vencida
        return False
    st.session_state["admin_hasta"] = time.time() + admin_auth.SESION_MINUTOS * 60  # se renueva al usarla
    return True


def _login(repo, esperada, cliente_ip: str) -> None:
    st.title("Panel del docente")
    if not admin_auth.password_valida(esperada):
        st.error(admin_auth.PanelDeshabilitado().mensaje)
        return
    with st.form("login"):
        clave = st.text_input("Contraseña", type="password", max_chars=200)
        entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
    if not entrar:
        return
    try:
        admin_auth.intentar_login(repo, clave, esperada, cliente_ip)
    except admin_auth.AdminError as exc:
        st.error(exc.mensaje)
    except Exception:
        log.exception("Error al validar el acceso del docente")
        st.error("No pudimos validar el acceso. Intenta de nuevo en un momento.")
    else:
        st.session_state["admin_hasta"] = time.time() + admin_auth.SESION_MINUTOS * 60
        st.rerun()


def _tabla_avance(panel: PanelDatos) -> pd.DataFrame:
    filas = []
    for f in panel.filas:
        a = f.alumno
        fila = {"Matrícula": a.matricula, "Nombre": a.nombre_completo, "Edad": a.edad, "Tutor": a.tutor,
                "Registro": a.creado_en.astimezone(ZONA).strftime("%d/%m/%Y %H:%M") if a.creado_en else "",
                "Estado": ESTADOS.get(a.estado, a.estado)}
        for n, t in enumerate(panel.tests, start=1):
            fila[f"Test {n}"] = f"{ESTADOS[f.estado_tests[n - 1]]} ({f.contestadas[n - 1]}/{len(t.preguntas)})"
        for n, r in enumerate(f.resultados, start=1):
            fila[f"1ª opción T{n}"] = next((x.nombre for x in r.afinidades if x.codigo == r.principal), "") if r else ""
        filas.append(fila)
    return pd.DataFrame(filas)


def _cargar(repo, tests: Sequence[TestConfig]) -> PanelDatos:
    if "panel" not in st.session_state:
        with st.spinner("Cargando alumnos…"):
            st.session_state["panel"] = cargar_panel(repo, tests)
    return st.session_state["panel"]


def _pestana_avance(panel: PanelDatos) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("Registrados", len(panel.filas))
    c2.metric("Terminaron todo", panel.terminados)
    c3.metric("En curso", len(panel.filas) - panel.terminados)
    for aviso in panel.problemas:
        st.warning(aviso)
    if panel.filas:
        st.dataframe(_tabla_avance(panel), hide_index=True, width="stretch")
    else:
        st.info("Todavía no hay alumnos registrados.")


def _pestana_descargas(repo, panel: PanelDatos) -> None:
    fecha = datetime.now(ZONA)
    sello = fecha.strftime("%Y%m%d_%H%M")
    st.markdown("**Todos los alumnos**")
    c1, c2 = st.columns(2)
    c1.download_button("Excel concentrado (con respaldo de respuestas)",
                       lambda: excel_concentrado(panel, fecha), file_name=f"concentrado_{sello}.xlsx",
                       mime=XLSX, type="primary", width="stretch", on_click="ignore",
                       disabled=not panel.filas)
    c2.download_button("ZIP con los PDF de quienes terminaron",
                       lambda: zip_pdfs(panel, fecha)[0], file_name=f"pdfs_{sello}.zip", mime="application/zip",
                       width="stretch", on_click="ignore",
                       disabled=not any(f.completo for f in panel.filas))
    st.caption("El concentrado trae una hoja por test y la hoja «Respuestas», que sirve de respaldo "
               "de la base de datos: descárgalo al cerrar cada aplicación.")

    st.markdown("**Un alumno**")
    completos = [f for f in panel.filas if f.completo]
    if not completos:
        st.info("Nadie ha terminado todos los tests todavía.")
    else:
        elegido = st.selectbox("Alumno", completos, format_func=lambda f: f"{f.alumno.matricula} · {f.alumno.nombre_completo}")
        d1, d2 = st.columns(2)
        d1.download_button("PDF", lambda: pdf_individual(elegido.alumno, panel.tests, list(elegido.resultados), fecha),
                           file_name=nombre_pdf(elegido), mime="application/pdf", width="stretch",
                           on_click="ignore")
        d2.download_button("Excel", lambda: excel_individual(elegido.alumno, panel.tests, list(elegido.resultados), fecha),
                           file_name=nombre_pdf(elegido).replace(".pdf", ".xlsx"), mime=XLSX,
                           width="stretch", on_click="ignore")

    st.markdown("**Base de datos**")
    if st.button("Guardar los resultados calculados en la tabla «resultados»"):
        try:
            n = sincronizar_resultados(repo, panel, datetime.now(ZONA))
            st.success(f"{n} resultado(s) guardados.")
        except Exception:
            log.exception("No se pudieron guardar los resultados")
            st.error("No se pudieron guardar los resultados en la base de datos.")


def _pestana_qr(url_publica: str | None) -> None:
    st.write("Genera el código QR que los alumnos escanean para entrar. Imprímelo o proyéctalo en el salón.")
    inicial = url_publica if url_publica and url_publica != URL_EJEMPLO else ""
    url = st.text_input("URL pública de la app", value=inicial, placeholder=URL_EJEMPLO)
    if not url:
        return
    try:
        png = qr_png(validar_url(url))
    except UrlInvalida as exc:
        st.error(str(exc))
        return
    st.image(png, width=320)
    st.download_button("Descargar QR (PNG de alta resolución)", png, file_name="qr_acceso.png",
                       mime="image/png", type="primary", on_click="ignore")
    st.caption("Antes de imprimir, pruébalo con el celular (iPhone y Android).")


def render(repo, tests: Sequence[TestConfig], esperada: object, cliente_ip: str, url_publica: str | None) -> None:
    if not _sesion_activa():
        _login(repo, esperada, cliente_ip)
        return
    st.html(_ANCHO)
    st.title("Panel del docente")
    c1, c2 = st.columns([3, 1])
    if c2.button("Cerrar sesión", width="stretch"):
        st.session_state.pop("admin_hasta", None)
        st.session_state.pop("panel", None)
        st.rerun()
    if c1.button("Actualizar datos"):
        st.session_state.pop("panel", None)
    try:
        panel = _cargar(repo, tests)
    except Exception:
        log.exception("No se pudo cargar el panel")
        st.error("No se pudieron cargar los datos. Pulsa «Actualizar datos» para reintentar.")
        return
    avance, descargas, qr = st.tabs(["Avance", "Descargas", "Código QR"])
    with avance:
        _pestana_avance(panel)
    with descargas:
        _pestana_descargas(repo, panel)
    with qr:
        _pestana_qr(url_publica)
