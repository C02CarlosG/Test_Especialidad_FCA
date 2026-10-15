from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent


def test_app_abre_sin_excepciones():
    at = AppTest.from_file(str(RAIZ / "app.py"), default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "Test de especialización"
    assert any("3 tests cargados" in s.value for s in at.success)
