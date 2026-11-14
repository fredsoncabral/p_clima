-- Climatologia de referência (normal) por estação e mês do ano, período-base 2001–2025.
-- Usa só meses válidos; exige pelo menos 5 anos de dados no período.
-- Obs.: a Normal Climatológica oficial da OMM usa 30 anos (1991–2020); as estações
-- automáticas só existem a partir de 2000, por isso a base aqui é mais curta.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_normal_mensal_estacao
COMMENT 'Normal mensal por estação (base 2001–2025, mínimo 5 anos válidos)'
AS
WITH t AS (
  SELECT cd_estacao, mes,
         count(*)                    AS n_anos_temp,
         round(avg(temp_media_c), 2) AS temp_media_normal_c,
         round(stddev(temp_media_c), 2) AS temp_media_desvio_c
  FROM gold_clima_mensal_estacao
  WHERE mes_valido_temp AND ano BETWEEN 2001 AND 2025
  GROUP BY cd_estacao, mes
),
c AS (
  SELECT cd_estacao, mes,
         count(*)                       AS n_anos_chuva,
         round(avg(precipitacao_mm), 1) AS precipitacao_normal_mm
  FROM gold_clima_mensal_estacao
  WHERE mes_valido_chuva AND ano BETWEEN 2001 AND 2025
  GROUP BY cd_estacao, mes
)
SELECT
  cd_estacao,
  mes,
  CASE WHEN n_anos_temp  >= 5 THEN temp_media_normal_c END    AS temp_media_normal_c,
  CASE WHEN n_anos_temp  >= 5 THEN temp_media_desvio_c END    AS temp_media_desvio_c,
  coalesce(n_anos_temp, 0)                                    AS n_anos_temp,
  CASE WHEN n_anos_chuva >= 5 THEN precipitacao_normal_mm END AS precipitacao_normal_mm,
  coalesce(n_anos_chuva, 0)                                   AS n_anos_chuva
FROM t FULL OUTER JOIN c USING (cd_estacao, mes)
WHERE coalesce(n_anos_temp, 0) >= 5 OR coalesce(n_anos_chuva, 0) >= 5;
