"""Que requirements.txt cubra todo lo que el código importa: en Streamlit Cloud solo se instala lo que
está ahí, y una dependencia que en esta máquina ya existe por casualidad rompería el despliegue."""
import ast
import re
import sys
from importlib.metadata import packages_distributions
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOCALES = {"modules", "views", "tests", "app", "fakes"}
TRANSITIVAS = {"postgrest": "supabase"}  # se importa directo, pero la instala supabase


def _requeridas() -> set[str]:
    nombres = set()
    for linea in (RAIZ / "requirements.txt").read_text().splitlines():
        linea = linea.split("#")[0].strip()
        if linea:
            nombres.add(re.split(r"[<>=!~\[; ]", linea)[0].lower().replace("_", "-"))
    return nombres


def _importados() -> set[str]:
    mods = set()
    for archivo in [RAIZ / "app.py", *(RAIZ / "modules").glob("*.py"), *(RAIZ / "views").glob("*.py")]:
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Import):
                mods |= {a.name.split(".")[0] for a in nodo.names}
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
                mods.add(nodo.module.split(".")[0])
    return {m for m in mods if m not in sys.stdlib_module_names and m not in LOCALES}


def test_todo_lo_que_se_importa_esta_en_requirements():
    requeridas = _requeridas()
    distribuciones = packages_distributions()
    faltan = []
    for mod in sorted(_importados()):
        dists = {d.lower().replace("_", "-") for d in distribuciones.get(mod, [mod])}
        if not dists & requeridas and TRANSITIVAS.get(mod) not in requeridas:
            faltan.append(f"{mod} (paquete: {', '.join(sorted(dists))})")
    assert not faltan, "Faltan en requirements.txt: " + "; ".join(faltan)


def test_tzdata_esta_en_requirements():
    assert "tzdata" in _requeridas()  # zoneinfo lo usa implícitamente: ninguna importación lo delata
