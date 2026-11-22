-- Classificação mensal do ENSO pelo critério operacional da NOAA:
--   El Niño  = ONI >= +0,5 por pelo menos 5 trimestres móveis consecutivos
--   La Niña  = ONI <= -0,5 por pelo menos 5 trimestres móveis consecutivos
--   Neutro   = demais meses
-- Intensidade pelo |ONI|: fraca (0,5–0,9), moderada (1,0–1,4), forte (1,5–1,9), muito forte (>= 2,0).
-- Obs.: nos meses mais recentes a sequência pode estar incompleta (classificação provisória).
CREATE OR REFRESH MATERIALIZED VIEW gold_enso_mensal
COMMENT 'Fase do ENSO por mês (critério NOAA de 5 trimestres consecutivos), a partir do ONI'
AS
WITH s AS (
  SELECT *,
    CASE WHEN oni >= 0.5 THEN 'quente' WHEN oni <= -0.5 THEN 'fria' ELSE 'neutra' END AS sinal,
    ano * 12 + mes AS idx
  FROM silver_noaa_oni
),
g AS (
  SELECT *, idx - row_number() OVER (PARTITION BY sinal ORDER BY idx) AS grp FROM s
),
r AS (
  SELECT *,
    count(*) OVER (PARTITION BY sinal, grp)                              AS meses_seq,
    max(idx) OVER (PARTITION BY sinal, grp) = (SELECT max(idx) FROM s)    AS seq_em_curso
  FROM g
)
SELECT
  ano, mes, mes_ref, temporada, oni, tsm_nino34_c,
  CASE WHEN sinal = 'quente' AND meses_seq >= 5 THEN 'El Niño'
       WHEN sinal = 'fria'   AND meses_seq >= 5 THEN 'La Niña'
       ELSE 'Neutro' END                                                 AS fase,
  CASE WHEN sinal = 'neutra' OR meses_seq < 5 THEN NULL
       WHEN abs(oni) >= 2.0 THEN 'Muito forte'
       WHEN abs(oni) >= 1.5 THEN 'Forte'
       WHEN abs(oni) >= 1.0 THEN 'Moderada'
       ELSE 'Fraca' END                                                  AS intensidade,
  meses_seq                                                              AS trimestres_consecutivos,
  seq_em_curso AND sinal <> 'neutra'                                     AS episodio_em_curso
FROM r;
