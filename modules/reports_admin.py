"""Reportes para el docente: Excel concentrado (con respaldo de respuestas) y ZIP de PDFs.

Todo en memoria. Los textos escritos por los alumnos pasan por `_seguro` (sin fórmulas ni
caracteres que Excel rechaza).
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

from modules.panel import FilaAlumno, PanelDatos
from modules.reports import AVISO, _nombre_de, _seguro, pct, pdf_individual
from modules.scoring import ResultadoTest

ZONA = ZoneInfo("America/Mexico_City")
ESTADOS = {"sin_iniciar": "Sin iniciar", "en_curso": "En curso", "terminado": "Terminado"}


def _num(valor) -> float | None:
    return None if valor is None else float(valor)


def _ranura(texto: str) -> str:
    """Texto seguro para un nombre de archivo: ASCII, sin separadores de ruta."""
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", ascii_).strip("_")[:40] or "alumno"


def nombre_pdf(fila: FilaAlumno) -> str:
    a = fila.alumno
    return f"{a.matricula}_{_ranura(a.apellido_paterno)}_{_ranura(a.nombres.split()[0])}.pdf"


def _fecha(valor: datetime | None) -> str:
    return "" if valor is None else valor.astimezone(ZONA).strftime("%d/%m/%Y %H:%M")


def excel_concentrado(panel: PanelDatos, fecha: datetime) -> bytes:
    """Hojas: Resumen, Alumnos, una por test con todos los puntajes y Respuestas (respaldo)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    negrita, cab = Font(bold=True), PatternFill("solid", fgColor="E8EDF8")
    wb = Workbook()

    def encabezado(ws, fila, valores):
        for c, v in enumerate(valores, start=1):
            celda = ws.cell(fila, c, v)
            celda.font, celda.fill = negrita, cab
            celda.alignment = Alignment(wrap_text=True, vertical="center")

    def porcentaje(ws, fila, col, valor):
        c = ws.cell(fila, col, "Sin datos" if valor is None else float(valor))
        if valor is not None:
            c.number_format = "0.0%"

    datos_alumno = lambda a: [_seguro(a.matricula), _seguro(a.apellido_paterno), _seguro(a.apellido_materno),  # noqa: E731
                              _seguro(a.nombres), a.edad, _seguro(a.tutor), _fecha(a.creado_en)]
    cols_alumno = ["Matrícula", "Apellido paterno", "Apellido materno", "Nombre(s)", "Edad", "Tutor", "Registro"]

    # --- Resumen ---
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = "Evaluación Diagnóstica FCA - Concentrado"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = f"Generado: {fecha.strftime('%d/%m/%Y %H:%M')}"
    total, terminados = len(panel.filas), panel.terminados
    filas = [("Alumnos registrados", total), ("Terminaron todos los tests", terminados),
             ("En curso", total - terminados)]
    for i, (k, v) in enumerate(filas, start=4):
        ws.cell(i, 1, k).font = negrita
        ws.cell(i, 2, v)
    fila = 8
    for n, t in enumerate(panel.tests):
        ws.cell(fila, 1, t.titulo).font = negrita
        fila += 1
        encabezado(ws, fila, ["Especialidad 1ª opción", "Alumnos"])
        conteo: dict[str, int] = {}
        for f in panel.filas:
            r = f.resultados[n]
            if r is not None and r.principal is not None:
                nombre = _nombre_de(r, r.principal)
                conteo[nombre] = conteo.get(nombre, 0) + 1
        for nombre, cuantos in sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0])):
            fila += 1
            ws.cell(fila, 1, nombre)
            ws.cell(fila, 2, cuantos)
        fila += 2
    for aviso in panel.problemas:
        ws.cell(fila, 1, "Aviso: " + _seguro(aviso))
        fila += 1
    ws.cell(fila + 1, 1, AVISO).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=fila + 1, start_column=1, end_row=fila + 1, end_column=4)
    ws.row_dimensions[fila + 1].height = 48

    # --- Alumnos (avance + 1ª/2ª opción) ---
    ws = wb.create_sheet("Alumnos")
    cab_tests = []
    for t in panel.tests:
        cab_tests += [f"{t.titulo} - estado", f"{t.titulo} - respondidas", f"{t.titulo} - 1ª opción", f"{t.titulo} - 2ª opción"]
    encabezado(ws, 1, cols_alumno + ["Estado general"] + cab_tests)
    for i, f in enumerate(panel.filas, start=2):
        valores = datos_alumno(f.alumno) + [ESTADOS.get(f.alumno.estado, f.alumno.estado)]
        for n, t in enumerate(panel.tests):
            r = f.resultados[n]
            valores += [ESTADOS[f.estado_tests[n]], f"{f.contestadas[n]} de {len(t.preguntas)}",
                        _nombre_de(r, r.principal) if r else "", _nombre_de(r, r.secundaria) if r else ""]
        for c, v in enumerate(valores, start=1):
            ws.cell(i, c, v)
    ws.freeze_panes = "B2"

    # --- una hoja por test ---
    for n, t in enumerate(panel.tests):
        ws = wb.create_sheet(f"Test {n + 1}")
        areas = [e.nombre for e in t.especialidades]
        afins = [a.nombre for a in t.afinidades]
        cab_h = cols_alumno + [f"{x} (%)" for x in areas] + [f"{x} - nivel" for x in areas] + \
                [f"Exploración: {x}" for x in areas] + [f"Afinidad {x} (%)" for x in afins] + \
                [f"Afinidad {x} - nivel" for x in afins] + ["1ª opción", "2ª opción", "Empate técnico"]
        encabezado(ws, 1, cab_h)
        i = 1
        for f in panel.filas:
            r: ResultadoTest | None = f.resultados[n]
            if r is None:
                continue
            i += 1
            for c, v in enumerate(datos_alumno(f.alumno), start=1):
                ws.cell(i, c, v)
            c = len(cols_alumno)
            for e in r.especialidades:
                c += 1
                porcentaje(ws, i, c, e.porcentaje)
            for e in r.especialidades:
                c += 1
                ws.cell(i, c, e.nivel or "—")
            for e in r.especialidades:
                c += 1
                ws.cell(i, c, "Sí" if e.requiere_exploracion else "No")
            if t.afinidades:
                for a in r.afinidades:
                    c += 1
                    porcentaje(ws, i, c, a.porcentaje)
                for a in r.afinidades:
                    c += 1
                    ws.cell(i, c, a.nivel or "—")
            ws.cell(i, c + 1, _nombre_de(r, r.principal))
            ws.cell(i, c + 2, _nombre_de(r, r.secundaria))
            ws.cell(i, c + 3, "Sí" if r.empate_tecnico else "No")
        ws.freeze_panes = "E2"

    # --- Respuestas (respaldo en formato largo; trae TODO lo guardado, aunque el test ya no exista) ---
    ws = wb.create_sheet("Respuestas")
    encabezado(ws, 1, ["Matrícula", "Test", "Pregunta", "Respuesta"])
    por_id = {f.alumno.id: f.alumno for f in panel.filas}
    en_config = [t.id for t in panel.tests]
    i = 1
    for test_id in en_config + sorted(set(panel.respuestas) - set(en_config)):
        test = next((t for t in panel.tests if t.id == test_id), None)
        orden = [p.id for p in test.preguntas] if test else []
        for alumno_id, resp in panel.respuestas[test_id].items():
            if alumno_id not in por_id:
                continue
            for pid in orden + sorted(set(resp) - set(orden)):
                if pid in resp:
                    i += 1
                    ws.cell(i, 1, _seguro(por_id[alumno_id].matricula))
                    ws.cell(i, 2, _seguro(test_id))
                    ws.cell(i, 3, _seguro(pid))
                    ws.cell(i, 4, "SE" if resp[pid] is None else resp[pid])
    ws.freeze_panes = "A2"

    for hoja in wb.worksheets:
        for col in range(1, hoja.max_column + 1):
            hoja.column_dimensions[get_column_letter(col)].width = 30 if col == 1 and hoja.title in ("Resumen",) else 18
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def zip_pdfs(panel: PanelDatos, fecha: datetime) -> tuple[bytes, int, int]:
    """ZIP con el PDF de cada alumno que terminó todos los tests, y un LEEME con los omitidos.
    Devuelve (bytes, pdfs incluidos, omitidos)."""
    incluidos, omitidos = 0, []
    nombres_usados: set[str] = set()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in panel.filas:
            if not f.completo:
                omitidos.append(f.alumno)
                continue
            nombre = nombre_pdf(f)
            if nombre in nombres_usados:  # no debería pasar: la matrícula es única
                nombre = nombre.replace(".pdf", f"_{incluidos}.pdf")
            nombres_usados.add(nombre)
            z.writestr(nombre, pdf_individual(f.alumno, panel.tests, list(f.resultados), fecha))
            incluidos += 1
        leeme = [f"Evaluación Diagnóstica FCA - PDFs generados el {fecha.strftime('%d/%m/%Y %H:%M')}",
                 f"Incluidos: {incluidos}. Omitidos por no haber terminado todos los tests: {len(omitidos)}."]
        leeme += [f"- {a.matricula}" for a in omitidos]
        z.writestr("LEEME.txt", "\n".join(leeme) + "\n")
    return buf.getvalue(), incluidos, len(omitidos)
