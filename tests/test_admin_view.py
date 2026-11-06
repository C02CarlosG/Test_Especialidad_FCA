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
    assert [t.label for t in at.tabs] == ["Alumnos", "Descargas", "Código QR"]
    frase = re.sub(r"<[^>]+>", "", next(h.value for h in at.get("html") if 'class="frase"' in h.value))
    assert re.sub(r"\s+", " ", frase).replace("·", " · ").split() == "4 alumnos registrados · 1 terminó · 3 en curso".split()
    assert _matriculas(at) == ["100001", "100002", "100003", "100004"]
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


def _matriculas(at):
    """Matrículas de las filas visibles de la lista (cada fila las pone en su primera celda)."""
    import re as _re
    return _re.findall(r'class="al-mat">(\d{6})<', " ".join(h.value for h in at.get("html")))


def _app_dialogo():
    """El cuadro de reinicio abierto para un alumno: AppTest no conserva abierto un st.dialog entre ejecuciones."""
    import streamlit as st
    from datetime import datetime
    from test_panel import poblar, TEST1, TEST2
    from modules.panel import cargar_panel
    from views import admin

    if "repo" not in st.session_state:
        st.session_state["repo"] = poblar()
    st.session_state["panel"] = cargar_panel(st.session_state["repo"], (TEST1, TEST2))
    fila = next(f for f in st.session_state["panel"].filas if f.alumno.id == st.session_state["quien"])
    admin._dialogo_reinicio(st.session_state["repo"], (TEST1, TEST2), fila)


def _abrir_reinicio(_at_ignorado, id_alumno):
    at = AppTest.from_function(_app_dialogo, default_timeout=60)
    at.session_state["quien"] = id_alumno
    return at.run()


def _reiniciar(_at_ignorado, id_alumno, que=None):
    """Abre el cuadro de reinicio del alumno, elige la opción que contiene `que` y confirma."""
    at = _abrir_reinicio(None, id_alumno)
    if que:
        radio = at.radio(key=f"que_{id_alumno}")
        radio.set_value(next(i for i, o in enumerate(radio.options) if que in o)).run()
    at.button(key="confirmar_reinicio").click().run()
    return at


def test_reiniciar_desde_el_test_2_borra_solo_ese_test_y_recarga_el_panel():
    from test_panel import TEST1, TEST2
    at = _reiniciar(None, "a2", "Rehacer el Test 2")
    repo = at.session_state["repo"]
    assert repo.reinicios == [("a2", (TEST2.id,), False)]
    assert ("a2", TEST1.id) in repo.respuestas and ("a2", TEST2.id) not in repo.respuestas
    assert not at.exception and not at.error
    assert "100002" in at.session_state["admin_aviso"] and "reiniciado" in at.session_state["admin_aviso"]
    assert "panel" not in at.session_state or at.session_state["panel"].filas[1].contestadas == (25, 0)  # se recarga el panel


def test_reiniciar_desde_el_test_1_borra_tambien_los_siguientes():
    from test_panel import TEST1, TEST2
    at = _reiniciar(None, "a1", "Rehacer el Test 1")
    assert at.session_state["repo"].reinicios == [("a1", (TEST1.id, TEST2.id), False)]


def test_borrar_el_registro_elimina_al_alumno():
    at = _reiniciar(None, "a3", "Quitar su registro")
    assert "100003" not in at.session_state["repo"].alumnos
    assert "quitado" in at.session_state["admin_aviso"]


def test_el_boton_de_reinicio_esta_en_la_fila_de_cada_alumno_registrado():
    at = _entrar(_nuevo())
    assert [b.key for b in at.button if b.key and b.key.startswith("rei_")] == ["rei_a1", "rei_a2", "rei_a3", "rei_a4"]


def test_los_reportes_se_descargan_desde_la_fila_solo_de_quien_termino():
    at = _entrar(_nuevo())
    ids = [b.proto.id for b in at.get("download_button")]
    assert any(i.endswith("-pdf_a1") for i in ids) and any(i.endswith("-xlsx_a1") for i in ids)  # Ana terminó todo
    assert not any(i.endswith(("-pdf_a2", "-pdf_a3", "-pdf_a4")) for i in ids)
    assert at.button(key="sin_reporte_a2").disabled and "sin_reporte_a1" not in [b.key for b in at.button]


def test_el_cuadro_de_reinicio_dice_cuantas_respuestas_se_borran_y_cancelar_no_borra_nada():
    at = _abrir_reinicio(None, "a2")  # Beto: 25 en el test 1 y 10 en el 2
    assert at.radio(key="que_a2").options == ["Rehacer el Test 1 y el Test 2", "Rehacer el Test 2", "Quitar su registro y sus datos"]
    assert at.radio(key="que_a2").index == 1  # lo menos destructivo
    assert at.button(key="confirmar_reinicio").label == "Borrar 10 respuestas"
    at.radio(key="que_a2").set_value(0).run()
    assert at.button(key="confirmar_reinicio").label == "Borrar 35 respuestas"
    at.button(key="cancelar_a2").click().run()
    assert at.session_state["repo"].reinicios == []


def test_a_quien_no_ha_contestado_nada_solo_se_le_ofrece_quitar_el_registro():
    at = _abrir_reinicio(None, "a3")  # Carla acaba de registrarse
    assert at.radio(key="que_a3").options == ["Quitar su registro y sus datos"]
    assert at.button(key="confirmar_reinicio").label == "Quitar registro"


def _app_con_lista():
    import streamlit as st
    from fakes import FakeRepo
    from test_panel import poblar, TEST1, TEST2
    from views import admin

    if "repo" not in st.session_state:
        repo = poblar()
        repo.autorizadas = {"100001": "PEREZ LOPEZ ANA", "100002": "PEREZ LOPEZ BETO", "200001": "ZAPATA RUIZ ZOE"}
        st.session_state["repo"] = repo
    admin.render(st.session_state["repo"], (TEST1, TEST2), "una-contraseña-larga-y-unica", "203.0.113.9", None)


def test_la_lista_muestra_a_quien_no_se_ha_registrado_y_a_los_registros_fuera_de_la_lista():
    at = AppTest.from_function(_app_con_lista, default_timeout=60).run()
    _entrar(at)
    assert _matriculas(at) == ["100001", "100002", "200001", "100003", "100004"]
    html = " ".join(h.value for h in at.get("html"))
    assert "Zapata Ruiz Zoe" in html and "Sin registrar" in html and "Fuera de la lista" in html
    assert "rei_a1" in [b.key for b in at.button] and not [b.key for b in at.button if b.key == "rei_200001"]  # sin registro, nada que reiniciar


def _app_muchos():
    import streamlit as st
    from fakes import FakeRepo
    from test_panel import TEST1, TEST2
    from views import admin

    if "repo" not in st.session_state:
        st.session_state["repo"] = FakeRepo(autorizadas={f"{100000 + i}": f"APELLIDO{i:03d} X NOMBRE" for i in range(45)})
    admin.render(st.session_state["repo"], (TEST1, TEST2), "una-contraseña-larga-y-unica", "203.0.113.9", None)


def test_la_lista_se_pagina_y_se_puede_buscar():
    at = AppTest.from_function(_app_muchos, default_timeout=60).run()
    _entrar(at)
    assert len(_matriculas(at)) == 20 and _matriculas(at)[0] == "100000"
    pagina = next(n for n in at.number_input if n.label.startswith("Página"))
    pagina.set_value(3).run()
    assert _matriculas(at) == [f"{100000 + i}" for i in range(40, 45)]
    next(t for t in at.text_input if t.label == "Buscar").input("apellido007").run()
    assert _matriculas(at) == ["100007"]
