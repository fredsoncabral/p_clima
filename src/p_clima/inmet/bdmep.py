"""Leitura dos CSVs horários do BDMEP (dados históricos de estações automáticas).

Layout de cada CSV (ISO-8859-1, separador ';', decimal ','):
  linhas 1-8  -> metadados (REGIAO, UF, ESTACAO, CODIGO (WMO), LATITUDE, LONGITUDE, ALTITUDE, DATA DE FUNDACAO)
  linha 9     -> cabeçalho (nomes variam ligeiramente entre anos; a ORDEM das colunas é estável)
  linhas 10+  -> 1 linha por hora UTC, com ';' no final

Na camada bronze tudo fica como string; tipagem/conversão de decimal ficam para a silver.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructField, StructType

# Ordem posicional das 19 colunas de medição do BDMEP.
COLUNAS_BDMEP = [
    "data",
    "hora_utc",
    "precipitacao_total_mm",
    "pressao_estacao_mb",
    "pressao_max_mb",
    "pressao_min_mb",
    "radiacao_global_kj_m2",
    "temp_ar_c",
    "temp_orvalho_c",
    "temp_max_c",
    "temp_min_c",
    "temp_orvalho_max_c",
    "temp_orvalho_min_c",
    "umidade_rel_max_pct",
    "umidade_rel_min_pct",
    "umidade_rel_pct",
    "vento_direcao_graus",
    "vento_rajada_max_ms",
    "vento_velocidade_ms",
]

# 19 colunas + 1 vazia gerada pelo ';' final. Schema explícito é obrigatório:
# sem ele o Spark infere 2 colunas a partir da 1ª linha de metadados.
_N_COLS = len(COLUNAS_BDMEP) + 1
SCHEMA_BRUTO = StructType([StructField(f"c{i:02d}", StringType()) for i in range(_N_COLS)])

# INMET_CO_DF_A001_BRASILIA_01-01-2024_A_31-12-2024.CSV
REGEX_ARQUIVO = r"(?i)^INMET_([A-Z]+)_([A-Z]{2})_([A-Z0-9]+)_(.+)_(\d{2}-\d{2}-\d{4})_A_(\d{2}-\d{2}-\d{4})\.csv$"
REGEX_DATA = r"^\d{4}[-/]\d{2}[-/]\d{2}$"


def _ler_bruto(spark: SparkSession, pasta_csv: str) -> DataFrame:
    return (
        spark.read.format("csv")
        .schema(SCHEMA_BRUTO)
        .option("sep", ";")
        .option("encoding", "ISO-8859-1")
        .option("header", "false")
        .option("mode", "PERMISSIVE")
        .option("recursiveFileLookup", "true")
        .option("pathGlobFilter", "*.[cC][sS][vV]")
        .load(pasta_csv)
        .select("*", F.col("_metadata.file_name").alias("_arquivo"))
    )


def ler_ano(spark: SparkSession, pasta_csv: str, ano: int) -> DataFrame:
    bruto = _ler_bruto(spark, pasta_csv)
    medicoes = [F.col(f"c{i:02d}").alias(nome) for i, nome in enumerate(COLUNAS_BDMEP)]
    arq = F.col("_arquivo")
    return bruto.where(F.col("c00").rlike(REGEX_DATA)).select(
        F.lit(ano).alias("ano"),
        F.regexp_extract(arq, REGEX_ARQUIVO, 3).alias("cd_estacao"),
        F.regexp_extract(arq, REGEX_ARQUIVO, 2).alias("sg_estado"),
        F.regexp_extract(arq, REGEX_ARQUIVO, 1).alias("regiao"),
        F.regexp_extract(arq, REGEX_ARQUIVO, 4).alias("nome_estacao"),
        *medicoes,
        arq.alias("_arquivo_origem"),
        F.current_timestamp().alias("_ingerido_em"),
    )


def cabecalhos_distintos(spark: SparkSession, pasta_csv: str) -> list[str]:
    """Linhas de cabeçalho distintas no ano — usado para detectar mudança de layout."""
    cols = [F.coalesce(F.col(f"c{i:02d}"), F.lit("")) for i in range(_N_COLS)]
    linhas = (
        _ler_bruto(spark, pasta_csv)
        .where(F.lower(F.col("c00")).startswith("data") & ~F.col("c00").contains(":") & F.col("c01").isNotNull())
        .select(F.concat_ws(";", *cols).alias("h"))
        .distinct()
    )
    return [r.h for r in linhas.collect()]
