import pytest

from modules import security as sec


BASE = dict(apellido_paterno="Pérez", apellido_materno="López", nombres="Ana María",
            matricula="123456", edad=20, tutor="Mtro. Juan Ruiz")


def test_datos_validos_se_normalizan():
    v, e = sec.validar_datos("  Pérez ", "López  ", " Ana   María ", " 123456 ", 20,
                             "  Mtro.  Juan Ruiz ")
    assert e == {}
    assert v == {"apellido_paterno": "Pérez", "apellido_materno": "López", "nombres": "Ana María",
                 "matricula": "123456", "edad": 20, "tutor": "Mtro. Juan Ruiz"}


@pytest.mark.parametrize("campo,valor", [
    ("apellido_paterno", ""), ("apellido_paterno", "123"), ("apellido_materno", "   "),
    ("nombres", ""), ("nombres", "A" * 81),
    ("matricula", ""), ("matricula", "12345"), ("matricula", "1234567"), ("matricula", "12345a"),
    ("matricula", "12 456"), ("matricula", "12-456"), ("matricula", "١٢٣٤٥٦"),
    ("edad", None), ("edad", 17), ("edad", 0), ("edad", 100),
    ("tutor", ""), ("tutor", "..."),
])
def test_campos_invalidos(campo, valor):
    _, errores = sec.validar_datos(**{**BASE, campo: valor})
    assert list(errores) == [campo]


def test_edad_limite_es_valida():
    assert sec.validar_datos(**{**BASE, "edad": 18})[1] == {}
    assert "mayores de 18" in sec.validar_datos(**{**BASE, "edad": 17})[1]["edad"]


def test_clave_cliente_no_guarda_la_ip():
    k = sec.clave_cliente("203.0.113.9")
    assert k.startswith("ip:") and "203" not in k
    assert k == sec.clave_cliente(" 203.0.113.9 ")
