-- Eventos extremos por estação e dia.
--  * calor_extremo: Tmáx > p95 local do mês     * frio_extremo: Tmín < p05 local do mês
--  * chuva_extrema: chuva diária > p95 local    * umidade_baixa: umidade mínima < 30 %
--  * vento_extremo: rajada >= 20 m/s (72 km/h)  * desconforto_calor: índice de calor >= 32 °C
--  * onda_de_calor: dia dentro de uma sequência de >= 5 dias consecutivos com Tmáx > p90 local
--  * dias_secos_consecutivos: posição do dia numa sequência de dias secos (< 1 mm)
-- Dias incompletos não entram em sequências (ausência de dado não é ausência de chuva).
-- QC de extremos: Tmáx > p95 local + 8 °C ou >= 45 °C (saturação; recorde oficial 44,8 °C),
--   Tmín < p05 local - 8 °C ou < -10 °C, e rajadas > 50 m/s (180 km/h)
--   são tratadas como defeito de sensor (ex.: 45 °C em Salvador em junho; rajada de 99,7 m/s em Manaus).
-- QC pluviômetro travado: sequência seca com >= 45 dias dentro da estação chuvosa local
-- (meses em que chove em >= 35 % dos dias) -> chuva_suspeita; esses dias não contam como secos.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_eventos_diarios
CLUSTER BY (cd_estacao, data_local)
COMMENT 'Indicadores diários de eventos extremos por estação, com limiares climatológicos locais'
AS
WITH d AS (
  SELECT x.* EXCEPT (temp_max_c, temp_min_c, rajada_max_ms),
    CASE WHEN x.temp_max_c < 45 AND (l.tmax_p95_c IS NULL OR x.temp_max_c <= l.tmax_p95_c + 8)
         THEN x.temp_max_c END                                                              AS temp_max_c,
    CASE WHEN x.temp_min_c >= -10 AND (l.tmin_p05_c IS NULL OR x.temp_min_c >= l.tmin_p05_c - 8)
         THEN x.temp_min_c END                                                              AS temp_min_c,
    CASE WHEN x.rajada_max_ms <= 50 THEN x.rajada_max_ms END                                AS rajada_max_ms
  FROM gold_clima_diario_estacao x
  LEFT JOIN gold_clima_limiares_estacao l USING (cd_estacao, mes)
),
f AS (
  SELECT
    d.cd_estacao, d.nome_estacao, d.sg_estado, d.regiao, d.latitude, d.longitude,
    d.data_local, d.ano, d.mes,
    d.temp_max_c, d.temp_min_c, d.precipitacao_mm, d.umidade_min_pct, d.rajada_max_ms, d.indice_calor_max_c,
    d.dia_completo_temp, d.dia_completo_chuva,
    l.tmax_p90_c, l.tmax_p95_c, l.tmin_p05_c, l.chuva_p95_mm,
    coalesce(l.frac_dias_chuvosos >= 0.35, false)                                           AS mes_chuvoso_local,
    coalesce(d.dia_completo_temp AND d.temp_max_c > l.tmax_p90_c, false)                    AS acima_p90,
    coalesce(d.dia_completo_temp AND d.temp_max_c > l.tmax_p95_c, false)                    AS calor_extremo,
    coalesce(d.dia_completo_temp AND d.temp_min_c < l.tmin_p05_c, false)                    AS frio_extremo,
    coalesce(d.dia_completo_chuva AND d.precipitacao_mm >= 1
             AND d.precipitacao_mm > l.chuva_p95_mm, false)                                AS chuva_extrema,
    coalesce(d.umidade_min_pct < 30, false)                                                 AS umidade_baixa,
    coalesce(d.rajada_max_ms >= 20, false)                                                  AS vento_extremo,
    coalesce(d.indice_calor_max_c >= 32, false)                                             AS desconforto_calor,
    coalesce(d.dia_completo_chuva AND d.precipitacao_mm < 1, false)                         AS dia_seco
  FROM d
  LEFT JOIN gold_clima_limiares_estacao l USING (cd_estacao, mes)
),
g AS (  -- "ilhas" de dias consecutivos: data - nº da linha é constante dentro de uma sequência
  SELECT *,
    date_sub(data_local, CAST(row_number() OVER (PARTITION BY cd_estacao, acima_p90 ORDER BY data_local) AS INT)) AS grp_calor,
    date_sub(data_local, CAST(row_number() OVER (PARTITION BY cd_estacao, dia_seco ORDER BY data_local) AS INT))  AS grp_seco
  FROM f
),
r AS (
  SELECT *,
    count(*)     OVER (PARTITION BY cd_estacao, acima_p90, grp_calor)                       AS tam_seq_calor,
    row_number() OVER (PARTITION BY cd_estacao, acima_p90, grp_calor ORDER BY data_local)   AS pos_seq_calor,
    row_number() OVER (PARTITION BY cd_estacao, dia_seco, grp_seco ORDER BY data_local)     AS pos_seq_seco,
    sum(CASE WHEN mes_chuvoso_local THEN 1 ELSE 0 END)
      OVER (PARTITION BY cd_estacao, dia_seco, grp_seco)                                    AS dias_chuvosos_na_seq
  FROM g
)
SELECT
  cd_estacao, nome_estacao, sg_estado, regiao, latitude, longitude, data_local, ano, mes,
  temp_max_c, temp_min_c, precipitacao_mm, umidade_min_pct, rajada_max_ms, indice_calor_max_c,
  dia_completo_temp, dia_completo_chuva,
  tmax_p90_c, tmax_p95_c, tmin_p05_c, chuva_p95_mm,
  calor_extremo, frio_extremo, chuva_extrema, umidade_baixa, vento_extremo, desconforto_calor,
  dia_seco AND dias_chuvosos_na_seq >= 45                 AS chuva_suspeita,
  dia_seco AND dias_chuvosos_na_seq < 45                  AS dia_seco,
  acima_p90 AND tam_seq_calor >= 5                        AS onda_de_calor,
  acima_p90 AND tam_seq_calor >= 5 AND pos_seq_calor = 1  AS inicio_onda_de_calor,
  CASE WHEN acima_p90 THEN tam_seq_calor END              AS duracao_seq_calor_dias,
  CASE WHEN dia_seco AND dias_chuvosos_na_seq < 45 THEN pos_seq_seco ELSE 0 END AS dias_secos_consecutivos
FROM r;
