"""Repositorio en memoria para probar el flujo de acceso sin Supabase."""
from datetime import datetime, timezone
from itertools import count

from modules.acceso import Alumno, MatriculaDuplicada


class FakeRepo:
    def __init__(self, alumnos=()):
        self.alumnos = {a.matricula: a for a in alumnos}
        self.intentos: list[tuple[str, str, datetime]] = []
        self._ids = count(1)
        self.reloj = lambda: datetime.now(timezone.utc)
        self.carrera = False  # simula que otro envío gana la matrícula justo antes de insertar

    def contar_intentos(self, tipo, clave, desde):
        return sum(1 for t, c, f in self.intentos if t == tipo and c == clave and f >= desde)

    def registrar_intento(self, tipo, clave):
        self.intentos.append((tipo, clave, self.reloj()))

    def obtener_alumno_por_matricula(self, matricula):
        return self.alumnos.get(matricula)

    def crear_alumno(self, apellido_paterno, apellido_materno, nombres, matricula, edad, tutor,
                     acepto_en):
        if self.carrera or matricula in self.alumnos:
            raise MatriculaDuplicada()
        a = Alumno(f"a{next(self._ids)}", apellido_paterno, apellido_materno, nombres,
                   matricula, edad, tutor, "en_curso")
        self.alumnos[matricula] = a
        return a


def alumno(matricula="123456", nombres="Ana", estado="en_curso"):
    return Alumno(f"x{matricula}", "Pérez", "López", nombres, matricula, 20, "Mtro. Ruiz", estado)
