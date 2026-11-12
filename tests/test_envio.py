import smtplib
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from fakes import FakeRepo, alumno
from modules import envio
from modules.envio import (ConfigCorreo, EnvioError, config_desde, enviar_pendientes,
                           enviar_reporte, entregar_reporte, pendientes_de_envio)
from modules.panel import FilaAlumno

AHORA = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
PDF = b"%PDF-1.4 falso"
CLAVE = "S3creta!"
CONFIG = ConfigCorreo("smtp.test", 465, "reportes@test.mx", CLAVE, "reportes@test.mx")


class FakeSMTP:
    """Reemplaza a smtplib.SMTP / SMTP_SSL: registra qué se hizo y puede fallar a pedido."""
    instancias: list = []
    mensajes: list = []
    falla: Exception | None = None
    falla_para: set = set()

    def __init__(self, host, port, timeout=None, *, tipo="plain"):
        self.host, self.port, self.timeout, self.tipo = host, port, timeout, tipo
        self.starttls_llamado, self.login_args = False, None
        FakeSMTP.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.starttls_llamado = True

    def login(self, usuario, contrasena):
        self.login_args = (usuario, contrasena)
        if FakeSMTP.falla and isinstance(FakeSMTP.falla, smtplib.SMTPAuthenticationError):
            raise FakeSMTP.falla

    def send_message(self, msg):
        if FakeSMTP.falla and not isinstance(FakeSMTP.falla, smtplib.SMTPAuthenticationError):
            raise FakeSMTP.falla
        if msg["To"] in FakeSMTP.falla_para:
            raise smtplib.SMTPRecipientsRefused({msg["To"]: (550, b"no existe")})
        FakeSMTP.mensajes.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instancias, FakeSMTP.mensajes, FakeSMTP.falla, FakeSMTP.falla_para = [], [], None, set()
    monkeypatch.setattr(envio.smtplib, "SMTP", lambda h, p, timeout=None: FakeSMTP(h, p, timeout))
    monkeypatch.setattr(envio.smtplib, "SMTP_SSL", lambda h, p, timeout=None: FakeSMTP(h, p, timeout, tipo="ssl"))
    return FakeSMTP


def con_correo(matricula="123456", correo="ana@mail.com", estado="terminado", **kw):
    return replace(alumno(matricula, estado=estado), correo=correo, **kw)


def repo_con(*alumnos):
    return FakeRepo(alumnos)


def estado_de(repo, a):
    return repo.alumnos[a.matricula]


# --- configuración ---

def test_config_desde_devuelve_none_si_falta_servidor():
    datos = {"usuario": "u", "puerto": 465, "remitente": "r@x.mx"}
    assert config_desde(lambda s, k, d=None: datos.get(k, d) if s == "correo" else d) is None


def test_config_desde_lee_todos_los_campos():
    datos = {"servidor": "smtp.gmail.com", "puerto": "465", "usuario": "u@x.mx",
             "contrasena": "abc", "remitente": "Reportes <u@x.mx>"}
    cfg = config_desde(lambda s, k, d=None: datos.get(k, d) if s == "correo" else d)
    assert cfg == ConfigCorreo("smtp.gmail.com", 465, "u@x.mx", "abc", "Reportes <u@x.mx>")


# --- envío SMTP ---

def test_envio_arma_el_mensaje(smtp):
    enviar_reporte("ana@mail.com", con_correo(), PDF, CONFIG)
    msg = smtp.mensajes[0]
    assert msg["To"] == "ana@mail.com" and msg["From"] == CONFIG.remitente
    assert msg["Subject"] == "Tu reporte de evaluación integral"
    cuerpo = msg.get_body().get_content()
    assert "Ana" in cuerpo and "Test" not in cuerpo and "Si no esperabas este mensaje, ignóralo." in cuerpo
    [adjunto] = list(msg.iter_attachments())
    assert adjunto.get_filename() == "resultados_123456.pdf"
    assert adjunto.get_content_type() == "application/pdf" and adjunto.get_content() == PDF


@pytest.mark.parametrize("puerto,tipo,starttls", [(465, "ssl", False), (587, "plain", True), (1025, "plain", False)])
def test_el_puerto_decide_el_cifrado(smtp, puerto, tipo, starttls):
    enviar_reporte("ana@mail.com", con_correo(), PDF, replace(CONFIG, puerto=puerto))
    [s] = smtp.instancias
    assert (s.tipo, s.starttls_llamado, s.timeout) == (tipo, starttls, 20)
    assert s.login_args == (CONFIG.usuario, CLAVE)


def test_no_hay_login_sin_contrasena(smtp):
    enviar_reporte("ana@mail.com", con_correo(), PDF, replace(CONFIG, contrasena=""))
    assert smtp.instancias[0].login_args is None


@pytest.mark.parametrize("destino", ["a@c.com\nBcc: x@y.com", "a b@c.com", "sin-arroba", ""])
def test_destino_invalido_no_abre_conexion(smtp, destino):
    with pytest.raises(EnvioError):
        enviar_reporte(destino, con_correo(), PDF, CONFIG)
    assert smtp.instancias == []


# --- estado del envío ---

def test_entregar_exitoso_marca_enviado(smtp):
    a = con_correo()
    repo = repo_con(a)
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == "enviado"
    assert estado_de(repo, a).reporte_estado == "enviado" and len(smtp.mensajes) == 1


def test_entregar_dos_veces_envia_una_sola(smtp):
    a = con_correo()
    repo = repo_con(a)
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == "enviado"
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == "omitido"
    assert len(smtp.mensajes) == 1


def test_fallo_smtp_marca_error_con_mensaje_fijo(smtp):
    smtp.falla = smtplib.SMTPAuthenticationError(535, f"usuario o clave {CLAVE} rechazada".encode())
    a = con_correo()
    repo = repo_con(a)
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == "error"
    r = estado_de(repo, a)
    assert r.reporte_estado == "error" and r.reporte_error
    assert CLAVE not in r.reporte_error and "535" not in r.reporte_error


def test_servidor_caido_marca_error(smtp):
    smtp.falla = OSError("timed out")
    a = con_correo()
    repo = repo_con(a)
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == "error"
    assert estado_de(repo, a).reporte_error == "No se pudo conectar con el servidor de correo."


def test_error_al_generar_el_pdf_marca_error(smtp):
    def pdf_roto():
        raise ValueError("detalle interno")
    a = con_correo()
    repo = repo_con(a)
    assert entregar_reporte(repo, a, pdf_roto, CONFIG, AHORA) == "error"
    assert estado_de(repo, a).reporte_error == "No se pudo generar o enviar el reporte."
    assert smtp.instancias == []


def test_un_error_se_puede_reintentar(smtp):
    smtp.falla = OSError("caído")
    a = con_correo()
    repo = repo_con(a)
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == "error"
    smtp.falla = None
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == "enviado"
    assert estado_de(repo, a).reporte_error is None


@pytest.mark.parametrize("minutos,esperado", [(11, "enviado"), (5, "omitido")])
def test_reserva_vencida_se_puede_tomar(smtp, minutos, esperado):
    a = con_correo(reporte_estado="enviando")
    repo = repo_con(a)
    repo.reservas[a.id] = AHORA - timedelta(minutes=minutos)
    assert entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA) == esperado


def test_sin_correo_no_toca_el_estado(smtp):
    a = con_correo(correo=None)
    repo = repo_con(a)
    llamado = []
    assert entregar_reporte(repo, a, lambda: llamado.append(1) or PDF, CONFIG, AHORA) == "sin_correo"
    assert estado_de(repo, a).reporte_estado == "pendiente" and llamado == []


def test_reiniciar_devuelve_el_estado_a_pendiente(smtp):
    a = con_correo()
    repo = repo_con(a)
    entregar_reporte(repo, a, lambda: PDF, CONFIG, AHORA)
    repo.reiniciar_alumno(a.id, ["t1"], False)
    assert estado_de(repo, a).reporte_estado == "pendiente" and estado_de(repo, a).reporte_error is None


# --- envío masivo ---

def fila(a, completo=True):
    return FilaAlumno(a, ("terminado",), (10,), (object() if completo else None,))


def test_pendientes_de_envio_filtra():
    ok = con_correo("1")
    con_error = con_correo("5", reporte_estado="error")
    sin_correo = con_correo("2", correo=None)
    en_curso = con_correo("3", estado="en_curso")
    enviado = con_correo("4", reporte_estado="enviado")
    incompleto = con_correo("6")
    filas = [fila(ok), fila(sin_correo), fila(en_curso), fila(enviado), fila(con_error), fila(incompleto, False)]
    assert [f.alumno.matricula for f in pendientes_de_envio(filas)] == ["1", "5"]


def test_enviar_pendientes_cuenta(smtp, monkeypatch):
    monkeypatch.setattr("modules.reports.pdf_individual", lambda *a, **k: PDF)
    bien1, bien2 = con_correo("1", "a@x.com"), con_correo("2", "b@x.com")
    mal = con_correo("3", "c@x.com")
    ocupado = con_correo("4", "d@x.com", reporte_estado="enviando")
    repo = repo_con(bien1, bien2, mal, ocupado)
    repo.reservas[ocupado.id] = AHORA - timedelta(minutes=1)
    smtp.falla_para = {"c@x.com"}
    filas = [fila(a) for a in (bien1, bien2, mal, ocupado)]
    assert enviar_pendientes(repo, (), filas, CONFIG, AHORA, AHORA) == (2, 1, 1)
