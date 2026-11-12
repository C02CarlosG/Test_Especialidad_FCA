"""Envío del reporte en PDF por correo (SMTP) y control de su estado.

El estado vive en la tabla `alumnos` (pendiente → enviando → enviado | error) y se toma con una reserva
atómica en el repositorio, para que un mismo reporte no salga dos veces aunque Streamlit vuelva a ejecutar
la página o haya dos pestañas abiertas. Nada de lo que se guarda o se muestra contiene la contraseña ni el
texto crudo de las excepciones: los motivos de error son mensajes fijos en español.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Callable, Protocol, Sequence

from modules.acceso import Alumno
from modules.security import correo_valido

log = logging.getLogger(__name__)

TIMEOUT_SMTP = 20  # segundos
RESERVA_VENCE = timedelta(minutes=10)
ASUNTO = "Tu reporte de evaluación integral"
MOTIVO_GENERICO = "No se pudo generar o enviar el reporte."


@dataclass(frozen=True)
class ConfigCorreo:
    servidor: str
    puerto: int
    usuario: str
    contrasena: str
    remitente: str


def config_desde(secreto: Callable[..., Any]) -> ConfigCorreo | None:
    """Lee la sección [correo] de los secretos. None si falta algo imprescindible (envío desactivado)."""
    def leer(clave: str) -> Any:
        return secreto("correo", clave, None)
    servidor, puerto, usuario, remitente = leer("servidor"), leer("puerto"), leer("usuario"), leer("remitente")
    if not (servidor and puerto and usuario and remitente):
        return None
    try:
        puerto = int(puerto)
    except (TypeError, ValueError):
        return None
    return ConfigCorreo(str(servidor), puerto, str(usuario), str(leer("contrasena") or ""), str(remitente))


class EnvioError(Exception):
    """El correo no salió. `str(exc)` es un mensaje fijo y mostrable, sin detalles del servidor."""


def enviar_reporte(destino: str, alumno: Alumno, pdf: bytes, config: ConfigCorreo) -> None:
    if not correo_valido(destino):
        raise EnvioError("La dirección de correo del alumno no es válida.")
    msg = EmailMessage()
    msg["From"] = config.remitente
    msg["To"] = destino
    msg["Subject"] = ASUNTO
    msg.set_content(f"Hola {alumno.nombres},\n\n"
                    "Adjuntamos tu Reporte de Evaluación Integral en formato PDF.\n\n"
                    "Si no esperabas este mensaje, ignóralo.\n")
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"resultados_{alumno.matricula}.pdf")
    conexion = smtplib.SMTP_SSL if config.puerto == 465 else smtplib.SMTP
    try:
        with conexion(config.servidor, config.puerto, timeout=TIMEOUT_SMTP) as smtp:
            if config.puerto == 587:
                smtp.starttls()
            if config.contrasena:
                smtp.login(config.usuario, config.contrasena)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise EnvioError("El servidor de correo rechazó el usuario o la contraseña.") from exc
    except smtplib.SMTPRecipientsRefused as exc:
        raise EnvioError("El servidor de correo rechazó la dirección del alumno.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise EnvioError("No se pudo conectar con el servidor de correo.") from exc


class RepositorioEnvio(Protocol):
    def reservar_envio(self, alumno_id: str, ahora: datetime, vencido_antes: datetime) -> bool: ...
    def marcar_enviado(self, alumno_id: str, ahora: datetime) -> None: ...
    def marcar_error(self, alumno_id: str, motivo: str) -> None: ...


def entregar_reporte(repo: RepositorioEnvio, alumno: Alumno, generar_pdf: Callable[[], bytes],
                     config: ConfigCorreo, ahora: datetime | None = None) -> str:
    """Envía el reporte una sola vez. Devuelve "enviado", "error", "omitido" (otro proceso lo tiene o ya
    se envió) o "sin_correo". Nunca lanza."""
    ahora = ahora or datetime.now(timezone.utc)
    if not alumno.correo:
        return "sin_correo"
    try:
        if not repo.reservar_envio(alumno.id, ahora, ahora - RESERVA_VENCE):
            return "omitido"
    except Exception:
        log.exception("No se pudo reservar el envío del reporte")
        return "error"
    try:
        enviar_reporte(alumno.correo, alumno, generar_pdf(), config)
    except Exception as exc:
        motivo = str(exc) if isinstance(exc, EnvioError) else MOTIVO_GENERICO
        log.warning("Falló el envío del reporte (%s)", type(exc).__name__)
        try:
            repo.marcar_error(alumno.id, motivo)
        except Exception:
            log.exception("No se pudo registrar el error del envío")
        return "error"
    try:
        repo.marcar_enviado(alumno.id, ahora)
    except Exception:
        log.exception("El reporte salió pero no se pudo registrar como enviado")
    return "enviado"


def pendientes_de_envio(filas: Sequence[Any]) -> list[Any]:
    """Alumnos que terminaron todo, tienen correo y cuyo reporte no está enviado."""
    return [f for f in filas
            if f.alumno.estado == "terminado" and f.completo and f.alumno.correo
            and f.alumno.reporte_estado in ("pendiente", "error", "enviando")]


def enviar_pendientes(repo: RepositorioEnvio, tests: Sequence[Any], filas: Sequence[Any], config: ConfigCorreo,
                      fecha: datetime, ahora: datetime | None = None) -> tuple[int, int, int]:
    """Envía los reportes pendientes. Devuelve (enviados, con error, omitidos)."""
    from modules.reports import pdf_individual  # import tardío: arrastra matplotlib y reportlab

    cuenta = {"enviado": 0, "error": 0, "omitido": 0, "sin_correo": 0}
    for f in pendientes_de_envio(filas):
        resultado = entregar_reporte(
            repo, f.alumno, lambda f=f: pdf_individual(f.alumno, tests, list(f.resultados), fecha), config, ahora)
        cuenta[resultado] += 1
    return cuenta["enviado"], cuenta["error"], cuenta["omitido"] + cuenta["sin_correo"]
