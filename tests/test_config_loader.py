from pathlib import Path

import pandas as pd
import pytest

from modules.config_loader import ConfigError, load_test_config

EJEMPLO = Path(__file__).resolve().parent.parent / "config" / "test.xlsx"


def _escribir(ruta, esp=None, pre=None, esc=None, omitir=()):
    esp = esp if esp is not None else [
        ("A", "Esp A", "d", "p"), ("B", "Esp B", "d", "p")]
    pre = pre if pre is not None else [
        ("P1", 1, "t1", "A", "NO"), ("P2", 1, "t2", "B", "SI")]
    esc = esc if esc is not None else [(1, "no"), (2, "neutral"), (3, "si")]
    hojas = {
        "especialidades": pd.DataFrame(esp, columns=["codigo", "nombre", "descripcion", "perfil_profesional"]),
        "preguntas": pd.DataFrame(pre, columns=["id", "bloque", "texto", "especialidad_codigo", "invertida"]),
        "escala": pd.DataFrame(esc, columns=["valor", "etiqueta"]),
    }
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        for nombre, df in hojas.items():
            if nombre not in omitir:
                df.to_excel(w, sheet_name=nombre, index=False)
    return ruta


def _errores(ruta) -> str:
    with pytest.raises(ConfigError) as exc:
        load_test_config(ruta)
    return "\n".join(exc.value.errores)


def test_ejemplo_valido():
    cfg = load_test_config(EJEMPLO)
    assert len(cfg.especialidades) == 3
    assert len(cfg.preguntas) == 12
    assert (cfg.valor_min, cfg.valor_max) == (1, 5)
    assert cfg.bloques == [1, 2]
    assert len(cfg.preguntas_de_bloque(1)) == 10
    assert sum(p.invertida for p in cfg.preguntas) == 2
    assert all("EJEMPLO" in e.nombre for e in cfg.especialidades)


def test_valido_minimo(tmp_path):
    cfg = load_test_config(_escribir(tmp_path / "t.xlsx"))
    assert cfg.preguntas[1].invertida and not cfg.preguntas[0].invertida
    assert len(cfg.version) == 16


def test_version_cambia_con_el_contenido(tmp_path):
    a = load_test_config(_escribir(tmp_path / "a.xlsx"))
    b = load_test_config(_escribir(tmp_path / "b.xlsx", esc=[(1, "x"), (2, "y")]))
    assert a.version != b.version


def test_archivo_inexistente(tmp_path):
    assert "No se encontró" in _errores(tmp_path / "nada.xlsx")


def test_archivo_no_excel(tmp_path):
    ruta = tmp_path / "t.xlsx"
    ruta.write_text("no soy un excel")
    assert "No se pudo abrir" in _errores(ruta)


def test_falta_hoja(tmp_path):
    msg = _errores(_escribir(tmp_path / "t.xlsx", omitir=("escala",)))
    assert "Falta la hoja 'escala'" in msg


def test_falta_columna(tmp_path):
    ruta = tmp_path / "t.xlsx"
    _escribir(ruta)
    with pd.ExcelWriter(ruta, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        pd.DataFrame({"valor": [1, 2]}).to_excel(w, sheet_name="escala", index=False)
    assert "no tiene las columnas: etiqueta" in _errores(ruta)


def test_id_pregunta_repetido(tmp_path):
    pre = [("P1", 1, "t", "A", "NO"), ("P1", 1, "t", "B", "NO")]
    assert "id repetido 'P1'" in _errores(_escribir(tmp_path / "t.xlsx", pre=pre))


def test_codigo_especialidad_repetido(tmp_path):
    esp = [("A", "x", "d", "p"), ("A", "y", "d", "p")]
    assert "código repetido 'A'" in _errores(_escribir(tmp_path / "t.xlsx", esp=esp))


def test_pregunta_con_especialidad_inexistente(tmp_path):
    pre = [("P1", 1, "t", "A", "NO"), ("P2", 1, "t", "ZZZ", "NO")]
    assert "la especialidad 'ZZZ' no existe" in _errores(_escribir(tmp_path / "t.xlsx", pre=pre))


def test_especialidad_sin_preguntas(tmp_path):
    pre = [("P1", 1, "t", "A", "NO")]
    assert "'B' no tiene ninguna pregunta" in _errores(_escribir(tmp_path / "t.xlsx", pre=pre))


def test_invertida_invalida(tmp_path):
    pre = [("P1", 1, "t", "A", "TAL VEZ"), ("P2", 1, "t", "B", "NO")]
    assert "SI o NO" in _errores(_escribir(tmp_path / "t.xlsx", pre=pre))


def test_bloque_invalido(tmp_path):
    pre = [("P1", "uno", "t", "A", "NO"), ("P2", 1, "t", "B", "NO")]
    assert "'bloque'" in _errores(_escribir(tmp_path / "t.xlsx", pre=pre))


def test_escala_no_consecutiva(tmp_path):
    assert "consecutivos" in _errores(_escribir(tmp_path / "t.xlsx", esc=[(1, "a"), (3, "b")]))


def test_escala_demasiado_corta(tmp_path):
    assert "al menos 2 valores" in _errores(_escribir(tmp_path / "t.xlsx", esc=[(1, "a")]))


def test_reporta_todos_los_errores_juntos(tmp_path):
    pre = [("P1", 1, "t", "ZZZ", "NO"), ("P1", 1, "", "A", "X")]
    with pytest.raises(ConfigError) as exc:
        load_test_config(_escribir(tmp_path / "t.xlsx", pre=pre))
    assert len(exc.value.errores) >= 3
