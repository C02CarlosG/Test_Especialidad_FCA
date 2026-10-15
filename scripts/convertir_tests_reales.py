"""Convierte las calculadoras de Excel de docs/referencia/ al formato del cargador
(config/tests/*.xlsx: hojas especialidades, preguntas, escala, info).

Uso:  python scripts/convertir_tests_reales.py

Solo copia texto de las calculadoras (reactivos, escalas, descripciones); no inventa contenido.
Lo que el cargador no representa (combinaciones OCEAN -> especialidad del test 1, opción
scoring de "SE" del test 2, textos por nivel) se queda en las calculadoras para la Fase 4.
"""
from math import ceil
from pathlib import Path

import openpyxl
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
REF = RAIZ / "docs" / "referencia"
DESTINO = RAIZ / "config" / "tests"
POR_BLOQUE = 10
# Códigos de las especialidades de la carrera; los comparten los dos tests (sirven para compararlos).
CODIGOS_ESPECIALIDAD = {"Mercadotecnia": "MKT", "Capital Humano": "CH", "Administración Financiera": "AF",
                        "Negocios Internacionales": "NI", "Emprendimiento": "EMP"}


def escribir(ruta: Path, titulo, instrucciones, especialidades, preguntas, escala,
             niveles, afinidades=None) -> None:
    hojas = {
        "info": pd.DataFrame([("titulo", titulo), ("instrucciones", instrucciones)],
                             columns=["clave", "valor"]),
        "especialidades": pd.DataFrame(especialidades, columns=["codigo", "nombre", "descripcion", "perfil_profesional"]),
        "preguntas": pd.DataFrame(
            [(pid, ceil(n / POR_BLOQUE), txt, esp, "NO") for n, (pid, txt, esp) in enumerate(preguntas, 1)],
            columns=["id", "bloque", "texto", "especialidad_codigo", "invertida"]),
        "escala": pd.DataFrame(escala, columns=["valor", "etiqueta"]),
        "niveles": pd.DataFrame(niveles, columns=["ambito", "minimo", "etiqueta"]),
    }
    if afinidades:
        hojas["afinidad"] = pd.DataFrame(
            afinidades, columns=["codigo", "nombre", "componentes", "descripcion"])
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        for nombre, df in hojas.items():
            df.to_excel(w, sheet_name=nombre, index=False)


def test_1() -> None:
    wb = openpyxl.load_workbook(REF / "1_test_big_five_fca_calculadora.xlsx")
    ws = wb["Test y Respuestas"]
    dims = {  # nombre en la calculadora -> código
        "Apertura a la Experiencia": "APERTURA", "Responsabilidad / Tesón": "RESPONSABILIDAD",
        "Extraversión": "EXTRAVERSION", "Amabilidad / Cordialidad": "AMABILIDAD",
        "Estabilidad Emocional": "ESTABILIDAD",
    }
    preguntas = [(f"BF{int(ws.cell(r, 1).value):02d}", ws.cell(r, 3).value.strip(), dims[ws.cell(r, 2).value])
                 for r in range(9, 34)]
    # Las 5 "especialidades" de este test son las dimensiones OCEAN; su relación con las
    # especialidades de la carrera (p. ej. Mercadotecnia = Apertura + Extraversión) se calcula en la Fase 4.
    esp = [(c, n, "", "") for n, c in dims.items()]
    escala = []
    for parte in ws["A6"].value.split("|"):
        valor, etiqueta = parte.split("=")
        escala.append((int(valor), etiqueta.strip()))
    # Afinidad con cada especialidad de la carrera: hoja "Resultados y Diagnóstico" A14:E18
    # (índice = suma de las dimensiones clave / (25 x número de dimensiones)).
    res = wb["Resultados y Diagnóstico"]
    claves = {"Apertura": "APERTURA", "Responsabilidad": "RESPONSABILIDAD", "Extraversión": "EXTRAVERSION",
              "Amabilidad": "AMABILIDAD", "Estabilidad": "ESTABILIDAD"}
    afinidades = [(CODIGOS_ESPECIALIDAD[res.cell(r, 1).value], res.cell(r, 1).value,
                   "+".join(claves[t.strip().split()[0]] for t in res.cell(r, 2).value.split("+")),
                   res.cell(r, 5).value) for r in range(14, 19)]
    # Umbrales de las fórmulas de la calculadora: D5 (>=18 de 25 Alto, >=14 Medio) y D14 (0.76 / 0.56).
    niveles = [("categoria", 0.72, "Alto"), ("categoria", 0.56, "Medio"), ("categoria", 0, "Área de Desarrollo"),
               ("afinidad", 0.76, "Alta Afinidad"), ("afinidad", 0.56, "Afinidad Media"),
               ("afinidad", 0, "Desarrollo Requerido")]
    # Se omite la frase de la calculadora que habla de la "columna Respuesta" de Excel.
    instrucciones = ws["A5"].value.split(" Selecciona")[0].strip()
    escribir(DESTINO / "1_test_big_five.xlsx", "Test 1: The Big Five", instrucciones, esp, preguntas, escala,
             niveles, afinidades)


def test_2() -> None:
    wb = openpyxl.load_workbook(REF / "2_test_orientacion_especialidades_administracion.xlsx")
    ws, guia = wb["Test_Orientación"], wb["Guía_Tutoría"]
    codigos = CODIGOS_ESPECIALIDAD
    preguntas = [(ws.cell(r, 3).value.strip(), ws.cell(r, 4).value.strip(), codigos[ws.cell(r, 2).value])
                 for r in range(23, 48)]
    esp = []
    for r in range(3, 8):
        nombre = guia.cell(r, 1).value
        perfil = f"DISC: {guia.cell(r, 2).value} Holland: {guia.cell(r, 3).value} HBDI: {guia.cell(r, 4).value}"
        esp.append((codigos[nombre], nombre, guia.cell(r, 5).value, perfil))
    # Escala 0-4 más la fila especial "SE" (sin experiencia: dato faltante, no es 0).
    escala = [(int(ws.cell(r, 1).value), ws.cell(r, 2).value) for r in range(14, 19)]
    escala.append(("SE", ws.cell(19, 2).value))
    # Umbrales de la fórmula E51 de la calculadora (% de dominio).
    niveles = [("categoria", 0.8, "ALTO (Perfil Fuerte)"), ("categoria", 0.5, "MEDIO (En Desarrollo)"),
               ("categoria", 0, "BAJO (Baja Afinidad)")]
    instrucciones = ws["A10"].value.split("\n")[0].strip()
    escribir(DESTINO / "2_test_orientacion_especialidades.xlsx",
             "Test 2: Administration Specialties", instrucciones, esp, preguntas, escala,
             niveles)


if __name__ == "__main__":
    test_1()
    test_2()
    print("Listo:", *sorted(p.name for p in DESTINO.glob("*.xlsx")), sep="\n- ")
