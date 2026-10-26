# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib"]
# ///
"""Gera ufs.png a partir de candidatos_uf.csv: onde estavam os votos depois das 17h e quem venceu em cada UF."""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

DIR = os.path.dirname(os.path.abspath(__file__))
COR = {"Flávio": "#2a78d6", "Lula": "#eb6834"}
TINTA, TINTA2, MUDA, GRADE, FUNDO = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"


def br(n, d=0):
    return f"{n:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


linhas = list(csv.DictReader(open(f"{DIR}/candidatos_uf.csv")))
for x in linhas:
    for k in ("urnas", "urnas_estendidas", "votos_apos_17h", "est_lula", "est_flavio", "uf_votos_lula", "uf_votos_flavio"):
        x[k] = int(x[k])
    x["uf_pct_lula"] = float(x["uf_pct_lula"])
total = sum(x["votos_apos_17h"] for x in linhas)
por_venc = {v: sum(x["votos_apos_17h"] for x in linhas if x["vencedor_uf"] == v) for v in COR}
est_l, est_f = sum(x["est_lula"] for x in linhas), sum(x["est_flavio"] for x in linhas)

plt.rcParams.update({"font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"], "text.color": TINTA})
fig = plt.figure(figsize=(11, 9.6), dpi=200, facecolor=FUNDO)
ax = fig.add_axes([0.07, 0.125, 0.44, 0.635], facecolor=FUNDO)

n = len(linhas)
y = list(range(n))[::-1]
xmax = max(x["votos_apos_17h"] for x in linhas)
ax.barh(y, [x["votos_apos_17h"] for x in linhas], height=0.62, color=[COR[x["vencedor_uf"]] for x in linhas], zorder=2)
for yi, x in zip(y, linhas):
    ax.text(x["votos_apos_17h"] + xmax * 0.015, yi, br(x["votos_apos_17h"]), va="center", fontsize=9, color=TINTA)
ax.set_yticks(y, [x["uf"] for x in linhas], fontsize=9.5, color=TINTA)
ax.set_xlim(0, xmax * 1.14)
ax.set_ylim(-0.7, n - 0.3)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: br(v)))
ax.tick_params(axis="x", colors=MUDA, labelsize=8.5, length=0)
ax.tick_params(axis="y", length=0, pad=6)
ax.grid(axis="x", color=GRADE, linewidth=0.8, zorder=0)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color("#c3c2b7")
ax.set_xlabel("Votos depois das 17h nas urnas estendidas", fontsize=9, color=TINTA2, labelpad=8)

# colunas de texto à direita, alinhadas às barras
col = {"est": 0.6, "estim": 0.665, "venc": 0.845}
yfig = lambda yi: fig.transFigure.inverted().transform(ax.transData.transform((0, yi)))[1]
cab = yfig(n - 0.3) + 0.012
fig.text(col["est"], cab, "Urnas\nestendidas", fontsize=8.5, color=TINTA2, ha="right", va="bottom", linespacing=1.2)
fig.text(col["estim"], cab, "Estimativa dos votos tardios\nLula · Flávio", fontsize=8.5, color=TINTA2, ha="left", va="bottom", linespacing=1.2)
fig.text(col["venc"], cab, "Quem venceu\nna UF", fontsize=8.5, color=TINTA2, ha="left", va="bottom", linespacing=1.2)
for yi, x in zip(y, linhas):
    yy = yfig(yi)
    pct = 100 * x["urnas_estendidas"] / x["urnas"]
    fig.text(col["est"], yy, f"{br(x['urnas_estendidas'])}  ({br(pct, 1) if pct >= 0.05 else '<0,1'}%)", fontsize=9, color=TINTA, ha="right", va="center")
    fig.text(col["estim"], yy, f"{br(x['est_lula'])} · {br(x['est_flavio'])}", fontsize=9, color=TINTA, ha="left", va="center")
    v = x["vencedor_uf"]
    pv = x["uf_pct_lula"] if v == "Lula" else 100 - x["uf_pct_lula"]
    fig.patches.append(matplotlib.patches.Circle((col["venc"] + 0.006, yy), 0.0055, color=COR[v], transform=fig.transFigure, figure=fig))
    fig.text(col["venc"] + 0.018, yy, f"{v} {br(pv, 1)}%", fontsize=9, color=TINTA, ha="left", va="center")

fig.text(0.07, 0.955, "Onde estavam as urnas que receberam votos depois das 17h", fontsize=16, weight="bold", color=TINTA)
fig.text(0.07, 0.928, "2º turno de 2026 (25/10) · urnas que encerraram depois das 17h45 de Brasília · sem o exterior · cor da barra = quem venceu na UF",
         fontsize=9.5, color=TINTA2)
destaques = [
    (br(total), "votos depois das 17h"),
    (f"{br(100 * por_venc['Flávio'] / total)}%", "deles em UFs vencidas por Flávio"),
    (f"{br(est_l)} · {br(est_f)}", "estimativa Lula · Flávio"),
]
for i, (val, rot) in enumerate(destaques):
    xx = 0.07 + i * 0.29
    fig.text(xx, 0.855, val, fontsize=22, weight="bold", color=TINTA)
    fig.text(xx, 0.833, rot, fontsize=9, color=TINTA2)
fig.legend(handles=[Patch(color=COR["Lula"], label="UF vencida por Lula"), Patch(color=COR["Flávio"], label="UF vencida por Flávio")],
           loc="upper left", bbox_to_anchor=(0.065, 0.815), ncol=2, frameon=False, fontsize=9, handlelength=1.1, handleheight=1.1, labelcolor=TINTA)
fig.text(0.07, 0.022,
         "O log da urna registra a hora de cada voto, mas não o candidato. A estimativa divide os votos tardios de cada seção na proporção do Boletim de Urna\n"
         "daquela seção (supõe que quem votou tarde votou como o resto da seção). Fonte: TSE, resultados.tse.jus.br (logs, BUs e resultado por UF).",
         fontsize=7.8, color=MUDA, linespacing=1.4)
fig.savefig(f"{DIR}/ufs.png", facecolor=FUNDO)
print(f"{DIR}/ufs.png")
