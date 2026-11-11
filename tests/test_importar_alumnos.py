import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importar_alumnos_autorizados import leer_lista  # noqa: E402

TABLA = """# Título
| N° | Matrícula | Nombre del alumno | Sexo | Fecha de pago | Estatus |
| --: | :-- | :-- | :-: | :-: | :-- |
| 1 | 177195 | AGUILAR VELASCO ALANN JOSUE | M | 09/08/26 | IRREGULAR |
| 2 | 38974 | BAUTISTA CABAÑAS SALVADOR | M | 26/08/26 | IRREGULAR |
| 4 | 12A456 | MATRICULA CON LETRA | F | 26/08/26 | REGULAR |
| 3 | 181462 | VENTURA GONZALEZ ROSALBA | F | 11/08/26 | REGULAR  |
"""


def test_lee_filas_validas_incluida_la_de_5_digitos_y_avisa_de_las_no_numericas():
    filas, avisos = leer_lista(TABLA)
    assert [f["matricula"] for f in filas] == ["177195", "38974", "181462"]
    assert filas[2] == {"matricula": "181462", "nombre": "VENTURA GONZALEZ ROSALBA",
                        "sexo": "F", "estatus": "REGULAR"}
    assert len(avisos) == 1 and "12A456" in avisos[0]  # la de 5 dígitos sí se carga
