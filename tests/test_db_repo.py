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
    a = SupabaseRepo(cliente).crear_alumno("P", "M", "N", "M1", 20, "T", ahora)
    enviado = cliente.table.return_value.insert.call_args.args[0]
    assert enviado["acepto_privacidad"] is True and enviado["acepto_en"] == ahora.isoformat()
    assert enviado["edad"] == 20 and enviado["tutor"] == "T" and "correo" not in enviado
    assert a.estado == "en_curso"
