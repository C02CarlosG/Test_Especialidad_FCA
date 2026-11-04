"""Gráficas del informe (PNG en memoria) con los colores de la marca. Las usan la pantalla y el PDF."""
from __future__ import annotations

import io
from math import pi

from modules.interpretacion import Informe, lectura_campo

MARINO, MARINO_2, ORO, AZUL, VERDE, PIZARRA, LINEA, TINTA = (
    "#0F1E4A", "#1B2F6B", "#E5B300", "#2552D0", "#2FB35F", "#A9B4CE", "#D6DDEB", "#1E2A4A")


def _png(fig) -> bytes:
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _corto(nombre: str) -> str:
    return nombre.split(" / ")[0].replace(" a la Experiencia", "").replace(" Emocional", " emocional")


def grafica_ocean(informe: Informe) -> bytes | None:
    """Radar de los rasgos Big Five. None con menos de 3 rasgos con dato."""
    rasgos = [r for r in informe.rasgos if r.porcentaje is not None]
    if len(rasgos) < 3:
        return None
    plt = _mpl()
    n = len(rasgos)
    ang = [i / n * 2 * pi for i in range(n)]
    val = [float(r.porcentaje) * 100 for r in rasgos]
    fig, ax = plt.subplots(figsize=(4.6, 4.2), subplot_kw={"projection": "polar"})
    ax.set_theta_offset(pi / 2)
    ax.set_theta_direction(-1)
    ax.plot(ang + ang[:1], val + val[:1], color=AZUL, linewidth=2.4)
    ax.fill(ang + ang[:1], val + val[:1], color=AZUL, alpha=0.18)
    ax.scatter(ang, val, s=34, color="white", edgecolor=AZUL, linewidth=1.8, zorder=3)
    ax.set_xticks(ang)
    ax.set_xticklabels([f"{_corto(r.nombre)}\n{round(v)} %" for r, v in zip(rasgos, val)], fontsize=8.5, color=MARINO)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels([])
    ax.grid(color=LINEA)
    ax.spines["polar"].set_color(LINEA)
    return _png(fig)


def grafica_campos(informe: Informe) -> bytes | None:
    """Barras con los puntos del test de competencias por campo; en verde, el campo (o campos) con más puntos."""
    campos = [c for c in informe.campos if c.puntos is not None]
    if not campos:
        return None
    plt = _mpl()
    maximo = max(c.maximo for c in campos)
    fig, ax = plt.subplots(figsize=(5.0, 4.0))
    mejor = max(c.puntos for c in campos)
    colores = [VERDE if c.puntos == mejor else PIZARRA for c in campos]
    barras = ax.bar(range(len(campos)), [c.puntos for c in campos], color=colores, width=0.62)
    for b, c in zip(barras, campos):
        ax.text(b.get_x() + b.get_width() / 2, c.puntos + maximo * 0.015, f"{c.puntos} pts", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=TINTA)
    ax.set_xticks(range(len(campos)))
    ax.set_xticklabels([c.nombre for c in campos], rotation=28, ha="right", fontsize=8.5, color="#5A6788")
    ax.set_ylim(0, maximo * 1.15)
    ax.set_ylabel(f"Puntaje (máx. {maximo})", fontsize=8.5, color="#5A6788")
    ax.grid(axis="y", color="#E1E6F0")
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(axis="y", labelsize=8, colors="#5A6788")
    return _png(fig)


def grafica_convergencia(informe: Informe) -> bytes | None:
    """Tabla con barras: personalidad, competencias y promedio por campo, y si los dos tests coinciden."""
    campos = list(informe.ranking)
    if not campos:
        return None
    plt = _mpl()
    from matplotlib.patches import FancyBboxPatch, Rectangle
    n = len(campos)
    fig, ax = plt.subplots(figsize=(8.4, 0.62 * n + 1.0))
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, n + 1.1)
    ax.add_patch(Rectangle((0, n + 0.1), 100, 0.9, color=MARINO))
    ax.text(1.5, n + 0.55, "Campo formativo", color="w", fontsize=9.5, fontweight="bold", va="center")
    columnas = ((34, "Personalidad"), (51, "Competencias"), (68, "Promedio"), (85, "Lectura"))
    for x, t in columnas:
        ax.text(x, n + 0.55, t, color="w", fontsize=9.5, fontweight="bold", va="center")

    def barra(x, y, v, color):
        if v is None:
            ax.text(x, y, "Sin datos", fontsize=8.5, va="center", color="#5A6788")
            return
        pct = float(v) * 100
        ax.add_patch(FancyBboxPatch((x, y - 0.12), 10, 0.24, boxstyle="round,pad=0,rounding_size=0.12", fc="#E3E9F4", ec="none"))
        ax.add_patch(FancyBboxPatch((x, y - 0.12), 10 * min(pct, 100) / 100, 0.24, boxstyle="round,pad=0,rounding_size=0.12", fc=color, ec="none"))
        ax.text(x + 10.8, y, f"{round(pct)} %", fontsize=9, va="center", color=MARINO)

    for i, c in enumerate(campos):
        y = n - i - 0.4
        if i % 2 == 0:
            ax.add_patch(Rectangle((0, y - 0.5), 100, 1, color="#F6F8FD", zorder=0))
        ax.text(1.5, y, c.nombre, fontsize=9, fontweight="bold", color=MARINO, va="center")
        barra(34, y, c.por_rasgos, ORO)
        barra(51, y, c.por_competencias, MARINO_2)
        barra(68, y, c.promedio, VERDE if i == 0 else PIZARRA)
        texto, coincide = lectura_campo(c)
        ax.text(85, y, texto, fontsize=8.5, va="center", fontweight="bold", color="#17803F" if coincide else "#8A5A00")
    return _png(fig)
