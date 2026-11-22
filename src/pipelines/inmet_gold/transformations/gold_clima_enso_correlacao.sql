-- Correlação de Pearson entre o ONI e as anomalias regionais, com defasagens de 0 a 6 meses
-- (o efeito do ENSO no Brasil costuma aparecer com atraso e varia por região).
-- Usa 2008+ (rede com > 400 estações); sem ajuste de sazonalidade/autocorrelação — exploratório.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_enso_correlacao
COMMENT 'Correlação ONI x anomalias regionais de temperatura e chuva, defasagem 0–6 meses (2008+)'
AS
SELECT
  r.regiao, r.regiao_nome, l.defasagem_meses,
  round(corr(e.oni, r.anomalia_temp_c), 2)          AS corr_oni_temperatura,
  round(corr(e.oni, r.anomalia_precipitacao_mm), 2) AS corr_oni_chuva,
  count(*)                                          AS n_meses
FROM gold_clima_enso_regiao_mensal r
CROSS JOIN (SELECT explode(sequence(0, 6)) AS defasagem_meses) l
JOIN gold_enso_mensal e ON e.mes_ref = add_months(r.mes_ref, -l.defasagem_meses)
WHERE r.ano >= 2008
GROUP BY r.regiao, r.regiao_nome, l.defasagem_meses;
