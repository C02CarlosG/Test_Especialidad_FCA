"""Genera config/test.xlsx de EJEMPLO (3 especialidades, 12 preguntas ficticias)."""
from pathlib import Path

import pandas as pd

DESTINO = Path(__file__).resolve().parent.parent / "config" / "test.xlsx"

especialidades = pd.DataFrame(
    [
        ("ESP_A", "EJEMPLO - Especialidad A", "EJEMPLO: descripción ficticia de la especialidad A. Reemplazar.", "EJEMPLO: perfil profesional ficticio A."),
        ("ESP_B", "EJEMPLO - Especialidad B", "EJEMPLO: descripción ficticia de la especialidad B. Reemplazar.", "EJEMPLO: perfil profesional ficticio B."),
        ("ESP_C", "EJEMPLO - Especialidad C", "EJEMPLO: descripción ficticia de la especialidad C. Reemplazar.", "EJEMPLO: perfil profesional ficticio C."),
    ],
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

DESTINO.parent.mkdir(exist_ok=True)
with pd.ExcelWriter(DESTINO, engine="openpyxl") as w:
    especialidades.to_excel(w, sheet_name="especialidades", index=False)
    preguntas.to_excel(w, sheet_name="preguntas", index=False)
    escala.to_excel(w, sheet_name="escala", index=False)
print(f"Escrito {DESTINO}")
