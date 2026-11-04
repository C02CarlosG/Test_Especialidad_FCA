from datetime import datetime, timedelta, timezone

import pytest

from fakes import FakeRepo
from modules import admin_auth as aa
from modules import security as sec

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
CLAVE = "una-contraseña-larga-y-unica"
IP = "203.0.113.9"


def repo():
    r = FakeRepo()
    r.reloj = lambda: AHORA
    return r


def test_contraseña_correcta_entra_y_no_registra_intentos():
    r = repo()
    aa.intentar_login(r, CLAVE, CLAVE, IP, AHORA)
    assert r.intentos == []


def test_contraseña_incorrecta_cuenta_intentos_y_avisa_cuantos_quedan():
    r = repo()
    with pytest.raises(aa.PasswordIncorrecta, match=f"Te quedan {aa.MAX_INTENTOS_CLIENTE - 1} intentos"):
        aa.intentar_login(r, "mala", CLAVE, IP, AHORA)
    assert {t for t, _, _ in r.intentos} == {"admin"} and len(r.intentos) == 2


def test_bloqueo_tras_n_fallos_incluso_con_la_contraseña_buena():
    r = repo()
    for _ in range(aa.MAX_INTENTOS_CLIENTE):
        with pytest.raises(aa.PasswordIncorrecta):
            aa.intentar_login(r, "mala", CLAVE, IP, AHORA)
    with pytest.raises(aa.LoginBloqueado):
        aa.intentar_login(r, CLAVE, CLAVE, IP, AHORA)
    despues = AHORA + timedelta(minutes=sec.VENTANA_INTENTOS_MIN + 1)
    aa.intentar_login(r, CLAVE, CLAVE, IP, despues)  # el bloqueo expira


def test_otra_ip_no_esta_bloqueada_por_los_fallos_de_la_primera():
    r = repo()
    for _ in range(aa.MAX_INTENTOS_CLIENTE):
        with pytest.raises(aa.PasswordIncorrecta):
            aa.intentar_login(r, "mala", CLAVE, IP, AHORA)
    aa.intentar_login(r, CLAVE, CLAVE, "198.51.100.7", AHORA)


def test_ataque_repartido_entre_muchas_ip_se_frena_con_el_tope_global():
    r = repo()
    for i in range(aa.MAX_INTENTOS_GLOBAL):
        with pytest.raises(aa.PasswordIncorrecta):
            aa.intentar_login(r, "mala", CLAVE, f"10.0.0.{i}", AHORA)
    with pytest.raises(aa.LoginBloqueado):
        aa.intentar_login(r, CLAVE, CLAVE, "10.9.9.9", AHORA)


@pytest.mark.parametrize("esperada", [None, "", "corta", "REEMPLAZAR", "x" * (aa.LARGO_MINIMO - 1), 123456789012, ["a" * 20]])
def test_sin_contraseña_valida_el_panel_queda_deshabilitado(esperada):
    r = repo()
    with pytest.raises(aa.PanelDeshabilitado):
        aa.intentar_login(r, "lo-que-sea", esperada, IP, AHORA)
    with pytest.raises(aa.PanelDeshabilitado):
        aa.intentar_login(r, "", esperada, IP, AHORA)  # la vacía tampoco entra
    assert r.intentos == []


def test_la_contraseña_vacia_o_parecida_no_entra():
    r = repo()
    for mala in ("", CLAVE + " ", CLAVE.upper(), CLAVE[:-1]):
        with pytest.raises(aa.PasswordIncorrecta):
            aa.intentar_login(r, mala, CLAVE, IP, AHORA)


def test_contraseña_con_acentos_y_emoji():
    clave = "contraseña-ñandú-🔐-larga"
    aa.intentar_login(repo(), clave, clave, IP, AHORA)


# ---- regresiones de la revisión independiente de la Fase 5 ----

def test_el_intento_se_reserva_antes_de_comparar_la_contraseña():
    """Contar -> comparar -> registrar dejaba pasar sesiones simultáneas por encima del tope."""
    eventos = []

    class Espia(FakeRepo):
        def registrar_intento(self, tipo, clave):
            eventos.append("registrar")
            super().registrar_intento(tipo, clave)

        def contar_intentos(self, tipo, clave, desde):
            eventos.append("contar")
            return super().contar_intentos(tipo, clave, desde)

    r = Espia()
    r.reloj = lambda: AHORA
    with pytest.raises(aa.PasswordIncorrecta):
        aa.intentar_login(r, "mala", CLAVE, IP, AHORA)
    assert eventos.index("registrar") < eventos.index("contar")


def test_intentos_simultaneos_no_superan_el_tope():
    """N sesiones que a la vez ya reservaron su cupo: solo las primeras MAX_INTENTOS_CLIENTE comparan."""
    r = repo()
    clave = sec.clave_cliente(IP)
    for _ in range(aa.MAX_INTENTOS_CLIENTE + 3):  # reservas hechas en paralelo antes de que nadie compare
        r.registrar_intento("admin", clave)
    with pytest.raises(aa.LoginBloqueado):
        aa.intentar_login(r, CLAVE, CLAVE, IP, AHORA)  # aun con la contraseña buena


def test_los_intentos_bloqueados_no_alargan_el_bloqueo():
    r = repo()
    for _ in range(aa.MAX_INTENTOS_CLIENTE):
        with pytest.raises(aa.PasswordIncorrecta):
            aa.intentar_login(r, "mala", CLAVE, IP, AHORA)
    diez_min = AHORA + timedelta(minutes=10)
    for _ in range(20):  # alguien insiste mientras está bloqueado
        with pytest.raises(aa.LoginBloqueado):
            aa.intentar_login(r, "mala", CLAVE, IP, diez_min)
    # 16 min después del último FALLO real el docente entra: lo bloqueado no cuenta como intento
    aa.intentar_login(r, CLAVE, CLAVE, IP, AHORA + timedelta(minutes=sec.VENTANA_INTENTOS_MIN + 1))


def test_un_acierto_devuelve_su_reserva_y_no_reinicia_los_fallos_previos():
    r = repo()
    for _ in range(2):
        with pytest.raises(aa.PasswordIncorrecta):
            aa.intentar_login(r, "mala", CLAVE, IP, AHORA)
    aa.intentar_login(r, CLAVE, CLAVE, IP, AHORA)
    assert len(r.intentos) == 4  # 2 fallos x (cliente + global); el acierto no deja huella
