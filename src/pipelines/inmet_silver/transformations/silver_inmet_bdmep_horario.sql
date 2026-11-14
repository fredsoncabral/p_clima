-- Série horária histórica (BDMEP) tipada.
--  * '-9999' (ausente) e vazios -> NULL; vírgula decimal -> ponto
--  * data/hora em dois layouts: '2024/01/01' + '0000 UTC'  |  '2000-05-13' + '00:00'
--  * linhas sem nenhuma medição são descartadas
CREATE OR REFRESH MATERIALIZED VIEW silver_inmet_bdmep_horario (
  CONSTRAINT ts_valido        EXPECT (ts_utc IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT tem_medicao      EXPECT (coalesce(precipitacao_mm, pressao_estacao_hpa, radiacao_global_kj_m2,
                                               temp_ar_c, umidade_rel_pct, vento_velocidade_ms) IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT temp_plausivel   EXPECT (temp_ar_c IS NULL OR temp_ar_c BETWEEN -15 AND 50),
  CONSTRAINT umidade_0_100    EXPECT (umidade_rel_pct IS NULL OR umidade_rel_pct BETWEEN 0 AND 100),
  CONSTRAINT chuva_nao_neg    EXPECT (precipitacao_mm IS NULL OR precipitacao_mm >= 0)
)
CLUSTER BY (cd_estacao, ts_utc)
COMMENT 'Observações horárias das estações automáticas do INMET (BDMEP), unidades métricas, horário UTC'
AS
WITH b AS (
  SELECT *,
    to_timestamp(
      concat(replace(data, '/', '-'), ' ', substr(regexp_replace(hora_utc, '[^0-9]', ''), 1, 4)),
      'yyyy-MM-dd HHmm') AS ts
  FROM bronze_inmet_bdmep_horario
)
SELECT
  cd_estacao,
  sg_estado,
  regiao,
  nome_estacao,
  ts                                                                         AS ts_utc,
  to_date(ts)                                                                AS data_utc,
  ano,
  nullif(try_cast(replace(precipitacao_total_mm, ',', '.') AS DOUBLE), -9999) AS precipitacao_mm,
  nullif(try_cast(replace(pressao_estacao_mb,   ',', '.') AS DOUBLE), -9999) AS pressao_estacao_hpa,
  nullif(try_cast(replace(pressao_max_mb,       ',', '.') AS DOUBLE), -9999) AS pressao_max_hpa,
  nullif(try_cast(replace(pressao_min_mb,       ',', '.') AS DOUBLE), -9999) AS pressao_min_hpa,
  nullif(try_cast(replace(radiacao_global_kj_m2, ',', '.') AS DOUBLE), -9999) AS radiacao_global_kj_m2,
  nullif(try_cast(replace(temp_ar_c,            ',', '.') AS DOUBLE), -9999) AS temp_ar_c,
  nullif(try_cast(replace(temp_orvalho_c,       ',', '.') AS DOUBLE), -9999) AS temp_orvalho_c,
  nullif(try_cast(replace(temp_max_c,           ',', '.') AS DOUBLE), -9999) AS temp_max_c,
  nullif(try_cast(replace(temp_min_c,           ',', '.') AS DOUBLE), -9999) AS temp_min_c,
  nullif(try_cast(replace(temp_orvalho_max_c,   ',', '.') AS DOUBLE), -9999) AS temp_orvalho_max_c,
  nullif(try_cast(replace(temp_orvalho_min_c,   ',', '.') AS DOUBLE), -9999) AS temp_orvalho_min_c,
  nullif(try_cast(replace(umidade_rel_max_pct,  ',', '.') AS DOUBLE), -9999) AS umidade_rel_max_pct,
  nullif(try_cast(replace(umidade_rel_min_pct,  ',', '.') AS DOUBLE), -9999) AS umidade_rel_min_pct,
  nullif(try_cast(replace(umidade_rel_pct,      ',', '.') AS DOUBLE), -9999) AS umidade_rel_pct,
  nullif(try_cast(replace(vento_direcao_graus,  ',', '.') AS DOUBLE), -9999) AS vento_direcao_graus,
  nullif(try_cast(replace(vento_rajada_max_ms,  ',', '.') AS DOUBLE), -9999) AS vento_rajada_max_ms,
  nullif(try_cast(replace(vento_velocidade_ms,  ',', '.') AS DOUBLE), -9999) AS vento_velocidade_ms,
  _arquivo_origem
FROM b;
