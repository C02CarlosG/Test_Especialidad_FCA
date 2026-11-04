from datetime import datetime, timedelta, timezone

import pytest

from fakes import FakeRepo, alumno
from modules import security as sec
from modules.acceso import (AccesoBloqueado, AccesoError, DatosAcceso, DatosInvalidos,
                            MatriculaNoDisponible, iniciar_acceso)

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
IP = "203.0.113.9"


def datos(**kw):
    base = dict(apellido_paterno="Pérez", apellido_materno="López", nombres="Ana",
                matricula="123456", edad=20, tutor="Mtro. Ruiz", acepto_privacidad=True)
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


def test_cualquier_matricula_valida_entra_sin_codigo_ni_lista():
    assert iniciar_acceso(repo(), datos(matricula=" 654321 "), IP, AHORA).alumno.matricula == "654321"


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
