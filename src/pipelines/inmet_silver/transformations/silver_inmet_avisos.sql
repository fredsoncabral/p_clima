-- Avisos meteorológicos: última versão de cada aviso (bronze guarda uma foto por execução).
-- inicio/fim vêm em horário de Brasília (texto 'yyyy-MM-dd HH:mm') e são convertidos para UTC.
CREATE OR REFRESH MATERIALIZED VIEW silver_inmet_avisos (
  CONSTRAINT id_ok EXPECT (id IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Avisos meteorológicos do INMET (apiprevmet3 /avisos/ativos), versão mais recente por id'
AS
WITH p AS (
  SELECT
    cast(id AS BIGINT)                                             AS id,
    cast(id_aviso AS BIGINT)                                       AS id_aviso,
    codigo,
    get_json_object(payload, '$.descricao')                        AS descricao,
    get_json_object(payload, '$.severidade')                       AS severidade,
    cast(get_json_object(payload, '$.id_severidade') AS INT)       AS id_severidade,
    get_json_object(payload, '$.aviso_cor')                        AS aviso_cor,
    to_utc_timestamp(to_timestamp(get_json_object(payload, '$.inicio'), 'yyyy-MM-dd HH:mm'), 'America/Sao_Paulo') AS inicio_utc,
    to_utc_timestamp(to_timestamp(get_json_object(payload, '$.fim'),    'yyyy-MM-dd HH:mm'), 'America/Sao_Paulo') AS fim_utc,
    split(get_json_object(payload, '$.estados'), ',')              AS estados,
    split(get_json_object(payload, '$.regioes'), ',')              AS regioes,
    transform(filter(split(get_json_object(payload, '$.geocodes'), ','), g -> g != ''),
              g -> trim(g))                                        AS geocodes_ibge,
    get_json_object(payload, '$.poligono')                         AS poligono_geojson,
    get_json_object(payload, '$.riscos')                           AS riscos,
    get_json_object(payload, '$.instrucoes')                       AS instrucoes,
    cast(get_json_object(payload, '$.alterado')  AS BOOLEAN)       AS alterado,
    cast(get_json_object(payload, '$.encerrado') AS BOOLEAN)       AS encerrado,
    cast(updated_at AS TIMESTAMP)                                  AS atualizado_em,
    _ingerido_em
  FROM bronze_inmet_avisos
)
SELECT * EXCEPT (rn) FROM (
  SELECT *, row_number() OVER (PARTITION BY id ORDER BY _ingerido_em DESC) AS rn FROM p
) WHERE rn = 1;
