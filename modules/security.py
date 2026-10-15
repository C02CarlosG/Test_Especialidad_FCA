"""Validación de entradas y política de intentos fallidos. Lógica pura, sin I/O."""
from __future__ import annotations

import hashlib
import re
import unicodedata

# Límites de intentos fallidos de acceso (matrícula ajena), en una ventana deslizante.
# Por matrícula: estricto. Por cliente (IP): holgado, porque en un salón de 30 a 40
# alumnos todos salen por la misma IP y no deben bloquearse entre sí por errores de dedo.
MAX_INTENTOS_MATRICULA = 5
MAX_INTENTOS_CLIENTE = 100
VENTANA_INTENTOS_MIN = 15

_RE_MATRICULA = re.compile(r"[0-9]{6}")  # exactamente 6 dígitos (solo ASCII)


EDAD_MINIMA = 18
EDAD_MAXIMA = 99


def normalizar_texto(valor: str) -> str:
    """Quita caracteres de control (p. ej. al pegar desde una terminal o un PDF) y los espacios
    sobrantes. Un carácter de control en un nombre rompería la generación del Excel."""
    sin_control = "".join(ch for ch in valor if ch.isspace() or unicodedata.category(ch) != "Cc")
    return " ".join(sin_control.split())


def normalizar_matricula(valor: str) -> str:
    return valor.strip()


def _nombre_ok(valor: str) -> bool:
    # Debe empezar con letra: así un nombre nunca se interpreta como fórmula al abrirlo en Excel.
    return 1 <= len(valor) <= 80 and valor[0].isalpha()


def validar_datos(apellido_paterno: str, apellido_materno: str, nombres: str,
                  matricula: str, edad: int | None, tutor: str
                  ) -> tuple[dict[str, str | int], dict[str, str]]:
    """Devuelve (valores normalizados, errores por campo). Sin errores = dict vacío."""
    v: dict[str, str | int] = {
        "apellido_paterno": normalizar_texto(apellido_paterno),
        "apellido_materno": normalizar_texto(apellido_materno),
        "nombres": normalizar_texto(nombres),
        "matricula": normalizar_matricula(matricula),
        "tutor": normalizar_texto(tutor),
        "edad": edad if edad is not None else 0,
    }
    errores: dict[str, str] = {}
    for campo, etiqueta in (("apellido_paterno", "el apellido paterno"),
                            ("apellido_materno", "el apellido materno"),
                            ("nombres", "tu(s) nombre(s)")):
        if not _nombre_ok(str(v[campo])):
            errores[campo] = f"Escribe {etiqueta}."
    if not _RE_MATRICULA.fullmatch(str(v["matricula"])):
        errores["matricula"] = "La matrícula debe tener exactamente 6 números."
    if edad is None:
        errores["edad"] = "Escribe tu edad."
    elif edad < EDAD_MINIMA:
        errores["edad"] = f"Este test es solo para mayores de {EDAD_MINIMA} años."
    elif edad > EDAD_MAXIMA:
        errores["edad"] = "Revisa tu edad."
    if not _nombre_ok(str(v["tutor"])):
        errores["tutor"] = "Escribe el nombre de tu tutor u orientador."
    return v, errores


def clave_matricula(matricula: str) -> str:
    return f"mat:{matricula}"


def clave_cliente(ip: str) -> str:
    """Identificador de cliente para limitar intentos. Se guarda el hash, no la IP
    (seudonimización: reduce datos personales almacenados, no es anonimización)."""
    return "ip:" + hashlib.sha256(ip.strip().encode()).hexdigest()[:16]
