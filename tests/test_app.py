from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent


def test_app_abre_sin_excepciones():
    """Con secretos sin configurar el alumno ve un aviso genérico, no un traceback.

    Se fijan secretos falsos para no depender del secrets.toml local ni tocar Supabase.
    """
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30)
    at.secrets["supabase"] = {"url": "https://x.supabase.co", "service_role_key": "REEMPLAZAR"}
    at.run()
    assert not at.exception
    assert at.title[0].value == "Evaluación Diagnóstica FCA"
    assert any("no está disponible" in e.value for e in at.error)
