-- Episódios de El Niño / La Niña (sequências de meses classificados), com duração e pico.
CREATE OR REFRESH MATERIALIZED VIEW gold_enso_episodios
COMMENT 'Episódios ENSO: início, fim, duração, pico do ONI e intensidade'
AS
WITH m AS (
  SELECT *, ano * 12 + mes AS idx FROM gold_enso_mensal WHERE fase <> 'Neutro'
),
g AS (
  SELECT *, idx - row_number() OVER (PARTITION BY fase ORDER BY idx) AS grp FROM m
)
SELECT
  fase,
  min(mes_ref)                                                    AS inicio,
  max(mes_ref)                                                    AS fim,
  count(*)                                                        AS duracao_meses,
  CASE fase WHEN 'El Niño' THEN max(oni) ELSE min(oni) END        AS pico_oni,
  max_by(intensidade, abs(oni))                                   AS intensidade_pico,
  bool_or(episodio_em_curso)                                      AS em_curso
FROM g
GROUP BY fase, grp;
