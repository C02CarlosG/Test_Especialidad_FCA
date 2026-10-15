import io
import shutil
import struct
import subprocess

import pytest

from modules.qr_utils import UrlInvalida, qr_png, validar_url

URL = "https://test-especialidad-fca.streamlit.app"


def _dim(png):
    return struct.unpack(">II", png[16:24])


def test_png_cuadrado_y_de_alta_resolucion():
    png = qr_png(URL)
    assert png.startswith(b"\x89PNG")
    w, h = _dim(png)
    assert w == h and w >= 1200


def test_el_lado_es_multiplo_entero_de_los_modulos():
    import qrcode
    from qrcode.constants import ERROR_CORRECT_Q
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_Q, border=4, box_size=1)
    qr.add_data(URL); qr.make(fit=True)
    w, _ = _dim(qr_png(URL))
    assert w % (qr.modules_count + 8) == 0  # módulos nítidos al imprimir


@pytest.mark.skipif(not shutil.which("zbarimg"), reason="zbarimg no está instalado")
@pytest.mark.parametrize("url", [URL, "https://a.streamlit.app/?x=1&y=%C3%B1", "https://" + "x" * 60 + ".streamlit.app"])
def test_el_qr_se_decodifica_a_la_misma_url(url, tmp_path):
    (tmp_path / "q.png").write_bytes(qr_png(url))
    salida = subprocess.run(["zbarimg", "--quiet", "--raw", str(tmp_path / "q.png")], capture_output=True, text=True)
    assert salida.stdout.strip() == url


@pytest.mark.parametrize("url", [
    "", "   ", "mi-app.streamlit.app", "http://mi-app.streamlit.app", "ftp://x.com", "https://",
    "https://a b.com", "https://a.streamlit.app/ñ", "https://user:pw@x.com", "javascript:alert(1)", "https://" + "a" * 600 + ".com",
])
def test_urls_rechazadas(url):
    with pytest.raises(UrlInvalida):
        validar_url(url)


def test_http_solo_en_localhost():
    assert validar_url("http://localhost:8503") == "http://localhost:8503"
    assert validar_url("  https://x.streamlit.app ") == "https://x.streamlit.app"
