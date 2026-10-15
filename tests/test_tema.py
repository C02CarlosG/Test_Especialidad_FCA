import re
from fractions import Fraction
from pathlib import Path

from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent


def _html(fn):
    at = AppTest.from_function(fn, default_timeout=30).run()
    assert not at.exception
    return [h.value for h in at.get("html")]


def test_el_camino_marca_hecho_actual_y_pendiente():
    def a0():
        from types import SimpleNamespace
        from views import tema
        tema.cabecera((SimpleNamespace(titulo="Test 1: A"), SimpleNamespace(titulo="Test 2: B")), 0)

    def a2():
        from types import SimpleNamespace
        from views import tema
        tema.cabecera((SimpleNamespace(titulo="Test 1: A"), SimpleNamespace(titulo="Test 2: B")), 2)

    def a3():
        from types import SimpleNamespace
        from views import tema
        tema.cabecera((SimpleNamespace(titulo="Test 1: A"), SimpleNamespace(titulo="Test 2: B")), 3)

    clases = lambda h: re.findall(r'<li class="(\w+)"', h)  # noqa: E731
    h0, h2, h3 = _html(a0)[0], _html(a2)[0], _html(a3)[0]
    assert clases(h0) == ["actual", "pendiente", "pendiente", "pendiente"]
    assert clases(h2) == ["hecho", "hecho", "actual", "pendiente"]
    assert clases(h3) == ["hecho", "hecho", "hecho", "actual"]
    assert h2.count('aria-current="step"') == 1 and "Registro" in h2 and "Test 1" in h2 and "Resultados" in h2
    assert 'aria-label="Progreso de la evaluación"' in h0 and "Facultad de Contaduría y Administración" in h0
    # un logo a cada lado: FCA a la izquierda y UABJO a la derecha, con texto alternativo
    assert h0.index("logo_fca.png") < h0.index('class="inst"') < h0.index("logo_uabjo.png")
    assert 'alt="Facultad de Contaduría y Administración, Calidad Académica"' in h0
    assert "Universidad Autónoma Benito Juárez de Oaxaca" in h0


def test_los_textos_de_datos_se_escapan(tmp_path):
    guion = tmp_path / "datos_raros.py"
    guion.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(RAIZ)!r})\n"
        "from types import SimpleNamespace\n"
        "from views import tema\n"
        "tema.tabla(['<b>x</b>'], [['&lt;img src=x onerror=alert(1)&gt;']])\n"
        "tema.tarjetas_resumen([{'titulo': '<script>1</script>', 'primera': 'A & B <i>', 'segunda': '<u>C</u>', 'nota': '<n>'}])\n"
        "tema.pregunta(1, '¿<script>alert(1)</script>?')\n"
        "tema.cabecera((SimpleNamespace(titulo='<svg onload=1>: x'),), 0)\n", encoding="utf-8")
    at = AppTest.from_file(str(guion), default_timeout=30).run()
    assert not at.exception
    html = "".join(h.value for h in at.get("html"))
    etiquetas = set(re.findall(r"<\s*/?\s*([a-zA-Z][\w-]*)", html))
    # solo las etiquetas que genera tema.py; nada de lo que vino en los datos
    assert etiquetas <= {"div", "span", "p", "nav", "ol", "li", "section", "table", "thead", "tbody", "tr", "th", "td", "b", "i", "img"}
    assert not {"script", "svg", "u", "n"} & etiquetas
    assert html.count("<img ") == 2 and "onerror" not in html.replace("&lt;img src=x onerror=alert(1)&gt;", "")  # solo los 2 logos
    assert "&lt;script&gt;" in html and "A &amp; B &lt;i&gt;" in html and "&lt;svg onload=1&gt;" in html
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_chips_y_barras():
    from views.tema import chip, porcentaje
    assert 'chip alto' in chip("ALTO (Perfil Fuerte)") and 'chip alto' in chip("Alta Afinidad")
    assert 'chip medio' in chip("Medio") and 'chip medio' in chip("MEDIO (En Desarrollo)") and 'chip medio' in chip("Afinidad Media")
    assert 'chip bajo' in chip("Área de Desarrollo") and 'chip bajo' in chip("BAJO (Baja Afinidad)")
    assert chip(None) == "—"
    assert 'width:75.0%' in porcentaje(Fraction(3, 4)) and "75.0 %" in porcentaje(Fraction(3, 4))
    assert porcentaje(None) == "Sin datos"
    assert "width:100.0%" in porcentaje(Fraction(3, 2))  # nunca desborda


def test_la_hoja_de_estilos_no_tiene_llaves_sin_cerrar_ni_oro_como_texto():
    from pathlib import Path
    css = (Path(__file__).resolve().parent.parent / "views" / "tema.css").read_text(encoding="utf-8")
    assert css.count("{") == css.count("}")
    assert "prefers-reduced-motion" in css and ":focus-visible" in css
    # el oro es acento (fondos, bordes, contornos), nunca el color de un texto (no contrasta con blanco)
    assert not re.search(r"(?<![-\w])color:\s*var\(--oro\)", css)


def test_el_tema_define_la_paleta_y_oculta_la_barra_de_streamlit():
    import tomllib
    from pathlib import Path
    cfg = tomllib.loads((Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml").read_text())
    assert cfg["theme"]["base"] == "light" and cfg["theme"]["primaryColor"] == "#0F1E4A"
    assert cfg["client"]["toolbarMode"] == "minimal" and cfg["browser"]["gatherUsageStats"] is False
    assert "googleapis" not in str(cfg) and "http" not in cfg["theme"]["font"]  # sin fuentes de terceros


def test_los_logos_existen_son_ligeros_y_se_sirven_como_archivos_estaticos():
    import tomllib
    from PIL import Image
    from views import tema
    for url, ancho, alto, _alt in (tema.LOGO_FCA, tema.LOGO_UABJO):
        archivo = RAIZ / "static" / url.rsplit("/", 1)[1]
        assert archivo.is_file() and archivo.stat().st_size < 60_000
        im = Image.open(archivo)
        assert im.size == (ancho, alto)  # width/height del HTML = tamaño real: sin saltos al cargar
        assert "A" in im.convert("RGBA").getbands() and im.convert("RGBA").getchannel("A").getextrema()[0] == 0  # fondo transparente
    cfg = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text())
    assert cfg["server"]["enableStaticServing"] is True and url.startswith("/app/static/")
