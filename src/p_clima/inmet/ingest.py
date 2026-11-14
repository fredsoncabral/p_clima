"""Tarefas de ingestão do INMET -> Unity Catalog (camada bronze).

Padrão de cada tarefa:
  1. busca na fonte
  2. grava o bruto (JSON/CSV) no volume  /Volumes/<catalog>/<schema>/inmet_raw/...
  3. carrega a tabela bronze correspondente (tudo string + colunas de auditoria)

Uso (entry point do wheel):
  inmet estacoes   --catalog workspace --schema clima
  inmet avisos     --catalog workspace --schema clima
  inmet bdmep      --catalog workspace --schema clima --ano-inicio 2000 --ano-fim 2026 [--forcar]
  inmet observacoes --catalog workspace --schema clima --dias 2
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import zipfile
from datetime import UTC, date, datetime, timedelta

from pyspark.sql import SparkSession
from pyspark.sql.types import StringType, StructField, StructType

from p_clima.inmet import bdmep
from p_clima.inmet.client import TIPOS_ESTACAO, InmetClient

VOLUME = "inmet_raw"
SECRET_SCOPE = "inmet"
SECRET_KEY_TOKEN = "api_token"


# ---------------------------------------------------------------- utilidades
def get_spark() -> SparkSession:
    if os.environ.get("DATABRICKS_RUNTIME_VERSION"):  # rodando no Databricks
        return SparkSession.builder.getOrCreate()
    try:
        from databricks.connect import DatabricksSession

        return DatabricksSession.builder.getOrCreate()
    except ImportError:
        return SparkSession.builder.getOrCreate()


class Contexto:
    def __init__(self, spark: SparkSession, catalog: str, schema: str):
        self.spark, self.catalog, self.schema = spark, catalog, schema
        self.volume = f"/Volumes/{catalog}/{schema}/{VOLUME}"
        self.agora = datetime.now(UTC)

    def tabela(self, nome: str) -> str:
        return f"`{self.catalog}`.`{self.schema}`.`{nome}`"

    def preparar(self) -> None:
        self.spark.sql(
            f"CREATE SCHEMA IF NOT EXISTS `{self.catalog}`.`{self.schema}` COMMENT 'Estudo de clima - INMET'"
        )
        self.spark.sql(
            f"CREATE VOLUME IF NOT EXISTS `{self.catalog}`.`{self.schema}`.`{VOLUME}` "
            "COMMENT 'Arquivos brutos baixados do INMET (landing)'"
        )

    def habilitar_row_tracking(self, nome: str) -> None:
        """Permite refresh incremental das materialized views da silver."""
        self.spark.sql(f"ALTER TABLE {self.tabela(nome)} SET TBLPROPERTIES ('delta.enableRowTracking' = 'true')")

    def caminho_raw(self, *partes: str) -> str:
        p = os.path.join(self.volume, *partes)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p

    def salvar_json(self, dado, *partes: str) -> str:
        p = self.caminho_raw(*partes)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(dado, f, ensure_ascii=False)
        return p


def _como_str(v) -> str | None:
    if v is None:
        return None
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _df_strings(spark: SparkSession, registros: list[dict]):
    colunas = sorted({k for r in registros for k in r})
    schema = StructType([StructField(c.lower(), StringType()) for c in colunas])
    linhas = [tuple(_como_str(r.get(c)) for c in colunas) for r in registros]
    return spark.createDataFrame(linhas, schema)


def _token_inmet() -> str | None:
    try:
        from databricks.sdk.runtime import dbutils

        return dbutils.secrets.get(SECRET_SCOPE, SECRET_KEY_TOKEN)
    except Exception:  # escopo/chave inexistente ou fora do Databricks
        return None


# ---------------------------------------------------------------- estações
def ingerir_estacoes(ctx: Contexto, client: InmetClient) -> None:
    from pyspark.sql import functions as F

    dt, hms = ctx.agora.strftime("%Y-%m-%d"), ctx.agora.strftime("%H%M%S")
    registros = []
    for tipo in TIPOS_ESTACAO:
        dados = client.estacoes(tipo)
        arq = ctx.salvar_json(dados, "estacoes", f"dt={dt}", f"estacoes_{tipo}_{hms}.json")
        print(f"[estacoes] tipo={tipo}: {len(dados)} estações -> {arq}")
        registros += [{**d, "_tipo_api": tipo, "_arquivo_origem": arq} for d in dados]

    df = _df_strings(ctx.spark, registros).withColumn("_ingerido_em", F.lit(ctx.agora))
    # Snapshot atual (o histórico de snapshots fica preservado no volume).
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(ctx.tabela("bronze_inmet_estacoes"))
    ctx.habilitar_row_tracking("bronze_inmet_estacoes")
    print(f"[estacoes] {df.count()} linhas em {ctx.tabela('bronze_inmet_estacoes')}")


# ---------------------------------------------------------------- avisos
def ingerir_avisos(ctx: Contexto, client: InmetClient) -> None:
    from pyspark.sql import functions as F

    dados = client.avisos_ativos()
    arq = ctx.salvar_json(dados, "avisos", f"dt={ctx.agora:%Y-%m-%d}", f"avisos_ativos_{ctx.agora:%H%M%S}.json")
    linhas = []
    for grupo, avisos in dados.items():
        for a in avisos:
            payload = {k: v for k, v in a.items() if k != "icone"}  # 'icone' é PNG base64, sem valor analítico
            linhas.append(
                (
                    grupo,
                    _como_str(a.get("id")),
                    _como_str(a.get("id_aviso")),
                    _como_str(a.get("codigo")),
                    _como_str(a.get("updated_at")),
                    json.dumps(payload, ensure_ascii=False),
                    arq,
                )
            )
    print(f"[avisos] {len(linhas)} avisos ativos -> {arq}")
    if not linhas:
        return
    schema = StructType(
        [
            StructField(c, StringType())
            for c in ("grupo", "id", "id_aviso", "codigo", "updated_at", "payload", "_arquivo_origem")
        ]
    )
    df = ctx.spark.createDataFrame(linhas, schema).withColumn("_ingerido_em", F.lit(ctx.agora))
    # Append: cada execução é uma "foto" dos avisos ativos; deduplicação na silver por (id, updated_at).
    df.write.mode("append").saveAsTable(ctx.tabela("bronze_inmet_avisos"))
    ctx.habilitar_row_tracking("bronze_inmet_avisos")


# ---------------------------------------------------------------- BDMEP
def _controle(ctx: Contexto) -> str:
    t = ctx.tabela("_controle_bdmep")
    ctx.spark.sql(
        f"""CREATE TABLE IF NOT EXISTS {t} (
              ano INT, url STRING, tamanho_bytes BIGINT, last_modified STRING,
              n_arquivos INT, n_linhas BIGINT, cabecalhos ARRAY<STRING>, carregado_em TIMESTAMP)"""
    )
    return t


def _extrair_zip(zip_path: str, destino: str) -> int:
    if os.path.isdir(destino):
        shutil.rmtree(destino)
    os.makedirs(destino)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            nome = os.path.basename(info.filename)  # achata subpastas e evita path traversal
            if info.is_dir() or not nome.lower().endswith(".csv"):
                continue
            with z.open(info) as src, open(os.path.join(destino, nome), "wb") as dst:
                shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
            n += 1
    return n


def ingerir_bdmep(ctx: Contexto, client: InmetClient, ano_inicio: int, ano_fim: int, forcar: bool) -> None:
    controle = _controle(ctx)
    tabela = ctx.tabela("bronze_inmet_bdmep_horario")

    for ano in range(ano_inicio, ano_fim + 1):
        info = client.bdmep_info(ano)
        if info is None:
            print(f"[bdmep] {ano}: arquivo não publicado, ignorando")
            continue

        ja = ctx.spark.sql(
            f"SELECT 1 FROM {controle} WHERE ano = :ano AND tamanho_bytes <=> :tam AND last_modified <=> :lm",
            args={"ano": ano, "tam": info.tamanho_bytes, "lm": info.last_modified},
        ).count()
        if ja and not forcar:
            print(f"[bdmep] {ano}: sem alteração na origem ({info.last_modified}), ignorando")
            continue

        zip_path = ctx.caminho_raw("bdmep", "zip", f"{ano}.zip")
        print(f"[bdmep] {ano}: baixando {info.url} ({(info.tamanho_bytes or 0) / 1e6:.1f} MB)")
        client.baixar(info.url, zip_path)
        pasta = os.path.join(ctx.volume, "bdmep", "csv", f"ano={ano}")
        n_arq = _extrair_zip(zip_path, pasta)
        os.remove(zip_path)

        df = bdmep.ler_ano(ctx.spark, pasta, ano)
        (
            df.write.format("delta")
            .mode("overwrite")
            .partitionBy("ano")
            .option("replaceWhere", f"ano = {ano}")
            .saveAsTable(tabela)
        )
        ctx.habilitar_row_tracking("bronze_inmet_bdmep_horario")
        n_linhas = ctx.spark.table(tabela).where(f"ano = {ano}").count()
        cabecalhos = bdmep.cabecalhos_distintos(ctx.spark, pasta)
        if len(cabecalhos) > 1:
            print(f"[bdmep] {ano}: ATENÇÃO {len(cabecalhos)} layouts de cabeçalho distintos — revisar mapeamento")

        ctx.spark.sql(f"DELETE FROM {controle} WHERE ano = :ano", args={"ano": ano})
        ctx.spark.sql(
            f"""INSERT INTO {controle} VALUES
                (:ano, :url, :tam, :lm, :narq, :nlin, from_json(:cab, 'ARRAY<STRING>'), current_timestamp())""",
            args={
                "ano": ano,
                "url": info.url,
                "tam": info.tamanho_bytes,
                "lm": info.last_modified,
                "narq": n_arq,
                "nlin": n_linhas,
                "cab": json.dumps(cabecalhos, ensure_ascii=False),
            },
        )
        print(f"[bdmep] {ano}: {n_arq} arquivos, {n_linhas} linhas carregadas")


# ---------------------------------------------------------------- observações (token)
def ingerir_observacoes(ctx: Contexto, client: InmetClient, dias: int) -> None:
    token = _token_inmet()
    if not token:
        print(
            f"[observacoes] token ausente (secret scope '{SECRET_SCOPE}', chave '{SECRET_KEY_TOKEN}'). "
            "Solicite em api@inmet.gov.br. Tarefa ignorada."
        )
        return

    from pyspark.sql import functions as F

    estacoes = [
        r.cd_estacao
        for r in ctx.spark.table(ctx.tabela("bronze_inmet_estacoes"))
        .where("_tipo_api = 'T' AND cd_situacao = 'Operante'")
        .select("cd_estacao")
        .collect()
    ]
    fim = date.today()
    inicio = fim - timedelta(days=dias)
    linhas, falhas = [], 0
    for cod in estacoes:
        try:
            dados = client.observacoes_estacao(cod, inicio, fim, token)
        except Exception as e:  # uma estação com erro não derruba a carga
            falhas += 1
            print(f"[observacoes] {cod}: erro {e!r}"[:300])
            continue
        if dados:
            arq = ctx.salvar_json(dados, "observacoes", f"dt={ctx.agora:%Y-%m-%d}", f"{cod}_{ctx.agora:%H%M%S}.json")
            linhas += [(cod, json.dumps(d, ensure_ascii=False), arq) for d in dados]

    print(f"[observacoes] {len(estacoes)} estações, {len(linhas)} registros, {falhas} falhas ({inicio}..{fim})")
    if falhas == len(estacoes) and estacoes:
        raise RuntimeError("Todas as estações falharam — verifique o token e a rota da API")
    if linhas:
        schema = StructType([StructField(c, StringType()) for c in ("cd_estacao", "payload", "_arquivo_origem")])
        df = ctx.spark.createDataFrame(linhas, schema).withColumn("_ingerido_em", F.lit(ctx.agora))
        df.write.mode("append").saveAsTable(ctx.tabela("bronze_inmet_observacoes"))


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="inmet")
    p.add_argument("tarefa", choices=["estacoes", "avisos", "bdmep", "observacoes"])
    p.add_argument("--catalog", required=True)
    p.add_argument("--schema", required=True)
    p.add_argument("--ano-inicio", type=int, default=2000)
    p.add_argument("--ano-fim", default="", help="vazio = ano corrente")
    p.add_argument("--forcar", default="false", help="true = recarrega anos do BDMEP mesmo sem alteração")
    p.add_argument("--dias", type=int, default=2, help="janela de observações (dias)")
    a = p.parse_args(argv)

    ctx = Contexto(get_spark(), a.catalog, a.schema)
    ctx.preparar()
    client = InmetClient()

    if a.tarefa == "estacoes":
        ingerir_estacoes(ctx, client)
    elif a.tarefa == "avisos":
        ingerir_avisos(ctx, client)
    elif a.tarefa == "bdmep":
        ano_fim = int(a.ano_fim) if a.ano_fim.strip() else date.today().year
        ingerir_bdmep(ctx, client, a.ano_inicio, ano_fim, a.forcar.lower() == "true")
    elif a.tarefa == "observacoes":
        ingerir_observacoes(ctx, client, a.dias)


if __name__ == "__main__":
    main()
