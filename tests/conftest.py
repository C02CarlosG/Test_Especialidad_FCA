import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import pytest


@pytest.fixture
def smtp(monkeypatch):
    """Reemplaza smtplib.SMTP / SMTP_SSL por un doble que registra los correos enviados y puede fallar."""
    import smtplib

    from fakes import FakeSMTP
    FakeSMTP.instancias, FakeSMTP.mensajes, FakeSMTP.falla, FakeSMTP.falla_para = [], [], None, set()
    monkeypatch.setattr(smtplib, "SMTP", lambda h, p, timeout=None: FakeSMTP(h, p, timeout))
    monkeypatch.setattr(smtplib, "SMTP_SSL", lambda h, p, timeout=None: FakeSMTP(h, p, timeout, tipo="ssl"))
    return FakeSMTP
