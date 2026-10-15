import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fakes import FakeRepo
from modules.acceso import Alumno
from modules.avance import ProgresoTest
from modules.config_loader import load_all_tests
from modules.panel import cargar_panel, sincronizar_resultados

RAIZ = Path(__file__).resolve().parent.parent
TEST1, TEST2 = load_all_tests(RAIZ / "config" / "tests")
GOLDEN = json.loads((Path(__file__).parent / "golden" / "scoring_golden.json").read_text(encoding="utf-8"))
AHORA = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)


def _resp2(i):
    return {k: (None if v == "SE" else v) for k, v in GOLDEN["test2"][i]["respuestas"].items()}


def poblar():
    """a1 terminó todo; a2 terminó el test 1 y va a la mitad del 2; a3 apenas se registró;
    a4 terminó el test 2 con una versión vieja."""
    repo = FakeRepo()
    for n, nombre in enumerate(["Ana", "Beto", "Carla", "Dani"], start=1):
        a = Alumno(f"a{n}", "Pérez", "López", nombre, f"10000{n}", 20, "Mtro. Ruiz",
                   "terminado" if n == 1 else "en_curso", AHORA)
        repo.alumnos[a.matricula] = a
    r1 = GOLDEN["test1"][0]["respuestas"]
    repo.progreso[("a1", TEST1.id)] = ProgresoTest("terminado", TEST1.version)
    repo.progreso[("a1", TEST2.id)] = ProgresoTest("terminado", TEST2.version)
    repo.respuestas[("a1", TEST1.id)] = dict(r1)
    repo.respuestas[("a1", TEST2.id)] = _resp2(0)
    repo.progreso[("a2", TEST1.id)] = ProgresoTest("terminado", TEST1.version)
    repo.progreso[("a2", TEST2.id)] = ProgresoTest("en_curso", TEST2.version)
    repo.respuestas[("a2", TEST1.id)] = dict(GOLDEN["test1"][1]["respuestas"])
    repo.respuestas[("a2", TEST2.id)] = dict(list(_resp2(1).items())[:10])
    repo.progreso[("a4", TEST2.id)] = ProgresoTest("terminado", "version-vieja")
    repo.respuestas[("a4", TEST2.id)] = _resp2(2)
    return repo


def test_carga_a_todos_los_alumnos_juntos_con_su_avance():
    panel = cargar_panel(poblar(), (TEST1, TEST2))
    assert [f.alumno.nombres for f in panel.filas] == ["Ana", "Beto", "Carla", "Dani"]
    estados = {f.alumno.nombres: f.estado_tests for f in panel.filas}
    assert estados["Ana"] == ("terminado", "terminado")
    assert estados["Beto"] == ("terminado", "en_curso")
    assert estados["Carla"] == ("sin_iniciar", "sin_iniciar")
    assert {f.alumno.nombres: f.contestadas for f in panel.filas}["Beto"] == (25, 10)
    assert panel.terminados == 1


def test_resultados_solo_donde_hay_test_terminado_y_version_vigente():
    panel = cargar_panel(poblar(), (TEST1, TEST2))
    por_nombre = {f.alumno.nombres: f for f in panel.filas}
    assert por_nombre["Ana"].completo and all(r is not None for r in por_nombre["Ana"].resultados)
    assert por_nombre["Beto"].resultados[0] is not None and por_nombre["Beto"].resultados[1] is None
    assert not por_nombre["Beto"].completo
    assert por_nombre["Carla"].resultados == (None, None)
    assert por_nombre["Dani"].resultados == (None, None)  # versión vieja: no se califica con la actual
    assert any("100004" in p and "versión anterior" in p for p in panel.problemas)


def test_respuestas_incompletas_de_un_test_terminado_se_reportan_sin_romper_el_panel():
    repo = poblar()
    del repo.respuestas[("a1", TEST1.id)]["BF03"]
    panel = cargar_panel(repo, (TEST1, TEST2))
    ana = panel.filas[0]
    assert ana.resultados[0] is None and ana.resultados[1] is not None
    assert any("100001" in p and "no se pudo calificar" in p for p in panel.problemas)


def test_panel_vacio():
    panel = cargar_panel(FakeRepo(), (TEST1, TEST2))
    assert panel.filas == () and panel.terminados == 0 and panel.problemas == ()


def test_sincronizar_guarda_un_resultado_por_test_terminado_y_calificable():
    repo = poblar()
    panel = cargar_panel(repo, (TEST1, TEST2))
    assert sincronizar_resultados(repo, panel, AHORA) == 3  # Ana x2 + Beto x1
    assert {(a, t) for a, t, _ in repo.resultados_guardados} == {("a1", TEST1.id), ("a1", TEST2.id), ("a2", TEST1.id)}
