-- Visão mensal por UF: média entre as estações com mês válido.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_mensal_uf
CLUSTER BY (sg_estado, mes_ref)
COMMENT 'Clima mensal por UF (média das estações válidas), com anomalias vs. normal 2001–2025'
AS
SELECT
  sg_estado,
  max(regiao)                                                   AS regiao,
  mes_ref, ano, mes,
  count(temp_media_c)                                           AS n_estacoes_temp,
  count(precipitacao_mm)                                        AS n_estacoes_chuva,
  round(avg(temp_media_c) FILTER (WHERE NOT qc_temp_suspeito), 2) AS temp_media_c,
  round(avg(anomalia_temp_c) FILTER (WHERE NOT qc_temp_suspeito), 2) AS anomalia_temp_c,
  round(avg(precipitacao_mm), 1)                                AS precipitacao_media_mm,
  round(percentile(precipitacao_pct_normal, 0.5), 1)            AS precipitacao_pct_normal_mediana
FROM gold_clima_anomalia_mensal_estacao
GROUP BY sg_estado, mes_ref, ano, mes;
