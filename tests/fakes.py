"""Repositorio en memoria para probar el flujo de acceso sin Supabase."""
from datetime import datetime, timezone
from itertools import count

from dataclasses import replace

from modules.acceso import Alumno, MatriculaDuplicada
from modules.avance import ProgresoTest
from modules.config_loader import Especialidad, OpcionEscala, Pregunta, TestConfig


class FakeRepo:
    def __init__(self, alumnos=()):
        self.alumnos = {a.matricula: a for a in alumnos}
        self.intentos: list[tuple[str, str, datetime]] = []
        self._ids = count(1)
        self.reloj = lambda: datetime.now(timezone.utc)
        self.progreso: dict[tuple[str, str], ProgresoTest] = {}
        self.respuestas: dict[tuple[str, str], dict] = {}
        self.resultados_guardados: list = []
        self.carrera = False  # simula que otro envío gana la matrícula justo antes de insertar

    def contar_intentos(self, tipo, clave, desde):
        return sum(1 for t, c, f in self.intentos if t == tipo and c == clave and f >= desde)

    def registrar_intento(self, tipo, clave):
        self.intentos.append((tipo, clave, self.reloj()))

    def liberar_intento(self, tipo, clave):
        for i in range(len(self.intentos) - 1, -1, -1):
            if self.intentos[i][0] == tipo and self.intentos[i][1] == clave:
                del self.intentos[i]
                return

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

    # --- avance ---
    def obtener_progreso(self, alumno_id):
        return {t: p for (a, t), p in self.progreso.items() if a == alumno_id}

    def iniciar_test(self, alumno_id, test_id, version, ahora):
        self.progreso.setdefault((alumno_id, test_id), ProgresoTest("en_curso", version))

    def obtener_respuestas(self, alumno_id, test_id):
        return dict(self.respuestas.get((alumno_id, test_id), {}))

    def guardar_respuestas(self, alumno_id, test_id, respuestas):
        self.respuestas.setdefault((alumno_id, test_id), {}).update(respuestas)

    def terminar_test(self, alumno_id, test_id, ahora):
        p = self.progreso[(alumno_id, test_id)]
        self.progreso[(alumno_id, test_id)] = replace(p, estado="terminado")

    def terminar_alumno(self, alumno_id):
        for m, a in self.alumnos.items():
            if a.id == alumno_id:
                self.alumnos[m] = replace(a, estado="terminado")

    # --- panel del docente ---
    def listar_alumnos(self):
        return list(self.alumnos.values())

    def obtener_progreso_todos(self):
        por_alumno = {}
        for (a, t), p in self.progreso.items():
            por_alumno.setdefault(a, {})[t] = p
        return por_alumno

    def obtener_respuestas_todas(self):
        por_test = {}
        for (a, t), r in self.respuestas.items():
            por_test.setdefault(t, {})[a] = dict(r)
        return por_test

    def guardar_resultado(self, alumno_id, resultado, ahora):
        self.resultados_guardados.append((alumno_id, resultado.test_id, resultado.principal))


def alumno(matricula="123456", nombres="Ana", estado="en_curso"):
    return Alumno(f"x{matricula}", "Pérez", "López", nombres, matricula, 20, "Mtro. Ruiz", estado)


def crear_test(id, n_preguntas, por_bloque=10, se=None, version="v1", escala=(1, 5), titulo=None):
    esp = (Especialidad("A", "A", "", ""),)
    preguntas = tuple(Pregunta(f"{id}-{i:02d}", (i - 1) // por_bloque + 1, f"p{i}", "A", False)
                      for i in range(1, n_preguntas + 1))
    esc = tuple(OpcionEscala(v, str(v)) for v in range(escala[0], escala[1] + 1))
    return TestConfig(id, titulo or id, esp, preguntas, esc, version, sin_experiencia=se)
