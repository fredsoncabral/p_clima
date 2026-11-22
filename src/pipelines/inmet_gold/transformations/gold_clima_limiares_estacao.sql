-- Limiares climatológicos por estação e mês do calendário (base 2001–2025, só dias completos).
-- Base para eventos extremos relativos ao clima LOCAL (40 °C é comum em Cuiabá e raro em Curitiba).
--  * tmax_p90 -> onda de calor (>= 5 dias consecutivos acima)
--  * tmax_p95 / tmin_p05 -> calor / frio extremo
--  * chuva_p95 -> chuva extrema (percentil 95 dos dias com chuva >= 1 mm)
--  * frac_dias_chuvosos -> fração de dias com chuva >= 1 mm (identifica a estação chuvosa local)
-- Limiares exigem amostra mínima (~5 anos de dias completos naquele mês).
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_limiares_estacao
COMMENT 'Percentis climatológicos diários por estação e mês (base 2001–2025)'
AS
WITH b AS (
  SELECT cd_estacao, mes,
    count_if(dia_completo_temp)                                                        AS n_dias_temp,
    count_if(dia_completo_chuva AND precipitacao_mm >= 1)                              AS n_dias_chuvosos,
    count_if(dia_completo_chuva)                                                       AS n_dias_chuva,
    percentile(temp_max_c, 0.90) FILTER (WHERE dia_completo_temp)                      AS tmax_p90,
    percentile(temp_max_c, 0.95) FILTER (WHERE dia_completo_temp)                      AS tmax_p95,
    percentile(temp_min_c, 0.05) FILTER (WHERE dia_completo_temp)                      AS tmin_p05,
    percentile(precipitacao_mm, 0.95) FILTER (WHERE dia_completo_chuva AND precipitacao_mm >= 1) AS chuva_p95
  FROM gold_clima_diario_estacao
  WHERE ano BETWEEN 2001 AND 2025
  GROUP BY cd_estacao, mes
)
SELECT cd_estacao, mes, n_dias_temp, n_dias_chuvosos,
  CASE WHEN n_dias_temp >= 140 THEN round(tmax_p90, 1) END     AS tmax_p90_c,
  CASE WHEN n_dias_temp >= 140 THEN round(tmax_p95, 1) END     AS tmax_p95_c,
  CASE WHEN n_dias_temp >= 140 THEN round(tmin_p05, 1) END     AS tmin_p05_c,
  CASE WHEN n_dias_chuvosos >= 30 THEN round(chuva_p95, 1) END AS chuva_p95_mm,
  CASE WHEN n_dias_chuva >= 140 THEN round(n_dias_chuvosos / n_dias_chuva, 3) END AS frac_dias_chuvosos
FROM b;
