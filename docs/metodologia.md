# Metodologia

## 1. Tratamento da série horária (silver)

- `-9999` e vazios → NULL; vírgula decimal → ponto.
- Dois layouts de data/hora no BDMEP (`2000-05-13` + `00:00` e `2024/01/01` + `0000 UTC`) unificados em `ts_utc`.
- Mapeamento posicional das 19 colunas de medição — os nomes do cabeçalho variam entre anos, a ordem não.
  A ingestão registra os cabeçalhos distintos de cada ano em `_controle_bdmep` para detectar mudanças de layout.
- Horas sem nenhuma medição são descartadas (14 milhões de linhas).

## 2. Agregação temporal (gold)

- **Dia local:** cada UF no seu fuso IANA (considera o horário de verão, extinto em 2019).
- **Dia completo:** ≥ 18 das 24 horas com dado.
- **Mês válido:** temperatura com ≥ 20 dias completos; chuva com no máximo 2 dias faltando
  (o total de chuva é sensível a lacunas — **ausência de dado não é ausência de chuva**).
- **Média anual:** normal anual + anomalia média dos meses válidos (≥ 10), o que evita o viés sazonal de anos incompletos.

## 3. Normal climatológica

Período-base **2001–2025**, mínimo de 5 anos válidos por estação e mês. A normal oficial da OMM usa 30 anos
(1991–2020), mas a rede automática do INMET só começa em 2000; a base usada aqui é, portanto, uma
**referência local**, não a normal oficial.

## 4. Controle de qualidade de sensores

| Regra | Efeito |
|---|---|
| Temperatura horária fora de −15 a 50 °C; radiação fora de 0 a 5.000 kJ/m²·h | NULL |
| \|anomalia mensal\| > 5 °C | `qc_temp_suspeito` (excluído de médias e do dashboard) |
| Tmáx ≥ 45 °C (saturação; recorde oficial 44,8 °C) ou > p95 local + 8 °C | Tmáx descartada |
| Tmín < −10 °C ou < p05 local − 8 °C | Tmín descartada |
| Rajada > 50 m/s (180 km/h) | descartada |
| Índice de calor > 60 °C (fora da validade da fórmula) | NULL |
| Sequência seca com ≥ 45 dias na estação chuvosa local (meses com chuva em ≥ 35 % dos dias) | **pluviômetro travado**: mês inválido para chuva |

Exemplos reais detectados: Salvador com 45 °C e 80 % de umidade em junho/2007; rajada de 99,7 m/s em Manaus (2000);
Guarantã do Norte (MT, Amazônia) com 579 dias "sem chuva". As regras são heurísticas — alguns casos ainda passam
(ver Limitações no README).

## 5. Eventos extremos (limiares relativos ao clima local)

Percentis calculados por **estação e mês do calendário** na base 2001–2025 (40 °C é comum em Cuiabá e raro em Curitiba).

| Evento | Critério |
|---|---|
| Onda de calor | ≥ 5 dias consecutivos com Tmáx > p90 local |
| Calor / frio extremo | Tmáx > p95 / Tmín < p05 local |
| Chuva extrema | chuva diária > p95 dos dias chuvosos (≥ 1 mm) |
| Umidade baixa | umidade mínima < 30 % |
| Vento extremo | rajada ≥ 20 m/s (72 km/h) |
| Desconforto por calor | índice de calor ≥ 32 °C (faixa "cautela extrema" do NWS) |

Calibração: 4,7 % dos dias acima do p95 e 4,6 % abaixo do p05 no período — próximo dos 5 % esperados.

## 6. Índices

- **Índice de calor:** equação de Rothfusz (NOAA/NWS) hora a hora, com os ajustes de baixa/alta umidade; o dia guarda o máximo.
- **SPI (McKee et al., 1993):** acumulados de 1, 3, 6 e 12 meses (só com todos os meses válidos), distribuição gama
  ajustada por estação e mês do calendário na base 2001–2025 (≥ 10 anos), distribuição mista para zeros
  (probabilidade "centro de massa", Stagge et al., 2015) e transformação para a normal padrão.
  Calibração: média ≈ 0 e desvio ≈ 1 em todas as escalas.
- **Tendência linear:** `regr_slope` da anomalia anual (°C/década) e da chuva anual (% da média/década), estações com
  ≥ 15 anos; significância aproximada por |t| ≥ 2,1.

## 7. ENSO

- **ONI (NOAA/CPC):** média móvel trimestral da anomalia de TSM no Niño 3.4, associada ao mês central do trimestre.
- **Fase mensal:** El Niño (La Niña) quando ONI ≥ +0,5 (≤ −0,5) por ≥ 5 trimestres consecutivos; intensidade por |ONI|:
  fraca 0,5–0,9, moderada 1,0–1,4, forte 1,5–1,9, muito forte ≥ 2,0.
- **Correlação regional:** Pearson entre ONI defasado (0–6 meses) e anomalias regionais mensais, 2008+ (rede > 400
  estações). Exploratória: sem remoção de autocorrelação; correlação não implica causalidade.
- Desde fev/2026 a NOAA monitora oficialmente pelo **RONI** (ONI relativo); este projeto usa o ONI tradicional,
  então os valores não são diretamente comparáveis aos boletins mais recentes.
