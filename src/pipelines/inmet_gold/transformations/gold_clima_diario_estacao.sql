-- Agregado diário por estação.
--  * Dia no fuso local da UF (IANA, considera o horário de verão histórico, extinto em 2019).
--  * Leituras fisicamente implausíveis viram NULL antes de agregar
--    (temperatura fora de -15..50 °C; radiação fora de 0..5000 kJ/m² por hora).
--  * Dia "completo" = pelo menos 18 das 24 horas com dado.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_diario_estacao
CLUSTER BY (cd_estacao, data_local)
COMMENT 'Clima diário por estação automática do INMET (BDMEP), unidades métricas, dia no fuso local'
AS
WITH h AS (
  SELECT
    cd_estacao, sg_estado, regiao, nome_estacao, ts_utc,
    to_date(from_utc_timestamp(ts_utc, CASE sg_estado
      WHEN 'AC' THEN 'America/Rio_Branco'
      WHEN 'AM' THEN 'America/Manaus'
      WHEN 'RR' THEN 'America/Boa_Vista'
      WHEN 'RO' THEN 'America/Porto_Velho'
      WHEN 'MT' THEN 'America/Cuiaba'
      WHEN 'MS' THEN 'America/Campo_Grande'
      ELSE 'America/Sao_Paulo' END))                                          AS data_local,
    CASE WHEN temp_ar_c  BETWEEN -15 AND 50 THEN temp_ar_c  END                 AS temp_c,
    CASE WHEN temp_max_c BETWEEN -15 AND 50 THEN temp_max_c END                 AS temp_max_hora_c,
    CASE WHEN temp_min_c BETWEEN -15 AND 50 THEN temp_min_c END                 AS temp_min_hora_c,
    CASE WHEN precipitacao_mm >= 0 THEN precipitacao_mm END                     AS chuva_mm,
    CASE WHEN umidade_rel_pct BETWEEN 0 AND 100 THEN umidade_rel_pct END        AS umidade_pct,
    CASE WHEN umidade_rel_min_pct BETWEEN 0 AND 100 THEN umidade_rel_min_pct END AS umidade_min_hora_pct,
    CASE WHEN radiacao_global_kj_m2 BETWEEN 0 AND 5000 THEN radiacao_global_kj_m2 END AS radiacao_kj_m2,
    CASE WHEN vento_velocidade_ms >= 0 THEN vento_velocidade_ms END             AS vento_ms,
    CASE WHEN vento_rajada_max_ms >= 0 THEN vento_rajada_max_ms END             AS rajada_ms,
    pressao_estacao_hpa
  FROM silver_inmet_bdmep_horario
),
d AS (
  SELECT
    cd_estacao,
    data_local,
    max_by(sg_estado, ts_utc)                                  AS sg_estado,
    max_by(regiao, ts_utc)                                     AS regiao,
    max_by(nome_estacao, ts_utc)                               AS nome_estacao_bdmep,
    count(*)                                                   AS horas_observadas,
    count(temp_c)                                              AS horas_temp,
    count(chuva_mm)                                            AS horas_chuva,
    round(avg(temp_c), 2)                                      AS temp_media_c,
    greatest(max(temp_max_hora_c), max(temp_c))                AS temp_max_c,
    least(min(temp_min_hora_c), min(temp_c))                   AS temp_min_c,
    round(sum(chuva_mm), 1)                                    AS precipitacao_mm,
    round(avg(umidade_pct), 1)                                 AS umidade_media_pct,
    least(min(umidade_min_hora_pct), min(umidade_pct))         AS umidade_min_pct,
    round(sum(radiacao_kj_m2) / 1000, 2)                       AS radiacao_global_mj_m2,
    round(avg(vento_ms), 2)                                    AS vento_medio_ms,
    max(rajada_ms)                                             AS rajada_max_ms,
    round(avg(pressao_estacao_hpa), 1)                         AS pressao_media_hpa
  FROM h
  GROUP BY cd_estacao, data_local
)
SELECT
  d.cd_estacao,
  coalesce(e.nome_estacao, d.nome_estacao_bdmep)               AS nome_estacao,
  d.sg_estado,
  d.regiao,
  e.latitude,
  e.longitude,
  e.altitude_m,
  d.data_local,
  year(d.data_local)                                           AS ano,
  month(d.data_local)                                          AS mes,
  d.* EXCEPT (cd_estacao, data_local, sg_estado, regiao, nome_estacao_bdmep),
  d.horas_temp  >= 18                                          AS dia_completo_temp,
  d.horas_chuva >= 18                                          AS dia_completo_chuva
FROM d
LEFT JOIN silver_inmet_estacoes e USING (cd_estacao);
