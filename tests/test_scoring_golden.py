"""Compara modules.scoring contra las calculadoras de Excel originales (docs/referencia),
recalculadas con LibreOffice (ver scripts/generar_golden_scoring.py)."""
import json
from pathlib import Path

import pytest

from modules.config_loader import load_all_tests
from modules.scoring import calificar

RAIZ = Path(__file__).resolve().parent.parent
GOLDEN = json.loads((Path(__file__).parent / "golden" / "scoring_golden.json").read_text(encoding="utf-8"))
TEST1, TEST2 = load_all_tests(RAIZ / "config" / "tests")


def _resp(respuestas):
    """En el Excel, "sin experiencia" se escribe SE; en la app se guarda como None."""
    return {k: (None if v == "SE" else v) for k, v in respuestas.items()}


def _estrictamente_decreciente(ranking, n):
    pct = [a.porcentaje for a in ranking[:n]]
    return len(pct) == n and all(x > y for x, y in zip(pct, pct[1:]))


def test_hay_suficientes_casos_golden():
    assert len(GOLDEN["test1"]) >= 100 and len(GOLDEN["test2"]) >= 140
    assert any("SE" in c["respuestas"].values() for c in GOLDEN["test2"])


@pytest.mark.parametrize("caso", GOLDEN["test1"])
def test_test1_igual_que_la_calculadora(caso):
    r = calificar(TEST1, _resp(caso["respuestas"]))
    for e in r.especialidades:
        esp = caso["dimensiones"][e.codigo]
        assert (e.obtenido, e.nivel) == (esp["obtenido"], esp["nivel"])
    for a in r.afinidades:
        esp = caso["afinidades"][a.codigo]
        assert float(a.porcentaje) == pytest.approx(esp["porcentaje"], abs=1e-12)
        assert a.nivel == esp["nivel"]
    top = r.ranking
    if _estrictamente_decreciente(top, 2):
        assert r.principal == caso["principal"]
    else:  # empate arriba: la calculadora toma el primero del Excel; aquí desempata el puntaje bruto
        assert caso["principal"] in {a.codigo for a in top if a.porcentaje == top[0].porcentaje}


@pytest.mark.parametrize("caso", GOLDEN["test2"])
def test_test2_igual_que_la_calculadora(caso):
    r = calificar(TEST2, _resp(caso["respuestas"]))
    for e in r.especialidades:
        esp = caso["especialidades"][e.codigo]
        assert (e.obtenido, e.maximo, e.requiere_exploracion) == (esp["obtenido"], esp["maximo"], esp["requiere_exploracion"])
        if e.maximo:
            assert float(e.porcentaje) == pytest.approx(esp["porcentaje"], abs=1e-12)
            assert e.nivel == esp["nivel"]
        else:  # todas "SE": la calculadora muestra 0 % y la pone al final; aquí es "sin datos" y fuera del ranking
            assert e.sin_datos and e.nivel is None and esp["porcentaje"] == 0
            assert e.codigo not in {a.codigo for a in r.ranking}
    if len(r.ranking) >= 2 and _estrictamente_decreciente(r.ranking, min(3, len(r.ranking))):
        assert (r.principal, r.secundaria) == (caso["principal"], caso["secundaria"])
        assert r.empate_tecnico == caso["empate_tecnico"]
