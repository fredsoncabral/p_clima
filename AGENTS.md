# Declarative Automation Bundles Project

This project uses Declarative Automation Bundles (DABs) for deployment. Add project-specific instructions below.

## For AI Agents: Use Databricks AI Tools

**BEFORE any other action, read the `databricks-core` skill.**

It sets you up to work with this project reliably: CLI authentication, profile
selection, data discovery, and the bundle deployment workflow. Without it,
results are often slower and less accurate.

If this skill is not available (Databricks AI Tools are not installed), you can install them for your coding agent in seconds:

```bash
databricks aitools install
```

If the CLI is not installed, see: https://docs.databricks.com/dev-tools/cli/install

---

## Project Instructions

<!-- Add your project-specific instructions, coding conventions, or notes here -->

### Ingestão INMET (estudo de clima)

- Código: `src/p_clima/inmet/` (wheel, entry point `inmet`); job: `resources/inmet_ingestao.job.yml` (serverless).
- Destino: `workspace.clima` (dev) / `workspace.clima_prod` (prod); arquivos brutos em `/Volumes/<catalog>/<schema>/inmet_raw/`.
- Tabelas bronze (tudo string): `bronze_inmet_estacoes` (snapshot), `bronze_inmet_avisos` (append),
  `bronze_inmet_bdmep_horario` (particionada por `ano`, replaceWhere por ano), `bronze_inmet_observacoes` (append, requer token).
- Controle incremental do BDMEP: `_controle_bdmep` (só recarrega o ano se tamanho/Last-Modified do ZIP mudar; `forcar=true` ignora).
- Silver: pipeline SDP `inmet_silver` (`src/pipelines/inmet_silver/transformations/*.sql`, materialized views),
  acionado pela tarefa `silver` do job: `silver_inmet_estacoes`, `silver_inmet_bdmep_horario` (tipada, -9999→NULL,
  `ts_utc`, clusterizada por estação/ts), `silver_inmet_avisos` (última versão por id, horários em UTC).
  Bronze tem `delta.enableRowTracking` para refresh incremental das MVs.
- Gold: pipeline SDP `inmet_gold` (`src/pipelines/inmet_gold/transformations/*.sql`), tarefa `gold` do job após `silver`:
  `gold_clima_diario_estacao` (dia no fuso local da UF; dia completo = >=18 h com dado; leituras implausíveis -> NULL),
  `gold_clima_mensal_estacao` (mês válido: temp >=20 dias completos, chuva <=2 dias faltantes),
  `gold_clima_normal_mensal_estacao` (base 2001–2025, mínimo 5 anos), `gold_clima_anomalia_mensal_estacao`, `gold_clima_mensal_uf`.
  Médias nacionais/UF são médias simples entre estações (sem ponderação por área) e o conjunto de estações muda ao longo dos anos.
- `gold_clima_anomalia_mensal_estacao.qc_temp_suspeito`: |anomalia| > 5 °C (defeito de sensor); excluir em análises.
- ENSO: tarefa `enso` do job baixa o ONI da NOAA/CPC -> `bronze_noaa_oni` -> `silver_noaa_oni` -> `gold_enso_mensal`
  (critério NOAA: |ONI| >= 0,5 por 5 trimestres), `gold_enso_episodios`, `gold_clima_enso_regiao_mensal`, `gold_clima_enso_correlacao` (defasagem 0–6 meses, 2008+).
- Índices gold: `gold_clima_limiares_estacao` (p90/p95/p05 locais, base 2001–2025), `gold_clima_eventos_diarios` / `_mensal_estacao`
  (ondas de calor, extremos, umidade < 30 %, vento, dias secos), `gold_clima_anual_estacao`, `gold_clima_tendencia_estacao`
  (regr_slope, >= 15 anos), `gold_clima_spi_mensal_estacao` (Python + scipy, gama; escalas 1/3/6/12) e `gold_clima_resumo_regiao` (textos automáticos).
- QC de sensores na gold: índice de calor > 60 °C -> NULL; Tmáx >= 45 °C ou > p95+8; Tmín < -10 °C ou < p05-8; rajada > 50 m/s;
  pluviômetro travado (>= 45 dias secos na estação chuvosa local) invalida a chuva do mês (`dias_chuva_suspeita`).
- Dashboard AI/BI "Climate Intelligence" (5 páginas + filtros): GERADO por `scripts/gerar_dashboard.py` -> `src/dashboards/clima_inmet.lvdash.json`.
  Edite o script (não o JSON) e rode `python scripts/gerar_dashboard.py`; ele valida bindings de campos e sobreposição de layout.
  Queries com nomes de tabela sem catálogo/schema (vêm de `dataset_catalog`/`dataset_schema`). Warehouse via lookup "Serverless Starter Warehouse".
  KPIs comparam 12 meses vs 12 anteriores só com estações presentes nos dois períodos; temperatura = normal anual + anomalia (sem viés sazonal).
- Portfólio: README e `docs/` (arquitetura, catálogo, metodologia, análises) em português. Nenhuma URL de workspace ou
  e-mail no repositório (público): o host vem do perfil da CLI / `DATABRICKS_HOST` (`.env.example`).
- Gráficos de análise: `scripts/grafico_linkedin.py` (Databricks SDK + `DATABRICKS_WAREHOUSE_ID`) gera `docs/img/` e o CSV em `docs/analises/`.
- Testes rodam offline: a sessão Spark do `tests/conftest.py` só é criada quando um teste usa a fixture `spark`.
  CI (`.github/workflows/ci.yml`): ruff, pytest e verificação de que o JSON do dashboard está sincronizado com o gerador.
- O INMET recusa conexões da máquina local de dev — teste chamadas HTTP pelo Databricks (serverless), não localmente.
- No BDMEP, `-9999` = valor ausente; decimais usam vírgula; `hora_utc` vem como `0000 UTC` (anos recentes) ou `00:00` (antigos).
- Token da API de observações: secret scope `inmet`, chave `api_token` (solicitado via api@inmet.gov.br). A rota com token em `client.py` precisa ser confirmada com a documentação do INMET.
