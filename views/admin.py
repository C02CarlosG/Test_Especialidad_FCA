"""Panel del docente: login, avance de todos los alumnos, descargas y código QR.

Se llega por la ruta oculta /admin (no aparece en ningún menú del alumno).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Sequence
from zoneinfo import ZoneInfo

import streamlit as st

from modules import admin_auth
from modules.config_loader import TestConfig
from modules.envio import ConfigCorreo, enviar_pendientes, pendientes_de_envio
from modules.panel import PanelDatos, cargar_panel, lista_de_alumnos, reiniciar, sincronizar_resultados
from modules.qr_utils import UrlInvalida, qr_png, validar_url
from modules.reports import excel_individual, pdf_individual
from modules.reports_admin import ESTADOS, excel_concentrado, nombre_pdf, zip_pdfs
from views import tema
from views.alumno import SEMESTRES

log = logging.getLogger(__name__)
ZONA = ZoneInfo("America/Mexico_City")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
URL_EJEMPLO = "https://tu-app.streamlit.app"
# La app usa diseño centrado (pensado para el celular del alumno); el panel necesita más ancho.
_ANCHO = '<style>[data-testid="stMainBlockContainer"] { max-width: 1200px; }</style>'


def _reloj() -> dict:
    """Plazo de la sesión en un dict mutable: las descargas diferidas corren en otro hilo, donde no
    se puede leer st.session_state, pero sí este objeto."""
    return st.session_state.setdefault("admin_reloj", {})


def _cerrar_sesion() -> None:
    _reloj()["hasta"] = 0  # también invalida las descargas que la pestaña aún tenga pendientes
    for clave in ("admin_hasta", "panel", "panel_en"):  # no dejar datos de alumnos en memoria
        st.session_state.pop(clave, None)


def _iniciar_sesion() -> None:
    hasta = time.time() + admin_auth.SESION_MINUTOS * 60
    st.session_state["admin_hasta"] = hasta
    _reloj()["hasta"] = hasta


def _sesion_activa() -> bool:
    hasta = st.session_state.get("admin_hasta")
    if hasta is None or time.time() > hasta:
        _cerrar_sesion()
        return False
    _iniciar_sesion()  # se renueva al usarla
    return True


def _vigente(fn):
    """Envuelve una descarga diferida: si la sesión venció mientras la pestaña seguía abierta, no
    entrega nada. Usar la sesión la renueva, igual que cualquier otra acción."""
    reloj = _reloj()

    def envuelta():
        if time.time() > reloj.get("hasta", 0):
            raise PermissionError("La sesión del docente venció; vuelve a entrar.")
        reloj["hasta"] = time.time() + admin_auth.SESION_MINUTOS * 60
        return fn()
    return envuelta


@st.fragment(run_every=60)
def _vigilante() -> None:
    """Cada minuto comprueba (sin renovar) que la sesión siga vigente; si venció, limpia la pantalla."""
    if time.time() > st.session_state.get("admin_hasta", 0):
        _cerrar_sesion()
        st.rerun()


def _login(repo, esperada, cliente_ip: str) -> None:
    tema.marca()
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
        _iniciar_sesion()
        st.rerun()


def _cargar(repo, tests: Sequence[TestConfig]) -> PanelDatos:
    if "panel" not in st.session_state:
        with st.spinner("Cargando alumnos…"):
            st.session_state["panel"] = cargar_panel(repo, tests)
            st.session_state["panel_en"] = datetime.now(ZONA)
    return st.session_state["panel"]


POR_PAGINA = 20
_TONO = {"terminado": "alto", "en_curso": "medio", "sin_registrar": "bajo"}


def _estado_reporte(alumno) -> str:
    """Texto breve del envío del reporte por correo; vacío para quien aún no termina."""
    if alumno is None or alumno.estado != "terminado":
        return ""
    if not alumno.correo:
        return "Sin correo"
    return {"enviado": "Reporte enviado", "enviando": "Enviando reporte…", "pendiente": "Reporte pendiente",
            "error": f"Reporte con error: {alumno.reporte_error or 'sin detalle'}"}.get(alumno.reporte_estado, "")


@st.dialog("Enviar reportes pendientes", width="medium")
def _dialogo_envio(repo, panel: PanelDatos, correo: ConfigCorreo) -> None:
    n = len(pendientes_de_envio(panel.filas))
    st.write(f"Se enviarán {n} reporte{'' if n == 1 else 's'} por correo a quienes terminaron y aún no lo reciben. "
             "¿Continuar?")
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", width="stretch", key="cancelar_envio"):
        st.rerun()
    if c2.button("Enviar", type="primary", width="stretch", key="confirmar_envio"):
        try:
            enviados, errores, omitidos = enviar_pendientes(
                repo, panel.tests, panel.filas, correo, st.session_state.get("panel_en") or datetime.now(ZONA))
        except Exception:
            log.exception("No se pudieron enviar los reportes pendientes")
            st.error("No se pudo completar el envío. Intenta de nuevo.")
            return
        resumen = f"Enviados: {enviados} · Con error: {errores} · Omitidos: {omitidos}"
        st.session_state["admin_alerta" if errores else "admin_aviso"] = resumen
        st.session_state.pop("panel", None)
        st.rerun()


def _bloque_envio(repo, panel: PanelDatos, correo: ConfigCorreo | None) -> None:
    pendientes = pendientes_de_envio(panel.filas)
    if correo is None:
        razon = "Falta configurar la sección [correo] en los secretos de la app."
    elif not pendientes:
        razon = "No hay reportes pendientes."
    else:
        razon = ""
    c1, c2 = st.columns([2, 3], vertical_alignment="center")
    if c1.button("Enviar reportes pendientes", key="enviar_pendientes", icon=":material/mail:",
                 width="stretch", disabled=bool(razon)):
        _dialogo_envio(repo, panel, correo)
    c2.caption(razon or f"{len(pendientes)} por enviar.")


def _pestana_avance(repo, tests: Sequence[TestConfig], panel: PanelDatos, correo: ConfigCorreo | None = None) -> None:
    if aviso := st.session_state.pop("admin_aviso", None):
        st.success(aviso)
    if alerta := st.session_state.pop("admin_alerta", None):
        st.warning(alerta)
    st.caption(f"Datos cargados a las {st.session_state['panel_en'].strftime('%H:%M')}. "
               "Pulsa «Actualizar datos» para ver lo más reciente.")
    tema.frase_avance(len(panel.filas), panel.terminados, len(panel.filas) - panel.terminados)
    _bloque_envio(repo, panel, correo)
    for aviso in panel.problemas:
        st.warning(aviso)
    lista = lista_de_alumnos(panel)
    if not lista:
        st.info("Todavía no hay alumnos registrados.")
        return
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    buscar = c1.text_input("Buscar", placeholder="Matrícula o nombre", max_chars=80)
    if q := buscar.strip().casefold():
        lista = [x for x in lista if q in x.matricula or q in x.nombre.casefold()]
    paginas = max(1, -(-len(lista) // POR_PAGINA))
    pagina = c2.number_input(f"Página (de {paginas})", 1, paginas, 1, step=1) if paginas > 1 else 1
    if not lista:
        st.info("Ningún alumno coincide con la búsqueda.")
        return
    anchos = [9.4, 1.9, 1.7]  # datos, reportes, reiniciar
    with st.container(key="lista_alumnos"):
        with st.container(key="cabecera_lista"):
            izq, *_ = st.columns(anchos)
            with izq:
                tema.cabecera_lista([f"Test {n}" for n in range(1, len(tests) + 1)])
        for item in lista[(pagina - 1) * POR_PAGINA: pagina * POR_PAGINA]:
            a = item.fila.alumno if item.fila else None
            estado = a.estado if a else "sin_registrar"
            nota = "Fuera de la lista" if panel.autorizados and not item.en_lista else \
                item.estatus.capitalize() if item.estatus == "IRREGULAR" else ""
            nota = " · ".join(x for x in (nota, _estado_reporte(a)) if x)
            with st.container(key=f"fila_{item.matricula}"):
                izq, centro, der = st.columns(anchos, vertical_alignment="center")
                with izq:
                    tema.fila_lista(item.matricula, a.nombre_completo if a else item.nombre,
                                    ESTADOS.get(estado, "Sin registrar"), _TONO[estado],
                                    [(item.fila.contestadas[n], len(t.preguntas)) for n, t in enumerate(tests)] if item.fila else None,
                                    nota, n_tests=len(tests))
                if item.fila:
                    with centro:
                        _boton_reportes(panel, item.fila)
                    if der.button("Reiniciar", key=f"rei_{a.id}", icon=":material/restart_alt:", width="stretch"):
                        _dialogo_reinicio(repo, tests, item.fila)


def _boton_reportes(panel: PanelDatos, fila) -> None:
    """«Reportes»: PDF y Excel del alumno, que se generan al descargar. Sin los tests terminados no hay reporte."""
    a = fila.alumno
    if not fila.completo:
        st.button("Reportes", key=f"sin_reporte_{a.id}", icon=":material/download:", width="stretch", disabled=True,
                  help="Todavía no termina todos los tests.")
        return
    fecha = st.session_state["panel_en"]  # el reporte lleva la hora real de los datos, no la del clic
    with st.popover("Reportes", icon=":material/download:", width="stretch"):
        st.caption(a.nombre_completo)
        st.download_button("PDF", _vigente(lambda: pdf_individual(a, panel.tests, list(fila.resultados), fecha)),
                           file_name=nombre_pdf(fila), mime="application/pdf", key=f"pdf_{a.id}",
                           icon=":material/picture_as_pdf:", width="stretch", on_click="ignore")
        st.download_button("Excel", _vigente(lambda: excel_individual(a, panel.tests, list(fila.resultados), fecha)),
                           file_name=nombre_pdf(fila).replace(".pdf", ".xlsx"), mime=XLSX, key=f"xlsx_{a.id}",
                           icon=":material/table_chart:", width="stretch", on_click="ignore")


def _opciones_reinicio(tests: Sequence[TestConfig], fila) -> list[tuple[str, int, int | None]]:
    """(texto, respuestas que se borran, desde qué test) para cada cosa que se puede reiniciar. Solo se ofrecen los
    tests con respuestas guardadas; `None` = quitar el registro. Los tests van en orden, así que reiniciar uno borra los siguientes."""
    opciones = []
    ultimo = len(tests) - 1
    for i in range(len(tests)):
        if fila.contestadas[i]:
            texto = (f"Rehacer el Test {i + 1}" if i == ultimo else
                     f"Rehacer el Test {i + 1} y el Test {i + 2}" if i + 1 == ultimo else
                     f"Rehacer del Test {i + 1} al Test {ultimo + 1}")
            opciones.append((texto, sum(fila.contestadas[i:]), i))
    opciones.append(("Quitar su registro y sus datos", sum(fila.contestadas), None))
    return opciones


@st.dialog("Reiniciar test", width="medium")
def _dialogo_reinicio(repo, tests: Sequence[TestConfig], fila) -> None:
    a = fila.alumno
    tema.ficha_reinicio(a.matricula, a.nombre_completo,
                        f"{SEMESTRES[a.semestre - 1] if a.semestre else 'Semestre sin indicar'} · {a.edad} años · Tutor: {a.tutor}",
                        [(t.titulo, fila.contestadas[i], len(t.preguntas)) for i, t in enumerate(tests)])
    opciones = _opciones_reinicio(tests, fila)
    # Por defecto, lo menos destructivo: el último test con respuestas (o el registro, si no hay ninguna).
    que = st.radio("¿Qué quieres reiniciar?", range(len(opciones)), index=max(0, len(opciones) - 2), key=f"que_{a.id}",
                   format_func=lambda i: opciones[i][0])
    texto, borradas, desde = opciones[que]
    if desde is None:
        efecto = "Tendrá que registrarse otra vez con su matrícula."
        boton = "Quitar registro"
    else:
        efecto = "Al entrar con su matrícula y nombre, volverá a contestar desde ahí."
        boton = f"Borrar {borradas} respuesta" + ("" if borradas == 1 else "s")
    st.html(f'<p class="rei-efecto">{efecto} Esta acción no se puede deshacer.</p>')
    c1, c2 = st.columns(2)
    if c1.button("Cancelar", width="stretch", key=f"cancelar_{a.id}"):
        st.rerun()
    if c2.button(boton, type="primary", width="stretch", key="confirmar_reinicio"):
        try:
            reiniciar(repo, a, tests, desde or 0, desde is None)
        except Exception:
            log.exception("No se pudo reiniciar al alumno")
            st.error("No se pudo reiniciar. Intenta de nuevo.")
            return
        st.session_state["admin_aviso"] = (f"{a.matricula} · {a.nombre_completo}: "
                                           f"{'registro quitado' if desde is None else 'test reiniciado'}.")
        st.session_state.pop("panel", None)
        st.rerun()


def _pestana_descargas(repo, panel: PanelDatos) -> None:
    fecha = st.session_state["panel_en"]  # los archivos llevan la hora real de los datos, no la del clic
    sello = fecha.strftime("%Y%m%d_%H%M")
    st.markdown("**Todos los alumnos**")
    c1, c2 = st.columns(2)
    c1.download_button("Excel concentrado (con respaldo de respuestas)",
                       _vigente(lambda: excel_concentrado(panel, fecha)), file_name=f"concentrado_{sello}.xlsx",
                       mime=XLSX, type="primary", width="stretch", on_click="ignore",
                       disabled=not panel.filas)
    c2.download_button("ZIP con los PDF de quienes terminaron",
                       _vigente(lambda: zip_pdfs(panel, fecha)[0]), file_name=f"pdfs_{sello}.zip", mime="application/zip",
                       width="stretch", on_click="ignore",
                       disabled=not any(f.completo for f in panel.filas))
    st.caption("El concentrado trae las hojas Resumen, Alumnos, Resultados (todos los tests juntos) y «Respuestas», que sirve de respaldo "
               "de la base de datos: descárgalo al cerrar cada aplicación.")

    st.markdown("**Un alumno**")
    completos = [f for f in panel.filas if f.completo]
    if not completos:
        st.info("Nadie ha terminado todos los tests todavía.")
    else:
        elegido = st.selectbox("Alumno", completos, format_func=lambda f: f"{f.alumno.matricula} · {f.alumno.nombre_completo}")
        d1, d2 = st.columns(2)
        d1.download_button("PDF", _vigente(lambda: pdf_individual(elegido.alumno, panel.tests, list(elegido.resultados), fecha)),
                           file_name=nombre_pdf(elegido), mime="application/pdf", width="stretch",
                           on_click="ignore")
        d2.download_button("Excel", _vigente(lambda: excel_individual(elegido.alumno, panel.tests, list(elegido.resultados), fecha)),
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


def render(repo, tests: Sequence[TestConfig], esperada: object, cliente_ip: str, url_publica: str | None,
           correo: ConfigCorreo | None = None) -> None:
    tema.aplicar()
    if not _sesion_activa():
        _login(repo, esperada, cliente_ip)
        return
    st.html(_ANCHO)
    tema.marca()
    st.title("Panel del docente")
    c1, c2 = st.columns([3, 1])
    if c2.button("Cerrar sesión", width="stretch"):
        _cerrar_sesion()
        st.rerun()
    if c1.button("Actualizar datos"):
        st.session_state.pop("panel", None)
    _vigilante()
    try:
        panel = _cargar(repo, tests)
    except Exception:
        log.exception("No se pudo cargar el panel")
        st.error("No se pudieron cargar los datos. Pulsa «Actualizar datos» para reintentar.")
        return
    avance, descargas, qr = st.tabs(["Alumnos", "Descargas", "Código QR"])
    with avance:
        _pestana_avance(repo, tests, panel, correo)
    with descargas:
        _pestana_descargas(repo, panel)
    with qr:
        _pestana_qr(url_publica)
