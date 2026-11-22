"""SPI — Standardized Precipitation Index (McKee et al., 1993; método recomendado pela OMM).

Para cada estação, escala k (1, 3, 6, 12 meses) e mês do calendário:
  1. acumula a chuva dos k meses anteriores (só se TODOS os k meses forem válidos —
     ausência de dado não é ausência de chuva);
  2. ajusta uma distribuição gama aos acumulados do período-base 2001–2025 (mínimo 10 anos);
  3. trata zeros com distribuição mista: H(x) = q + (1 - q)·G(x), q = fração de zeros;
     acumulados iguais a zero usam a probabilidade "centro de massa" (Stagge et al., 2015);
  4. transforma H(x) na normal padrão -> SPI.

Classes (OMM): >= 2 extremamente úmido | 1,5–2 muito úmido | 1–1,5 moderadamente úmido |
-1–1 normal | -1,5–-1 seca moderada | -2–-1,5 seca severa | <= -2 seca extrema.
"""

import numpy as np
import pandas as pd
from pyspark import pipelines as dp
from pyspark.sql import functions as F

ESCALAS = (1, 3, 6, 12)
ANO_BASE_INI, ANO_BASE_FIM = 2001, 2025
MIN_ANOS_BASE = 10

SCHEMA_SAIDA = "cd_estacao STRING, mes_ref DATE, escala_meses INT, precip_acumulada_mm DOUBLE, spi DOUBLE"


def _spi_estacao(pdf: pd.DataFrame) -> pd.DataFrame:
    from scipy import stats

    cod = pdf["cd_estacao"].iloc[0]
    pdf = pdf.assign(mes_ref=pd.to_datetime(pdf["mes_ref"])).sort_values("mes_ref")
    meses = pd.date_range(pdf["mes_ref"].min(), pdf["mes_ref"].max(), freq="MS")
    serie = pdf.set_index("mes_ref")["precipitacao_mm"].reindex(meses)  # NaN = mês ausente/inválido

    saidas = []
    for k in ESCALAS:
        acum = serie.rolling(k, min_periods=k).sum()
        spi = pd.Series(np.nan, index=acum.index)
        for mes in range(1, 13):
            sel = acum.index.month == mes
            valores = acum[sel]
            base = valores[(valores.index.year >= ANO_BASE_INI) & (valores.index.year <= ANO_BASE_FIM)].dropna()
            if len(base) < MIN_ANOS_BASE:
                continue
            n, n0 = len(base), int((base <= 0).sum())
            q = n0 / n
            positivos = base[base > 0]
            if len(positivos) < 5 or positivos.nunique() < 3:
                continue
            forma, _, escala = stats.gamma.fit(positivos.to_numpy(), floc=0)
            v = valores.to_numpy()
            h = np.where(v > 0, q + (1 - q) * stats.gamma.cdf(v, forma, loc=0, scale=escala), (n0 + 1) / (2 * (n + 1)))
            h = np.clip(h, 1e-6, 1 - 1e-6)
            spi[sel] = np.where(np.isnan(v), np.nan, stats.norm.ppf(h))
        saidas.append(
            pd.DataFrame(
                {
                    "cd_estacao": cod,
                    "mes_ref": acum.index.date,
                    "escala_meses": k,
                    "precip_acumulada_mm": acum.to_numpy(),
                    "spi": spi.to_numpy(),
                }
            )
        )
    res = pd.concat(saidas, ignore_index=True)
    return res[res["spi"].notna()]


@dp.materialized_view(
    name="gold_clima_spi_mensal_estacao",
    comment="SPI (índice padronizado de precipitação) por estação, mês e escala de 1, 3, 6 e 12 meses; base 2001–2025",
    cluster_by=["cd_estacao", "mes_ref"],
)
def gold_clima_spi_mensal_estacao():
    mensal = spark.read.table("gold_clima_mensal_estacao")  # noqa: F821 (spark é injetado pelo pipeline)
    chuva = mensal.select(
        "cd_estacao",
        "mes_ref",
        F.when(F.col("mes_valido_chuva"), F.col("precipitacao_mm")).cast("double").alias("precipitacao_mm"),
    )
    atributos = mensal.groupBy("cd_estacao").agg(
        F.max("nome_estacao").alias("nome_estacao"),
        F.max("sg_estado").alias("sg_estado"),
        F.max("regiao").alias("regiao"),
        F.max("latitude").alias("latitude"),
        F.max("longitude").alias("longitude"),
    )
    spi = chuva.groupBy("cd_estacao").applyInPandas(_spi_estacao, schema=SCHEMA_SAIDA)
    return (
        spi.join(atributos, "cd_estacao", "left")
        .withColumn("spi", F.round("spi", 2))
        .withColumn("precip_acumulada_mm", F.round("precip_acumulada_mm", 1))
        .withColumn("ano", F.year("mes_ref"))
        .withColumn("mes", F.month("mes_ref"))
        .withColumn(
            "categoria",
            F.when(F.col("spi") >= 2, "Extremamente úmido")
            .when(F.col("spi") >= 1.5, "Muito úmido")
            .when(F.col("spi") >= 1, "Moderadamente úmido")
            .when(F.col("spi") > -1, "Normal")
            .when(F.col("spi") > -1.5, "Seca moderada")
            .when(F.col("spi") > -2, "Seca severa")
            .otherwise("Seca extrema"),
        )
    )
