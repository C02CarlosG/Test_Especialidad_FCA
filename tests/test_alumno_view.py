from datetime import datetime

from streamlit.testing.v1 import AppTest


def _app():
    from fakes import FakeRepo, crear_test
    from views import alumno

    # El repo vive en la sesión: AppTest vuelve a ejecutar la función en cada interacción.
    import streamlit as st
    if "repo" not in st.session_state:
        st.session_state["repo"] = FakeRepo()
    tests = (crear_test("t1", 12, titulo="Test Uno"),
             crear_test("t2", 10, titulo="Test Dos", se="Sin experiencia", escala=(0, 4)))
    alumno.render(st.session_state["repo"], tests, "Aviso de prueba", "203.0.113.9")


def _app_sin_resultados():
    import streamlit as st
    from fakes import FakeRepo, crear_test
    from views import alumno

    if "repo" not in st.session_state:
        st.session_state["repo"] = FakeRepo()
    alumno.render(st.session_state["repo"], (crear_test("t1", 10),), "Aviso", "203.0.113.9",
                  mostrar_resultados=False)


def _nuevo():
    return AppTest.from_function(_app, default_timeout=30).run()


def _llenar(at, matricula="123456", edad=20, acepto=True, nombres="Ana María"):
    at.text_input[0].input("Pérez")
    at.text_input[1].input("López")
    at.text_input[2].input(nombres)
    at.text_input[3].input(matricula)
    at.number_input[0].set_value(edad)
    at.text_input[5].input("Mtro. Ruiz")  # text_input[4] es la fecha (deshabilitada)
    if acepto:
        at.checkbox[0].check()
    at.button[0].click().run()
    return at


def _contestar_todo(at, clave="3"):
    """`clave` es el valor interno de la opción ("3", "SE"...), no su texto visible."""
    for r in at.radio:
        r.set_value(clave)
    return at


def test_registro_lleva_al_primer_bloque_del_primer_test():
    at = _llenar(_nuevo())
    assert not at.exception and not at.error
    assert len(at.radio) == 10  # bloque 1 de 12 preguntas = 10 preguntas
    assert at.subheader[0].value == "Test Uno"
    assert [m.value for m in at.markdown if m.value.startswith("**1. ")] == ["**1. p1**"]


def test_no_hay_campo_de_codigo_de_grupo():
    assert not any("ódigo" in t.label for t in _nuevo().text_input)


def test_la_fecha_de_aplicacion_esta_deshabilitada_y_es_de_hoy():
    from views.alumno import ZONA
    fecha = _nuevo().text_input[4]
    assert fecha.disabled and fecha.value == datetime.now(ZONA).strftime("%d/%m/%Y")


def test_sin_aceptar_privacidad_no_registra():
    at = _llenar(_nuevo(), acepto=False)
    assert "aviso de privacidad" in at.error[0].value
    assert not at.radio


def test_menor_de_edad_no_entra():
    at = _llenar(_nuevo(), edad=17)
    assert "mayores de 18" in at.error[0].value
    assert not at.radio


def test_todas_obligatorias_bloque_incompleto_no_avanza():
    at = _llenar(_nuevo())
    at.radio[0].set_value("1")  # solo 1 de 10
    at.button[0].click().run()
    assert "Te faltan 9" in at.error[0].value
    assert len(at.radio) == 10 and "Bloque 1 de 2" in at.get("progress")[0].proto.text


def test_flujo_completo_hasta_la_pantalla_final():
    at = _llenar(_nuevo())
    _contestar_todo(at, "3").button[0].click().run()          # t1 bloque 1
    assert not at.error and len(at.radio) == 2              # t1 bloque 2: 2 preguntas
    assert "Terminar este test" == at.button[0].label
    _contestar_todo(at, "1").button[0].click().run()          # termina t1
    assert at.subheader[0].value == "Test Dos" and len(at.radio) == 10
    assert at.radio[0].options[-1] == "Sin experiencia"      # opción SE al final de la escala
    _contestar_todo(at, "SE").button[0].click().run()          # todo "SE"; termina t2
    assert not at.radio and "Terminaste" in at.success[0].value
    assert not at.exception and not at.error
    assert "Tus resultados" in [h.value for h in at.subheader]
    botones = at.get("download_button")
    assert [b.proto.label for b in botones] == ["Descargar PDF", "Descargar Excel"]


def test_recargar_conserva_el_avance():
    at = _llenar(_nuevo())
    _contestar_todo(at).button[0].click().run()
    repo = at.session_state["repo"]
    # "Recargar" = sesión nueva, misma BD: vuelve a entrar con su matrícula y nombre.
    nueva = AppTest.from_function(_app, default_timeout=30)
    nueva.session_state["repo"] = repo
    _llenar(nueva.run())
    assert not nueva.error
    assert "Bienvenida" not in nueva.success[0].value and "bienvenida de nuevo" in nueva.success[0].value
    assert "Bloque 2 de 2" in nueva.get("progress")[0].proto.text
    assert len(nueva.radio) == 2


def test_si_no_se_muestran_resultados_solo_agradece():
    at = AppTest.from_function(_app_sin_resultados, default_timeout=30).run()
    _llenar(at)
    _contestar_todo(at, "3").button[0].click().run()
    assert "Terminaste" in at.success[0].value
    assert not at.get("download_button") and "Tus resultados" not in [h.value for h in at.subheader]


def test_si_falla_el_excel_no_queda_cache_a_medias_y_reintentar_lo_resuelve(monkeypatch):
    import views.test as vt
    original = vt.excel_individual

    def roto(*a, **k):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(vt, "excel_individual", roto)
    at = _llenar(_nuevo())
    _contestar_todo(at, "3").button[0].click().run()   # t1 bloque 1
    _contestar_todo(at, "3").button[0].click().run()   # t1 bloque 2 (cierra t1)
    _contestar_todo(at, "SE").button[0].click().run()  # t2: último bloque -> pantalla final con fallo
    assert not at.exception                            # antes: KeyError en el siguiente rerun
    assert "no pudimos generar tus resultados" in at.error[0].value
    assert [b.label for b in at.button] == ["Reintentar"] and not at.get("download_button")
    at.run()                                            # otro rerun con el fallo persistente
    assert not at.exception and "no pudimos generar" in at.error[0].value
    monkeypatch.setattr(vt, "excel_individual", original)
    at.button[0].click().run()
    assert not at.exception and not at.error
    assert [b.proto.label for b in at.get("download_button")] == ["Descargar PDF", "Descargar Excel"]


def test_con_resultados_en_sesion_no_se_consulta_la_bd_en_cada_rerun():
    at = _llenar(_nuevo())
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "SE").button[0].click().run()
    assert len(at.get("download_button")) == 2
    repo = at.session_state["repo"]

    def prohibido(*a, **k):
        raise ConnectionError("la BD no debe consultarse")

    repo.obtener_progreso = prohibido
    repo.obtener_respuestas = prohibido
    at.run()
    assert not at.exception and not at.error
    assert len(at.get("download_button")) == 2


def test_los_botones_de_descarga_no_disparan_rerun():
    at = _llenar(_nuevo())
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "SE").button[0].click().run()
    botones = at.get("download_button")
    assert len(botones) == 2 and all(b.proto.ignore_rerun for b in botones)
