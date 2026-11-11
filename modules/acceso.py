"""Flujo de acceso del alumno: validar datos, limitar intentos y registrar al alumno una
sola vez por matrícula. Habla con la BD solo a través de `Repositorio` (en producción
`db.SupabaseRepo`; en pruebas, un doble en memoria).

El acceso está limitado a la lista de matrículas autorizadas (tabla `alumnos_autorizados`):
con el QR solo entra quien está en la lista. No hay código de grupo.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Protocol

from modules import security as sec

TIPO_INTENTO = "acceso"


@dataclass(frozen=True)
class Alumno:
    id: str
    apellido_paterno: str
    apellido_materno: str
    nombres: str
    matricula: str
    edad: int
    tutor: str
    estado: str  # en_curso | terminado
    creado_en: datetime | None = None  # solo lo llenan las consultas del panel del docente
    semestre: int | None = None  # None en los alumnos registrados antes de pedirlo

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellido_paterno} {self.apellido_materno}"


@dataclass(frozen=True)
class DatosAcceso:
    apellido_paterno: str
    apellido_materno: str
    nombres: str
    matricula: str
    edad: int | None
    tutor: str
    acepto_privacidad: bool
    semestre: int | None = None


@dataclass(frozen=True)
class ResultadoAcceso:
    alumno: Alumno
    reanudado: bool  # True si la matrícula ya existía y seguía en curso


class MatriculaDuplicada(Exception):
    """El repositorio detectó que la matrícula ya existe (restricción UNIQUE)."""


class Repositorio(Protocol):
    def contar_intentos(self, tipo: str, clave: str, desde: datetime) -> int: ...
    def registrar_intento(self, tipo: str, clave: str) -> None: ...
    def nombre_autorizado(self, matricula: str) -> str | None: ...  # None = no está en la lista
    def obtener_alumno_por_matricula(self, matricula: str) -> Alumno | None: ...
    def crear_alumno(self, apellido_paterno: str, apellido_materno: str, nombres: str,
                     matricula: str, edad: int, tutor: str, acepto_en: datetime,
                     semestre: int | None = None) -> Alumno: ...
    def actualizar_datos(self, alumno_id: str, edad: int, tutor: str, semestre: int) -> None: ...


class AccesoError(Exception):
    """Error mostrable al alumno. `mensaje` no revela detalles internos."""

    def __init__(self, mensaje: str) -> None:
        self.mensaje = mensaje
        super().__init__(mensaje)


class DatosInvalidos(AccesoError):
    def __init__(self, errores: dict[str, str]) -> None:
        self.errores = errores
        super().__init__("Revisa los datos marcados.")


class AccesoBloqueado(AccesoError):
    def __init__(self) -> None:
        super().__init__(
            f"Demasiados intentos fallidos. Espera {sec.VENTANA_INTENTOS_MIN} minutos "
            "y vuelve a intentar, o pide ayuda a tu tutor."
        )


class MatriculaNoDisponible(AccesoError):
    def __init__(self) -> None:
        super().__init__(
            "Esta matrícula ya está registrada o ya contestó el test. "
            "Si crees que es un error, avisa a tu tutor."
        )


class MatriculaNoAutorizada(AccesoError):
    def __init__(self) -> None:
        super().__init__(
            "Tu matrícula no está en la lista de alumnos autorizados. Revisa que la hayas escrito "
            "bien; si es correcta, avisa a tu tutor."
        )


_PARTICULAS = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "SAN", "SANTA", "MC", "VAN", "VON"}


def separar_nombre(nombre: str) -> tuple[str, str, str]:
    """Separa «PATERNO MATERNO NOMBRE(S)» (como viene en la lista) en (paterno, materno, nombres).

    Es una aproximación: respeta las partículas («DE LA VEGA») y las palabras con guion, pero con
    solo tres palabras no hay forma de saber si falta un apellido o un nombre. Por eso el alumno
    ve los campos llenos y puede corregirlos."""
    t = nombre.split()

    def apellido(i: int) -> tuple[str, int]:
        j = i
        while j < len(t) - 1 and t[j].upper() in _PARTICULAS:
            j += 1
        return " ".join(t[i:j + 1]), j + 1

    if not t:
        return "", "", ""
    paterno, i = apellido(0)
    materno = ""
    if i < len(t) - 1:  # siempre debe quedar al menos una palabra para el nombre
        materno, i = apellido(i)
    return paterno.title(), materno.title(), " ".join(t[i:]).title()


def _mismo_nombre(alumno: Alumno, v: dict) -> bool:
    """Segundo dato (además de la matrícula) para reanudar un test en curso."""
    return ((alumno.apellido_paterno.casefold(), alumno.apellido_materno.casefold(),
             alumno.nombres.casefold())
            == (str(v["apellido_paterno"]).casefold(), str(v["apellido_materno"]).casefold(),
                str(v["nombres"]).casefold()))


def _intentos_en_ventana(repo: Repositorio, clave: str, ahora: datetime) -> int:
    desde = ahora - timedelta(minutes=sec.VENTANA_INTENTOS_MIN)
    return repo.contar_intentos(TIPO_INTENTO, clave, desde)


def _registrar_fallo(repo: Repositorio, clave_mat: str, clave_cli: str) -> None:
    repo.registrar_intento(TIPO_INTENTO, clave_mat)
    repo.registrar_intento(TIPO_INTENTO, clave_cli)


def _verificar_no_bloqueado(repo: Repositorio, clave_mat: str, clave_cli: str, ahora: datetime) -> None:
    if (_intentos_en_ventana(repo, clave_mat, ahora) >= sec.MAX_INTENTOS_MATRICULA
            or _intentos_en_ventana(repo, clave_cli, ahora) >= sec.MAX_INTENTOS_CLIENTE):
        raise AccesoBloqueado()


def buscar_autorizado(repo: Repositorio, matricula: str, cliente_ip: str,
                      ahora: datetime | None = None) -> str | None:
    """Nombre del alumno en la lista (para llenar el registro al escribir la matrícula), o None.

    Una matrícula que no está en la lista cuenta como intento fallido, igual que al registrarse: así
    nadie puede recorrer matrículas para averiguar nombres. Lanza AccesoBloqueado si ya se bloqueó."""
    ahora = ahora or datetime.now(timezone.utc)
    m = sec.normalizar_matricula(matricula)
    if not (len(m) == 6 and m.isascii() and m.isdigit()):
        return None
    clave_mat, clave_cli = sec.clave_matricula(m), sec.clave_cliente(cliente_ip)
    _verificar_no_bloqueado(repo, clave_mat, clave_cli, ahora)
    nombre = repo.nombre_autorizado(m)
    if nombre is None:
        _registrar_fallo(repo, clave_mat, clave_cli)
    return nombre


def _con_datos_nuevos(repo: Repositorio, existente: Alumno, v: dict[str, str | int]) -> Alumno:
    """Al reanudar (p. ej. tras reiniciar un test) vale lo que el alumno acaba de escribir: edad, tutor y
    semestre se actualizan si cambiaron. El nombre no, porque es lo que identifica a quien reanuda."""
    edad, tutor, semestre = int(v["edad"]), str(v["tutor"]), int(v["semestre"])
    if (edad, tutor, semestre) == (existente.edad, existente.tutor, existente.semestre):
        return existente
    repo.actualizar_datos(existente.id, edad, tutor, semestre)
    return replace(existente, edad=edad, tutor=tutor, semestre=semestre)


def iniciar_acceso(repo: Repositorio, datos: DatosAcceso, cliente_ip: str,
                   ahora: datetime | None = None) -> ResultadoAcceso:
    """Valida y registra al alumno. Lanza AccesoError (o subclase) si no puede entrar.

    - Una matrícula fuera de la lista autorizada se rechaza y cuenta como intento fallido.
    - Un alumno nuevo queda registrado.
    - Una matrícula ya terminada, o en curso pero con otro nombre, se rechaza.
    - Una matrícula en curso con el mismo nombre reanuda (la sesión del navegador pudo
      perderse a mitad del test).
    - Intentar entrar con una matrícula ajena cuenta como intento fallido y, al llegar
      al límite, bloquea esa matrícula y al cliente por unos minutos.
    """
    ahora = ahora or datetime.now(timezone.utc)
    if not datos.acepto_privacidad:
        raise AccesoError("Debes aceptar el aviso de privacidad para continuar.")
    v, errores = sec.validar_datos(datos.apellido_paterno, datos.apellido_materno, datos.nombres,
                                   datos.matricula, datos.edad, datos.tutor, datos.semestre)
    if errores:
        raise DatosInvalidos(errores)

    clave_mat = sec.clave_matricula(str(v["matricula"]))
    clave_cli = sec.clave_cliente(cliente_ip)
    # El bloqueo se revisa antes de consultar nada más, para que no sirva de oráculo.
    _verificar_no_bloqueado(repo, clave_mat, clave_cli, ahora)

    if repo.nombre_autorizado(str(v["matricula"])) is None:
        _registrar_fallo(repo, clave_mat, clave_cli)  # también frena a quien prueba matrículas al azar
        raise MatriculaNoAutorizada()

    existente = repo.obtener_alumno_por_matricula(str(v["matricula"]))
    if existente is not None:
        if existente.estado == "en_curso" and _mismo_nombre(existente, v):
            return ResultadoAcceso(_con_datos_nuevos(repo, existente, v), reanudado=True)
        if existente.estado != "terminado":  # intento de entrar con datos ajenos
            _registrar_fallo(repo, clave_mat, clave_cli)
        raise MatriculaNoDisponible()

    try:
        alumno = repo.crear_alumno(
            str(v["apellido_paterno"]), str(v["apellido_materno"]), str(v["nombres"]),
            str(v["matricula"]), int(v["edad"]), str(v["tutor"]), ahora, semestre=int(v["semestre"]))
    except MatriculaDuplicada:  # dos envíos simultáneos con la misma matrícula
        raise MatriculaNoDisponible() from None
    return ResultadoAcceso(alumno, reanudado=False)
