-- Resumo anual por estação, com comparação contra a normal (2001–2025) e contra o ano anterior.
--  * Temperatura média anual = normal anual + anomalia média dos meses válidos (>= 10 meses).
--    Reconstruir pela anomalia evita o viés sazonal de anos com meses faltando.
--  * Chuva anual só com os 12 meses válidos (ausência de dado não é ausência de chuva).
--  * Meses com qc_temp_suspeito são ignorados.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_anual_estacao
CLUSTER BY (cd_estacao, ano)
COMMENT 'Clima anual por estação: médias, extremos, chuva, eventos extremos, anomalias e variação vs. ano anterior'
AS
WITH a AS (
  SELECT cd_estacao, ano,
    count(anomalia_temp_c) FILTER (WHERE NOT qc_temp_suspeito)  AS n_meses_temp,
    avg(anomalia_temp_c)   FILTER (WHERE NOT qc_temp_suspeito)  AS anomalia_media,
    count(precipitacao_mm)                                      AS n_meses_chuva,
    sum(precipitacao_mm)                                        AS chuva_soma
  FROM gold_clima_anomalia_mensal_estacao
  GROUP BY cd_estacao, ano
),
n AS (
  SELECT cd_estacao,
    avg(temp_media_normal_c)       AS temp_normal_anual_c,
    count(temp_media_normal_c)     AS n_normais_temp,
    sum(precipitacao_normal_mm)    AS chuva_normal_anual_mm,
    count(precipitacao_normal_mm)  AS n_normais_chuva
  FROM gold_clima_normal_mensal_estacao
  GROUP BY cd_estacao
),
m AS (
  SELECT cd_estacao, ano,
    max(nome_estacao) AS nome_estacao, max(sg_estado) AS sg_estado, max(regiao) AS regiao,
    max(latitude) AS latitude, max(longitude) AS longitude,
    avg(temp_max_media_c) FILTER (WHERE mes_valido_temp)        AS temp_max_media_c,
    avg(temp_min_media_c) FILTER (WHERE mes_valido_temp)        AS temp_min_media_c,
    sum(dias_com_chuva)                                         AS dias_com_chuva,
    avg(umidade_media_pct)                                      AS umidade_media_pct
  FROM gold_clima_mensal_estacao
  GROUP BY cd_estacao, ano
),
e AS (
  SELECT cd_estacao, ano,
    sum(dias_validos_temp)          AS dias_validos_temp,
    sum(dias_onda_calor)            AS dias_onda_calor,
    sum(n_ondas_calor)              AS n_ondas_calor,
    sum(dias_calor_extremo)         AS dias_calor_extremo,
    sum(dias_frio_extremo)          AS dias_frio_extremo,
    sum(dias_chuva_extrema)         AS dias_chuva_extrema,
    sum(dias_umidade_baixa)         AS dias_umidade_baixa,
    sum(dias_vento_extremo)         AS dias_vento_extremo,
    sum(dias_desconforto_calor)     AS dias_desconforto_calor,
    max(max_dias_secos_consecutivos) AS max_dias_secos_consecutivos,
    max(chuva_max_24h_mm)           AS chuva_max_24h_mm,
    max(rajada_max_ms)              AS rajada_max_ms,
    max(temp_max_absoluta_c)        AS temp_max_absoluta_c,
    min(temp_min_absoluta_c)        AS temp_min_absoluta_c,
    max(indice_calor_max_c)         AS indice_calor_max_c
  FROM gold_clima_eventos_mensal_estacao
  GROUP BY cd_estacao, ano
),
j AS (
  SELECT
    m.cd_estacao, m.nome_estacao, m.sg_estado, m.regiao, m.latitude, m.longitude, m.ano,
    a.n_meses_temp, a.n_meses_chuva,
    CASE WHEN a.n_meses_temp >= 10 AND n.n_normais_temp = 12
         THEN round(n.temp_normal_anual_c + a.anomalia_media, 2) END            AS temp_media_c,
    CASE WHEN n.n_normais_temp = 12 THEN round(n.temp_normal_anual_c, 2) END   AS temp_normal_c,
    CASE WHEN a.n_meses_temp >= 10 THEN round(a.anomalia_media, 2) END          AS anomalia_temp_c,
    round(m.temp_max_media_c, 2) AS temp_max_media_c,
    round(m.temp_min_media_c, 2) AS temp_min_media_c,
    round(m.temp_max_media_c - m.temp_min_media_c, 2)                          AS amplitude_termica_media_c,
    CASE WHEN a.n_meses_chuva = 12 THEN round(a.chuva_soma, 1) END              AS precipitacao_mm,
    CASE WHEN n.n_normais_chuva = 12 THEN round(n.chuva_normal_anual_mm, 1) END AS precipitacao_normal_mm,
    CASE WHEN a.n_meses_chuva = 12 AND n.n_normais_chuva = 12
         THEN round(a.chuva_soma - n.chuva_normal_anual_mm, 1) END              AS desvio_precipitacao_mm,
    CASE WHEN a.n_meses_chuva = 12 AND n.n_normais_chuva = 12 AND n.chuva_normal_anual_mm > 0
         THEN round(100 * a.chuva_soma / n.chuva_normal_anual_mm, 1) END        AS precipitacao_pct_normal,
    m.dias_com_chuva,
    round(m.umidade_media_pct, 1) AS umidade_media_pct,
    e.* EXCEPT (cd_estacao, ano)
  FROM m
  LEFT JOIN a USING (cd_estacao, ano)
  LEFT JOIN n USING (cd_estacao)
  LEFT JOIN e USING (cd_estacao, ano)
)
SELECT *,
  CASE WHEN lag(ano) OVER w = ano - 1 THEN round(temp_media_c - lag(temp_media_c) OVER w, 2) END     AS var_temp_ano_anterior_c,
  CASE WHEN lag(ano) OVER w = ano - 1 THEN round(precipitacao_mm - lag(precipitacao_mm) OVER w, 1) END AS var_precipitacao_ano_anterior_mm
FROM j
WINDOW w AS (PARTITION BY cd_estacao ORDER BY ano);
