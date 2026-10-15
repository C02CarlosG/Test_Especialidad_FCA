"""Generación del QR de acceso (PNG de alta resolución) para imprimir o proyectar."""
from __future__ import annotations

import io
from urllib.parse import urlsplit

import qrcode
from qrcode.constants import ERROR_CORRECT_Q

LADO_MINIMO_PX = 1200  # suficiente para imprimir a ~10 cm a 300 dpi


class UrlInvalida(ValueError):
    """La URL no sirve para un QR público."""


def validar_url(url: str) -> str:
    """Devuelve la URL limpia. Solo https (o http en localhost, para pruebas), sin espacios."""
    url = url.strip()
    partes = urlsplit(url)
    local = partes.hostname in ("localhost", "127.0.0.1", "::1")
    if not url or any(c.isspace() for c in url) or not partes.hostname:
        raise UrlInvalida("Escribe una URL completa, sin espacios (p. ej. https://mi-app.streamlit.app).")
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
