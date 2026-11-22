-- Série mensal por região (e Brasil) com anomalias observadas e a fase do ENSO no mesmo mês.
-- Médias simples entre estações; meses com qc_temp_suspeito ignorados.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_enso_regiao_mensal
COMMENT 'Anomalias mensais por região (e Brasil) com ONI e fase do ENSO'
AS
WITH r AS (
  SELECT
    coalesce(regiao, 'BR')                                                        AS regiao,
    mes_ref, ano, mes,
    avg(anomalia_temp_c) FILTER (WHERE NOT qc_temp_suspeito)                      AS anomalia_temp_c,
    count(anomalia_temp_c) FILTER (WHERE NOT qc_temp_suspeito)                    AS n_estacoes_temp,
    avg(anomalia_precipitacao_mm)                                                 AS anomalia_precipitacao_mm,
    sum(precipitacao_mm)
      / sum(CASE WHEN precipitacao_mm IS NOT NULL THEN precipitacao_normal_mm END) AS razao_chuva_normal,
    count(precipitacao_mm)                                                        AS n_estacoes_chuva
  FROM gold_clima_anomalia_mensal_estacao
  GROUP BY GROUPING SETS ((regiao, mes_ref, ano, mes), (mes_ref, ano, mes))
)
SELECT
  r.regiao,
  CASE r.regiao WHEN 'N' THEN 'Norte' WHEN 'NE' THEN 'Nordeste' WHEN 'CO' THEN 'Centro-Oeste'
                WHEN 'SE' THEN 'Sudeste' WHEN 'S' THEN 'Sul' ELSE 'Brasil' END    AS regiao_nome,
  r.mes_ref, r.ano, r.mes,
  round(r.anomalia_temp_c, 2)           AS anomalia_temp_c,
  r.n_estacoes_temp,
  round(r.anomalia_precipitacao_mm, 1)  AS anomalia_precipitacao_mm,
  round(r.razao_chuva_normal, 3)        AS razao_chuva_normal,
  r.n_estacoes_chuva,
  e.oni, e.fase, e.intensidade
FROM r
LEFT JOIN gold_enso_mensal e ON e.mes_ref = r.mes_ref;
