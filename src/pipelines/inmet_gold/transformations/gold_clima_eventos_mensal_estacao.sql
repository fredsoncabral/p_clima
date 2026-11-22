-- Contagem mensal de eventos extremos por estação (base para rankings, frequências e mapas).
-- Frequências relativas (% dos dias válidos) permitem comparar períodos com redes de tamanhos diferentes.
CREATE OR REFRESH MATERIALIZED VIEW gold_clima_eventos_mensal_estacao
CLUSTER BY (cd_estacao, mes_ref)
COMMENT 'Eventos extremos por estação e mês: ondas de calor, extremos de temperatura/chuva, umidade baixa, vento'
AS SELECT
  cd_estacao,
  max(nome_estacao)                          AS nome_estacao,
  max(sg_estado)                             AS sg_estado,
  max(regiao)                                AS regiao,
  max(latitude)                              AS latitude,
  max(longitude)                             AS longitude,
  make_date(ano, mes, 1)                     AS mes_ref,
  ano, mes,
  count_if(dia_completo_temp)                AS dias_validos_temp,
  count_if(dia_completo_chuva)               AS dias_validos_chuva,
  count_if(onda_de_calor)                    AS dias_onda_calor,
  count_if(inicio_onda_de_calor)             AS n_ondas_calor,
  count_if(calor_extremo)                    AS dias_calor_extremo,
  count_if(frio_extremo)                     AS dias_frio_extremo,
  count_if(chuva_extrema)                    AS dias_chuva_extrema,
  count_if(umidade_baixa)                    AS dias_umidade_baixa,
  count_if(vento_extremo)                    AS dias_vento_extremo,
  count_if(desconforto_calor)                AS dias_desconforto_calor,
  count_if(indice_calor_max_c >= 41)         AS dias_perigo_calor,
  max(dias_secos_consecutivos)               AS max_dias_secos_consecutivos,
  max(precipitacao_mm) FILTER (WHERE dia_completo_chuva) AS chuva_max_24h_mm,
  max(rajada_max_ms)                         AS rajada_max_ms,
  max(indice_calor_max_c)                    AS indice_calor_max_c,
  max(temp_max_c) FILTER (WHERE dia_completo_temp)       AS temp_max_absoluta_c,
  min(temp_min_c) FILTER (WHERE dia_completo_temp)       AS temp_min_absoluta_c
FROM gold_clima_eventos_diarios
GROUP BY cd_estacao, ano, mes;
