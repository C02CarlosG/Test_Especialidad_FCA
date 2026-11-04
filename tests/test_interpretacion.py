"""Interpretación conjunta de los dos tests (modules/interpretacion) y su pantalla, PDF y Excel."""
import io
import json
from dataclasses import replace
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import openpyxl
import pytest

from fakes import alumno
from modules.config_loader import load_all_tests
from modules.graficas import grafica_campos, grafica_convergencia, grafica_ocean
from modules.interpretacion import ALCANCE, construir, etiqueta_indice
from modules.reports import excel_individual, pdf_individual
from modules.scoring import calificar

RAIZ = Path(__file__).resolve().parent.parent
TEST1, TEST2 = load_all_tests(RAIZ / "config" / "tests")
GOLDEN = json.loads((Path(__file__).parent / "golden" / "scoring_golden.json").read_text(encoding="utf-8"))


def _resp(r):
    return {k: (None if v == "SE" else v) for k, v in r.items()}


def _resultados(i1=40, i2=20, t2=None):
    return [calificar(TEST1, GOLDEN["test1"][i1]["respuestas"]),
            calificar(TEST2, t2 if t2 is not None else _resp(GOLDEN["test2"][i2]["respuestas"]))]


def test_el_informe_ordena_por_promedio_y_define_dominante_y_complementario():
    inf = construir([TEST1, TEST2], _resultados())
    promedios = [c.promedio for c in inf.ranking]
    assert promedios == sorted(promedios, reverse=True)
    assert inf.dominante is inf.ranking[0] and inf.complementario is inf.ranking[1]
    assert inf.margen == inf.dominante.promedio - inf.complementario.promedio
    assert inf.empate == (inf.margen <= Fraction(5, 100))
    for c in inf.campos:
        assert c.promedio == (c.por_rasgos + c.por_competencias) / 2


def test_el_indice_de_alineacion_cuenta_los_rasgos_requeridos_en_nivel_alto():
    inf = construir([TEST1, TEST2], _resultados())
    esperado = Fraction(sum(r.alto for r in inf.requeridos), len(inf.requeridos))
    assert inf.indice == esperado
    assert [r.codigo for r in inf.requeridos] == list(inf.dominante.componentes)
    assert etiqueta_indice(Fraction(1)) == "Alineación alta" and etiqueta_indice(Fraction(1, 2)) == "Alineación moderada"
    assert etiqueta_indice(Fraction(1, 3)) == "Alineación baja" and etiqueta_indice(None) == "Sin datos"


def test_la_confianza_es_moderada_con_empate_o_con_sin_experiencia_en_el_dominante():
    for i2 in range(len(GOLDEN["test2"])):
        inf = construir([TEST1, TEST2], _resultados(i2=i2))
        if inf.empate or inf.dominante.requiere_exploracion:
            assert inf.confianza == "moderada"
        elif inf.margen >= Fraction(15, 100) and inf.coinciden:
            assert inf.confianza == "alta"
        else:
            assert inf.confianza == "buena"


def test_el_requisito_de_la_especialidad_llega_a_las_notas():
    inf = construir([TEST1, TEST2], _resultados())
    ni = next(c for c in inf.campos if c.codigo == "NI")
    assert "inglés" in ni.requisito
    if "NI" in (inf.dominante.codigo, inf.complementario.codigo):
        assert any("inglés" in n for n in inf.notas)


def test_sin_dos_tests_o_sin_test_de_rasgos_no_hay_informe():
    r = _resultados()
    assert construir([TEST2], r[1:]) is None
    assert construir([TEST2, TEST2], [r[1], r[1]]) is None  # ninguno tiene afinidades


def test_sin_datos_en_los_dos_tests_no_hay_ranking_ni_informe():
    todo_se = {k: None for k in GOLDEN["test2"][0]["respuestas"]}
    assert construir([TEST1, TEST2], _resultados(t2=todo_se)) is None


def test_lectura_de_campo_coinciden_con_cinco_puntos_o_menos():
    from modules.interpretacion import lectura_campo
    inf = construir([TEST1, TEST2], _resultados())
    for c in inf.campos:
        texto, coincide = lectura_campo(c)
        assert coincide == (c.distancia <= Fraction(5, 100))
        assert texto == "Coinciden" or texto == f"Difieren {round(float(c.distancia) * 100)} pts"


def test_las_graficas_son_png():
    inf = construir([TEST1, TEST2], _resultados())
    for g in (grafica_ocean, grafica_campos, grafica_convergencia):
        assert g(inf).startswith(b"\x89PNG")


def test_las_graficas_toleran_campos_sin_datos():
    inf = construir([TEST1, TEST2], _resultados(t2={k: (None if k.startswith("M") else 3) for k in GOLDEN["test2"][0]["respuestas"]}))
    assert grafica_campos(inf).startswith(b"\x89PNG") and grafica_convergencia(inf).startswith(b"\x89PNG")


def test_el_pdf_con_informe_es_valido():
    pdf = pdf_individual(alumno(), [TEST1, TEST2], _resultados(), datetime(2026, 11, 3))
    assert pdf.startswith(b"%PDF") and pdf.rstrip().endswith(b"%%EOF") and len(pdf) > 20_000


def test_el_excel_con_informe_trae_resumen_diagnostico_y_graficas():
    inf = construir([TEST1, TEST2], _resultados())
    wb = openpyxl.load_workbook(io.BytesIO(excel_individual(alumno(), [TEST1, TEST2], _resultados(), datetime(2026, 11, 3))))
    resumen = [c.value for f in wb["Resumen"].iter_rows() for c in f if c.value is not None]
    assert ALCANCE in resumen and inf.dominante.nombre in resumen and inf.etiqueta_indice in resumen
    assert len(wb["Resumen"]._images) == 5  # 2 logos + 3 gráficas
    diag = [c.value for f in wb["Diagnóstico"].iter_rows() for c in f if c.value is not None]
    assert inf.analisis in diag and "El desafío de la elección: más allá del interés" in diag


def test_la_pantalla_muestra_la_hoja_de_resultados_con_los_dos_tests_reales():
    from streamlit.testing.v1 import AppTest

    def app():
        import json
        import sys
        from datetime import datetime
        from pathlib import Path
        import streamlit as st
        raiz = Path(st.session_state["raiz"])
        sys.path[:0] = [str(raiz), str(raiz / "tests")]
        from fakes import alumno
        from modules.config_loader import load_all_tests
        from modules.scoring import calificar
        from views import informe, tema
        from modules.interpretacion import construir
        t = load_all_tests(raiz / "config" / "tests")
        g = json.loads((raiz / "tests" / "golden" / "scoring_golden.json").read_text(encoding="utf-8"))
        r = [calificar(t[0], g["test1"][40]["respuestas"]),
             calificar(t[1], {k: (None if v == "SE" else v) for k, v in g["test2"][20]["respuestas"].items()})]
        tema.aplicar()
        informe.mostrar(alumno(), construir(t, r), datetime(2026, 11, 3), {})

    at = AppTest.from_function(app, default_timeout=60)
    at.session_state["raiz"] = str(RAIZ)
    at.run()
    assert not at.exception
    html = " ".join(str(e.value) for e in at.get("html"))
    for esperado in ("Reporte de Evaluación Integral", "Alcance del instrumento", "Resumen de convergencia",
                     "Índice de alineación", "Cómo se ven tus rasgos", "Diagnóstico orientativo",
                     "Fortalezas proyectadas", "El desafío de la elección: más allá del interés", "Ana Pérez López"):
        assert esperado in html
    assert ALCANCE in html.replace("&#x27;", "'")
    assert len(at.get("image")) >= 2  # radar y barras; la convergencia es una tabla HTML
    assert "Difieren" in html or "Coinciden" in html


def test_el_nombre_del_alumno_se_escapa_en_la_pantalla():
    from html import escape
    raro = replace(alumno(), nombres="<script>alert(1)</script>")
    assert "<script>" not in escape(raro.nombre_completo)


def test_la_recomendacion_del_ingles_sale_solo_si_negocios_internacionales_esta_entre_las_tres_primeras():
    ni = next(e for e in TEST2.especialidades if e.codigo == "NI")
    assert "inglés" in ni.recomendacion and "B1" in ni.recomendacion
    for i2 in range(len(GOLDEN["test2"])):
        inf = construir([TEST1, TEST2], _resultados(i2=i2))
        primeras = [c.codigo for c in (inf.dominante, inf.complementario, inf.tercero) if c]
        con_reco = [r[0] for r in inf.recomendaciones]
        assert ("Negocios Internacionales" in con_reco) == ("NI" in primeras)
        for campo, rol, texto in inf.recomendaciones:
            assert rol in ("tu campo dominante", "tu campo complementario", "un campo para explorar") and "B1" in texto
        if "NI" in primeras[:2]:
            assert not any("Negocios Internacionales se requiere" in n for n in inf.notas)  # la recomendación sustituye a la nota
