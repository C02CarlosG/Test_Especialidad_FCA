"""Entrada de la app. Fase 1: verifica configuración y conexión.

Las vistas de alumno y admin se conectan en las Fases 2, 3 y 5.
"""
from pathlib import Path

import streamlit as st

from modules.config_loader import ConfigError, load_test_config
from modules.db import DBConfigError, crear_cliente, verificar_conexion

RAIZ = Path(__file__).parent

st.set_page_config(page_title="Test de especialización", page_icon="🎓", layout="centered")
st.title("Test de especialización")

try:
    cfg = load_test_config(RAIZ / "config" / "test.xlsx")
    st.success(
        f"Test cargado: {len(cfg.especialidades)} especialidades, "
        f"{len(cfg.preguntas)} preguntas, escala {cfg.valor_min}-{cfg.valor_max}."
    )
except ConfigError as exc:
    st.error("El archivo test.xlsx no es válido:")
    for e in exc.errores:
        st.write(f"- {e}")

try:
    verificar_conexion(crear_cliente(st.secrets))
    st.success("Conexión con Supabase correcta.")
except (DBConfigError, FileNotFoundError) as exc:
    st.warning(f"Supabase sin configurar: {exc}")
except Exception as exc:  # red, esquema sin crear, clave inválida
    st.error(f"No se pudo consultar Supabase: {type(exc).__name__}")
