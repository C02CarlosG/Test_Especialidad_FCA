from unittest.mock import MagicMock

import pytest
from postgrest.exceptions import APIError

from datetime import datetime, timezone

from modules.acceso import MatriculaDuplicada
from modules.db import SupabaseRepo


def _ejecuta(error=None, data=None):
    cliente = MagicMock()
    ejecutar = cliente.table.return_value.insert.return_value.execute
    if error:
        ejecutar.side_effect = error
    else:
        ejecutar.return_value.data = data
    return cliente


def test_unique_violation_se_traduce_a_matricula_duplicada():
    err = APIError({"code": "23505", "message": "duplicate key", "details": "", "hint": ""})
    with pytest.raises(MatriculaDuplicada):
        SupabaseRepo(_ejecuta(error=err)).crear_alumno("P", "M", "N", "M1", 20, "T", datetime.now(timezone.utc))


def test_otros_errores_de_bd_se_propagan():
    err = APIError({"code": "42501", "message": "denied", "details": "", "hint": ""})
    with pytest.raises(APIError):
        SupabaseRepo(_ejecuta(error=err)).crear_alumno("P", "M", "N", "M1", 20, "T", datetime.now(timezone.utc))


def test_crear_alumno_envia_aceptacion_de_privacidad():
    fila = {"id": "1", "apellido_paterno": "P", "apellido_materno": "M", "nombres": "N",
            "matricula": "M1", "edad": 20, "tutor": "T", "estado": "en_curso"}
    cliente = _ejecuta(data=[fila])
    ahora = datetime(2026, 10, 14, tzinfo=timezone.utc)
    a = SupabaseRepo(cliente).crear_alumno("P", "M", "N", "M1", 20, "T", ahora, correo="a@b.com")
    enviado = cliente.table.return_value.insert.call_args.args[0]
    assert enviado["acepto_privacidad"] is True and enviado["acepto_en"] == ahora.isoformat()
    assert enviado["edad"] == 20 and enviado["tutor"] == "T" and enviado["correo"] == "a@b.com"
    assert a.estado == "en_curso"


def test_actualizar_datos_envia_edad_tutor_semestre_y_correo():
    cliente = MagicMock()
    SupabaseRepo(cliente).actualizar_datos("id1", 21, "Mtra. Gómez", 6, "a@b.com")
    tabla = cliente.table
    tabla.assert_called_with("alumnos")
    actualizar = tabla.return_value.update
    actualizar.assert_called_once_with({"edad": 21, "tutor": "Mtra. Gómez", "semestre": 6, "correo": "a@b.com"})
    actualizar.return_value.eq.assert_called_once_with("id", "id1")


def _cliente_reserva(filas):
    cliente = MagicMock()
    cliente.table.return_value.update.return_value.eq.return_value.or_.return_value.execute.return_value.data = filas
    return cliente


def test_reservar_envio_filtra_por_estado_y_devuelve_true_si_tomo_la_fila():
    cliente = _cliente_reserva([{"id": "x"}])
    ahora = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
    vencido = datetime(2026, 11, 12, 17, 50, tzinfo=timezone.utc)
    assert SupabaseRepo(cliente).reservar_envio("x", ahora, vencido) is True
    update = cliente.table.return_value.update
    assert update.call_args.args[0] == {"reporte_estado": "enviando", "reporte_reservado_en": ahora.isoformat()}
    cliente.table.return_value.update.return_value.eq.assert_called_once_with("id", "x")
    filtro = cliente.table.return_value.update.return_value.eq.return_value.or_.call_args.args[0]
    assert "reporte_estado.in.(pendiente,error)" in filtro
    assert f"reporte_reservado_en.lt.{vencido.isoformat()}" in filtro


def test_reservar_envio_devuelve_false_si_otro_ya_lo_tomo():
    assert SupabaseRepo(_cliente_reserva([])).reservar_envio(
        "x", datetime.now(timezone.utc), datetime.now(timezone.utc)) is False


def test_marcar_enviado_y_marcar_error_actualizan_el_estado():
    cliente = MagicMock()
    ahora = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
    repo = SupabaseRepo(cliente)
    repo.marcar_enviado("x", ahora)
    cliente.table.return_value.update.assert_called_with(
        {"reporte_estado": "enviado", "reporte_enviado_en": ahora.isoformat(), "reporte_error": None})
    repo.marcar_error("x", "No se pudo conectar con el servidor de correo.")
    cliente.table.return_value.update.assert_called_with(
        {"reporte_estado": "error", "reporte_error": "No se pudo conectar con el servidor de correo."})


def test_reiniciar_alumno_devuelve_el_reporte_a_pendiente():
    cliente = MagicMock()
    SupabaseRepo(cliente).reiniciar_alumno("x", ["t1"], False)
    cliente.table.return_value.update.assert_called_once_with(
        {"estado": "en_curso", "reporte_estado": "pendiente", "reporte_enviado_en": None,
         "reporte_reservado_en": None, "reporte_error": None})
