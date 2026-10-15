from streamlit.testing.v1 import AppTest


def _app():
    from types import SimpleNamespace
    from fakes import FakeRepo
    from views import alumno

    repo = FakeRepo()
    tests = [SimpleNamespace(id="t1", titulo="Test Uno"), SimpleNamespace(id="t2", titulo="Test Dos")]
    alumno.render(repo, tests, "Aviso de prueba", "203.0.113.9")


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


def _nuevo():
    return AppTest.from_function(_app, default_timeout=30).run()


def test_flujo_completo_registra_y_lista_los_tests_en_orden():
    at = _llenar(_nuevo())
    assert not at.exception and not at.error
    assert at.success[0].value == "Tu registro quedó listo."
    textos = [m.value for m in at.markdown]
    assert "1. Test Uno" in textos and "2. Test Dos" in textos


def test_no_hay_campo_de_codigo_de_grupo():
    etiquetas = [t.label for t in _nuevo().text_input]
    assert not any("ódigo" in e for e in etiquetas)


def test_la_fecha_de_aplicacion_esta_deshabilitada_y_es_de_hoy():
    from datetime import datetime
    from views.alumno import ZONA
    fecha = _nuevo().text_input[4]
    assert fecha.disabled and fecha.value == datetime.now(ZONA).strftime("%d/%m/%Y")


def test_sin_aceptar_privacidad_no_registra():
    at = _llenar(_nuevo(), acepto=False)
    assert "aviso de privacidad" in at.error[0].value
    assert not at.success


def test_menor_de_edad_no_entra():
    at = _llenar(_nuevo(), edad=17)
    assert "mayores de 18" in at.error[0].value
    assert not at.success
