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
    assert "Test 1 de 2" in at.caption[0].value
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
    assert "Test 2 de 2" in at.caption[0].value and len(at.radio) == 10
    assert at.radio[0].options[-1] == "Sin experiencia"      # opción SE al final de la escala
    _contestar_todo(at, "SE").button[0].click().run()          # todo "SE"; termina t2
    assert not at.radio and "Terminaste" in at.success[0].value


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
