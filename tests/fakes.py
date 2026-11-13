"""Repositorio en memoria para probar el flujo de acceso sin Supabase."""
import smtplib
from datetime import datetime, timezone
from itertools import count

from dataclasses import replace

from modules.acceso import Alumno, MatriculaDuplicada
from modules.avance import ProgresoTest
from modules.panel import Autorizado
from modules.config_loader import Especialidad, OpcionEscala, Pregunta, TestConfig


class FakeRepo:
    def __init__(self, alumnos=(), autorizadas=None):
        # {matrícula: nombre}. None = cualquier matrícula está autorizada (la mayoría de las pruebas
        # no se ocupa de la lista).
        self.autorizadas = None if autorizadas is None else dict(autorizadas)
        self.alumnos = {a.matricula: a for a in alumnos}
        self.intentos: list[tuple[str, str, datetime]] = []
        self._ids = count(1)
        self.reloj = lambda: datetime.now(timezone.utc)
        self.progreso: dict[tuple[str, str], ProgresoTest] = {}
        self.respuestas: dict[tuple[str, str], dict] = {}
        self.resultados_guardados: list = []
        self.reinicios: list = []
        self.reservas: dict = {}  # alumno_id -> cuándo se tomó la reserva del envío
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

    def nombre_autorizado(self, matricula):
        if self.autorizadas is None:
            return "SIN LISTA"
        return self.autorizadas.get(matricula)

    def obtener_alumno_por_matricula(self, matricula):
        return self.alumnos.get(matricula)

    def crear_alumno(self, apellido_paterno, apellido_materno, nombres, matricula, edad, tutor,
                     acepto_en, semestre=None, correo=None):
        if self.carrera or matricula in self.alumnos:
            raise MatriculaDuplicada()
        a = Alumno(f"a{next(self._ids)}", apellido_paterno, apellido_materno, nombres,
                   matricula, edad, tutor, "en_curso", semestre=semestre, correo=correo)
        self.alumnos[matricula] = a
        return a

    def actualizar_datos(self, alumno_id, edad, tutor, semestre, correo):
        for m, a in self.alumnos.items():
            if a.id == alumno_id:
                self.alumnos[m] = replace(a, edad=edad, tutor=tutor, semestre=semestre, correo=correo)

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

    # --- envío del reporte por correo ---
    def _cambiar(self, alumno_id, **campos):
        for m, a in self.alumnos.items():
            if a.id == alumno_id:
                self.alumnos[m] = replace(a, **campos)

    def reservar_envio(self, alumno_id, ahora, vencido_antes):
        a = next((x for x in self.alumnos.values() if x.id == alumno_id), None)
        if a is None:
            return False
        libre = a.reporte_estado in ("pendiente", "error") or (
            a.reporte_estado == "enviando" and self.reservas.get(alumno_id, ahora) < vencido_antes)
        if libre:
            self._cambiar(alumno_id, reporte_estado="enviando")
            self.reservas[alumno_id] = ahora
        return libre

    def marcar_enviado(self, alumno_id, ahora):
        self._cambiar(alumno_id, reporte_estado="enviado", reporte_error=None)

    def marcar_error(self, alumno_id, motivo):
        self._cambiar(alumno_id, reporte_estado="error", reporte_error=motivo)

    # --- panel del docente ---
    def listar_alumnos(self):
        return list(self.alumnos.values())

    def listar_autorizados(self):
        return [Autorizado(m, n, "REGULAR") for m, n in (self.autorizadas or {}).items()]

    def reiniciar_alumno(self, alumno_id, test_ids, borrar_registro):
        self.reinicios.append((alumno_id, tuple(test_ids), borrar_registro))
        if borrar_registro:
            self.alumnos = {m: a for m, a in self.alumnos.items() if a.id != alumno_id}
            test_ids = {t for (a, t) in [*self.progreso, *self.respuestas] if a == alumno_id}
        for t in test_ids:
            self.progreso.pop((alumno_id, t), None)
            self.respuestas.pop((alumno_id, t), None)
        self.reservas.pop(alumno_id, None)
        self._cambiar(alumno_id, estado="en_curso", reporte_estado="pendiente", reporte_error=None)

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


class FakeSMTP:
    """Reemplaza a smtplib.SMTP / SMTP_SSL: registra qué se hizo y puede fallar a pedido."""
    instancias: list = []
    mensajes: list = []
    falla: Exception | None = None
    falla_para: set = set()

    def __init__(self, host, port, timeout=None, *, tipo="plain"):
        self.host, self.port, self.timeout, self.tipo = host, port, timeout, tipo
        self.starttls_llamado, self.login_args = False, None
        FakeSMTP.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.starttls_llamado = True

    def login(self, usuario, contrasena):
        self.login_args = (usuario, contrasena)
        if FakeSMTP.falla and isinstance(FakeSMTP.falla, smtplib.SMTPAuthenticationError):
            raise FakeSMTP.falla

    def send_message(self, msg):
        if FakeSMTP.falla and not isinstance(FakeSMTP.falla, smtplib.SMTPAuthenticationError):
            raise FakeSMTP.falla
        if msg["To"] in FakeSMTP.falla_para:
            raise smtplib.SMTPRecipientsRefused({msg["To"]: (550, b"no existe")})
        FakeSMTP.mensajes.append(msg)
