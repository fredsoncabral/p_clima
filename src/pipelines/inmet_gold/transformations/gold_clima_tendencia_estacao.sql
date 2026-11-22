-- Tendência linear (mínimos quadrados) por estação, a partir das séries anuais.
--  * Exige >= 15 anos com dado anual válido.
--  * tendencia_temp_c_decada: inclinação da anomalia anual de temperatura (°C por década).
--  * significativa_95: |t| >= 2,1 (aprox. 95 % bicaudal para 13–25 graus de liberdade).
--  Séries curtas (15–26 anos) e mudanças de instrumento/local exigem cautela na interpretação.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_tendencia_estacao
COMMENT 'Tendência linear de temperatura e chuva por estação (°C/década, mm/década)'
AS
WITH r AS (
  SELECT cd_estacao,
    max(nome_estacao) AS nome_estacao, max(sg_estado) AS sg_estado, max(regiao) AS regiao,
    max(latitude) AS latitude, max(longitude) AS longitude,
    count(anomalia_temp_c)                                      AS n_anos_temp,
    min(ano) FILTER (WHERE anomalia_temp_c IS NOT NULL)         AS ano_inicio_temp,
    max(ano) FILTER (WHERE anomalia_temp_c IS NOT NULL)         AS ano_fim_temp,
    regr_slope(anomalia_temp_c, ano)                            AS b_temp,
    regr_r2(anomalia_temp_c, ano)                               AS r2_temp,
    count(precipitacao_mm)                                      AS n_anos_chuva,
    regr_slope(precipitacao_mm, ano)                            AS b_chuva,
    regr_r2(precipitacao_mm, ano)                               AS r2_chuva,
    avg(precipitacao_mm)                                        AS chuva_media_anual_mm
  FROM gold_clima_anual_estacao
  GROUP BY cd_estacao
)
SELECT cd_estacao, nome_estacao, sg_estado, regiao, latitude, longitude,
  n_anos_temp, ano_inicio_temp, ano_fim_temp,
  CASE WHEN n_anos_temp >= 15 THEN round(b_temp * 10, 2) END                            AS tendencia_temp_c_decada,
  CASE WHEN n_anos_temp >= 15 THEN round(r2_temp, 3) END                                AS r2_temp,
  CASE WHEN n_anos_temp >= 15 AND r2_temp < 1
       THEN abs(sqrt(r2_temp) * sqrt((n_anos_temp - 2) / (1 - r2_temp))) >= 2.1 END    AS significativa_95_temp,
  n_anos_chuva,
  CASE WHEN n_anos_chuva >= 15 THEN round(b_chuva * 10, 1) END                          AS tendencia_chuva_mm_decada,
  CASE WHEN n_anos_chuva >= 15 AND chuva_media_anual_mm > 0
       THEN round(100 * b_chuva * 10 / chuva_media_anual_mm, 1) END                     AS tendencia_chuva_pct_decada,
  CASE WHEN n_anos_chuva >= 15 AND r2_chuva < 1
       THEN abs(sqrt(r2_chuva) * sqrt((n_anos_chuva - 2) / (1 - r2_chuva))) >= 2.1 END AS significativa_95_chuva
FROM r;
