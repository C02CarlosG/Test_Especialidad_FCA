"""Carga y validación de los tests definidos en config/tests/*.xlsx.

Hay un archivo .xlsx por test. El alumno los contesta en orden fijo: el orden
alfabético del nombre de archivo (test_1_*.xlsx, test_2_*.xlsx, ...). El id del
test es el nombre del archivo sin extensión.

Hojas requeridas en cada archivo:
  - especialidades: codigo, nombre, descripcion, perfil_profesional
  - preguntas:      id, bloque, texto, especialidad_codigo, invertida (SI/NO)
  - escala:         valor, etiqueta   (valor numérico, o la fila especial 'SE' = sin experiencia)
Hojas opcionales:
  - info:           clave, valor   (claves: 'titulo' = nombre visible, 'instrucciones' = texto
                    que ve el alumno antes de contestar)
  - niveles:        ambito, minimo, etiqueta   (ambito: 'categoria' o 'afinidad'; minimo = fracción
                    0-1 del puntaje máximo desde la que aplica la etiqueta; debe haber una fila con 0)
  - afinidad:       codigo, nombre, componentes, descripcion   (afinidades derivadas: porcentaje
                    combinado de varias especialidades del test, p. ej. 'APERTURA+EXTRAVERSION')
Si algo está mal formado, se lanza ConfigError con TODOS los problemas encontrados.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import pandas as pd

HOJAS_REQUERIDAS: dict[str, list[str]] = {
    "especialidades": ["codigo", "nombre", "descripcion", "perfil_profesional"],
    "preguntas": ["id", "bloque", "texto", "especialidad_codigo", "invertida"],
    "escala": ["valor", "etiqueta"],
}


ID_TEST_VALIDO = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


class ConfigError(Exception):
    """El archivo de configuración del test no es válido."""

    def __init__(self, errores: list[str]) -> None:
        self.errores = errores
        super().__init__("Configuración de test inválida:\n- " + "\n- ".join(errores))


@dataclass(frozen=True)
class Especialidad:
    codigo: str
    nombre: str
    descripcion: str
    perfil_profesional: str


@dataclass(frozen=True)
class Pregunta:
    id: str
    bloque: int
    texto: str
    especialidad_codigo: str
    invertida: bool


@dataclass(frozen=True)
class OpcionEscala:
    valor: int
    etiqueta: str


@dataclass(frozen=True)
class Nivel:
    minimo: Fraction  # fracción del puntaje máximo (0 a 1) desde la que aplica la etiqueta
    etiqueta: str


@dataclass(frozen=True)
class AfinidadDef:
    codigo: str
    nombre: str
    componentes: tuple[str, ...]  # códigos de especialidades del mismo test
    descripcion: str


@dataclass(frozen=True)
class TestConfig:
    __test__ = False  # que pytest no lo tome por una clase de pruebas
    id: str  # nombre del archivo sin extensión; se guarda en la BD con cada respuesta
    titulo: str
    especialidades: tuple[Especialidad, ...]
    preguntas: tuple[Pregunta, ...]
    escala: tuple[OpcionEscala, ...]
    version: str  # hash del archivo: identifica con qué test respondió cada alumno
    # Etiqueta de la opción "SE" (sin experiencia), si el test la tiene. Es un dato faltante,
    # no un número: se guarda como valor NULL y no entra a la escala numérica.
    sin_experiencia: str | None = None
    instrucciones: str = ""
    niveles_categoria: tuple[Nivel, ...] = ()  # de mayor a menor `minimo`
    niveles_afinidad: tuple[Nivel, ...] = ()
    afinidades: tuple[AfinidadDef, ...] = ()

    @property
    def valor_min(self) -> int:
        return self.escala[0].valor

    @property
    def valor_max(self) -> int:
        return self.escala[-1].valor

    @property
    def bloques(self) -> list[int]:
        return sorted({p.bloque for p in self.preguntas})

    def preguntas_de_bloque(self, bloque: int) -> list[Pregunta]:
        return [p for p in self.preguntas if p.bloque == bloque]

    def especialidad(self, codigo: str) -> Especialidad:
        return next(e for e in self.especialidades if e.codigo == codigo)


def _texto(valor: object) -> str:
    return "" if pd.isna(valor) else str(valor).strip()


def _entero(valor: object) -> int | None:
    if pd.isna(valor):
        return None
    try:
        f = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return int(f) if f.is_integer() else None


def _duplicados(valores: list[str]) -> list[str]:
    vistos: set[str] = set()
    repetidos: list[str] = []
    for v in valores:
        if v in vistos and v not in repetidos:
            repetidos.append(v)
        vistos.add(v)
    return repetidos


def _version(preguntas: list[Pregunta], escala: list[OpcionEscala], sin_experiencia: str | None) -> str:
    """Identifica con qué preguntas y escala contestó el alumno. Solo depende de lo que cambia
    el significado de las respuestas; corregir descripciones o niveles NO invalida avances."""
    canon = json.dumps(
        [[(p.id, p.bloque, p.texto, p.especialidad_codigo, p.invertida) for p in preguntas],
         [(o.valor, o.etiqueta) for o in escala], sin_experiencia],
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def load_test_config(ruta: str | Path) -> TestConfig:
    ruta = Path(ruta)
    test_id = ruta.stem.lower()
    if not ID_TEST_VALIDO.match(test_id):
        raise ConfigError([
            f"Nombre de archivo inválido '{ruta.name}': usa minúsculas, números, '_' o '-' "
            "(p. ej. test_1_intereses.xlsx)."
        ])
    if not ruta.is_file():
        raise ConfigError([f"No se encontró el archivo {ruta}"])
    try:
        hojas = pd.read_excel(ruta, sheet_name=None, dtype=object, engine="openpyxl")
    except Exception as exc:  # archivo corrupto o no es xlsx
        raise ConfigError([f"No se pudo abrir {ruta.name} como Excel: {exc}"]) from exc

    errores: list[str] = []
    hojas = {nombre.strip().lower(): df for nombre, df in hojas.items()}
    for hoja, columnas in HOJAS_REQUERIDAS.items():
        if hoja not in hojas:
            errores.append(f"Falta la hoja '{hoja}'.")
            continue
        hojas[hoja].columns = [str(c).strip().lower() for c in hojas[hoja].columns]
        faltan = [c for c in columnas if c not in hojas[hoja].columns]
        if faltan:
            errores.append(f"La hoja '{hoja}' no tiene las columnas: {', '.join(faltan)}.")
    if errores:  # sin estructura básica no tiene caso validar contenido
        raise ConfigError(errores)

    titulo, instrucciones = test_id, ""
    if "info" in hojas:
        info = hojas["info"]
        info.columns = [str(c).strip().lower() for c in info.columns]
        if {"clave", "valor"} <= set(info.columns):
            for _, fila in info.iterrows():
                clave, valor = _texto(fila["clave"]).lower(), _texto(fila["valor"])
                if clave == "titulo" and valor:
                    titulo = valor
                elif clave == "instrucciones":
                    instrucciones = valor

    # --- especialidades ---
    especialidades: list[Especialidad] = []
    for i, fila in hojas["especialidades"].iterrows():
        n = int(i) + 2  # número de fila en Excel (encabezado = 1)
        esp = Especialidad(*(_texto(fila[c]) for c in HOJAS_REQUERIDAS["especialidades"]))
        if not esp.codigo or not esp.nombre:
            errores.append(f"especialidades fila {n}: 'codigo' y 'nombre' son obligatorios.")
            continue
        especialidades.append(esp)
    for cod in _duplicados([e.codigo for e in especialidades]):
        errores.append(f"especialidades: código repetido '{cod}'.")
    if len(especialidades) < 2:
        errores.append("Se requieren al menos 2 especialidades.")
    codigos = {e.codigo for e in especialidades}

    # --- escala ---
    escala: list[OpcionEscala] = []
    sin_experiencia: str | None = None
    for i, fila in hojas["escala"].iterrows():
        n = int(i) + 2
        if _texto(fila["valor"]).upper() == "SE":
            if sin_experiencia is not None:
                errores.append(f"escala fila {n}: la opción 'SE' está repetida.")
            elif not _texto(fila["etiqueta"]):
                errores.append(f"escala fila {n}: la opción 'SE' necesita etiqueta.")
            else:
                sin_experiencia = _texto(fila["etiqueta"])
            continue
        valor = _entero(fila["valor"])
        if valor is None:
            errores.append(f"escala fila {n}: 'valor' debe ser un número entero.")
            continue
        escala.append(OpcionEscala(valor, _texto(fila["etiqueta"])))
    escala.sort(key=lambda o: o.valor)
    valores = [o.valor for o in escala]
    if len(valores) < 2:
        errores.append("La escala necesita al menos 2 valores.")
    elif len(set(valores)) != len(valores):
        errores.append("escala: hay valores repetidos.")
    elif valores != list(range(valores[0], valores[-1] + 1)):
        errores.append("escala: los valores deben ser enteros consecutivos (p. ej. 1,2,3,4,5).")
    if any(not o.etiqueta for o in escala):
        errores.append("escala: todas las opciones necesitan etiqueta.")

    # --- preguntas ---
    preguntas: list[Pregunta] = []
    for i, fila in hojas["preguntas"].iterrows():
        n = int(i) + 2
        pid, texto = _texto(fila["id"]), _texto(fila["texto"])
        esp = _texto(fila["especialidad_codigo"])
        bloque = _entero(fila["bloque"])
        inv = _texto(fila["invertida"]).upper()
        fila_ok = True
        if not pid or not texto:
            errores.append(f"preguntas fila {n}: 'id' y 'texto' son obligatorios.")
            fila_ok = False
        if bloque is None or bloque < 1:
            errores.append(f"preguntas fila {n}: 'bloque' debe ser un entero >= 1.")
            fila_ok = False
        if esp not in codigos:
            errores.append(f"preguntas fila {n}: la especialidad '{esp}' no existe.")
            fila_ok = False
        if inv not in ("SI", "NO", "SÍ"):
            errores.append(f"preguntas fila {n}: 'invertida' debe ser SI o NO (es '{inv}').")
            fila_ok = False
        if fila_ok:
            preguntas.append(Pregunta(pid, bloque or 1, texto, esp, inv != "NO"))
    for pid in _duplicados([p.id for p in preguntas]):
        errores.append(f"preguntas: id repetido '{pid}'.")
    if not preguntas:
        errores.append("La hoja 'preguntas' está vacía.")
    usadas = {p.especialidad_codigo for p in preguntas}
    for cod in sorted(codigos - usadas):
        errores.append(f"La especialidad '{cod}' no tiene ninguna pregunta.")

    # --- niveles y afinidades (opcionales) ---
    niveles = {"categoria": [], "afinidad": []}
    if "niveles" in hojas:
        df = hojas["niveles"]
        df.columns = [str(c).strip().lower() for c in df.columns]
        faltan = [c for c in ("ambito", "minimo", "etiqueta") if c not in df.columns]
        if faltan:
            errores.append(f"La hoja 'niveles' no tiene las columnas: {', '.join(faltan)}.")
        else:
            for i, fila in df.iterrows():
                n = int(i) + 2
                ambito, etiqueta = _texto(fila["ambito"]).lower(), _texto(fila["etiqueta"])
                try:
                    minimo = Fraction(_texto(fila["minimo"]).replace(",", "."))
                except (ValueError, ZeroDivisionError):
                    minimo = None
                if ambito not in niveles:
                    errores.append(f"niveles fila {n}: 'ambito' debe ser categoria o afinidad.")
                elif minimo is None or not 0 <= minimo <= 1:
                    errores.append(f"niveles fila {n}: 'minimo' debe ser un número entre 0 y 1.")
                elif not etiqueta:
                    errores.append(f"niveles fila {n}: 'etiqueta' es obligatoria.")
                else:
                    niveles[ambito].append(Nivel(minimo, etiqueta))
        for ambito, filas in niveles.items():
            if not filas:
                continue
            if _duplicados([str(n.minimo) for n in filas]):
                errores.append(f"niveles ({ambito}): hay valores de 'minimo' repetidos.")
            if all(n.minimo != 0 for n in filas):
                errores.append(f"niveles ({ambito}): falta una fila con minimo 0 (cubre el resto).")
            filas.sort(key=lambda n: n.minimo, reverse=True)

    afinidades: list[AfinidadDef] = []
    if "afinidad" in hojas:
        df = hojas["afinidad"]
        df.columns = [str(c).strip().lower() for c in df.columns]
        faltan = [c for c in ("codigo", "nombre", "componentes", "descripcion") if c not in df.columns]
        if faltan:
            errores.append(f"La hoja 'afinidad' no tiene las columnas: {', '.join(faltan)}.")
        else:
            for i, fila in df.iterrows():
                n = int(i) + 2
                cod, nombre = _texto(fila["codigo"]), _texto(fila["nombre"])
                comps = tuple(c.strip() for c in _texto(fila["componentes"]).split("+") if c.strip())
                if not cod or not nombre:
                    errores.append(f"afinidad fila {n}: 'codigo' y 'nombre' son obligatorios.")
                elif not comps:
                    errores.append(f"afinidad fila {n}: 'componentes' no puede estar vacío.")
                elif (malas := [c for c in comps if c not in codigos]):
                    errores.append(f"afinidad fila {n}: componentes inexistentes: {', '.join(malas)}.")
                elif len(set(comps)) != len(comps):
                    errores.append(f"afinidad fila {n}: hay componentes repetidos.")
                else:
                    afinidades.append(AfinidadDef(cod, nombre, comps, _texto(fila["descripcion"])))
            for cod in _duplicados([a.codigo for a in afinidades]):
                errores.append(f"afinidad: código repetido '{cod}'.")
            if not afinidades:
                errores.append("La hoja 'afinidad' está vacía.")
    if niveles["afinidad"] and not afinidades:
        errores.append("niveles: hay filas de ambito 'afinidad' pero no existe la hoja 'afinidad'.")

    if errores:
        raise ConfigError(errores)

    return TestConfig(
        id=test_id,
        titulo=titulo,
        especialidades=tuple(especialidades),
        preguntas=tuple(preguntas),
        escala=tuple(escala),
        version=_version(preguntas, escala, sin_experiencia),
        sin_experiencia=sin_experiencia,
        instrucciones=instrucciones,
        niveles_categoria=tuple(niveles["categoria"]),
        niveles_afinidad=tuple(niveles["afinidad"]),
        afinidades=tuple(afinidades),
    )


def load_all_tests(carpeta: str | Path) -> tuple[TestConfig, ...]:
    """Carga todos los tests de la carpeta, en el orden en que los contestará el alumno.

    Valida cada archivo y reporta los errores de todos juntos, con el nombre del archivo.
    """
    carpeta = Path(carpeta)
    archivos = sorted(
        p for p in carpeta.glob("*.xlsx") if not p.name.startswith(("~$", "."))
    )
    if not archivos:
        raise ConfigError([f"No hay archivos .xlsx de tests en {carpeta}."])
    tests: list[TestConfig] = []
    errores: list[str] = []
    for archivo in archivos:
        try:
            tests.append(load_test_config(archivo))
        except ConfigError as exc:
            errores.extend(f"[{archivo.name}] {e}" for e in exc.errores)
    if errores:
        raise ConfigError(errores)
    for tid in _duplicados([t.id for t in tests]):
        errores.append(f"Id de test repetido '{tid}'.")
    if errores:
        raise ConfigError(errores)
    return tuple(tests)
