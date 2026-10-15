"""Entrada de la app. Fase 1: verifica configuración y conexión.

Las vistas de alumno y admin se conectan en las Fases 2, 3 y 5.
"""
from pathlib import Path

import streamlit as st

from modules.config_loader import ConfigError, load_all_tests
from modules.db import DBConfigError, crear_cliente, verificar_conexion

RAIZ = Path(__file__).parent

st.set_page_config(page_title="Test de especialización", page_icon="🎓", layout="centered")
st.title("Test de especialización")

try:
    tests = load_all_tests(RAIZ / "config" / "tests")
    st.success(f"{len(tests)} tests cargados (se contestan en este orden):")
    for i, t in enumerate(tests, start=1):
        st.write(f"{i}. **{t.titulo}**: {len(t.especialidades)} especialidades, "
                 f"{len(t.preguntas)} preguntas, escala {t.valor_min}-{t.valor_max}.")
except ConfigError as exc:
    st.error("Los archivos de config/tests no son válidos:")
    for e in exc.errores:
        st.write(f"- {e}")

try:
    verificar_conexion(crear_cliente(st.secrets))
    st.success("Conexión con Supabase correcta.")
except (DBConfigError, FileNotFoundError) as exc:
    st.warning(f"Supabase sin configurar: {exc}")
except Exception as exc:  # red, esquema sin crear, clave inválida
    st.error(f"No se pudo consultar Supabase: {type(exc).__name__}")
