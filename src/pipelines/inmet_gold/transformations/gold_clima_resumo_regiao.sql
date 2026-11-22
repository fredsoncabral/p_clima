-- "Climate Intelligence": resumo automático (baseado em regras) por região e Brasil,
-- para os últimos 12 e 3 meses com dados no BDMEP. Textos gerados a partir dos indicadores.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_resumo_regiao
COMMENT 'Resumo climático automático por região (temperatura, chuva, seca, calor, ENSO)'
AS
WITH ult AS (SELECT max(mes_ref) AS ultimo FROM gold_clima_anomalia_mensal_estacao),
a AS (
  SELECT
    coalesce(regiao, 'BR') AS regiao,
    avg(anomalia_temp_c) FILTER (WHERE NOT qc_temp_suspeito AND mes_ref > add_months(u.ultimo, -12)) AS anom_12m,
    avg(anomalia_temp_c) FILTER (WHERE NOT qc_temp_suspeito AND mes_ref > add_months(u.ultimo, -3))  AS anom_3m,
    sum(precipitacao_mm) FILTER (WHERE mes_ref > add_months(u.ultimo, -12))
      / sum(precipitacao_normal_mm) FILTER (WHERE precipitacao_mm IS NOT NULL AND mes_ref > add_months(u.ultimo, -12)) AS chuva_12m,
    sum(precipitacao_mm) FILTER (WHERE mes_ref > add_months(u.ultimo, -3))
      / sum(precipitacao_normal_mm) FILTER (WHERE precipitacao_mm IS NOT NULL AND mes_ref > add_months(u.ultimo, -3))  AS chuva_3m,
    count(DISTINCT cd_estacao) FILTER (WHERE mes_ref > add_months(u.ultimo, -12)) AS n_estacoes
  FROM gold_clima_anomalia_mensal_estacao CROSS JOIN ult u
  GROUP BY GROUPING SETS ((regiao), ())
),
s AS (
  SELECT coalesce(regiao, 'BR') AS regiao,
    percentile(spi, 0.5)                     AS spi3_mediano,
    avg(CASE WHEN spi <= -1 THEN 1 ELSE 0 END) AS frac_seca
  FROM gold_clima_spi_mensal_estacao CROSS JOIN ult u
  WHERE escala_meses = 3 AND mes_ref = u.ultimo
  GROUP BY GROUPING SETS ((regiao), ())
),
c AS (
  SELECT coalesce(regiao, 'BR') AS regiao,
    sum(dias_onda_calor) FILTER (WHERE mes_ref > add_months(u.ultimo, -12))
      / sum(dias_validos_temp) FILTER (WHERE mes_ref > add_months(u.ultimo, -12)) AS freq_onda_12m,
    sum(dias_onda_calor) FILTER (WHERE ano BETWEEN 2001 AND 2025)
      / sum(dias_validos_temp) FILTER (WHERE ano BETWEEN 2001 AND 2025)          AS freq_onda_base
  FROM gold_clima_eventos_mensal_estacao CROSS JOIN ult u
  GROUP BY GROUPING SETS ((regiao), ())
),
e AS (
  SELECT fase, intensidade, oni, temporada, ano AS ano_oni
  FROM gold_enso_mensal ORDER BY mes_ref DESC LIMIT 1
),
j AS (
  SELECT a.*, s.spi3_mediano, s.frac_seca, c.freq_onda_12m, c.freq_onda_base, e.*, u.ultimo
  FROM a LEFT JOIN s USING (regiao) LEFT JOIN c USING (regiao) CROSS JOIN e CROSS JOIN ult u
)
SELECT
  regiao,
  CASE regiao WHEN 'N' THEN 'Norte' WHEN 'NE' THEN 'Nordeste' WHEN 'CO' THEN 'Centro-Oeste'
              WHEN 'SE' THEN 'Sudeste' WHEN 'S' THEN 'Sul' ELSE 'Brasil' END             AS regiao_nome,
  CASE regiao WHEN 'BR' THEN 0 WHEN 'N' THEN 1 WHEN 'NE' THEN 2 WHEN 'CO' THEN 3
              WHEN 'SE' THEN 4 ELSE 5 END                                                AS ordem,
  add_months(ultimo, -11)                                                                AS periodo_inicio,
  ultimo                                                                                 AS periodo_fim,
  n_estacoes,
  round(anom_12m, 2) AS anomalia_temp_12m_c, round(anom_3m, 2) AS anomalia_temp_3m_c,
  round(chuva_12m, 3) AS chuva_12m_razao_normal, round(chuva_3m, 3) AS chuva_3m_razao_normal,
  round(spi3_mediano, 2) AS spi3_mediano, round(frac_seca, 3) AS frac_estacoes_seca,
  round(freq_onda_12m, 4) AS freq_onda_calor_12m, round(freq_onda_base, 4) AS freq_onda_calor_base,
  fase AS enso_fase, intensidade AS enso_intensidade, oni AS enso_oni,
  -- textos
  concat('Temperatura ',
    CASE WHEN anom_12m >= 0.5 THEN 'acima da normal' WHEN anom_12m <= -0.5 THEN 'abaixo da normal'
         ELSE 'próxima da normal' END,
    ': ', replace(format_string('%+.2f', anom_12m), '.', ','), ' °C nos últimos 12 meses (',
    replace(format_string('%+.2f', anom_3m), '.', ','), ' °C nos últimos 3).')                AS texto_temperatura,
  concat('Chuva ',
    CASE WHEN chuva_12m < 0.8 THEN 'com déficit' WHEN chuva_12m > 1.2 THEN 'com excesso'
         ELSE 'dentro do esperado' END,
    ': ', cast(round(100 * chuva_12m) AS INT), '% da normal em 12 meses e ',
    cast(round(100 * chuva_3m) AS INT), '% nos últimos 3 meses.')                             AS texto_chuva,
  concat('Seca (SPI-3): mediana ', replace(format_string('%.2f', spi3_mediano), '.', ','), ' — ',
    cast(round(100 * frac_seca) AS INT), '% das estações com SPI-3 ≤ -1 ',
    CASE WHEN frac_seca >= 0.3 THEN '(atenção ao déficit hídrico).' ELSE '.' END)            AS texto_seca,
  concat('Ondas de calor: ', replace(format_string('%.1f', 100 * freq_onda_12m), '.', ','),
    '% dos dias nos últimos 12 meses vs ', replace(format_string('%.1f', 100 * freq_onda_base), '.', ','),
    '% na base 2001–2025.')                                                                  AS texto_calor,
  concat('ENSO: ', fase, coalesce(concat(' ', lower(intensidade)), ''), ' (ONI ',
    replace(format_string('%+.2f', oni), '.', ','), ' em ', temporada, '/', ano_oni,
    '). Os efeitos variam por região e com defasagem — não atribuir anomalias automaticamente ao ENSO.') AS texto_enso
FROM j;
