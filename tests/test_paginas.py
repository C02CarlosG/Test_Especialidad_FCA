import pytest
from streamlit.testing.v1 import AppTest


def _admin_roto():
    import streamlit as st
    from views import paginas

    def cargar():
        raise RuntimeError("/home/servidor/secreto/config/tests: Falta la hoja 'preguntas'")

    paginas.pagina_admin(cargar, lambda *a, **k: None, "203.0.113.9")


def _admin_bien():
    from test_panel import poblar, TEST1, TEST2
    from views import paginas
    paginas.pagina_admin(lambda: ((TEST1, TEST2), poblar()), lambda s, c, d=None: "una-contraseña-larga-y-unica" if (s, c) == ("admin", "password") else d, "203.0.113.9")


def _alumno_roto():
    from views import paginas

    def cargar():
        raise RuntimeError("detalle interno")

    paginas.pagina_alumno(cargar, "aviso", lambda *a, **k: None, "203.0.113.9")


def test_admin_con_configuracion_rota_no_filtra_detalles_antes_del_login():
    at = AppTest.from_function(_admin_roto, default_timeout=30).run()
    assert not at.exception and not at.text_input
    assert at.error[0].value == ("El panel no está disponible por un problema de configuración. "
                                 "Revisa los registros de la app.")
    texto = " ".join([e.value for e in at.error] + [m.value for m in at.markdown] + [t.value for t in at.title])
    assert "/home" not in texto and "hoja" not in texto and "secreto" not in texto


def test_alumno_con_configuracion_rota_tampoco_ve_detalles():
    at = AppTest.from_function(_alumno_roto, default_timeout=30).run()
    assert "detalle interno" not in " ".join(e.value for e in at.error)
    assert "no está disponible" in at.error[0].value


def test_admin_con_configuracion_buena_pide_la_contraseña():
    at = AppTest.from_function(_admin_bien, default_timeout=60).run()
    assert not at.exception and len(at.text_input) == 1 and not at.error
