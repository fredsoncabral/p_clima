-- Cadastro de estações (automáticas + convencionais), tipado.
CREATE OR REFRESH MATERIALIZED VIEW silver_inmet_estacoes (
  CONSTRAINT cd_estacao_ok EXPECT (cd_estacao IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT lat_no_brasil EXPECT (latitude BETWEEN -34 AND 6),
  CONSTRAINT lon_no_brasil EXPECT (longitude BETWEEN -75 AND -28)
)
COMMENT 'Estações meteorológicas do INMET (fonte: apitempo /estacoes/T e /estacoes/M)'
AS SELECT
  trim(cd_estacao)                                   AS cd_estacao,
  trim(dc_nome)                                      AS nome_estacao,
  tp_estacao                                         AS tipo_estacao,
  sg_estado,
  cd_situacao                                        AS situacao,
  fl_capital = 'S'                                   AS fl_capital,
  try_cast(vl_latitude  AS DOUBLE)                   AS latitude,
  try_cast(vl_longitude AS DOUBLE)                   AS longitude,
  try_cast(vl_altitude  AS DOUBLE)                   AS altitude_m,
  to_date(substr(dt_inicio_operacao, 1, 10))         AS dt_inicio_operacao,
  to_date(substr(dt_fim_operacao, 1, 10))            AS dt_fim_operacao,
  cd_oscar,
  cd_wsi,
  trim(cd_distrito)                                  AS cd_distrito,
  sg_entidade,
  _ingerido_em
FROM bronze_inmet_estacoes;
