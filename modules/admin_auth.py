"""Acceso del docente al panel: una contraseña compartida y límite de intentos fallidos."""
from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Protocol

from modules import security as sec

TIPO = "admin"
LARGO_MINIMO = 12
MAX_INTENTOS_CLIENTE = 5
MAX_INTENTOS_GLOBAL = 30  # frena un ataque repartido entre muchas IP, a costa de bloquear al docente un rato
CLAVE_GLOBAL = "global"
SESION_MINUTOS = 60  # inactividad máxima antes de volver a pedir la contraseña


class RepositorioIntentos(Protocol):
    def contar_intentos(self, tipo: str, clave: str, desde: datetime) -> int: ...
    def registrar_intento(self, tipo: str, clave: str) -> None: ...
    def liberar_intento(self, tipo: str, clave: str) -> None: ...


class AdminError(Exception):
    def __init__(self, mensaje: str) -> None:
        self.mensaje = mensaje
        super().__init__(mensaje)


class PanelDeshabilitado(AdminError):
    def __init__(self) -> None:
        super().__init__("El panel no está configurado: falta una contraseña de al menos "
                         f"{LARGO_MINIMO} caracteres en [admin] password de los secretos.")


class LoginBloqueado(AdminError):
    def __init__(self) -> None:
        super().__init__(f"Demasiados intentos fallidos. Espera {sec.VENTANA_INTENTOS_MIN} minutos.")


class PasswordIncorrecta(AdminError):
    def __init__(self, restantes: int) -> None:
        super().__init__("Contraseña incorrecta." + (f" Te quedan {restantes} intentos." if restantes > 0 else ""))


def password_valida(esperada: object) -> bool:
    return isinstance(esperada, str) and len(esperada) >= LARGO_MINIMO and esperada != "REEMPLAZAR"


def intentar_login(repo: RepositorioIntentos, ingresada: str, esperada: object, cliente_ip: str,
                   ahora: datetime | None = None) -> None:
    """Termina sin error si la contraseña es correcta; si no, lanza AdminError.

    El intento se reserva ANTES de comparar la contraseña y recién entonces se cuenta, de modo que
    varias sesiones simultáneas no pueden colarse por encima del tope (contar -> comparar -> registrar
    dejaba una ventana). Un acierto, o un intento bloqueado, devuelve su reserva.
    """
    if not password_valida(esperada):
        raise PanelDeshabilitado()
    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(minutes=sec.VENTANA_INTENTOS_MIN)
    clave_cli = sec.clave_cliente(cliente_ip)
    repo.registrar_intento(TIPO, clave_cli)
    repo.registrar_intento(TIPO, CLAVE_GLOBAL)

    def devolver() -> None:
        repo.liberar_intento(TIPO, clave_cli)
        repo.liberar_intento(TIPO, CLAVE_GLOBAL)

    n_cli = repo.contar_intentos(TIPO, clave_cli, desde)  # ya incluye este intento
    if n_cli > MAX_INTENTOS_CLIENTE or repo.contar_intentos(TIPO, CLAVE_GLOBAL, desde) > MAX_INTENTOS_GLOBAL:
        devolver()  # el bloqueo termina 15 min después del último fallo real, no del último intento
        raise LoginBloqueado()
    # compare_digest evita filtrar la contraseña por tiempos de respuesta
    if hmac.compare_digest(ingresada.encode(), str(esperada).encode()):
        devolver()
        return
    raise PasswordIncorrecta(MAX_INTENTOS_CLIENTE - n_cli)
