-- Anomalias mensais por estação em relação à normal 2001–2025.
--  * anomalia_temp_c: diferença em °C para a média normal do mês
--  * anomalia_temp_padronizada: anomalia / desvio-padrão interanual (z-score)
--  * precipitacao_pct_normal: chuva do mês como % da normal (100 = igual à normal)
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_anomalia_mensal_estacao
CLUSTER BY (cd_estacao, mes_ref)
COMMENT 'Clima mensal por estação com anomalias de temperatura e chuva (base 2001–2025)'
AS
SELECT
  m.cd_estacao, m.nome_estacao, m.sg_estado, m.regiao, m.latitude, m.longitude,
  m.mes_ref, m.ano, m.mes,
  CASE WHEN m.mes_valido_temp  THEN m.temp_media_c END                      AS temp_media_c,
  n.temp_media_normal_c,
  CASE WHEN m.mes_valido_temp THEN round(m.temp_media_c - n.temp_media_normal_c, 2) END AS anomalia_temp_c,
  CASE WHEN m.mes_valido_temp AND n.temp_media_desvio_c > 0
       THEN round((m.temp_media_c - n.temp_media_normal_c) / n.temp_media_desvio_c, 2) END AS anomalia_temp_padronizada,
  CASE WHEN m.mes_valido_chuva THEN m.precipitacao_mm END                   AS precipitacao_mm,
  n.precipitacao_normal_mm,
  CASE WHEN m.mes_valido_chuva THEN round(m.precipitacao_mm - n.precipitacao_normal_mm, 1) END AS anomalia_precipitacao_mm,
  CASE WHEN m.mes_valido_chuva AND n.precipitacao_normal_mm > 0
       THEN round(100 * m.precipitacao_mm / n.precipitacao_normal_mm, 1) END AS precipitacao_pct_normal,
  n.n_anos_temp,
  n.n_anos_chuva
FROM gold_clima_mensal_estacao m
JOIN gold_clima_normal_mensal_estacao n USING (cd_estacao, mes)
WHERE m.mes_valido_temp OR m.mes_valido_chuva;
