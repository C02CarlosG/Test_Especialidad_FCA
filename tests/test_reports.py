import io
import json
import shutil
import subprocess
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import openpyxl
import pytest

from fakes import alumno
from modules.config_loader import load_all_tests
from modules.reports import (excel_individual, grafica_radar, pct, pdf_individual, vista_conjunta)
from modules.scoring import calificar

RAIZ = Path(__file__).resolve().parent.parent
TEST1, TEST2 = load_all_tests(RAIZ / "config" / "tests")
GOLDEN = json.loads((Path(__file__).parent / "golden" / "scoring_golden.json").read_text(encoding="utf-8"))
FECHA = datetime(2026, 10, 15)


def _resp(r):
    return {k: (None if v == "SE" else v) for k, v in r.items()}


@pytest.fixture(scope="module")
def resultados():
    return [calificar(TEST1, GOLDEN["test1"][40]["respuestas"]),
            calificar(TEST2, _resp(GOLDEN["test2"][20]["respuestas"]))]


def test_pct():
    assert pct(Fraction(3, 4)) == "75.0 %" and pct(None) == "Sin datos"


def test_vista_conjunta_comparte_especialidades_y_promedia(resultados):
    vc = vista_conjunta(resultados)
    assert {f.codigo for f in vc.filas} == {"MKT", "CH", "AF", "NI", "EMP"}
    for f in vc.filas:
        assert f.promedio == sum(f.porcentajes, Fraction(0)) / 2
    promedios = [f.promedio for f in vc.filas]
    assert promedios == sorted(promedios, reverse=True)
    assert vc.coinciden == (resultados[0].principal == resultados[1].principal)


def test_vista_conjunta_no_aplica_con_un_solo_test(resultados):
    assert vista_conjunta(resultados[:1]) is None
    assert grafica_radar(resultados[:1], ["x"]) is None


def test_vista_conjunta_promedio_requiere_dos_tests_con_dato():
    sin_dato = {k: ("SE" if k.startswith("M") else v) for k, v in GOLDEN["test2"][20]["respuestas"].items()}
    r = [calificar(TEST1, GOLDEN["test1"][0]["respuestas"]), calificar(TEST2, _resp(sin_dato))]
    mkt = next(f for f in vista_conjunta(r).filas if f.codigo == "MKT")
    assert mkt.porcentajes[1] is None and mkt.promedio is None
    assert vista_conjunta(r).filas[-1].codigo == "MKT"  # sin promedio va al final


def test_radar_es_un_png(resultados):
    png = grafica_radar(resultados, ["Test 1", "Test 2"])
    assert png.startswith(b"\x89PNG") and len(png) > 5000


def test_pdf_es_valido_y_contiene_los_datos(resultados):
    pdf = pdf_individual(alumno(), [TEST1, TEST2], resultados, FECHA)
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF")
    if not shutil.which("pdftotext"):
        pytest.skip("pdftotext no está instalado: solo se validó la estructura del PDF")
    texto = subprocess.run(["pdftotext", "-layout", "-", "-"], input=pdf, capture_output=True, check=True).stdout.decode()
    for esperado in ("123456", "Ana Pérez López", "Big Five (OCEAN)", "Vista conjunta", "15/10/2026",
                     "no son un diagnóstico", "Test 2: Orientación para especialidades"):
        assert esperado in texto
    for e in resultados[0].especialidades:
        assert e.nombre in texto


def test_pdf_con_un_test_sin_principal_no_falla():
    todo_se = {k: None for k in GOLDEN["test2"][0]["respuestas"]}
    r = calificar(TEST2, todo_se)
    assert r.principal is None
    pdf = pdf_individual(alumno(), [TEST2], [r], FECHA)
    assert pdf.startswith(b"%PDF")
    xlsx = excel_individual(alumno(), [TEST2], [r], FECHA)
    ws = openpyxl.load_workbook(io.BytesIO(xlsx))["Test 1"]
    assert any(c.value == "Sin datos" for fila in ws.iter_rows() for c in fila)


def test_excel_hojas_y_valores(resultados):
    wb = openpyxl.load_workbook(io.BytesIO(excel_individual(alumno(), [TEST1, TEST2], resultados, FECHA)))
    assert wb.sheetnames == ["Resumen", "Test 1", "Test 2"]
    resumen = {fila[0].value: fila[1].value for fila in wb["Resumen"].iter_rows(min_row=3, max_row=7)}
    assert resumen["Matrícula"] == "123456" and resumen["Alumno"] == "Ana Pérez López"
    h1 = wb["Test 1"]
    filas = {f[0].value: f for f in h1.iter_rows(min_row=4, max_row=8)}
    r1 = resultados[0]
    for e in r1.especialidades:
        fila = filas[e.nombre]
        assert fila[1].value == e.obtenido and fila[2].value == e.maximo
        assert fila[3].value == pytest.approx(float(e.porcentaje)) and fila[3].number_format == "0.0%"
    assert wb["Test 2"].cell(1, 1).value == TEST2.titulo


def test_excel_no_deja_pasar_formulas_del_alumno(resultados):
    from dataclasses import replace
    malo = replace(alumno(), nombres="=HYPERLINK(\"http://x\")", tutor="@cmd")
    wb = openpyxl.load_workbook(io.BytesIO(excel_individual(malo, [TEST1, TEST2], resultados, FECHA)))
    celdas = [c.value for fila in wb["Resumen"].iter_rows(min_row=3, max_row=7) for c in fila if isinstance(c.value, str)]
    assert not any(v.startswith(("=", "@")) for v in celdas)
    assert any(v.startswith("'=") for v in celdas) and any(v == "'@cmd" for v in celdas)
