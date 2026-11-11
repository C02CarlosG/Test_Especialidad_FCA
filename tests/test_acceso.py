from datetime import datetime, timedelta, timezone

import pytest

from fakes import FakeRepo, alumno
from modules import security as sec
from modules.acceso import (AccesoBloqueado, AccesoError, DatosAcceso, DatosInvalidos,
                            MatriculaNoAutorizada, MatriculaNoDisponible, buscar_autorizado,
                            iniciar_acceso, separar_nombre)

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
IP = "203.0.113.9"


def datos(**kw):
    base = dict(apellido_paterno="Pérez", apellido_materno="López", nombres="Ana",
                matricula="123456", edad=20, tutor="Mtro. Ruiz", acepto_privacidad=True,
                semestre=5)
    return DatosAcceso(**{**base, **kw})


def repo(*alumnos):
    r = FakeRepo(alumnos)
    r.reloj = lambda: AHORA
    return r


def test_alumno_nuevo_queda_registrado():
    r = repo()
    res = iniciar_acceso(r, datos(), IP, AHORA)
    assert not res.reanudado
    a = r.alumnos["123456"]
    assert a.nombre_completo == "Ana Pérez López" and a.edad == 20 and a.tutor == "Mtro. Ruiz"


def test_matricula_en_la_lista_entra_aunque_venga_con_espacios():
    r = FakeRepo(autorizadas={"654321": "PEREZ LOPEZ ANA"})
    assert iniciar_acceso(r, datos(matricula=" 654321 "), IP, AHORA).alumno.matricula == "654321"


def test_matricula_fuera_de_la_lista_no_entra_ni_se_registra():
    r = FakeRepo(autorizadas={"654321": "PEREZ LOPEZ ANA"})
    with pytest.raises(MatriculaNoAutorizada):
        iniciar_acceso(r, datos(matricula="123456"), IP, AHORA)
    assert not r.alumnos
    assert len(r.intentos) == 2  # cuenta como intento fallido (matrícula y cliente)


def test_probar_matriculas_al_azar_termina_en_bloqueo():
    r = FakeRepo(autorizadas={"654321": "PEREZ LOPEZ ANA"})
    for i in range(sec.MAX_INTENTOS_CLIENTE):
        with pytest.raises(MatriculaNoAutorizada):
            iniciar_acceso(r, datos(matricula=f"{100000 + i}"), IP, AHORA)
    with pytest.raises(AccesoBloqueado):
        iniciar_acceso(r, datos(matricula="654321"), IP, AHORA)


def test_sin_aceptar_privacidad_no_entra():
    r = repo()
    with pytest.raises(AccesoError, match="aviso de privacidad"):
        iniciar_acceso(r, datos(acepto_privacidad=False), IP, AHORA)
    assert not r.alumnos


def test_datos_invalidos():
    with pytest.raises(DatosInvalidos) as exc:
        iniciar_acceso(repo(), datos(edad=17), IP, AHORA)
    assert "edad" in exc.value.errores


def test_matricula_terminada_no_puede_repetir():
    with pytest.raises(MatriculaNoDisponible):
        iniciar_acceso(repo(alumno(estado="terminado")), datos(), IP, AHORA)


def test_matricula_terminada_con_otro_nombre_tampoco():
    r = repo(alumno(estado="terminado"))
    with pytest.raises(MatriculaNoDisponible):
        iniciar_acceso(r, datos(nombres="Beatriz"), IP, AHORA)
    assert not r.intentos  # no es un intento de intrusión sobre un test en curso


def test_matricula_en_curso_reanuda_con_mismo_nombre():
    r = repo()
    iniciar_acceso(r, datos(), IP, AHORA)
    res = iniciar_acceso(r, datos(nombres=" ANA ", apellido_paterno="PÉREZ"), IP, AHORA)
    assert res.reanudado and len(r.alumnos) == 1


def test_al_reanudar_se_actualizan_edad_tutor_y_semestre():
    r = repo()
    iniciar_acceso(r, datos(), IP, AHORA)
    res = iniciar_acceso(r, datos(edad=21, tutor="Mtra. Gómez", semestre=6), IP, AHORA)
    assert res.reanudado
    a = r.alumnos["123456"]
    assert (a.edad, a.tutor, a.semestre) == (21, "Mtra. Gómez", 6)
    assert (res.alumno.edad, res.alumno.tutor, res.alumno.semestre) == (21, "Mtra. Gómez", 6)


def test_al_reanudar_con_los_mismos_datos_no_se_escribe_nada():
    r = repo()
    iniciar_acceso(r, datos(), IP, AHORA)
    llamadas = []
    r.actualizar_datos = lambda *a: llamadas.append(a)
    assert iniciar_acceso(r, datos(), IP, AHORA).reanudado
    assert llamadas == []


def test_reanudar_con_otro_nombre_no_cambia_los_datos():
    r = repo()
    iniciar_acceso(r, datos(), IP, AHORA)
    with pytest.raises(MatriculaNoDisponible):
        iniciar_acceso(r, datos(nombres="Beatriz", edad=30), IP, AHORA)
    assert r.alumnos["123456"].edad == 20


def test_matricula_en_curso_con_otro_nombre_se_rechaza_y_cuenta_como_intento():
    r = repo()
    iniciar_acceso(r, datos(), IP, AHORA)
    with pytest.raises(MatriculaNoDisponible):
        iniciar_acceso(r, datos(nombres="Beatriz"), IP, AHORA)
    assert len(r.intentos) == 2  # uno por matrícula y otro por cliente


def test_carrera_entre_dos_envios_simultaneos():
    r = repo()
    r.carrera = True
    with pytest.raises(MatriculaNoDisponible):
        iniciar_acceso(r, datos(), IP, AHORA)


def test_bloqueo_por_matricula_aunque_luego_use_el_nombre_correcto():
    r = repo(alumno())
    for _ in range(sec.MAX_INTENTOS_MATRICULA):
        with pytest.raises(MatriculaNoDisponible):
            iniciar_acceso(r, datos(nombres="Intruso"), IP, AHORA)
    with pytest.raises(AccesoBloqueado):
        iniciar_acceso(r, datos(), IP, AHORA)


def test_el_bloqueo_expira_con_la_ventana():
    r = repo(alumno())
    for _ in range(sec.MAX_INTENTOS_MATRICULA):
        with pytest.raises(MatriculaNoDisponible):
            iniciar_acceso(r, datos(nombres="Intruso"), IP, AHORA)
    despues = AHORA + timedelta(minutes=sec.VENTANA_INTENTOS_MIN + 1)
    assert iniciar_acceso(r, datos(), IP, despues).reanudado


def test_un_salon_con_la_misma_ip_no_se_bloquea_entre_si():
    r = repo(*[alumno(f"{100000 + i}") for i in range(30)])
    for i in range(30):  # 30 alumnos, cada uno con un error de dedo en su nombre
        with pytest.raises(MatriculaNoDisponible):
            iniciar_acceso(r, datos(matricula=f"{100000 + i}", nombres="Anna"), IP, AHORA)
    assert iniciar_acceso(r, datos(matricula="999999"), IP, AHORA).alumno


def test_ip_que_prueba_muchas_matriculas_se_bloquea():
    r = repo(*[alumno(f"{100000 + i}") for i in range(sec.MAX_INTENTOS_CLIENTE)])
    for i in range(sec.MAX_INTENTOS_CLIENTE):
        with pytest.raises(MatriculaNoDisponible):
            iniciar_acceso(r, datos(matricula=f"{100000 + i}", nombres="Intruso"), IP, AHORA)
    with pytest.raises(AccesoBloqueado):
        iniciar_acceso(r, datos(matricula="999999"), IP, AHORA)
    assert iniciar_acceso(r, datos(matricula="999999"), "198.51.100.7", AHORA).alumno  # otra IP


@pytest.mark.parametrize("nombre, esperado", [
    ("AGUILAR VELASCO ALANN JOSUE", ("Aguilar", "Velasco", "Alann Josue")),
    ("DE LA VEGA CRUZ MARÍA FERNANDA", ("De La Vega", "Cruz", "María Fernanda")),
    ("HERNANDEZ PORRAS TADEO DE JESUS", ("Hernandez", "Porras", "Tadeo De Jesus")),
    ("VALENCIA-VELASQUEZ INGRID MARITZA", ("Valencia-Velasquez", "Ingrid", "Maritza")),
    ("ALONSO AGATON XIMENA", ("Alonso", "Agaton", "Ximena")),
    ("PEÑA RUIZ", ("Peña", "", "Ruiz")),
    ("PEÑA", ("Peña", "", "")),
])
def test_separar_nombre(nombre, esperado):
    assert separar_nombre(nombre) == esperado


def test_buscar_autorizado_devuelve_el_nombre_y_no_cuenta_intento():
    r = FakeRepo(autorizadas={"654321": "PEREZ LOPEZ ANA"})
    assert buscar_autorizado(r, " 654321 ", IP, AHORA) == "PEREZ LOPEZ ANA"
    assert not r.intentos


def test_buscar_autorizado_ignora_lo_incompleto_sin_consultar_ni_contar():
    r = FakeRepo(autorizadas={"654321": "X"})
    assert buscar_autorizado(r, "65A43", IP, AHORA) is None and not r.intentos  # no es numérica: ni se consulta


def test_buscar_matriculas_ajenas_cuenta_intentos_y_termina_bloqueando():
    r = FakeRepo(autorizadas={"654321": "X"})
    for i in range(sec.MAX_INTENTOS_MATRICULA):
        assert buscar_autorizado(r, "111111", IP, AHORA) is None
    with pytest.raises(AccesoBloqueado):
        buscar_autorizado(r, "111111", IP, AHORA)


def test_matricula_de_5_digitos_de_la_lista_entra_y_se_autocompleta():
    r = FakeRepo(autorizadas={"38974": "BAUTISTA CABAÑAS SALVADOR"})
    assert buscar_autorizado(r, "38974", IP, AHORA) == "BAUTISTA CABAÑAS SALVADOR"
    assert iniciar_acceso(r, datos(matricula="38974"), IP, AHORA).alumno.matricula == "38974"
