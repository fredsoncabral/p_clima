-- Agregado mensal por estação, usando apenas dias completos.
--  * Temperatura do mês válida com >= 20 dias completos.
--  * Chuva do mês válida com no máximo 2 dias faltantes (o total é sensível a lacunas)
--    e sem dias marcados como pluviômetro travado (ver gold_clima_eventos_diarios.chuva_suspeita).
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_mensal_estacao
CLUSTER BY (cd_estacao, mes_ref)
COMMENT 'Clima mensal por estação do INMET, com indicadores de validade do mês'
AS
WITH qc AS (
  SELECT cd_estacao, ano, mes, count_if(chuva_suspeita) AS dias_chuva_suspeita
  FROM gold_clima_eventos_diarios
  GROUP BY cd_estacao, ano, mes
)
SELECT
  cd_estacao,
  max(nome_estacao)                                                          AS nome_estacao,
  max(sg_estado)                                                             AS sg_estado,
  max(regiao)                                                                AS regiao,
  max(latitude)                                                              AS latitude,
  max(longitude)                                                             AS longitude,
  make_date(ano, mes, 1)                                                     AS mes_ref,
  ano,
  mes,
  day(last_day(make_date(ano, mes, 1)))                                      AS dias_no_mes,
  count_if(dia_completo_temp)                                                AS dias_completos_temp,
  count_if(dia_completo_chuva)                                               AS dias_completos_chuva,
  round(avg(temp_media_c) FILTER (WHERE dia_completo_temp), 2)               AS temp_media_c,
  round(avg(temp_max_c)   FILTER (WHERE dia_completo_temp), 2)               AS temp_max_media_c,
  round(avg(temp_min_c)   FILTER (WHERE dia_completo_temp), 2)               AS temp_min_media_c,
  max(temp_max_c)         FILTER (WHERE dia_completo_temp)                   AS temp_max_absoluta_c,
  min(temp_min_c)         FILTER (WHERE dia_completo_temp)                   AS temp_min_absoluta_c,
  round(sum(precipitacao_mm) FILTER (WHERE dia_completo_chuva), 1)           AS precipitacao_mm,
  max(precipitacao_mm)    FILTER (WHERE dia_completo_chuva)                  AS precipitacao_max_diaria_mm,
  count_if(dia_completo_chuva AND precipitacao_mm >= 1)                      AS dias_com_chuva,
  round(avg(umidade_media_pct), 1)                                           AS umidade_media_pct,
  min(umidade_min_pct)                                                       AS umidade_min_pct,
  round(avg(radiacao_global_mj_m2) FILTER (WHERE dia_completo_temp), 2)      AS radiacao_media_diaria_mj_m2,
  max(rajada_max_ms)                                                         AS rajada_max_ms,
  round(avg(vento_medio_ms), 2)                                              AS vento_medio_ms,
  count_if(dia_completo_temp)  >= 20                                         AS mes_valido_temp,
  max(coalesce(qc.dias_chuva_suspeita, 0))                                   AS dias_chuva_suspeita,
  count_if(dia_completo_chuva) >= day(last_day(make_date(ano, mes, 1))) - 2
    AND max(coalesce(qc.dias_chuva_suspeita, 0)) = 0                         AS mes_valido_chuva
FROM gold_clima_diario_estacao
LEFT JOIN qc USING (cd_estacao, ano, mes)
GROUP BY cd_estacao, ano, mes;
