"""Genera los 3 tests de EJEMPLO en config/tests/ (3 especialidades, 12 preguntas cada uno).

Todo el contenido es ficticio y está marcado como EJEMPLO. Reemplazar con los tests reales.
"""
from pathlib import Path

import pandas as pd

DESTINO = Path(__file__).resolve().parent.parent / "config" / "tests"

TESTS = [
    ("test_1_ejemplo", "EJEMPLO - Test 1: Intereses"),
    ("test_2_ejemplo", "EJEMPLO - Test 2: Habilidades"),
    ("test_3_ejemplo", "EJEMPLO - Test 3: Valores"),
]


def construir(titulo: str):
    especialidades = pd.DataFrame(
        [(f"ESP_{c}", f"EJEMPLO - Especialidad {c}",
          f"EJEMPLO: descripción ficticia de la especialidad {c}. Reemplazar.",
          f"EJEMPLO: perfil profesional ficticio {c}.") for c in "ABC"],
        columns=["codigo", "nombre", "descripcion", "perfil_profesional"],
    )
    filas = []
    for n in range(1, 13):
        esp = ["ESP_A", "ESP_B", "ESP_C"][(n - 1) % 3]
        invertida = "SI" if n in (4, 11) else "NO"  # dos ítems de ejemplo con puntuación invertida
        filas.append((f"P{n:02d}", 1 if n <= 10 else 2, f"EJEMPLO - Pregunta ficticia {n} ({esp})", esp, invertida))
    preguntas = pd.DataFrame(filas, columns=["id", "bloque", "texto", "especialidad_codigo", "invertida"])
    escala = pd.DataFrame(
        [(1, "Nada de acuerdo"), (2, "Poco de acuerdo"), (3, "Neutral"), (4, "De acuerdo"), (5, "Totalmente de acuerdo")],
        columns=["valor", "etiqueta"],
    )
    info = pd.DataFrame([("titulo", titulo)], columns=["clave", "valor"])
    return {"info": info, "especialidades": especialidades, "preguntas": preguntas, "escala": escala}


DESTINO.mkdir(parents=True, exist_ok=True)
for nombre, titulo in TESTS:
    with pd.ExcelWriter(DESTINO / f"{nombre}.xlsx", engine="openpyxl") as w:
        for hoja, df in construir(titulo).items():
            df.to_excel(w, sheet_name=hoja, index=False)
    print(f"Escrito {DESTINO / (nombre + '.xlsx')}")
