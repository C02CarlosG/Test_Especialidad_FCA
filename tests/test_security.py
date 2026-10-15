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
    ("tutor", ""), ("tutor", "..."), ("tutor", "=HYPERLINK(1)"), ("nombres", "+52 Ana"), ("apellido_paterno", "@x"),
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


def test_los_caracteres_de_control_se_eliminan_antes_de_validar():
    v, e = sec.validar_datos("Pérez", "López", "Ana\x01 Mar\x1bía\x08", "123456", 20, "Mtro.\x07 Ruiz")
    assert e == {} and v["nombres"] == "Ana María" and v["tutor"] == "Mtro. Ruiz"


def test_un_nombre_solo_de_control_es_invalido():
    _, e = sec.validar_datos("\x01\x02", "López", "Ana", "123456", 20, "Tutor X")
    assert "apellido_paterno" in e


@pytest.mark.parametrize("sucio,limpio", [
    ("Ab\ufffe\uffffC", "AbC"),          # no-caracteres: dejan XML mal formado en el Excel
    ("Ana\ud800 Mar\udfffía", "Ana María"),  # sustitutos sueltos
    ("Ana\u0378Pérez", "AnaPérez"),       # sin asignar (Cn)
    ("Ana\x00\x01 María", "Ana María"),  # control
    ("José  Ñandú\t Díaz", "José Ñandú Díaz"),
    ("Ana\u200dMaría", "Ana\u200dMaría"),   # formato (ZWJ) se conserva
])
def test_normalizar_texto_quita_caracteres_no_validos(sucio, limpio):
    assert sec.normalizar_texto(sucio) == limpio


def test_un_nombre_con_no_caracteres_se_guarda_limpio():
    v, e = sec.validar_datos("Pérez\ufffe", "López", "Ana\uffff", "123456", 20, "Mtro. \ufffeRuiz")
    assert e == {} and (v["apellido_paterno"], v["nombres"], v["tutor"]) == ("Pérez", "Ana", "Mtro. Ruiz")
