-- ONI (Oceanic Niño Index) da NOAA/CPC, tipado.
-- Cada temporada é uma média móvel de 3 meses; associamos ao mês CENTRAL (DJF -> jan, JFM -> fev, ...).
CREATE OR REFRESH MATERIALIZED VIEW silver_noaa_oni (
  CONSTRAINT oni_valido EXPECT (oni IS NOT NULL AND mes BETWEEN 1 AND 12) ON VIOLATION DROP ROW
)
COMMENT 'ONI mensal (mês central da média trimestral), NOAA/CPC, anomalia de TSM no Niño 3.4 em °C'
AS SELECT
  cast(ano AS INT)                                                     AS ano,
  array_position(array('DJF','JFM','FMA','MAM','AMJ','MJJ','JJA','JAS','ASO','SON','OND','NDJ'), temporada)
                                                                       AS mes,
  make_date(cast(ano AS INT),
    cast(array_position(array('DJF','JFM','FMA','MAM','AMJ','MJJ','JJA','JAS','ASO','SON','OND','NDJ'), temporada) AS INT), 1)
                                                                       AS mes_ref,
  temporada,
  try_cast(anomalia AS DOUBLE)                                         AS oni,
  try_cast(total AS DOUBLE)                                            AS tsm_nino34_c,
  _ingerido_em
FROM bronze_noaa_oni;
