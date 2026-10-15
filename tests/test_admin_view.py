import re
import time

import pytest
from streamlit.proto.TextInput_pb2 import TextInput
from streamlit.testing.v1 import AppTest

CLAVE = "una-contraseña-larga-y-unica"


def _app():
    import streamlit as st
    from pathlib import Path
    from test_panel import poblar, TEST1, TEST2
    from views import admin

    if "repo" not in st.session_state:
        st.session_state["repo"] = poblar()
    esperada = st.session_state.get("esperada", "una-contraseña-larga-y-unica")
    admin.render(st.session_state["repo"], (TEST1, TEST2), esperada, "203.0.113.9", st.session_state.get("url"))


def _nuevo(**estado):
    at = AppTest.from_function(_app, default_timeout=60)
    for k, v in estado.items():
        at.session_state[k] = v
    return at.run()


def _entrar(at, clave=CLAVE):
    at.text_input[0].input(clave)
    at.button[0].click().run()
    return at


def test_sin_sesion_solo_se_ve_el_login():
    at = _nuevo()
    assert at.title[0].value == "Panel del docente"
    assert at.text_input[0].proto.type == TextInput.PASSWORD and not at.tabs and not at.dataframe


def test_contraseña_incorrecta_no_entra_y_cuenta_el_intento():
    at = _entrar(_nuevo(), "mala")
    assert "incorrecta" in at.error[0].value and not at.tabs
    assert len(at.session_state["repo"].intentos) == 2


def test_bloqueo_por_intentos_aunque_luego_use_la_buena():
    at = _nuevo()
    for _ in range(5):
        _entrar(at, "mala")
    _entrar(at, CLAVE)
    assert "Demasiados intentos" in at.error[0].value and not at.tabs


def test_sin_contraseña_configurada_el_panel_esta_deshabilitado():
    at = _nuevo(esperada="REEMPLAZAR")
    assert "no está configurado" in at.error[0].value and not at.text_input


def test_con_la_contraseña_buena_se_ve_el_panel_completo():
    at = _entrar(_nuevo())
    assert not at.exception and not at.error
    assert [t.label for t in at.tabs] == ["Avance", "Descargas", "Código QR"]
    frase = re.sub(r"<[^>]+>", "", next(h.value for h in at.get("html") if 'class="frase"' in h.value))
    assert re.sub(r"\s+", " ", frase).replace("·", " · ").split() == "4 alumnos registrados · 1 terminó · 3 en curso".split()
    tabla = at.dataframe[0].value
    assert list(tabla["Matrícula"]) == ["100001", "100002", "100003", "100004"]
    assert any("versión anterior" in w.value for w in at.warning)  # aviso del alumno con test viejo


def test_las_descargas_se_ofrecen_y_se_generan_bajo_demanda():
    at = _entrar(_nuevo())
    etiquetas = [b.proto.label for b in at.get("download_button")]
    assert "Excel concentrado (con respaldo de respuestas)" in etiquetas
    assert "ZIP con los PDF de quienes terminaron" in etiquetas
    assert etiquetas[-2:] == ["PDF", "Excel"]
    assert all(b.proto.ignore_rerun for b in at.get("download_button"))


def test_el_qr_pide_https_y_genera_el_png():
    at = _entrar(_nuevo())
    campo = next(t for t in at.text_input if t.label == "URL pública de la app")
    campo.input("http://mi-app.streamlit.app").run()
    assert any("https://" in e.value for e in at.error)
    campo = next(t for t in at.text_input if t.label == "URL pública de la app")
    campo.input("https://mi-app.streamlit.app").run()
    assert not at.error and "Descargar QR (PNG de alta resolución)" in [b.proto.label for b in at.get("download_button")]


def test_guardar_resultados_en_la_base():
    at = _entrar(_nuevo())
    boton = next(b for b in at.button if b.label.startswith("Guardar los resultados"))
    boton.click().run()
    assert at.success[0].value == "3 resultado(s) guardados."
    assert len(at.session_state["repo"].resultados_guardados) == 3


def test_cerrar_sesion_vuelve_al_login_y_borra_los_datos():
    at = _entrar(_nuevo())
    next(b for b in at.button if b.label == "Cerrar sesión").click().run()
    assert at.text_input[0].proto.type == TextInput.PASSWORD and "panel" not in at.session_state and "admin_hasta" not in at.session_state


def test_sesion_vencida_pide_la_contraseña_de_nuevo():
    at = _entrar(_nuevo())
    at.session_state["admin_hasta"] = time.time() - 1
    at.run()
    assert at.text_input[0].proto.type == TextInput.PASSWORD and not at.tabs and "panel" not in at.session_state


def test_la_sesion_se_renueva_con_el_uso():
    at = _entrar(_nuevo())
    at.session_state["admin_hasta"] = time.time() + 5
    at.run()
    assert at.session_state["admin_hasta"] > time.time() + 3000


def _app_descarga():
    import streamlit as st
    from views import admin
    st.session_state["envuelta"] = admin._vigente(lambda: "datos del docente")
    st.session_state["sesion"] = admin._sesion_activa()


def test_una_descarga_pendiente_no_entrega_nada_con_la_sesion_vencida():
    """La descarga diferida corre sin re-ejecutar el script: debe revisar el plazo por su cuenta."""
    at = AppTest.from_function(_app_descarga, default_timeout=30)
    at.session_state["admin_hasta"] = time.time() + 600
    at.run()
    assert at.session_state["sesion"] is True
    envuelta = at.session_state["envuelta"]
    assert envuelta() == "datos del docente"
    at.session_state["admin_reloj"]["hasta"] = time.time() - 1  # venció con la pestaña abierta
    with pytest.raises(PermissionError, match="venció"):
        envuelta()


def test_cerrar_sesion_invalida_las_descargas_pendientes():
    at = _entrar(_nuevo())
    reloj = at.session_state["admin_reloj"]
    assert reloj["hasta"] > time.time()
    next(b for b in at.button if b.label == "Cerrar sesión").click().run()
    assert reloj["hasta"] == 0 and "panel_en" not in at.session_state


def test_usar_una_descarga_renueva_la_sesion():
    at = AppTest.from_function(_app_descarga, default_timeout=30)
    at.session_state["admin_hasta"] = time.time() + 600
    at.run()
    reloj = at.session_state["admin_reloj"]
    reloj["hasta"] = time.time() + 5
    at.session_state["envuelta"]()
    assert reloj["hasta"] > time.time() + 3000


def test_el_panel_muestra_desde_cuando_son_los_datos():
    at = _entrar(_nuevo())
    assert any(c.value.startswith("Datos cargados a las ") for c in at.caption)
    assert at.session_state["panel_en"].tzinfo is not None
