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


def _llenar(at, matricula="123456", edad=20, acepto=True, nombres="Ana María", semestre=5,
            correo="ana@mail.com", correo2=None):
    # La matrícula (text_input[0]) llena los demás campos al escribirse: primero se corre, luego se corrigen.
    at.text_input[0].input(matricula).run()
    at.text_input[1].input("Pérez")
    at.text_input[2].input("López")
    at.text_input[3].input(nombres)
    at.selectbox[0].set_value(semestre)
    at.number_input[0].set_value(edad)
    at.text_input[4].input("Mtro. Ruiz")  # text_input[5] es la fecha (deshabilitada)
    at.text_input[6].input(correo)
    at.text_input[7].input(correo if correo2 is None else correo2)
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
    preguntas = [h.value for h in at.get("html") if 'class="pregunta' in h.value]
    assert len(preguntas) == 10 and 'class="pregunta primera"' in preguntas[0]
    assert '<span class="num">1</span><p>p1</p>' in preguntas[0]


def test_no_hay_campo_de_codigo_de_grupo():
    assert not any("ódigo" in t.label for t in _nuevo().text_input)


def test_la_fecha_de_aplicacion_esta_deshabilitada_y_es_de_hoy():
    from views.alumno import ZONA
    fecha = _nuevo().text_input[5]
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
    assert [b.proto.label for b in botones] == ["Descargar PDF"]


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


def test_si_falla_el_pdf_no_queda_cache_a_medias_y_reintentar_lo_resuelve(monkeypatch):
    import views.test as vt
    original = vt.pdf_individual

    def roto(*a, **k):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(vt, "pdf_individual", roto)
    at = _llenar(_nuevo())
    _contestar_todo(at, "3").button[0].click().run()   # t1 bloque 1
    _contestar_todo(at, "3").button[0].click().run()   # t1 bloque 2 (cierra t1)
    _contestar_todo(at, "SE").button[0].click().run()  # t2: último bloque -> pantalla final con fallo
    assert not at.exception                            # antes: KeyError en el siguiente rerun
    assert "no pudimos generar tus resultados" in at.error[0].value
    assert [b.label for b in at.button] == ["Reintentar"] and not at.get("download_button")
    at.run()                                            # otro rerun con el fallo persistente
    assert not at.exception and "no pudimos generar" in at.error[0].value
    monkeypatch.setattr(vt, "pdf_individual", original)
    at.button[0].click().run()
    assert not at.exception and not at.error
    assert [b.proto.label for b in at.get("download_button")] == ["Descargar PDF"]


def test_con_resultados_en_sesion_no_se_consulta_la_bd_en_cada_rerun():
    at = _llenar(_nuevo())
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "SE").button[0].click().run()
    assert len(at.get("download_button")) == 1
    repo = at.session_state["repo"]

    def prohibido(*a, **k):
        raise ConnectionError("la BD no debe consultarse")

    repo.obtener_progreso = prohibido
    repo.obtener_respuestas = prohibido
    at.run()
    assert not at.exception and not at.error
    assert len(at.get("download_button")) == 1


def test_los_botones_de_descarga_no_disparan_rerun():
    at = _llenar(_nuevo())
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "SE").button[0].click().run()
    botones = at.get("download_button")
    assert len(botones) == 1 and all(b.proto.ignore_rerun for b in botones)


def test_el_semestre_es_un_desplegable_del_primero_al_octavo():
    at = _nuevo()
    caja = at.selectbox[0]
    assert caja.label == "Semestre *" and caja.value is None
    assert caja.options == ["Primer semestre", "Segundo semestre", "Tercer semestre", "Cuarto semestre",
                            "Quinto semestre", "Sexto semestre", "Séptimo semestre", "Octavo semestre"]


def test_sin_semestre_no_registra():
    at = _nuevo()
    at.text_input[0].input("123456").run()
    at.text_input[1].input("Pérez")
    at.text_input[2].input("López")
    at.text_input[3].input("Ana")
    at.selectbox[0].set_value(None)  # la matrícula de la lista ya había puesto el 5.º
    at.number_input[0].set_value(20)
    at.text_input[4].input("Mtro. Ruiz")
    at.text_input[6].input("ana@mail.com")
    at.text_input[7].input("ana@mail.com")
    at.checkbox[0].check()
    at.button[0].click().run()
    assert "Elige tu semestre" in at.error[0].value and not at.radio


def test_el_semestre_elegido_se_guarda_con_el_alumno():
    at = _llenar(_nuevo(), semestre=8)
    assert at.session_state["alumno"].semestre == 8


def _app_con_lista():
    import streamlit as st
    from fakes import FakeRepo, crear_test
    from views import alumno

    if "repo" not in st.session_state:
        st.session_state["repo"] = FakeRepo(autorizadas={"177195": "AGUILAR VELASCO ALANN JOSUE"})
    alumno.render(st.session_state["repo"], (crear_test("t1", 10),), "Aviso", "203.0.113.9")


def test_al_escribir_la_matricula_se_cargan_los_datos_de_la_lista():
    at = AppTest.from_function(_app_con_lista, default_timeout=30).run()
    at.text_input[0].input("177195").run()
    assert [t.value for t in at.text_input[1:4]] == ["Aguilar", "Velasco", "Alann Josue"]
    assert at.selectbox[0].value == 5
    assert at.success and "Cargamos tus datos" in at.success[0].value


def test_matricula_fuera_de_la_lista_avisa_y_deja_los_campos_vacios():
    at = AppTest.from_function(_app_con_lista, default_timeout=30).run()
    at.text_input[0].input("999999").run()
    assert "no está en la lista" in at.error[0].value
    assert [t.value for t in at.text_input[1:4]] == ["", "", ""]


def test_cambiar_a_una_matricula_ajena_borra_los_datos_cargados():
    at = AppTest.from_function(_app_con_lista, default_timeout=30).run()
    at.text_input[0].input("177195").run()
    at.text_input[0].input("999999").run()
    assert [t.value for t in at.text_input[1:4]] == ["", "", ""]


def test_el_registro_pide_correo_y_confirmacion():
    etiquetas = [t.label for t in _nuevo().text_input]
    assert "Correo electrónico *" in etiquetas and "Confirma tu correo *" in etiquetas


def test_correos_distintos_muestran_error_y_no_registran():
    at = _llenar(_nuevo(), correo="ana@mail.com", correo2="ana@otro.com")
    assert any("Los correos no coinciden." in e.value for e in at.error)
    assert not at.radio and at.session_state["repo"].alumnos == {}


def test_registro_con_correo_guarda_al_alumno_normalizado():
    at = _llenar(_nuevo(), correo=" Ana@Mail.COM ", correo2="ana@mail.com")
    assert not at.exception and not at.error
    assert at.session_state["repo"].alumnos["123456"].correo == "ana@mail.com"


# --- envío del reporte por correo al terminar ---

def _app_correo():
    import streamlit as st
    from fakes import FakeRepo, crear_test
    from modules.envio import ConfigCorreo
    from views import alumno

    if "repo" not in st.session_state:
        st.session_state["repo"] = FakeRepo()
    tests = (crear_test("t1", 12, titulo="Test Uno"),
             crear_test("t2", 10, titulo="Test Dos", se="Sin experiencia", escala=(0, 4)))
    cfg = ConfigCorreo("smtp.test", 465, "r@test.mx", "S3creta!", "r@test.mx") \
        if st.session_state.get("con_config", True) else None
    alumno.render(st.session_state["repo"], tests, "Aviso", "203.0.113.9",
                  st.session_state.get("mostrar", True), cfg)


def _terminar(**estado):
    at = AppTest.from_function(_app_correo, default_timeout=30)
    for k, v in estado.items():
        at.session_state[k] = v
    _llenar(at.run())
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "3").button[0].click().run()
    _contestar_todo(at, "SE").button[0].click().run()
    return at


def _textos(at):
    return [x.value for x in (*at.info, *at.warning, *at.error)]


def test_al_terminar_se_envia_el_reporte_y_se_avisa(smtp):
    at = _terminar()
    assert not at.exception
    assert len(smtp.mensajes) == 1 and smtp.mensajes[0]["To"] == "ana@mail.com"
    assert at.session_state["repo"].alumnos["123456"].reporte_estado == "enviado"
    avisos = " ".join(_textos(at))
    assert "Te enviamos tu reporte a ana@mail.com" in avisos and "spam" in avisos


def test_rerun_no_envia_dos_veces(smtp):
    at = _terminar()
    at.run()
    at.run()
    assert len(smtp.mensajes) == 1


def test_si_el_envio_falla_igual_ve_sus_resultados(smtp):
    smtp.falla = OSError("caído")
    at = _terminar()
    assert not at.exception
    assert [b.proto.label for b in at.get("download_button")] == ["Descargar PDF"]
    assert any("No pudimos enviarte el correo" in t for t in _textos(at))
    repo_alumno = at.session_state["repo"].alumnos["123456"]
    assert repo_alumno.reporte_estado == "error" and "S3creta!" not in repo_alumno.reporte_error
    assert "S3creta!" not in " ".join(_textos(at))


def test_sin_configuracion_de_correo_no_envia_ni_avisa_error(smtp):
    at = _terminar(con_config=False)
    assert not at.exception and smtp.mensajes == []
    assert at.session_state["repo"].alumnos["123456"].reporte_estado == "pendiente"
    assert not any("correo" in t.lower() for t in _textos(at))


def test_si_no_se_muestran_resultados_no_se_envia(smtp):
    at = _terminar(mostrar=False)
    assert not at.exception and smtp.mensajes == []
    assert at.session_state["repo"].alumnos["123456"].reporte_estado == "pendiente"
