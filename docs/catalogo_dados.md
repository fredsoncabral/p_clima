# Catálogo de dados

Todas as tabelas ficam em `<catalog>.<schema>` (dev: `workspace.clima`). Unidades métricas;
horários em UTC, salvo indicação (dias da gold usam o fuso local da UF).

## Bronze — dados brutos (job `inmet_ingestao`)

| Tabela | Grão | Carga | Fonte |
|---|---|---|---|
| `bronze_inmet_estacoes` | estação | snapshot (overwrite) | apitempo `/estacoes/{T,M}` |
| `bronze_inmet_avisos` | aviso × execução | append | apiprevmet3 `/avisos/ativos` |
| `bronze_inmet_bdmep_horario` | estação × hora | `replaceWhere` por `ano` (particionada) | BDMEP `dadoshistoricos/{ano}.zip` |
| `bronze_inmet_observacoes` | estação × hora | append (requer token) | apitempo (rota com token) |
| `bronze_noaa_oni` | trimestre móvel | snapshot | NOAA/CPC `oni.ascii.txt` |
| `_controle_bdmep` | ano | upsert | metadados do ZIP (tamanho, Last-Modified, layouts) |

Volume `inmet_raw`: cópia de todo arquivo baixado (`estacoes/`, `avisos/`, `bdmep/csv/ano=YYYY/`, `enso/`).

## Silver — dados tratados (pipeline `inmet_silver`)

| Tabela | Conteúdo |
|---|---|
| `silver_inmet_estacoes` | Cadastro tipado (lat/lon/altitude numéricos, datas de operação) |
| `silver_inmet_bdmep_horario` | Série horária tipada: `-9999` → NULL, vírgula decimal, `ts_utc` unificado entre layouts; expectations de plausibilidade; clusterizada por estação/hora |
| `silver_inmet_avisos` | Última versão de cada aviso; início/fim convertidos de Brasília para UTC |
| `silver_noaa_oni` | ONI por mês central do trimestre (DJF → janeiro) |

## Gold — dados analíticos (pipeline `inmet_gold`)

| Tabela | Grão | Conteúdo |
|---|---|---|
| `gold_clima_diario_estacao` | estação × dia local | Médias/extremos, chuva, umidade, radiação (MJ/m²), vento, índice de calor, flags de dia completo |
| `gold_clima_mensal_estacao` | estação × mês | Agregados de dias completos, validade do mês (temperatura e chuva) |
| `gold_clima_normal_mensal_estacao` | estação × mês do ano | Normal 2001–2025 (mín. 5 anos) e desvio interanual |
| `gold_clima_anomalia_mensal_estacao` | estação × mês | Anomalias de temperatura (°C, z-score) e chuva (mm, % da normal), `qc_temp_suspeito` |
| `gold_clima_anual_estacao` | estação × ano | Média anual (normal + anomalia), extremos, chuva anual, eventos, variação vs. ano anterior |
| `gold_clima_mensal_uf` | UF × mês | Médias entre estações válidas |
| `gold_clima_limiares_estacao` | estação × mês do ano | Percentis locais p90/p95 Tmáx, p05 Tmín, p95 chuva, fração de dias chuvosos |
| `gold_clima_eventos_diarios` | estação × dia | Ondas de calor, calor/frio extremo, chuva extrema, umidade < 30 %, vento, dias secos consecutivos, QC |
| `gold_clima_eventos_mensal_estacao` | estação × mês | Contagens de eventos e recordes do mês |
| `gold_clima_spi_mensal_estacao` | estação × mês × escala | SPI 1/3/6/12 meses e classe (OMM) |
| `gold_clima_tendencia_estacao` | estação | Tendência linear (°C/década, % de chuva/década), R², significância aproximada |
| `gold_enso_mensal` | mês | ONI, fase (El Niño / La Niña / Neutro) e intensidade pelo critério NOAA |
| `gold_enso_episodios` | episódio | Início, fim, duração e pico de cada El Niño / La Niña |
| `gold_clima_enso_regiao_mensal` | região × mês | Anomalias regionais (e Brasil) com ONI e fase |
| `gold_clima_enso_correlacao` | região × defasagem | Correlação ONI × anomalias (0–6 meses, 2008+) |
| `gold_clima_resumo_regiao` | região | "Climate Intelligence": indicadores dos últimos 3/12 meses e textos automáticos |

## Volumes (referência, nov/2026)

| Item | Valor |
|---|---|
| Linhas horárias na bronze do BDMEP (2000–2026) | 89,6 milhões |
| Linhas horárias na silver (após descartar horas sem medição) | 75,5 milhões |
| Estações automáticas com histórico | 704 |
| Dias-estação na gold | 3,27 milhões |
| Estações com série longa (15+ anos) | 201 |
