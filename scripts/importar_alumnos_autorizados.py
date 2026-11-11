"""Carga la lista de alumnos autorizados (tabla de Markdown) a Supabase.

Uso:  python scripts/importar_alumnos_autorizados.py ["ALUMNOS DE 5o. SEMESTRE Licenciatura.md"] [--reemplazar]

Requiere haber ejecutado sql/04_alumnos_autorizados.sql y tener .streamlit/secrets.toml con [supabase].
Es repetible: actualiza por matrícula. Con --reemplazar borra las matrículas que ya no vienen
en el archivo, salvo los accesos de prueba con estatus PRUEBA (quedan sin acceso, pero los alumnos ya registrados conservan su avance).
Las filas cuya matrícula no sea solo números (hasta 10) no se cargan y se avisan.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "ALUMNOS DE 5o. SEMESTRE Licenciatura.md"
_RE_MAT = re.compile(r"[0-9]{1,10}")


def leer_lista(texto: str) -> tuple[list[dict[str, str]], list[str]]:
    """Devuelve (filas válidas, avisos). Ignora encabezados, separadores y texto fuera de la tabla."""
    filas: dict[str, dict[str, str]] = {}
    avisos: list[str] = []
    for linea in texto.splitlines():
        celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
        if len(celdas) < 6 or not celdas[0].isdigit():
            continue
        _, matricula, nombre, sexo, _fecha, estatus = celdas[:6]
        if not _RE_MAT.fullmatch(matricula):
            avisos.append(f"Matrícula «{matricula}» ({nombre}) no es numérica (hasta 10 dígitos): no se carga.")
            continue
        if matricula in filas:
            avisos.append(f"Matrícula {matricula} repetida ({nombre}): se conserva la última.")
        filas[matricula] = {"matricula": matricula, "nombre": nombre, "sexo": sexo, "estatus": estatus}
    return list(filas.values()), avisos


def main(argv: list[str]) -> int:
    reemplazar = "--reemplazar" in argv
    rutas = [a for a in argv if not a.startswith("--")]
    ruta = Path(rutas[0]) if rutas else ARCHIVO
    filas, avisos = leer_lista(ruta.read_text(encoding="utf-8"))
    for a in avisos:
        print("AVISO:", a)
    if not filas:
        print("No se encontró ninguna fila válida; no se cargó nada.")
        return 1

    from modules.db import crear_cliente  # import tardío: leer_lista no necesita supabase

    secretos = tomllib.loads((RAIZ / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))
    cliente = crear_cliente(secretos)
    for i in range(0, len(filas), 200):
        cliente.table("alumnos_autorizados").upsert(filas[i:i + 200], on_conflict="matricula").execute()
    if reemplazar:
        vigentes = {f["matricula"] for f in filas}
        actuales = {r["matricula"] for r in cliente.table("alumnos_autorizados").select("matricula").neq("estatus", "PRUEBA").execute().data}
        for m in sorted(actuales - vigentes):  # los accesos de PRUEBA se conservan
            cliente.table("alumnos_autorizados").delete().eq("matricula", m).execute()
            print("Quitada:", m)
    print(f"Listo: {len(filas)} matrículas autorizadas.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    raise SystemExit(main(sys.argv[1:]))
