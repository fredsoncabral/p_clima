"""Gera src/dashboards/clima_inmet.lvdash.json — dashboard "Climate Intelligence" (AI/BI).

Uso:  python scripts/gerar_dashboard.py

O JSON é gerado (e não editado à mão) para garantir que cada `fieldName` das encodings
corresponda a um campo da query do widget. Queries usam nomes de tabela SEM catálogo/schema
(vêm de dataset_catalog/dataset_schema no recurso do bundle).
"""

import itertools
import json
import pathlib

SAIDA = pathlib.Path(__file__).resolve().parents[1] / "src/dashboards/clima_inmet.lvdash.json"

# ------------------------------------------------------------------ identidade visual
AZUL, VERMELHO, CIANO, AMARELO, ROXO, CINZA, VERDE, MARROM = (
    "#3A8DDE", "#E5484D", "#22C3E6", "#F5C518", "#8B5CF6", "#9AA4B2", "#2EBD85", "#B7791F")
FASES = [{"value": "El Niño", "color": VERMELHO}, {"value": "La Niña", "color": CIANO}, {"value": "Neutro", "color": CINZA}]
RAMPA_TEMP = {"mode": "custom-sequential", "colors": {"start": CIANO, "end": VERMELHO}}
RAMPA_CHUVA = {"mode": "custom-sequential", "colors": {"start": MARROM, "end": AZUL}}

DEC2 = {"type": "number-plain", "decimalPlaces": {"type": "exact", "places": 2}}
DEC1 = {"type": "number-plain", "decimalPlaces": {"type": "exact", "places": 1}}
DEC0 = {"type": "number-plain", "decimalPlaces": {"type": "exact", "places": 0}}
PCT0 = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 0}}
PCT1 = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}

REGIAO = ("CASE {c} WHEN 'N' THEN 'Norte' WHEN 'NE' THEN 'Nordeste' WHEN 'CO' THEN 'Centro-Oeste' "
          "WHEN 'SE' THEN 'Sudeste' WHEN 'S' THEN 'Sul' ELSE {c} END")
ROTULO = "concat({p}nome_estacao, ' (', {p}sg_estado, ')')"


def ql(sql: str) -> list[str]:
    return [linha + "\n" for linha in sql.strip().splitlines()]


def ds(nome, titulo, sql, colunas=None):
    d = {"name": nome, "displayName": titulo, "queryLines": ql(sql)}
    if colunas:
        d["columns"] = [{"displayName": n, "description": desc, "expression": e} for n, desc, e in colunas]
    return d


# ------------------------------------------------------------------ datasets
DATASETS = [
    ds("ds_resumo", "Climate Intelligence — resumo por região", """
SELECT regiao_nome, ordem, texto_temperatura, texto_chuva, texto_seca, texto_calor,
  anomalia_temp_12m_c, chuva_12m_razao_normal, spi3_mediano, periodo_inicio, periodo_fim
FROM gold_clima_resumo_regiao
ORDER BY ordem
"""),
    ds("ds_enso_atual", "ENSO — situação atual", """
SELECT concat(fase, coalesce(concat(' ', lower(intensidade)), '')) AS fase_atual, oni, temporada, ano,
  concat(temporada, '/', ano) AS referencia,
  'Os efeitos do ENSO variam por região e com defasagem; não atribuir anomalias automaticamente ao fenômeno.' AS ressalva
FROM gold_enso_mensal
ORDER BY mes_ref DESC
LIMIT 1
"""),
    # KPIs: últimos 12 meses vs 12 meses anteriores (mesmas regras de validade)
    ds("ds_kpi", "KPIs — 12 meses vs 12 meses anteriores", f"""
WITH u AS (SELECT max(mes_ref) AS ultimo FROM gold_clima_anomalia_mensal_estacao),
nrm AS (
  SELECT cd_estacao, avg(temp_media_normal_c) AS temp_normal_anual_c
  FROM gold_clima_normal_mensal_estacao GROUP BY cd_estacao HAVING count(temp_media_normal_c) = 12
),
base AS (
SELECT m.cd_estacao, {ROTULO.format(p='m.')} AS estacao, m.sg_estado, {REGIAO.format(c='m.regiao')} AS regiao,
  m.latitude, m.longitude, m.mes_ref,
  CASE WHEN m.mes_ref > add_months(u.ultimo, -12) THEN 'atual' ELSE 'anterior' END AS periodo,
  CASE WHEN m.mes_valido_temp AND NOT coalesce(a.qc_temp_suspeito, false) THEN m.temp_media_c END AS temp_media_c,
  CASE WHEN NOT coalesce(a.qc_temp_suspeito, false) THEN a.anomalia_temp_c END AS anomalia_temp_c,
  CASE WHEN NOT coalesce(a.qc_temp_suspeito, false) AND a.anomalia_temp_c IS NOT NULL THEN n.temp_normal_anual_c END AS temp_normal_anual_c,
  CASE WHEN m.mes_valido_chuva THEN m.precipitacao_mm END AS precipitacao_mm,
  CASE WHEN m.mes_valido_chuva THEN a.precipitacao_normal_mm END AS precipitacao_normal_mm,
  CASE WHEN m.mes_valido_chuva AND a.precipitacao_normal_mm IS NOT NULL THEN m.precipitacao_mm END AS precip_com_normal_mm,
  CASE WHEN m.mes_valido_chuva THEN m.dias_com_chuva END AS dias_com_chuva,
  m.umidade_media_pct, m.vento_medio_ms * 3.6 AS vento_medio_kmh
FROM gold_clima_mensal_estacao m
CROSS JOIN u
LEFT JOIN nrm n ON n.cd_estacao = m.cd_estacao
LEFT JOIN gold_clima_anomalia_mensal_estacao a ON a.cd_estacao = m.cd_estacao AND a.mes_ref = m.mes_ref
WHERE m.mes_ref > add_months(u.ultimo, -24)
)
-- só estações com dados nos dois períodos: evita viés de composição na comparação
SELECT * FROM base
WHERE cd_estacao IN (SELECT cd_estacao FROM base GROUP BY cd_estacao HAVING count(DISTINCT periodo) = 2)
""", [
        ("Temp atual", "Temperatura média, últimos 12 meses (°C) = normal anual + anomalia média (sem viés sazonal)", "AVG(CASE WHEN `periodo`='atual' THEN `temp_normal_anual_c` END) + AVG(CASE WHEN `periodo`='atual' THEN `anomalia_temp_c` END)"),
        ("Temp anterior", "Temperatura média, 12 meses anteriores (°C)", "AVG(CASE WHEN `periodo`='anterior' THEN `temp_normal_anual_c` END) + AVG(CASE WHEN `periodo`='anterior' THEN `anomalia_temp_c` END)"),
        ("Anom atual", "Anomalia térmica, últimos 12 meses (°C)", "AVG(CASE WHEN `periodo`='atual' THEN `anomalia_temp_c` END)"),
        ("Anom anterior", "Anomalia térmica, 12 meses anteriores (°C)", "AVG(CASE WHEN `periodo`='anterior' THEN `anomalia_temp_c` END)"),
        ("Chuva atual", "Chuva acumulada em 12 meses (média por estação, mm)", "12 * AVG(CASE WHEN `periodo`='atual' THEN `precipitacao_mm` END)"),
        ("Chuva anterior", "Chuva acumulada nos 12 meses anteriores (mm)", "12 * AVG(CASE WHEN `periodo`='anterior' THEN `precipitacao_mm` END)"),
        ("Chuva pct atual", "Chuva / normal, últimos 12 meses", "SUM(CASE WHEN `periodo`='atual' THEN `precip_com_normal_mm` END) / SUM(CASE WHEN `periodo`='atual' AND `precip_com_normal_mm` IS NOT NULL THEN `precipitacao_normal_mm` END)"),
        ("Chuva pct anterior", "Chuva / normal, 12 meses anteriores", "SUM(CASE WHEN `periodo`='anterior' THEN `precip_com_normal_mm` END) / SUM(CASE WHEN `periodo`='anterior' AND `precip_com_normal_mm` IS NOT NULL THEN `precipitacao_normal_mm` END)"),
        ("Umid atual", "Umidade relativa média, últimos 12 meses (%)", "AVG(CASE WHEN `periodo`='atual' THEN `umidade_media_pct` END)"),
        ("Umid anterior", "Umidade relativa média, 12 meses anteriores (%)", "AVG(CASE WHEN `periodo`='anterior' THEN `umidade_media_pct` END)"),
        ("Vento atual", "Vento médio, últimos 12 meses (km/h)", "AVG(CASE WHEN `periodo`='atual' THEN `vento_medio_kmh` END)"),
        ("Vento anterior", "Vento médio, 12 meses anteriores (km/h)", "AVG(CASE WHEN `periodo`='anterior' THEN `vento_medio_kmh` END)"),
        ("Dias chuva atual", "Dias com chuva >= 1 mm em 12 meses (média por estação)", "12 * AVG(CASE WHEN `periodo`='atual' THEN `dias_com_chuva` END)"),
        ("Dias chuva anterior", "Dias com chuva nos 12 meses anteriores", "12 * AVG(CASE WHEN `periodo`='anterior' THEN `dias_com_chuva` END)"),
    ]),
    ds("ds_kpi_mapa", "Mapa — anomalia dos últimos 12 meses (estações com coordenadas)", "__KPI_SQL__ AND latitude IS NOT NULL",
       [("Anom atual", "Anomalia térmica, últimos 12 meses (°C)", "AVG(CASE WHEN `periodo`='atual' THEN `anomalia_temp_c` END)")]),
    ds("ds_avisos", "Avisos meteorológicos vigentes", """
SELECT descricao, severidade,
  from_utc_timestamp(inicio_utc, 'America/Sao_Paulo') AS inicio_brasilia,
  from_utc_timestamp(fim_utc, 'America/Sao_Paulo') AS fim_brasilia,
  array_join(estados, ', ') AS estados, size(geocodes_ibge) AS n_municipios
FROM silver_inmet_avisos
WHERE fim_utc >= current_timestamp() AND NOT coalesce(encerrado, false)
ORDER BY id_severidade DESC, inicio_utc
"""),
    ds("ds_anual", "Resumo anual por estação", f"""
WITH longa AS (SELECT cd_estacao, n_anos_temp >= 15 AS longa FROM gold_clima_tendencia_estacao)
SELECT a.cd_estacao, {ROTULO.format(p='a.')} AS estacao, a.sg_estado, {REGIAO.format(c='a.regiao')} AS regiao,
  make_date(a.ano, 1, 1) AS mes_ref, a.ano,
  CASE WHEN l.longa THEN 'Sim' ELSE 'Não' END AS serie_longa,
  a.temp_media_c, a.temp_max_media_c, a.temp_min_media_c, a.temp_normal_c, a.anomalia_temp_c,
  a.precipitacao_mm, a.precipitacao_normal_mm, a.precipitacao_pct_normal / 100 AS precipitacao_razao_normal,
  a.var_temp_ano_anterior_c
FROM gold_clima_anual_estacao a
LEFT JOIN longa l USING (cd_estacao)
"""),
    # formato longo (uma coluna de valor + série): eixo com título e cores fixas por série no gráfico de linhas
    ds("ds_anual_series", "Temperatura anual por série (máx./média/mín./normal)", f"""
WITH longa AS (SELECT cd_estacao, n_anos_temp >= 15 AS longa FROM gold_clima_tendencia_estacao)
SELECT a.cd_estacao, {ROTULO.format(p='a.')} AS estacao, a.sg_estado, {REGIAO.format(c='a.regiao')} AS regiao,
  make_date(a.ano, 1, 1) AS mes_ref, a.ano,
  CASE WHEN l.longa THEN 'Sim' ELSE 'Não' END AS serie_longa,
  s.serie, s.temp_c
FROM gold_clima_anual_estacao a
LEFT JOIN longa l USING (cd_estacao)
LATERAL VIEW stack(4, 'Máxima média', a.temp_max_media_c, 'Média', a.temp_media_c,
                      'Mínima média', a.temp_min_media_c, 'Normal 2001–2025', a.temp_normal_c) s AS serie, temp_c
WHERE a.temp_media_c IS NOT NULL
"""),
    ds("ds_mensal_hist", "Série mensal por estação (histórico)", f"""
WITH longa AS (SELECT cd_estacao, n_anos_temp >= 15 AS longa FROM gold_clima_tendencia_estacao)
SELECT a.cd_estacao, {ROTULO.format(p='a.')} AS estacao, a.sg_estado, {REGIAO.format(c='a.regiao')} AS regiao,
  a.mes_ref, a.ano, a.mes,
  CASE WHEN l.longa THEN 'Sim' ELSE 'Não' END AS serie_longa,
  a.temp_media_c, a.anomalia_temp_c
FROM gold_clima_anomalia_mensal_estacao a
LEFT JOIN longa l USING (cd_estacao)
WHERE NOT a.qc_temp_suspeito
"""),
    ds("ds_sazonal", "Sazonalidade — comparação entre anos", f"""
WITH longa AS (SELECT cd_estacao, n_anos_temp >= 15 AS longa FROM gold_clima_tendencia_estacao)
SELECT a.cd_estacao, {ROTULO.format(p='a.')} AS estacao, a.sg_estado, {REGIAO.format(c='a.regiao')} AS regiao,
  a.mes_ref, cast(a.ano AS STRING) AS ano_txt, a.mes,
  CASE WHEN l.longa THEN 'Sim' ELSE 'Não' END AS serie_longa,
  a.temp_media_c, a.precipitacao_mm
FROM gold_clima_anomalia_mensal_estacao a
LEFT JOIN longa l USING (cd_estacao)
WHERE NOT a.qc_temp_suspeito
"""),
    ds("ds_enso", "ONI mensal e fase do ENSO", """
SELECT mes_ref, ano, mes, oni, fase, coalesce(intensidade, '-') AS intensidade
FROM gold_enso_mensal
WHERE ano >= 2000
ORDER BY mes_ref
"""),
    ds("ds_enso_regiao", "Anomalias regionais x fase do ENSO", """
SELECT regiao_nome AS regiao, mes_ref, ano, mes, oni, fase,
  anomalia_temp_c, anomalia_precipitacao_mm, razao_chuva_normal
FROM gold_clima_enso_regiao_mensal
WHERE ano >= 2008
"""),
    ds("ds_enso_corr", "Correlação ONI x clima regional", """
SELECT regiao_nome AS regiao, defasagem_meses, cast(defasagem_meses AS STRING) AS defasagem,
  corr_oni_temperatura, corr_oni_chuva, n_meses
FROM gold_clima_enso_correlacao
"""),
    ds("ds_enso_episodios", "Episódios ENSO desde 2000", """
SELECT fase, inicio, fim, duracao_meses, pico_oni, intensidade_pico,
  CASE WHEN em_curso THEN 'em curso' ELSE '' END AS situacao
FROM gold_enso_episodios
WHERE fim >= '2000-01-01'
ORDER BY inicio DESC
"""),
    ds("ds_eventos", "Eventos extremos por estação e mês", f"""
WITH longa AS (SELECT cd_estacao, n_anos_temp >= 15 AS longa FROM gold_clima_tendencia_estacao)
SELECT e.cd_estacao, {ROTULO.format(p='e.')} AS estacao, e.sg_estado, {REGIAO.format(c='e.regiao')} AS regiao,
  e.mes_ref, e.ano, concat(cast(floor(e.ano / 10) * 10 AS STRING), 's') AS decada,
  CASE WHEN l.longa THEN 'Sim' ELSE 'Não' END AS serie_longa,
  e.dias_validos_temp, e.dias_validos_chuva, e.dias_onda_calor, e.n_ondas_calor, e.dias_calor_extremo,
  e.dias_frio_extremo, e.dias_chuva_extrema, e.dias_umidade_baixa, e.dias_vento_extremo, e.dias_desconforto_calor,
  e.max_dias_secos_consecutivos, e.chuva_max_24h_mm, e.rajada_max_ms * 3.6 AS rajada_max_kmh,
  e.temp_max_absoluta_c, e.temp_min_absoluta_c
FROM gold_clima_eventos_mensal_estacao e
LEFT JOIN longa l USING (cd_estacao)
""", [
        ("Dias onda calor ano", "Dias em onda de calor por estação-ano", "365 * SUM(`dias_onda_calor`) / SUM(`dias_validos_temp`)"),
        ("Ondas calor ano", "Ondas de calor (>= 5 dias > p90 local) por estação-ano", "365 * SUM(`n_ondas_calor`) / SUM(`dias_validos_temp`)"),
        ("Dias chuva extrema ano", "Dias com chuva > p95 local por estação-ano", "365 * SUM(`dias_chuva_extrema`) / SUM(`dias_validos_chuva`)"),
        ("Dias umidade baixa ano", "Dias com umidade mínima < 30% por estação-ano", "365 * SUM(`dias_umidade_baixa`) / SUM(`dias_validos_temp`)"),
        ("Freq calor extremo", "Fração de dias com Tmáx > p95 local (esperado ~5%)", "SUM(`dias_calor_extremo`) / SUM(`dias_validos_temp`)"),
        ("Freq frio extremo", "Fração de dias com Tmín < p05 local (esperado ~5%)", "SUM(`dias_frio_extremo`) / SUM(`dias_validos_temp`)"),
        ("Freq desconforto", "Fração de dias com índice de calor >= 32 °C", "SUM(`dias_desconforto_calor`) / SUM(`dias_validos_temp`)"),
    ]),
    ds("ds_freq_extremos", "Frequência de dias de calor/frio extremo", f"""
WITH longa AS (SELECT cd_estacao, n_anos_temp >= 15 AS longa FROM gold_clima_tendencia_estacao)
SELECT e.cd_estacao, {ROTULO.format(p='e.')} AS estacao, e.sg_estado, {REGIAO.format(c='e.regiao')} AS regiao,
  e.mes_ref, e.ano, CASE WHEN l.longa THEN 'Sim' ELSE 'Não' END AS serie_longa,
  e.dias_validos_temp, s.tipo, s.dias
FROM gold_clima_eventos_mensal_estacao e
LEFT JOIN longa l USING (cd_estacao)
LATERAL VIEW stack(2, 'Calor extremo (Tmáx > p95)', e.dias_calor_extremo,
                      'Frio extremo (Tmín < p05)', e.dias_frio_extremo) s AS tipo, dias
""", [("Freq", "Fração dos dias válidos com o evento (esperado ~5%)", "SUM(`dias`) / SUM(`dias_validos_temp`)")]),
    ds("ds_spi", "SPI mensal por estação", f"""
SELECT cd_estacao, {ROTULO.format(p='')} AS estacao, sg_estado, {REGIAO.format(c='regiao')} AS regiao,
  mes_ref, ano, cast(escala_meses AS STRING) AS escala, spi, categoria
FROM gold_clima_spi_mensal_estacao
WHERE ano >= 2008
"""),
    ds("ds_spi_atual", "SPI-3 do último mês disponível", f"""
SELECT cd_estacao, {ROTULO.format(p='')} AS estacao, sg_estado, {REGIAO.format(c='regiao')} AS regiao,
  latitude, longitude, mes_ref, spi, categoria, precip_acumulada_mm
FROM gold_clima_spi_mensal_estacao
WHERE escala_meses = 3 AND mes_ref = (SELECT max(mes_ref) FROM gold_clima_spi_mensal_estacao)
ORDER BY spi
"""),
    ds("ds_tendencia", "Tendência linear por estação", f"""
SELECT cd_estacao, {ROTULO.format(p='')} AS estacao, sg_estado, {REGIAO.format(c='regiao')} AS regiao,
  latitude, longitude, n_anos_temp, concat(ano_inicio_temp, '–', ano_fim_temp) AS periodo,
  tendencia_temp_c_decada, CASE WHEN significativa_95_temp THEN 'Sim' ELSE 'Não' END AS significativa,
  tendencia_chuva_pct_decada
FROM gold_clima_tendencia_estacao
WHERE tendencia_temp_c_decada IS NOT NULL AND latitude IS NOT NULL  -- 3 estações antigas sem coordenadas
ORDER BY tendencia_temp_c_decada DESC
"""),
    ds("ds_geo", "Comparação geográfica (mensal por estação)", f"""
SELECT m.cd_estacao, {ROTULO.format(p='m.')} AS estacao, m.sg_estado, {REGIAO.format(c='m.regiao')} AS regiao,
  m.latitude, m.longitude, e.altitude_m, m.mes_ref, m.ano,
  CASE WHEN m.mes_valido_temp AND NOT coalesce(a.qc_temp_suspeito, false) THEN m.temp_media_c END AS temp_media_c,
  CASE WHEN NOT coalesce(a.qc_temp_suspeito, false) THEN a.anomalia_temp_c END AS anomalia_temp_c,
  CASE WHEN m.mes_valido_chuva THEN m.precipitacao_mm END AS precipitacao_mm,
  CASE WHEN m.mes_valido_chuva THEN a.precipitacao_normal_mm END AS precipitacao_normal_mm,
  CASE WHEN m.mes_valido_chuva AND a.precipitacao_normal_mm IS NOT NULL THEN m.precipitacao_mm END AS precip_com_normal_mm,
  CASE WHEN m.mes_valido_chuva THEN m.dias_com_chuva END AS dias_com_chuva,
  m.umidade_media_pct
FROM gold_clima_mensal_estacao m
LEFT JOIN gold_clima_anomalia_mensal_estacao a ON a.cd_estacao = m.cd_estacao AND a.mes_ref = m.mes_ref
LEFT JOIN silver_inmet_estacoes e ON e.cd_estacao = m.cd_estacao
""", [
        ("Temp media", "Temperatura média (°C)", "AVG(`temp_media_c`)"),
        ("Anomalia", "Anomalia térmica média (°C)", "AVG(`anomalia_temp_c`)"),
        ("Chuva anual", "Chuva média anual (mm/ano) = 12 x média mensal", "12 * AVG(`precipitacao_mm`)"),
        ("Chuva pct normal", "Chuva / normal", "SUM(`precip_com_normal_mm`) / SUM(CASE WHEN `precip_com_normal_mm` IS NOT NULL THEN `precipitacao_normal_mm` END)"),
        ("Dias chuva ano", "Dias com chuva por ano", "12 * AVG(`dias_com_chuva`)"),
        ("Umidade", "Umidade relativa média (%)", "AVG(`umidade_media_pct`)"),
    ]),
    ds("ds_estacoes", "Rede de estações", """
SELECT cd_estacao, concat(nome_estacao, ' (', sg_estado, ')') AS estacao, sg_estado, tipo_estacao, situacao,
  latitude, longitude, altitude_m, dt_inicio_operacao
FROM silver_inmet_estacoes
WHERE latitude IS NOT NULL
"""),
]

# ------------------------------------------------------------------ helpers de widgets
def pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def texto(nome, linhas, x, y, w, h):
    return {"widget": {"name": nome, "multilineTextboxSpec": {"lines": linhas}}, "position": pos(x, y, w, h)}


def query(dataset, campos, desagregado=False, ordens=None, nome="main_query"):
    q = {"datasetName": dataset, "fields": [{"name": n, "expression": e} for n, e in campos], "disaggregated": desagregado}
    if ordens:
        q["orders"] = ordens
    return [{"name": nome, "query": q}]


def M(medida):
    return (f"measure({medida})", f"MEASURE(`{medida}`)")


def C(col):
    return (col, f"`{col}`")


def A(func, col):
    return (f"{func.lower()}({col})", f"{func.upper()}(`{col}`)")


def frame(titulo, descricao=None):
    f = {"showTitle": True, "title": titulo}
    if descricao:
        f.update({"showDescription": True, "description": descricao})
    return f


def kpi(nome, dataset, medida, titulo, fmt, sufixo, x, y, alvo=None, descricao=None, w=3, h=3):
    campos = [M(medida)] + ([M(alvo)] if alvo else [])
    valor = {"fieldName": f"measure({medida})", "displayName": titulo, "format": fmt}
    if sufixo:
        valor["formatTemplate"] = "{{ @formatted }}" + sufixo
    enc = {"value": valor}
    if alvo:
        enc["target"] = {"fieldName": f"measure({alvo})", "displayName": "12 meses anteriores", "format": fmt}
    return {"widget": {"name": nome, "queries": query(dataset, campos),
                       "spec": {"version": 2, "widgetType": "counter", "encodings": enc, "frame": frame(titulo, descricao)}},
            "position": pos(x, y, w, h)}


def grafico(nome, tipo, dataset, campos, enc, titulo, x, y, w, h, descricao=None, versao=3, extra=None, ordens=None,
            desagregado=False):
    spec = {"version": versao, "widgetType": tipo, "encodings": enc, "frame": frame(titulo, descricao)}
    if extra:
        spec.update(extra)
    return {"widget": {"name": nome, "queries": query(dataset, campos, desagregado, ordens), "spec": spec},
            "position": pos(x, y, w, h)}


def tabela(nome, dataset, colunas, titulo, x, y, w, h, descricao=None, desagregado=True, campos=None, ordens=None):
    """colunas: lista (fieldName, displayName, format|None)."""
    if campos is None:
        campos = [C(c[0]) for c in colunas]
    cols = []
    for c in colunas:
        d = {"fieldName": c[0], "displayName": c[1]}
        if len(c) > 2 and c[2]:
            d["format"] = c[2]
        if len(c) > 3 and c[3]:
            d["style"] = c[3]
        cols.append(d)
    return {"widget": {"name": nome, "queries": query(dataset, campos, desagregado, ordens),
                       "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": cols},
                                "frame": frame(titulo, descricao)}},
            "position": pos(x, y, w, h)}


def hlinha(valor, rotulo, cor=CINZA, tipo="DOUBLE"):
    return {"type": "horizontal-line", "encodings": {"y": {"dataValue": str(valor), "dataType": tipo},
                                                     "label": {"value": rotulo}, "color": {"value": cor}}}


def q(field, scale="quantitative", **kw):
    d = {"fieldName": field, "scale": {"type": scale}}
    d.update(kw)
    return d


def destaque(limite, op, cor):
    return {"type": "basic", "rules": [{"condition": {"operand": {"type": "data-value", "value": str(limite)}, "operator": op},
                                        "backgroundColor": {"hex": cor}}]}


# ------------------------------------------------------------------ página 1 — visão geral
p1 = [
    texto("p1-titulo", ["# Climate Intelligence — Brasil\n"], 0, 0, 12, 1),
    texto("p1-sub", ["Situação climática dos **últimos 12 meses disponíveis no BDMEP/INMET**, comparada à normal 2001–2025 de cada estação ",
                     "e aos 12 meses anteriores (valor de comparação abaixo de cada indicador). Anomalia > 0 = mais quente que o normal."], 0, 1, 12, 1),
    tabela("p1-resumo", "ds_resumo", [
        ("regiao_nome", "Região"), ("texto_temperatura", "Temperatura"), ("texto_chuva", "Precipitação"),
        ("texto_seca", "Seca"), ("texto_calor", "Calor")],
        "Análise climática automática por região", 0, 2, 12, 6,
        "Texto gerado por regras a partir dos indicadores gold (temperatura, chuva, SPI-3 e ondas de calor)."),
    tabela("p1-enso", "ds_enso_atual", [
        ("fase_atual", "Fase atual do ENSO"), ("referencia", "Referência (trimestre)"), ("oni", "ONI (°C)", DEC2),
        ("ressalva", "Interpretação")], "Fenômeno ENSO (NOAA/CPC)", 0, 8, 12, 2),
    kpi("k-temp", "ds_kpi", "Temp atual", "Temperatura média", DEC1, " °C", 0, 10, "Temp anterior"),
    kpi("k-anom", "ds_kpi", "Anom atual", "Anomalia térmica", DEC2, " °C", 3, 10, "Anom anterior",
        "Desvio em relação à normal 2001–2025"),
    kpi("k-chuva", "ds_kpi", "Chuva atual", "Precipitação acumulada", DEC0, " mm", 6, 10, "Chuva anterior",
        "Média por estação em 12 meses"),
    kpi("k-chuva-pct", "ds_kpi", "Chuva pct atual", "Chuva vs. normal", PCT0, None, 9, 10, "Chuva pct anterior"),
    kpi("k-umid", "ds_kpi", "Umid atual", "Umidade relativa", DEC0, " %", 0, 13, "Umid anterior"),
    kpi("k-vento", "ds_kpi", "Vento atual", "Vento médio", DEC1, " km/h", 3, 13, "Vento anterior"),
    kpi("k-dias-chuva", "ds_kpi", "Dias chuva atual", "Dias com chuva", DEC0, " dias", 6, 13, "Dias chuva anterior",
        "Dias com >= 1 mm em 12 meses (média por estação)"),
    {"widget": {"name": "k-estacoes", "queries": query("ds_kpi", [("countdistinct(cd_estacao)", "COUNT(DISTINCT `cd_estacao`)")]),
                "spec": {"version": 2, "widgetType": "counter",
                         "encodings": {"value": {"fieldName": "countdistinct(cd_estacao)", "displayName": "Estações", "format": DEC0}},
                         "frame": frame("Estações comparadas", "Estações com dados nos dois períodos de 12 meses")}},
     "position": pos(9, 13, 3, 3)},
    grafico("p1-mapa", "symbol-map", "ds_kpi_mapa",
            [C("latitude"), C("longitude"), M("Anom atual")],
            {"coordinates": {"latitude": {"fieldName": "latitude"}, "longitude": {"fieldName": "longitude"}},
             "color": {"fieldName": "measure(Anom atual)", "displayName": "Anomalia (°C)",
                       "scale": {"type": "quantitative", "colorRamp": RAMPA_TEMP}}},
            "Anomalia térmica dos últimos 12 meses por estação (°C)", 0, 16, 7, 8,
            "Ciano = mais frio que a normal; vermelho = mais quente.", versao=2, extra={"mark": {"opacity": 0.85}}),
    tabela("p1-avisos", "ds_avisos", [
        ("descricao", "Aviso"), ("severidade", "Severidade"), ("inicio_brasilia", "Início (Brasília)"),
        ("fim_brasilia", "Fim (Brasília)"), ("n_municipios", "Municípios"), ("estados", "Estados")],
        "Avisos meteorológicos vigentes (INMET)", 7, 16, 5, 8, "Atualizado a cada execução do job de ingestão."),
]
# ------------------------------------------------------------------ página 2 — histórico
p2 = [
    texto("p2-titulo", ["# Histórico meteorológico\n"], 0, 0, 12, 1),
    texto("p2-sub", ["A rede cresceu de 5 estações (2000) para mais de 500 (2016+). Para comparar anos sem viés de composição, ",
                     "mantenha o filtro **Série longa = Sim** (estações com 15+ anos de dados). Use Região/UF/Estação na aba Filtros."], 0, 1, 12, 1),
    grafico("p2-temp-anual", "line", "ds_anual_series", [C("ano"), C("serie"), A("avg", "temp_c")],
            {"x": q("ano", "categorical", displayName="Ano"),
             "y": q("avg(temp_c)", displayName="Temperatura (°C)", format=DEC1),
             "color": {"fieldName": "serie", "displayName": "Série", "scale": {"type": "categorical", "mappings": [
                 {"value": "Máxima média", "color": VERMELHO}, {"value": "Média", "color": AMARELO},
                 {"value": "Mínima média", "color": CIANO}, {"value": "Normal 2001–2025", "color": CINZA}]}}},
            "Evolução da temperatura anual (°C)", 0, 2, 8, 7,
            "Média dos anos com >= 10 meses válidos; normal = referência climatológica das mesmas estações."),
    grafico("p2-anom-anual", "bar", "ds_anual", [C("ano"), A("avg", "anomalia_temp_c")],
            {"x": q("ano", "categorical", displayName="Ano"),
             "y": q("avg(anomalia_temp_c)", displayName="Anomalia (°C)", format=DEC2)},
            "Anomalia anual (°C)", 8, 2, 4, 7, extra={"annotations": [hlinha(0, "normal")]}),
    grafico("p2-chuva-anual", "combo", "ds_anual", [C("ano"), A("avg", "precipitacao_mm"), A("avg", "precipitacao_normal_mm")],
            {"x": q("ano", "categorical", displayName="Ano"),
             "y": {"scale": {"type": "quantitative"},
                   "primary": {"fields": [{"fieldName": "avg(precipitacao_mm)", "displayName": "Chuva anual (mm)"}]},
                   "secondary": {"fields": [{"fieldName": "avg(precipitacao_normal_mm)", "displayName": "Normal (mm)"}]}},
             "label": {"show": False}},
            "Precipitação anual vs. normal (mm, média por estação)", 0, 9, 8, 7,
            "Somente anos com os 12 meses válidos (ausência de dado não é ausência de chuva).", versao=1),
    tabela("p2-ranking-chuva", "ds_anual", [
        ("ano", "Ano"), ("avg(precipitacao_mm)", "Chuva (mm)", DEC0), ("avg(precipitacao_razao_normal)", "% da normal", PCT0)],
        "Anos mais chuvosos e mais secos", 8, 9, 4, 7, "Ordenado por % da normal (mais chuvoso no topo).",
        desagregado=False, campos=[C("ano"), A("avg", "precipitacao_mm"), A("avg", "precipitacao_razao_normal")],
        ordens=[{"direction": "DESC", "expression": "AVG(`precipitacao_razao_normal`)"}]),
    texto("p2-saz-titulo", ["## Sazonalidade — compare anos (filtro *Anos* ao lado)\n"], 0, 16, 9, 1),
    {"widget": {"name": "p2-filtro-anos",
                "queries": [{"name": "f_anos", "query": {"datasetName": "ds_sazonal", "fields": [{"name": "ano_txt", "expression": "`ano_txt`"}], "disaggregated": False}}],
                "spec": {"version": 2, "widgetType": "filter-multi-select",
                         "encodings": {"fields": [{"fieldName": "ano_txt", "displayName": "Anos", "queryName": "f_anos"}]},
                         "selection": {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": "2024"}, {"value": "2025"}, {"value": "2026"}]}}},
                         "frame": frame("Anos")}},
     "position": pos(9, 16, 3, 1)},
    grafico("p2-saz-temp", "line", "ds_sazonal", [C("mes"), C("ano_txt"), A("avg", "temp_media_c")],
            {"x": q("mes", "categorical", displayName="Mês"),
             "y": q("avg(temp_media_c)", displayName="Temperatura média (°C)", format=DEC1),
             "color": {"fieldName": "ano_txt", "scale": {"type": "categorical"}, "displayName": "Ano"}},
            "Temperatura média mensal por ano (°C)", 0, 17, 6, 6),
    grafico("p2-saz-chuva", "bar", "ds_sazonal", [C("mes"), C("ano_txt"), A("avg", "precipitacao_mm")],
            {"x": q("mes", "categorical", displayName="Mês"),
             "y": q("avg(precipitacao_mm)", displayName="Chuva (mm)", format=DEC0),
             "color": {"fieldName": "ano_txt", "scale": {"type": "categorical"}, "displayName": "Ano"}},
            "Chuva mensal por ano (mm, média por estação)", 6, 17, 6, 6, extra={"mark": {"layout": "group"}}),
    grafico("p2-heatmap", "heatmap", "ds_mensal_hist", [C("mes"), C("ano"), A("avg", "anomalia_temp_c")],
            {"x": q("mes", "categorical", displayName="Mês", axis={"hideTitle": True}),
             "y": q("ano", "categorical", displayName="Ano", axis={"hideTitle": True}),
             "color": {"fieldName": "avg(anomalia_temp_c)", "displayName": "Anomalia (°C)",
                       "scale": {"type": "quantitative", "colorRamp": RAMPA_TEMP}}},
            "Anomalia térmica — ano × mês (°C)", 0, 23, 7, 9,
            "Cada célula = média das estações selecionadas nos filtros globais."),
    grafico("p2-box", "box", "ds_mensal_hist", [C("mes"), C("temp_media_c")],
            {"x": {"fieldName": "mes", "displayName": "Mês"},
             "y": {"fieldName": "temp_media_c", "displayName": "Temperatura média mensal (°C)", "scale": {"type": "quantitative"}}},
            "Distribuição da temperatura média mensal (estações × anos)", 7, 23, 5, 9,
            "Mediana, quartis e extremos de cada mês.", versao=1, desagregado=True),
]
# o filtro "Anos" (de página) só alcança ds_sazonal — heatmap e box usam ds_mensal_hist e não são afetados

# ------------------------------------------------------------------ página 3 — ENSO
p3 = [
    texto("p3-titulo", ["# El Niño, La Niña e o clima\n"], 0, 0, 12, 1),
    texto("p3-sub", ["Classificação mensal oficial pelo **ONI (NOAA/CPC)**: El Niño/La Niña quando |ONI| >= 0,5 °C por 5 trimestres consecutivos. ",
                     "Os impactos variam por região e aparecem com **defasagem** — use as correlações por defasagem. Séries regionais a partir de 2008 (rede > 400 estações). ",
                     "Correlação não implica causalidade."], 0, 1, 12, 2),
    grafico("p3-oni", "bar", "ds_enso", [C("mes_ref"), C("fase"), A("avg", "oni")],
            {"x": q("mes_ref", "temporal", displayName="Mês"),
             "y": q("avg(oni)", displayName="ONI (°C)", format=DEC2),
             "color": {"fieldName": "fase", "scale": {"type": "categorical", "mappings": FASES}, "displayName": "Fase"}},
            "Índice Oceânico Niño (ONI) e fase do ENSO desde 2000", 0, 3, 12, 6,
            extra={"annotations": [hlinha(0.5, "+0,5 (El Niño)", VERMELHO), hlinha(-0.5, "-0,5 (La Niña)", CIANO)]}),
    grafico("p3-temp-fase", "bar", "ds_enso_regiao", [C("regiao"), C("fase"), A("avg", "anomalia_temp_c")],
            {"x": q("regiao", "categorical", displayName="Região"),
             "y": q("avg(anomalia_temp_c)", displayName="Anomalia (°C)", format=DEC2),
             "color": {"fieldName": "fase", "scale": {"type": "categorical", "mappings": FASES}, "displayName": "Fase"}},
            "A. Anomalia térmica média por fase e região (°C)", 0, 9, 6, 7, extra={"mark": {"layout": "group"}}),
    grafico("p3-chuva-fase", "bar", "ds_enso_regiao", [C("regiao"), C("fase"), A("avg", "anomalia_precipitacao_mm")],
            {"x": q("regiao", "categorical", displayName="Região"),
             "y": q("avg(anomalia_precipitacao_mm)", displayName="Anomalia de chuva (mm/mês)", format=DEC1),
             "color": {"fieldName": "fase", "scale": {"type": "categorical", "mappings": FASES}, "displayName": "Fase"}},
            "B. Anomalia de chuva média por fase e região (mm/mês)", 6, 9, 6, 7, extra={"mark": {"layout": "group"}}),
    grafico("p3-corr-chuva", "heatmap", "ds_enso_corr", [C("defasagem"), C("regiao"), A("avg", "corr_oni_chuva")],
            {"x": q("defasagem", "categorical", displayName="Defasagem (meses)"),
             "y": q("regiao", "categorical", displayName="Região", axis={"hideTitle": True}),
             "color": {"fieldName": "avg(corr_oni_chuva)", "displayName": "Correlação",
                       "scale": {"type": "quantitative", "colorRamp": RAMPA_CHUVA}},
             "label": {"show": True}},
            "D. Correlação ONI × anomalia de chuva, por defasagem", 0, 16, 6, 6,
            "Negativo (marrom) = El Niño associado a menos chuva; positivo (azul) = mais chuva."),
    grafico("p3-corr-temp", "heatmap", "ds_enso_corr", [C("defasagem"), C("regiao"), A("avg", "corr_oni_temperatura")],
            {"x": q("defasagem", "categorical", displayName="Defasagem (meses)"),
             "y": q("regiao", "categorical", displayName="Região", axis={"hideTitle": True}),
             "color": {"fieldName": "avg(corr_oni_temperatura)", "displayName": "Correlação",
                       "scale": {"type": "quantitative", "colorRamp": RAMPA_TEMP}},
             "label": {"show": True}},
            "D. Correlação ONI × anomalia térmica, por defasagem", 6, 16, 6, 6),
    grafico("p3-scatter", "scatter", "ds_enso_regiao", [C("oni"), C("anomalia_temp_c"), C("regiao")],
            {"x": q("oni", displayName="ONI (°C)"), "y": q("anomalia_temp_c", displayName="Anomalia térmica (°C)"),
             "color": {"fieldName": "regiao", "scale": {"type": "categorical"}, "displayName": "Região"}},
            "ONI × anomalia térmica mensal (cada ponto = região-mês)", 0, 22, 6, 7, desagregado=True),
    tabela("p3-episodios", "ds_enso_episodios", [
        ("fase", "Fase"), ("inicio", "Início"), ("fim", "Fim"), ("duracao_meses", "Meses"),
        ("pico_oni", "Pico ONI", DEC2), ("intensidade_pico", "Intensidade"), ("situacao", "")],
        "C. Episódios de El Niño e La Niña desde 2000", 6, 22, 6, 7),
]

# ------------------------------------------------------------------ página 4 — extremos e anomalias
p4 = [
    texto("p4-titulo", ["# Extremos e seca\n"], 0, 0, 12, 1),
    texto("p4-sub", ["Limiares **relativos ao clima local** de cada estação e mês (base 2001–2025): onda de calor = 5+ dias seguidos com Tmáx > p90; ",
                     "calor/frio extremo = Tmáx > p95 / Tmín < p05; chuva extrema = dia > p95 dos dias chuvosos. Valores por estação-ano normalizam o tamanho da rede."], 0, 1, 12, 2),
    kpi("k4-onda", "ds_eventos", "Dias onda calor ano", "Dias em onda de calor", DEC1, " dias/ano", 0, 3, descricao="Por estação-ano no período filtrado"),
    kpi("k4-n-ondas", "ds_eventos", "Ondas calor ano", "Ondas de calor", DEC1, " por ano", 3, 3, descricao="Por estação-ano"),
    kpi("k4-chuva-ext", "ds_eventos", "Dias chuva extrema ano", "Dias de chuva extrema", DEC1, " dias/ano", 6, 3, descricao="Por estação-ano"),
    kpi("k4-umid", "ds_eventos", "Dias umidade baixa ano", "Dias com umidade < 30%", DEC1, " dias/ano", 9, 3, descricao="Por estação-ano"),
]
for i, (campo, func, titulo, fmt, suf) in enumerate([
        ("temp_max_absoluta_c", "max", "Temperatura máxima absoluta", DEC1, " °C"),
        ("temp_min_absoluta_c", "min", "Temperatura mínima absoluta", DEC1, " °C"),
        ("chuva_max_24h_mm", "max", "Maior chuva em 24 h", DEC0, " mm"),
        ("rajada_max_kmh", "max", "Rajada máxima de vento", DEC0, " km/h")]):
    nome_f = f"{func}({campo})"
    p4.append({"widget": {"name": f"k4-{campo}", "queries": query("ds_eventos", [A(func, campo)]),
                          "spec": {"version": 2, "widgetType": "counter",
                                   "encodings": {"value": {"fieldName": nome_f, "displayName": titulo, "format": fmt,
                                                           "formatTemplate": "{{ @formatted }}" + suf}},
                                   "frame": frame(titulo, "Após controle de qualidade de sensores")}},
               "position": pos(3 * i, 6, 3, 3)})
p4 += [
    grafico("p4-freq", "line", "ds_freq_extremos", [C("ano"), C("tipo"), M("Freq")],
            {"x": q("ano", "categorical", displayName="Ano"),
             "y": q("measure(Freq)", displayName="% dos dias", format=PCT1),
             "color": {"fieldName": "tipo", "displayName": "Evento", "scale": {"type": "categorical", "mappings": [
                 {"value": "Calor extremo (Tmáx > p95)", "color": VERMELHO},
                 {"value": "Frio extremo (Tmín < p05)", "color": CIANO}]}}},
            "A frequência de dias acima do p95 aumentou? (% dos dias)", 0, 9, 7, 7,
            "Por construção, ~5% na média do período-base; valores acima indicam aquecimento.",
            extra={"annotations": [hlinha(0.05, "esperado (5%)")]}),
    grafico("p4-decada", "bar", "ds_eventos", [C("decada"), M("Dias onda calor ano")],
            {"x": q("decada", "categorical", displayName="Década"),
             "y": q("measure(Dias onda calor ano)", displayName="Dias em onda de calor por estação-ano", format=DEC1)},
            "Ondas de calor por década (dias/estação-ano)", 7, 9, 5, 7),
    grafico("p4-heat-uf", "heatmap", "ds_eventos", [C("ano"), C("sg_estado"), M("Dias onda calor ano")],
            {"x": q("ano", "categorical", displayName="Ano", axis={"hideTitle": True}),
             "y": q("sg_estado", "categorical", displayName="UF", axis={"hideTitle": True}),
             "color": {"fieldName": "measure(Dias onda calor ano)", "displayName": "Dias/estação-ano",
                       "scale": {"type": "quantitative", "colorRamp": {"mode": "custom-sequential", "colors": {"start": "#1B2436", "end": VERMELHO}}}}},
            "Calendário de ondas de calor — dias por estação-ano, UF × ano", 0, 16, 12, 9),
    texto("p4-spi-titulo", ["## Seca e excesso de chuva — SPI (índice padronizado de precipitação)\n"], 0, 25, 12, 1),
    grafico("p4-spi-mapa", "symbol-map", "ds_spi_atual", [C("latitude"), C("longitude"), A("avg", "spi")],
            {"coordinates": {"latitude": {"fieldName": "latitude"}, "longitude": {"fieldName": "longitude"}},
             "color": {"fieldName": "avg(spi)", "displayName": "SPI-3",
                       "scale": {"type": "quantitative", "colorRamp": RAMPA_CHUVA}}},
            "SPI-3 do último mês por estação", 0, 26, 6, 8,
            "Marrom = seca (SPI <= -1); azul = excesso (SPI >= 1).", versao=2, extra={"mark": {"opacity": 0.85}}),
    {"widget": {"name": "p4-filtro-escala",
                "queries": [{"name": "f_escala", "query": {"datasetName": "ds_spi", "fields": [{"name": "escala", "expression": "`escala`"}], "disaggregated": False}}],
                "spec": {"version": 2, "widgetType": "filter-single-select",
                         "encodings": {"fields": [{"fieldName": "escala", "displayName": "Escala do SPI (meses)", "queryName": "f_escala"}]},
                         "selection": {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": "12"}]}}},
                         "frame": frame("Escala do SPI (meses)")}},
     "position": pos(6, 26, 6, 1)},
    grafico("p4-spi-serie", "line", "ds_spi", [C("mes_ref"), C("regiao"), A("avg", "spi")],
            {"x": q("mes_ref", "temporal", displayName="Mês"),
             "y": q("avg(spi)", displayName="SPI médio", format=DEC2),
             "color": {"fieldName": "regiao", "scale": {"type": "categorical"}, "displayName": "Região"}},
            "SPI médio por região (escala selecionada)", 6, 27, 6, 7,
            extra={"annotations": [hlinha(-1, "seca moderada", MARROM), hlinha(1, "úmido", AZUL)]}),
    tabela("p4-spi-tabela", "ds_spi_atual", [
        ("estacao", "Estação"), ("regiao", "Região"), ("spi", "SPI-3", DEC2, destaque(-1.5, "<=", MARROM)),
        ("categoria", "Classe"), ("precip_acumulada_mm", "Chuva 3 meses (mm)", DEC0)],
        "Estações por SPI-3 no último mês (mais secas primeiro)", 0, 34, 12, 7),
]

# ------------------------------------------------------------------ página 5 — geográfica
p5 = [
    texto("p5-titulo", ["# Análise geográfica\n"], 0, 0, 12, 1),
    texto("p5-sub", ["Rankings e comparações respeitam os filtros de **Período, Região, UF e Estação**. Para comparar estações lado a lado, ",
                     "selecione-as no filtro *Estação*. Compare estações com cautela: altitude, localização e continuidade da série importam."], 0, 1, 12, 1),
    grafico("p5-tend-mapa", "symbol-map", "ds_tendencia", [C("latitude"), C("longitude"), A("avg", "tendencia_temp_c_decada")],
            {"coordinates": {"latitude": {"fieldName": "latitude"}, "longitude": {"fieldName": "longitude"}},
             "color": {"fieldName": "avg(tendencia_temp_c_decada)", "displayName": "°C/década",
                       "scale": {"type": "quantitative", "colorRamp": RAMPA_TEMP}}},
            "Tendência linear de temperatura (°C por década)", 0, 2, 7, 8,
            "Estações com 15+ anos de dados; vermelho = aquecimento.", versao=2, extra={"mark": {"opacity": 0.85}}),
    grafico("p5-tend-uf", "bar", "ds_tendencia", [C("sg_estado"), A("avg", "tendencia_temp_c_decada")],
            {"x": q("avg(tendencia_temp_c_decada)", displayName="°C por década", format=DEC2),
             "y": q("sg_estado", "categorical", displayName="UF", sort={"by": "value"})},
            "Tendência média por UF (°C/década)", 7, 2, 5, 8),
    tabela("p5-rank-quente", "ds_geo", [("estacao", "Estação"), ("measure(Temp media)", "Temp. média (°C)", DEC1)],
           "Ranking — estações mais quentes", 0, 10, 4, 7, desagregado=False,
           campos=[C("estacao"), M("Temp media")], ordens=[{"direction": "DESC", "expression": "MEASURE(`Temp media`)"}]),
    tabela("p5-rank-chuva", "ds_geo", [("estacao", "Estação"), ("measure(Chuva anual)", "Chuva (mm/ano)", DEC0)],
           "Ranking — estações mais chuvosas", 4, 10, 4, 7, desagregado=False,
           campos=[C("estacao"), M("Chuva anual")], ordens=[{"direction": "DESC", "expression": "MEASURE(`Chuva anual`)"}]),
    tabela("p5-rank-deficit", "ds_geo", [("estacao", "Estação"), ("measure(Chuva pct normal)", "% da normal", PCT0)],
           "Ranking — maior déficit de chuva", 8, 10, 4, 7, "Período filtrado vs. normal 2001–2025.", desagregado=False,
           campos=[C("estacao"), M("Chuva pct normal")], ordens=[{"direction": "ASC", "expression": "MEASURE(`Chuva pct normal`)"}]),
    tabela("p5-uf", "ds_geo", [
        ("sg_estado", "UF"), ("regiao", "Região"), ("measure(Temp media)", "Temp. média (°C)", DEC1),
        ("measure(Anomalia)", "Anomalia (°C)", DEC2), ("measure(Chuva anual)", "Chuva (mm/ano)", DEC0),
        ("measure(Chuva pct normal)", "% da normal", PCT0), ("measure(Umidade)", "Umidade (%)", DEC0),
        ("countdistinct(cd_estacao)", "Estações", DEC0)],
        "Indicadores por UF (período filtrado)", 0, 17, 12, 8, desagregado=False,
        campos=[C("sg_estado"), C("regiao"), M("Temp media"), M("Anomalia"), M("Chuva anual"), M("Chuva pct normal"),
                M("Umidade"), ("countdistinct(cd_estacao)", "COUNT(DISTINCT `cd_estacao`)")],
        ordens=[{"direction": "DESC", "expression": "MEASURE(`Temp media`)"}]),
    tabela("p5-comparacao", "ds_geo", [
        ("estacao", "Estação"), ("max(altitude_m)", "Altitude (m)", DEC0), ("measure(Temp media)", "Temp. média (°C)", DEC1),
        ("measure(Chuva anual)", "Chuva (mm/ano)", DEC0), ("measure(Umidade)", "Umidade (%)", DEC0),
        ("measure(Dias chuva ano)", "Dias com chuva/ano", DEC0), ("measure(Anomalia)", "Anomalia (°C)", DEC2)],
        "Comparação entre estações (selecione no filtro Estação)", 0, 25, 7, 8, desagregado=False,
        campos=[C("estacao"), A("max", "altitude_m"), M("Temp media"), M("Chuva anual"), M("Umidade"), M("Dias chuva ano"), M("Anomalia")]),
    grafico("p5-rede", "symbol-map", "ds_estacoes", [C("latitude"), C("longitude"), C("situacao")],
            {"coordinates": {"latitude": {"fieldName": "latitude"}, "longitude": {"fieldName": "longitude"}},
             "color": {"fieldName": "situacao", "displayName": "Situação",
                       "scale": {"type": "categorical", "mappings": [
                           {"value": "Operante", "color": VERDE}, {"value": "Pane", "color": AMARELO}]}}},
            "Rede de estações meteorológicas do INMET", 7, 25, 5, 8,
            "Automáticas e convencionais; situação atual informada pelo INMET.", versao=2,
            extra={"mark": {"opacity": 0.8}}, desagregado=True),
]

# ------------------------------------------------------------------ ajustes de layout
def esticar(pagina, nome, nova_altura):
    """Aumenta a altura de um widget e empurra para baixo tudo o que vem depois dele."""
    item = next(i for i in pagina if i["widget"]["name"] == nome)
    fim, delta = item["position"]["y"] + item["position"]["height"], nova_altura - item["position"]["height"]
    item["position"]["height"] = nova_altura
    for outro in pagina:
        if outro is not item and outro["position"]["y"] >= fim:
            outro["position"]["y"] += delta


for _pagina, _nome in ((p1, "p1-sub"), (p2, "p2-sub"), (p5, "p5-sub")):
    esticar(_pagina, _nome, 2)

_kpi = next(d for d in DATASETS if d["name"] == "ds_kpi")
_mapa = next(d for d in DATASETS if d["name"] == "ds_kpi_mapa")
_mapa["queryLines"] = [linha for linha in _kpi["queryLines"] if not linha.lstrip().startswith("--")]
_mapa["queryLines"][-1] = _mapa["queryLines"][-1].rstrip("\n") + "\n  AND latitude IS NOT NULL\n"


# ------------------------------------------------------------------ filtros globais
def filtro(nome, tipo, titulo, campo, datasets, x, y, w, padrao=None):
    queries = [{"name": f"{nome}_{d}", "query": {"datasetName": d, "fields": [{"name": campo, "expression": f"`{campo}`"}],
                                                   "disaggregated": False}} for d in datasets]
    spec = {"version": 2, "widgetType": tipo,
            "encodings": {"fields": [{"fieldName": campo, "displayName": titulo, "queryName": qq["name"]} for qq in queries]},
            "frame": frame(titulo)}
    if padrao:
        spec["selection"] = {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": v} for v in padrao]}}}
    return {"widget": {"name": nome, "queries": queries, "spec": spec}, "position": pos(x, y, w, 2)}


COM_REGIAO = ["ds_kpi", "ds_kpi_mapa", "ds_anual", "ds_anual_series", "ds_mensal_hist", "ds_sazonal", "ds_eventos",
              "ds_freq_extremos", "ds_spi", "ds_spi_atual", "ds_tendencia", "ds_geo", "ds_enso_regiao"]
filtros = [
    filtro("f-periodo", "filter-date-range-picker", "Período", "mes_ref",
           ["ds_anual", "ds_anual_series", "ds_mensal_hist", "ds_sazonal", "ds_eventos", "ds_freq_extremos", "ds_spi", "ds_geo",
            "ds_enso_regiao", "ds_enso"], 0, 0, 4),
    filtro("f-regiao", "filter-multi-select", "Região", "regiao", COM_REGIAO, 4, 0, 4),
    filtro("f-uf", "filter-multi-select", "UF", "sg_estado", [d for d in COM_REGIAO if d != "ds_enso_regiao"], 8, 0, 4),
    filtro("f-estacao", "filter-multi-select", "Estação", "estacao",
           ["ds_kpi", "ds_kpi_mapa", "ds_anual", "ds_anual_series", "ds_mensal_hist", "ds_sazonal", "ds_eventos",
            "ds_freq_extremos", "ds_spi", "ds_spi_atual", "ds_tendencia", "ds_geo"], 0, 2, 8),
    filtro("f-serie-longa", "filter-single-select", "Série longa (15+ anos)", "serie_longa",
           ["ds_anual", "ds_anual_series", "ds_mensal_hist", "ds_sazonal", "ds_eventos", "ds_freq_extremos"], 8, 2, 4,
           padrao=["Sim"]),
]

DASH = {
    "datasets": DATASETS,
    "pages": [
        {"name": "p1-visao-geral", "displayName": "01 · Visão geral", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": p1},
        {"name": "p2-historico", "displayName": "02 · Histórico", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": p2},
        {"name": "p3-enso", "displayName": "03 · El Niño / La Niña", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": p3},
        {"name": "p4-extremos", "displayName": "04 · Extremos e seca", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": p4},
        {"name": "p5-geografica", "displayName": "05 · Geográfica", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": p5},
        {"name": "filtros", "displayName": "Filtros", "pageType": "PAGE_TYPE_GLOBAL_FILTERS", "layoutVersion": "GRID_V1", "layout": filtros},
    ],
    "uiSettings": {"theme": {
        # identidade "plataforma científica": fundo escuro também no modo claro
        "canvasBackgroundColor": {"light": "#0B1220", "dark": "#0B1220"},
        "widgetBackgroundColor": {"light": "#111A2B", "dark": "#111A2B"},
        "widgetBorderColor": {"light": "#111A2B", "dark": "#111A2B"},
        "fontColor": {"light": "#E6EDF7", "dark": "#E6EDF7"},
        "selectionColor": {"light": AMARELO, "dark": AMARELO},
        "visualizationColors": [AZUL, VERMELHO, CIANO, AMARELO, ROXO, VERDE, CINZA, MARROM],
        "widgetHeaderAlignment": "LEFT",
        "widgetCornerRadius": 10,
    }},
}


# ------------------------------------------------------------------ validações
def _field_names(o) -> list[str]:
    if isinstance(o, dict):
        return ([o["fieldName"]] if "fieldName" in o else []) + [n for v in o.values() for n in _field_names(v)]
    if isinstance(o, list):
        return [n for v in o for n in _field_names(v)]
    return []


def validar(d):
    nomes_ds = {x["name"]: x for x in d["datasets"]}
    nomes_w = set()
    for pg in d["pages"]:
        linhas = {}
        for item in pg["layout"]:
            w, p = item["widget"], item["position"]
            assert w["name"] not in nomes_w, f"widget duplicado {w['name']}"
            nomes_w.add(w["name"])
            for yy in range(p["y"], p["y"] + p["height"]):
                linhas.setdefault(yy, []).append((p["x"], p["x"] + p["width"], w["name"]))
            if "queries" not in w:
                continue
            for qq in w["queries"]:
                assert qq["query"]["datasetName"] in nomes_ds, (w["name"], qq["query"]["datasetName"])
            if w["spec"]["widgetType"].startswith("filter"):
                continue
            campos = {f["name"] for qq in w["queries"] for f in qq["query"]["fields"]}
            usados = _field_names(w["spec"]["encodings"])
            falta = set(usados) - campos
            assert not falta, (w["name"], falta)
            # medidas referenciadas existem no dataset
            for qq in w["queries"]:
                cols = {c["displayName"] for c in nomes_ds[qq["query"]["datasetName"]].get("columns", [])}
                for f in qq["query"]["fields"]:
                    if f["expression"].startswith("MEASURE("):
                        assert f["expression"][9:-2] in cols, (w["name"], f["expression"])
        # sobreposição de widgets
        for yy, segs in linhas.items():
            segs.sort()
            for a, b in itertools.pairwise(segs):
                assert a[1] <= b[0], f"sobreposição na página {pg['name']} linha {yy}: {a[2]} x {b[2]}"
            assert max(s[1] for s in segs) <= 12


validar(DASH)
SAIDA.write_text(json.dumps(DASH, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"ok: {SAIDA} — {len(DASH['datasets'])} datasets, "
      f"{sum(len(p['layout']) for p in DASH['pages'])} widgets em {len(DASH['pages'])} páginas")
