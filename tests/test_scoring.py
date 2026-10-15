from fractions import Fraction

import pytest

from modules.config_loader import (AfinidadDef, Especialidad, Nivel, OpcionEscala, Pregunta,
                                   TestConfig)
from modules.scoring import ErrorDeCalificacion, calificar

NIVELES = (Nivel(Fraction(4, 5), "ALTO"), Nivel(Fraction(1, 2), "MEDIO"), Nivel(Fraction(0), "BAJO"))


def armar(preguntas, escala=(0, 4), se="Sin experiencia", niveles=NIVELES, afinidades=(),
          niveles_afinidad=()):
    """`preguntas`: {codigo_especialidad: [invertida, invertida, ...]} -> ids 'A1', 'A2', 'B1'..."""
    esp = tuple(Especialidad(c, f"Esp {c}", "", "") for c in preguntas)
    pregs = tuple(Pregunta(f"{c}{i}", 1, "t", c, inv)
                  for c, invs in preguntas.items() for i, inv in enumerate(invs, 1))
    esc = tuple(OpcionEscala(v, str(v)) for v in range(escala[0], escala[1] + 1))
    return TestConfig("t", "T", esp, pregs, esc, "v", sin_experiencia=se, niveles_categoria=niveles,
                      afinidades=afinidades, niveles_afinidad=niveles_afinidad)


def resp(**por_esp):
    """resp(A=[4, 3], B=[None]) -> {'A1': 4, 'A2': 3, 'B1': None}"""
    return {f"{c}{i}": v for c, vs in por_esp.items() for i, v in enumerate(vs, 1)}


def test_suma_porcentaje_y_nivel():
    t = armar({"A": [False] * 5, "B": [False] * 5})
    r = calificar(t, resp(A=[4, 4, 4, 4, 0], B=[2, 2, 2, 2, 2]))
    a, b = r.especialidades
    assert (a.obtenido, a.maximo, a.porcentaje, a.nivel) == (16, 20, Fraction(4, 5), "ALTO")  # 0.8 exacto
    assert (b.obtenido, b.maximo, b.nivel) == (10, 20, "MEDIO")  # 0.5 exacto
    assert (r.principal, r.secundaria) == ("A", "B")


def test_niveles_en_el_limite_de_cada_umbral():
    t = armar({"A": [False] * 100})
    for obtenido, esperado in [(79, "MEDIO"), (80, "ALTO"), (49, "BAJO"), (50, "MEDIO")]:
        # 100 preguntas de escala 0-4 -> máximo 400; se reparte `obtenido*4` en respuestas de 4
        r = armar({"A": [False] * 100})
        valores = [4] * obtenido + [0] * (100 - obtenido)
        res = calificar(r, {f"A{i}": v for i, v in enumerate(valores, 1)})
        assert res.especialidades[0].obtenido == obtenido * 4
        assert res.especialidades[0].nivel == esperado


def test_pregunta_invertida_escala_1_a_5():
    t = armar({"A": [True, False]}, escala=(1, 5), se=None)
    r = calificar(t, resp(A=[2, 5]))  # invertida: 1+5-2 = 4
    e = r.especialidades[0]
    assert (e.obtenido, e.maximo) == (9, 10)


def test_pregunta_invertida_escala_0_a_4():
    t = armar({"A": [True]})
    assert calificar(t, resp(A=[1])).especialidades[0].obtenido == 3  # 0+4-1


def test_se_no_suma_ni_cuenta_en_el_maximo():
    t = armar({"A": [False] * 5, "B": [False] * 5})
    r = calificar(t, resp(A=[4, 4, 4, 4, None], B=[1, 1, 1, 1, 1]))
    a = r.especialidades[0]
    assert (a.obtenido, a.maximo, a.respondidas, a.sin_experiencia) == (16, 16, 4, 1)
    assert a.porcentaje == 1 and not a.requiere_exploracion


def test_dos_se_piden_exploracion_y_uno_no():
    t = armar({"A": [False] * 5, "B": [False] * 5})
    r = calificar(t, resp(A=[3, 3, 3, None, None], B=[3, 3, 3, 3, None]))
    assert r.especialidades[0].requiere_exploracion and not r.especialidades[1].requiere_exploracion


def test_todas_se_es_sin_datos_y_sale_del_ranking_no_vale_cero():
    t = armar({"A": [False] * 2, "B": [False] * 2, "C": [False] * 2})
    r = calificar(t, resp(A=[None, None], B=[1, 1], C=[2, 2]))
    a = r.especialidades[0]
    assert a.sin_datos and a.porcentaje is None and a.nivel is None and a.requiere_exploracion
    assert [x.codigo for x in r.ranking] == ["C", "B"]  # A no aparece, ni siquiera al final
    assert (r.principal, r.secundaria) == ("C", "B")


def test_menos_de_dos_con_datos_no_hay_principal_ni_secundaria():
    t = armar({"A": [False] * 2, "B": [False] * 2, "C": [False] * 2})
    r = calificar(t, resp(A=[None, None], B=[None, None], C=[2, 2]))
    assert [x.codigo for x in r.ranking] == ["C"]
    assert (r.principal, r.secundaria, r.empate_tecnico) == (None, None, False)
    r0 = calificar(t, resp(A=[None] * 2, B=[None] * 2, C=[None] * 2))
    assert r0.ranking == () and r0.principal is None


def test_empate_de_porcentaje_gana_el_mayor_puntaje_bruto():
    # A: 4/8 = 50 %; B: 2/4 = 50 % (con un SE). B aparece antes en el Excel pero A tiene más puntos.
    t = armar({"B": [False, False], "A": [False, False]})
    r = calificar(t, resp(B=[2, None], A=[2, 2]))
    assert r.especialidades[0].porcentaje == r.especialidades[1].porcentaje == Fraction(1, 2)
    assert [x.codigo for x in r.ranking] == ["A", "B"]


def test_empate_total_gana_el_orden_del_excel():
    t = armar({"X": [False] * 2, "Y": [False] * 2, "Z": [False] * 2})
    r = calificar(t, resp(X=[2, 2], Y=[2, 2], Z=[2, 2]))
    assert [x.codigo for x in r.ranking] == ["X", "Y", "Z"]
    assert (r.principal, r.secundaria, r.empate_tecnico) == ("X", "Y", True)


def test_empate_en_los_dos_primeros_no_repite_la_misma_especialidad():
    # Defecto de la calculadora: con 1ª y 2ª empatadas devuelve la misma especialidad dos veces.
    t = armar({"X": [False] * 2, "Y": [False] * 2, "Z": [False] * 2})
    r = calificar(t, resp(X=[4, 4], Y=[4, 4], Z=[0, 0]))
    assert (r.principal, r.secundaria) == ("X", "Y")


@pytest.mark.parametrize("a,b,esperado", [(18, 17, True), (18, 16, False), (20, 19, True), (20, 18, False), (17, 17, True)])
def test_empate_tecnico_es_5_puntos_porcentuales_o_menos(a, b, esperado):
    # Cada especialidad: 5 preguntas, máximo 20. 18/20 - 17/20 = 5 pp exactos -> sí es empate técnico.
    def vals(total):
        v, resto = [], total
        for _ in range(5):
            x = min(4, resto)
            v.append(x)
            resto -= x
        return v
    t = armar({"A": [False] * 5, "B": [False] * 5})
    r = calificar(t, resp(A=vals(a), B=vals(b)))
    assert r.empate_tecnico is esperado


def test_afinidad_derivada_suma_componentes_y_rankea_sobre_ellas():
    afs = (AfinidadDef("MKT", "Mercadotecnia", ("A", "C"), ""), AfinidadDef("CH", "Capital Humano", ("B", "C"), ""))
    niv = (Nivel(Fraction(19, 25), "Alta"), Nivel(Fraction(14, 25), "Media"), Nivel(Fraction(0), "Baja"))
    t = armar({"A": [False] * 5, "B": [False] * 5, "C": [False] * 5}, escala=(1, 5), se=None,
              afinidades=afs, niveles_afinidad=niv)
    r = calificar(t, resp(A=[5] * 5, B=[1] * 5, C=[4] * 5))
    mkt, ch = r.afinidades
    assert (mkt.obtenido, mkt.maximo, mkt.porcentaje, mkt.nivel) == (45, 50, Fraction(9, 10), "Alta")
    assert (ch.obtenido, ch.maximo, ch.nivel) == (25, 50, "Baja")
    assert (r.principal, r.secundaria) == ("MKT", "CH")
    assert [e.codigo for e in r.especialidades] == ["A", "B", "C"]  # las categorías siguen disponibles


def test_afinidad_con_componente_sin_datos_usa_los_que_si_tienen():
    afs = (AfinidadDef("X", "X", ("A", "B"), ""), AfinidadDef("Y", "Y", ("B",), ""), AfinidadDef("Z", "Z", ("C",), ""))
    t = armar({"A": [False] * 2, "B": [False] * 2, "C": [False] * 2}, afinidades=afs)
    r = calificar(t, resp(A=[None, None], B=[2, 2], C=[None, None]))
    x, y, z = r.afinidades
    assert x.porcentaje == Fraction(1, 2) and z.sin_datos
    assert [a.codigo for a in r.ranking] == ["X", "Y"]  # empate 50 %/4 pts: orden del Excel


@pytest.mark.parametrize("respuestas,mensaje", [
    ({"A1": 1}, "Faltan 1"),
    ({"A1": 1, "A2": 1, "ZZ": 1}, "no existen"),
    ({"A1": 5, "A2": 1}, "fuera de la escala"),
    ({"A1": -1, "A2": 1}, "fuera de la escala"),
    ({"A1": True, "A2": 1}, "fuera de la escala"),
    ({"A1": "3", "A2": 1}, "fuera de la escala"),
])
def test_respuestas_invalidas(respuestas, mensaje):
    t = armar({"A": [False, False]})
    with pytest.raises(ErrorDeCalificacion, match=mensaje):
        calificar(t, respuestas)


def test_se_en_un_test_que_no_la_tiene():
    t = armar({"A": [False, False]}, se=None)
    with pytest.raises(ErrorDeCalificacion, match="sin experiencia"):
        calificar(t, resp(A=[1, None]))


def test_a_json_es_serializable_y_conserva_none():
    import json
    t = armar({"A": [False] * 2, "B": [False] * 2})
    r = calificar(t, resp(A=[None, None], B=[1, 3]))
    puntajes, afinidad = r.a_json()
    json.dumps([puntajes, afinidad])
    assert puntajes["A"]["porcentaje"] is None and puntajes["A"]["nivel"] is None
    assert puntajes["B"] == {"obtenido": 4, "maximo": 8, "porcentaje": 0.5, "nivel": "MEDIO",
                             "respondidas": 2, "sin_experiencia": 0, "requiere_exploracion": False}
    assert set(afinidad) == {"A", "B"}


def test_no_modifica_las_respuestas_recibidas():
    t = armar({"A": [True, False]})
    entrada = resp(A=[1, 2])
    copia = dict(entrada)
    calificar(t, entrada)
    assert entrada == copia
