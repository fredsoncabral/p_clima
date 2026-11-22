"""Gráfico: temperatura média no Brasil nos últimos 6 meses + tendência para os próximos 3 meses.

Método (transparente e reproduzível):
  * Conjunto fixo de estações: com temperatura válida nos 6 últimos meses observados e normal nos 12 meses
    (evita que a média oscile por mudança de composição da rede).
  * Observado: média mensal dessas estações (gold_clima_anomalia_mensal_estacao).
  * Tendência: normal 2001–2025 das mesmas estações + anomalia composta dos análogos de El Niño
    forte/muito forte no mesmo mês do calendário (2009-10, 2015-16, 2023-24). Faixa = mínimo–máximo dos análogos.
  * É uma TENDÊNCIA ESTATÍSTICA, não previsão do tempo. Para decisões, use os prognósticos oficiais (INMET/INPE).

Uso:
  export DATABRICKS_CONFIG_PROFILE=<perfil>   # ou DATABRICKS_HOST/DATABRICKS_TOKEN
  export DATABRICKS_WAREHOUSE_ID=<id>
  uv run python scripts/grafico_linkedin.py [--catalog workspace] [--schema clima]
"""

import argparse
import csv
import os
import pathlib
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
from matplotlib.transforms import blended_transform_factory

RAIZ = pathlib.Path(__file__).resolve().parents[1]
ANALOGOS = {"2009-10": 2009, "2015-16": 2015, "2023-24": 2023}  # ano de início de cada El Niño forte

# paleta de referência (skill dataviz): série 1 azul + tinta neutra
SUPERFICIE, TINTA, TINTA_2, GRADE, AZUL, CINZA = "#fcfcfb", "#0b0b0b", "#52514e", "#e7e6e2", "#2a78d6", "#8a8984"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def consultar(w: WorkspaceClient, wh: str, sql: str) -> list[dict]:
    r = w.statement_execution.execute_statement(statement=sql, warehouse_id=wh, wait_timeout="50s")
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{r.status.state}: {r.status.error}")
    cols = [c.name for c in r.manifest.schema.columns]
    return [dict(zip(cols, linha, strict=True)) for linha in (r.result.data_array or [])]


def add_meses(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="workspace")
    ap.add_argument("--schema", default="clima")
    ap.add_argument("--saida", default=str(RAIZ / "docs/img/temperatura_6m_tendencia_3m.png"))
    a = ap.parse_args()
    t = f"`{a.catalog}`.`{a.schema}`"
    w, wh = WorkspaceClient(), os.environ["DATABRICKS_WAREHOUSE_ID"]

    ultimo = date.fromisoformat(consultar(w, wh, f"SELECT max(mes_ref) AS m FROM {t}.gold_clima_anomalia_mensal_estacao")[0]["m"])
    ini = add_meses(ultimo, -5)
    estacoes = f"""
      SELECT cd_estacao FROM {t}.gold_clima_anomalia_mensal_estacao
      WHERE mes_ref BETWEEN '{ini}' AND '{ultimo}' AND temp_media_c IS NOT NULL AND NOT qc_temp_suspeito
      GROUP BY cd_estacao HAVING count(*) = 6
      INTERSECT
      SELECT cd_estacao FROM {t}.gold_clima_normal_mensal_estacao
      WHERE temp_media_normal_c IS NOT NULL GROUP BY cd_estacao HAVING count(*) = 12"""
    n_est = int(consultar(w, wh, f"SELECT count(*) AS n FROM ({estacoes})")[0]["n"])

    obs = consultar(w, wh, f"""
      SELECT a.mes_ref, avg(a.temp_media_c) AS obs, avg(a.temp_media_normal_c) AS normal
      FROM {t}.gold_clima_anomalia_mensal_estacao a JOIN ({estacoes}) s USING (cd_estacao)
      WHERE a.mes_ref BETWEEN '{ini}' AND '{ultimo}' GROUP BY a.mes_ref ORDER BY a.mes_ref""")

    futuros = [add_meses(ultimo, i) for i in (1, 2, 3)]
    normais = {int(r["mes"]): float(r["normal"]) for r in consultar(w, wh, f"""
      SELECT n.mes, avg(n.temp_media_normal_c) AS normal
      FROM {t}.gold_clima_normal_mensal_estacao n JOIN ({estacoes}) s USING (cd_estacao)
      WHERE n.mes IN ({",".join(str(f.month) for f in futuros)}) GROUP BY n.mes""")}

    # anomalia nacional (mesmas estações) em cada análogo, alinhada pelo deslocamento do mês
    datas_analogo = []
    for nome, ano0 in ANALOGOS.items():
        for f in futuros:
            ano = ano0 + (f.year - ultimo.year)
            datas_analogo.append((nome, f.month, date(ano, f.month, 1)))
    lista = ",".join(f"'{d}'" for _, _, d in datas_analogo)
    anom = {r["mes_ref"]: float(r["anom"]) for r in consultar(w, wh, f"""
      SELECT a.mes_ref, avg(a.anomalia_temp_c) AS anom
      FROM {t}.gold_clima_anomalia_mensal_estacao a JOIN ({estacoes}) s USING (cd_estacao)
      WHERE NOT a.qc_temp_suspeito AND a.mes_ref IN ({lista}) GROUP BY a.mes_ref""")}

    proj = []
    for f in futuros:
        valores = [anom[str(d)] for _, m, d in datas_analogo if m == f.month and str(d) in anom]
        media = sum(valores) / len(valores)
        proj.append({"mes_ref": f, "normal": normais[f.month], "anom": media,
                     "centro": normais[f.month] + media,
                     "min": normais[f.month] + min(valores), "max": normais[f.month] + max(valores),
                     "analogos": valores})

    # ------------------------------------------------------------- dados (CSV para transparência)
    csv_path = RAIZ / "docs/analises/dados_grafico_linkedin.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["mes_ref", "tipo", "temp_c", "normal_c", "anomalia_c", "faixa_min_c", "faixa_max_c"])
        for r in obs:
            o, n = float(r["obs"]), float(r["normal"])
            wr.writerow([r["mes_ref"], "observado", f"{o:.2f}", f"{n:.2f}", f"{o - n:+.2f}", "", ""])
        for p in proj:
            wr.writerow([p["mes_ref"], "tendencia_analogos", f"{p['centro']:.2f}", f"{p['normal']:.2f}",
                         f"{p['anom']:+.2f}", f"{p['min']:.2f}", f"{p['max']:.2f}"])

    # ------------------------------------------------------------- gráfico
    x_obs = list(range(6))
    x_proj = [5, 6, 7, 8]  # começa no último observado para a linha ser contínua
    y_obs = [float(r["obs"]) for r in obs]
    y_norm = [float(r["normal"]) for r in obs] + [p["normal"] for p in proj]
    y_proj = [y_obs[-1]] + [p["centro"] for p in proj]
    rotulos = [f"{MESES[d.month - 1]}/{str(d.year)[2:]}" for d in [add_meses(ini, i) for i in range(9)]]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=180)
    fig.patch.set_facecolor(SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)

    ax.axvspan(5.5, 8.4, color=GRADE, alpha=0.35, lw=0)
    ax.fill_between(x_proj[1:], [p["min"] for p in proj], [p["max"] for p in proj], color=AZUL, alpha=0.12, lw=0)
    ax.plot(range(9), y_norm, color=CINZA, lw=2, solid_capstyle="round", label="Normal 2001–2025")
    ax.plot(x_proj, y_proj, color=AZUL, lw=2.4, ls=(0, (4, 3)), marker="o", ms=6, mfc=SUPERFICIE, mew=2,
            label="Tendência (análogos de El Niño forte)")
    ax.plot(x_obs, y_obs, color=AZUL, lw=2.4, marker="o", ms=6, solid_capstyle="round", label="Observado", zorder=3)

    # rótulos seletivos: último observado e pico da tendência
    ax.annotate(f"{y_obs[-1]:.1f} °C".replace(".", ","), (5, y_obs[-1]), xytext=(0, -20), textcoords="offset points",
                ha="center", color=TINTA, fontsize=11, fontweight="bold")
    # maior anomalia observada no período
    i_max = max(range(6), key=lambda i: y_obs[i] - y_norm[i])
    ax.annotate(f"{y_obs[i_max] - y_norm[i_max]:+.1f} °C acima da normal".replace(".", ","), (i_max, y_obs[i_max]),
                xytext=(-30, 22), textcoords="offset points", ha="right", va="bottom", color=TINTA_2, fontsize=10,
                arrowprops={"arrowstyle": "-", "color": CINZA, "lw": 1, "shrinkB": 5})
    i_pico = max(range(3), key=lambda i: proj[i]["centro"])
    p = proj[i_pico]
    ax.annotate(f"{p['centro']:.1f} °C ({p['anom']:+.1f} °C)".replace(".", ","), (6 + i_pico, p["centro"]),
                xytext=(0, 14), textcoords="offset points", ha="center", color=TINTA, fontsize=11, fontweight="bold")
    ax.text(6.7, 0.985, "próximos 3 meses", transform=blended_transform_factory(ax.transData, ax.transAxes),
            color=TINTA_2, fontsize=10, ha="center", va="top")

    ax.set_xticks(range(9), rotulos)
    ax.set_xlim(-0.3, 8.4)
    ax.set_ylabel("Temperatura média mensal (°C)", color=TINTA_2)
    ax.grid(axis="y", color=GRADE, lw=1)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(GRADE)
    ax.tick_params(colors=TINTA_2, length=0)
    handles, labels = ax.get_legend_handles_labels()
    ordem = [labels.index(n) for n in ("Observado", "Tendência (análogos de El Niño forte)", "Normal 2001–2025")]
    ax.legend([handles[i] for i in ordem], [labels[i] for i in ordem],
              loc="upper left", frameon=False, labelcolor=TINTA_2, fontsize=10)

    fig.text(0.06, 0.965, "Temperatura média no Brasil: últimos 6 meses e tendência sob El Niño",
             fontsize=14.5, fontweight="bold", color=TINTA, ha="left")
    fig.text(0.06, 0.925, f"Média de {n_est} estações automáticas do INMET · faixa = mínimo–máximo dos análogos "
             "2009-10, 2015-16 e 2023-24", fontsize=10.5, color=TINTA_2, ha="left")
    fig.text(0.06, 0.02, "Fontes: INMET/BDMEP e NOAA/CPC · Tendência estatística, não é previsão do tempo · "
             "github.com/fredsoncabral/p_clima", fontsize=9, color=TINTA_2, ha="left")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.86, bottom=0.11)
    pathlib.Path(a.saida).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.saida, facecolor=SUPERFICIE)

    print(f"estações: {n_est} | observado {ini}..{ultimo}")
    for r in obs:
        print(f"  {r['mes_ref']}  obs {float(r['obs']):.2f}  normal {float(r['normal']):.2f}")
    for p in proj:
        print(f"  {p['mes_ref']}  tendência {p['centro']:.2f} (anom {p['anom']:+.2f}; "
              f"faixa {p['min']:.2f}–{p['max']:.2f}; análogos {[round(v, 2) for v in p['analogos']]})")
    print(f"gráfico: {a.saida}\ndados: {csv_path}")


if __name__ == "__main__":
    main()
