from datetime import datetime, timezone

import pytest

from fakes import FakeRepo, alumno, crear_test
from modules.avance import (BloqueIncompleto, RespuestaInvalida, CambioDeTest, calcular_posicion,
                            guardar_bloque)

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def setup(*tests):
    repo = FakeRepo([alumno()])
    return repo, repo.alumnos["123456"], tests


def contestar(test, bloque, valor=3):
    return {p.id: valor for p in test.preguntas_de_bloque(bloque)}


def test_alumno_nuevo_empieza_en_el_primer_bloque_del_primer_test():
    t1, t2 = crear_test("t1", 25), crear_test("t2", 12)
    repo, a, tests = setup(t1, t2)
    pos = calcular_posicion(repo, a, tests, AHORA)
    assert (pos.numero_test, pos.total_tests, pos.bloque, pos.numero_bloque, pos.total_bloques) == (1, 2, 1, 1, 3)
    assert pos.contestadas == 0
    assert repo.progreso[(a.id, "t1")].version_test == "v1"


def test_guardar_bloque_avanza_y_conserva_el_avance_al_reanudar():
    t1 = crear_test("t1", 25)
    repo, a, tests = setup(t1)
    guardar_bloque(repo, a, tests, t1, 1, contestar(t1, 1), AHORA)
    # "recarga": se vuelve a calcular la posición solo con lo guardado en la BD
    pos = calcular_posicion(repo, a, tests, AHORA)
    assert (pos.bloque, pos.contestadas) == (2, 10)


def test_los_tests_van_en_orden_y_se_termina_al_final():
    t1, t2 = crear_test("t1", 10), crear_test("t2", 15)
    repo, a, tests = setup(t1, t2)
    guardar_bloque(repo, a, tests, t1, 1, contestar(t1, 1), AHORA)
    assert repo.progreso[(a.id, "t1")].estado == "terminado"
    assert repo.alumnos["123456"].estado == "en_curso"
    pos = calcular_posicion(repo, a, tests, AHORA)
    assert (pos.test.id, pos.numero_test, pos.bloque) == ("t2", 2, 1)
    guardar_bloque(repo, a, tests, t2, 1, contestar(t2, 1), AHORA)
    guardar_bloque(repo, a, tests, t2, 2, contestar(t2, 2), AHORA)
    assert repo.alumnos["123456"].estado == "terminado"
    assert calcular_posicion(repo, a, tests, AHORA) is None


def test_bloque_incompleto_no_se_guarda():
    t1 = crear_test("t1", 10)
    repo, a, tests = setup(t1)
    parcial = contestar(t1, 1)
    parcial.pop("t1-03"); parcial.pop("t1-07")
    with pytest.raises(BloqueIncompleto, match="faltan 2"):
        guardar_bloque(repo, a, tests, t1, 1, parcial, AHORA)
    assert repo.obtener_respuestas(a.id, "t1") == {}


@pytest.mark.parametrize("valor", [0, 6, -1, 99])
def test_valor_fuera_de_la_escala(valor):
    t1 = crear_test("t1", 10)
    repo, a, tests = setup(t1)
    with pytest.raises(RespuestaInvalida):
        guardar_bloque(repo, a, tests, t1, 1, contestar(t1, 1, valor), AHORA)


def test_pregunta_ajena_al_bloque():
    t1 = crear_test("t1", 25)
    repo, a, tests = setup(t1)
    r = contestar(t1, 1)
    r["t1-11"] = 3  # es del bloque 2
    with pytest.raises(RespuestaInvalida):
        guardar_bloque(repo, a, tests, t1, 1, r, AHORA)


def test_se_cuenta_como_respuesta_y_se_guarda_como_null():
    t2 = crear_test("t2", 10, se="Sin experiencia", escala=(0, 4))
    repo, a, tests = setup(t2)
    r = contestar(t2, 1, 2)
    r["t2-01"] = None
    guardar_bloque(repo, a, tests, t2, 1, r, AHORA)
    assert repo.obtener_respuestas(a.id, "t2")["t2-01"] is None
    assert repo.progreso[(a.id, "t2")].estado == "terminado"  # SE no deja el test incompleto
    assert calcular_posicion(repo, a, tests, AHORA) is None


def test_se_se_rechaza_si_el_test_no_la_tiene():
    t1 = crear_test("t1", 10)  # sin_experiencia = None
    repo, a, tests = setup(t1)
    r = contestar(t1, 1)
    r["t1-01"] = None
    with pytest.raises(RespuestaInvalida):
        guardar_bloque(repo, a, tests, t1, 1, r, AHORA)


def test_valor_cero_no_es_se():
    t2 = crear_test("t2", 10, se="Sin experiencia", escala=(0, 4))
    repo, a, tests = setup(t2)
    guardar_bloque(repo, a, tests, t2, 1, contestar(t2, 1, 0), AHORA)
    assert set(repo.obtener_respuestas(a.id, "t2").values()) == {0}


def test_si_el_test_cambia_a_mitad_se_avisa():
    t1 = crear_test("t1", 25)
    repo, a, tests = setup(t1)
    calcular_posicion(repo, a, tests, AHORA)
    nuevo = crear_test("t1", 25, version="v2")
    with pytest.raises(CambioDeTest):
        calcular_posicion(repo, a, (nuevo,), AHORA)


def test_test_contestado_pero_sin_cerrar_se_cierra_al_reanudar():
    t1, t2 = crear_test("t1", 10), crear_test("t2", 10)
    repo, a, tests = setup(t1, t2)
    calcular_posicion(repo, a, tests, AHORA)
    repo.guardar_respuestas(a.id, "t1", contestar(t1, 1))  # se cayó antes de terminar_test
    pos = calcular_posicion(repo, a, tests, AHORA)
    assert pos.test.id == "t2" and repo.progreso[(a.id, "t1")].estado == "terminado"


def test_reguardar_un_bloque_no_duplica():
    t1 = crear_test("t1", 25)
    repo, a, tests = setup(t1)
    guardar_bloque(repo, a, tests, t1, 1, contestar(t1, 1, 2), AHORA)
    guardar_bloque(repo, a, tests, t1, 1, contestar(t1, 1, 4), AHORA)
    assert len(repo.obtener_respuestas(a.id, "t1")) == 10
    assert set(repo.obtener_respuestas(a.id, "t1").values()) == {4}
