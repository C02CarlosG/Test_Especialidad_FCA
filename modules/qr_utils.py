"""Generación del QR de acceso (PNG de alta resolución) para imprimir o proyectar."""
from __future__ import annotations

import io
import re
from urllib.parse import urlsplit

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

LADO_MINIMO_PX = 1200  # suficiente para imprimir a ~10 cm a 300 dpi


class UrlInvalida(ValueError):
    """La URL no sirve para un QR público."""


_ETIQUETA_DNS = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOST_DNS = re.compile(rf"^(?:{_ETIQUETA_DNS}\.)+{_ETIQUETA_DNS}$")


def validar_url(url: str) -> str:
    """Devuelve la URL limpia. Solo https (o http en localhost, para pruebas), sin espacios."""
    url = url.strip()
    if not url or any(c.isspace() for c in url):
        raise UrlInvalida("Escribe una URL completa, sin espacios (p. ej. https://mi-app.streamlit.app).")
    try:
        partes = urlsplit(url)
        partes.port  # noqa: B018  (lanza ValueError si el puerto es inválido)
    except ValueError as exc:
        raise UrlInvalida("La URL no es válida; revisa el host y el puerto (p. ej. https://mi-app.streamlit.app).") from exc
    local = partes.hostname in ("localhost", "127.0.0.1", "::1")
    if not partes.hostname:
        raise UrlInvalida("Escribe una URL completa, sin espacios (p. ej. https://mi-app.streamlit.app).")
    if not local and not (_HOST_DNS.match(partes.hostname) and len(partes.hostname) <= 253):
        raise UrlInvalida("El nombre del sitio no es válido (p. ej. mi-app.streamlit.app).")
    ruta = partes.path.lower().rstrip("/")
    if ruta == "/admin" or ruta.startswith("/admin/"):
        raise UrlInvalida("Esa es la dirección del panel del docente. Usa la dirección principal de la app.")
    if partes.scheme != "https" and not (partes.scheme == "http" and local):
        raise UrlInvalida("La URL debe empezar con https:// (los celulares avisan al abrir http://).")
    if not url.isascii():
        raise UrlInvalida("La URL solo puede tener caracteres ASCII; los acentos van codificados (p. ej. %C3%B1).")
    if partes.username or partes.password:
        raise UrlInvalida("La URL no debe incluir usuario ni contraseña.")
    if len(url) > 500:
        raise UrlInvalida("La URL es demasiado larga para un QR legible.")
    return url


def qr_png(url: str, lado_minimo: int = LADO_MINIMO_PX) -> bytes:
    """PNG en blanco y negro con borde de 4 módulos y corrección de errores Q (25 %).

    Cada módulo se dibuja de un número entero de píxeles, así que los bordes quedan nítidos
    al imprimir; el lado final es el primer múltiplo que alcanza `lado_minimo`.
    """
    url = validar_url(url)
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, border=4, box_size=1)
    qr.add_data(url)
    qr.make(fit=True)
    modulos = qr.modules_count + 2 * qr.border
    box = max(1, -(-lado_minimo // modulos))  # techo
    qr.box_size = box
    imagen = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    imagen.save(buf, format="PNG")
    return buf.getvalue()
