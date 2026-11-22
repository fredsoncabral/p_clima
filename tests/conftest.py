"""This file configures pytest, initializes Databricks Connect, and provides fixtures for Spark and loading test data."""

import os
import pathlib
import sys

try:
    import csv
    import json
    import os

    import pytest
    from databricks.connect import DatabricksSession
    from databricks.sdk import WorkspaceClient
    from pyspark.sql import SparkSession
except ImportError:
    raise ImportError(
        "Test dependencies not found.\n\nRun tests using 'uv run pytest'. See http://docs.astral.sh/uv to learn more about uv."
    )


@pytest.fixture()
def spark() -> SparkSession:
    """Provide a SparkSession fixture for tests.

    Minimal example:
        def test_uses_spark(spark):
            df = spark.createDataFrame([(1,)], ["x"])
            assert df.count() == 1
    """
    _enable_fallback_compute()
    return DatabricksSession.builder.getOrCreate()


@pytest.fixture()
def load_fixture(spark: SparkSession):
    """Provide a callable to load JSON or CSV from fixtures/ directory.

    Example usage:

        def test_using_fixture(load_fixture):
            data = load_fixture("my_data.json")
            assert data.count() >= 1
    """

    def _loader(filename: str):
        path = pathlib.Path(__file__).parent.parent / "fixtures" / filename
        suffix = path.suffix.lower()
        if suffix == ".json":
            rows = json.loads(path.read_text())
            return spark.createDataFrame(rows)
        if suffix == ".csv":
            with path.open(newline="") as f:
                rows = list(csv.DictReader(f))
            return spark.createDataFrame(rows)
        raise ValueError(f"Unsupported fixture type for: {filename}")

    return _loader


def _enable_fallback_compute():
    """Enable serverless compute if no compute is specified."""
    conf = WorkspaceClient().config
    if conf.serverless_compute_id or conf.cluster_id or os.environ.get("SPARK_REMOTE"):
        return

    url = "https://docs.databricks.com/dev-tools/databricks-connect/cluster-config"
    print("☁️ no compute specified, falling back to serverless compute", file=sys.stderr)
    print(f"  see {url} for manual configuration", file=sys.stdout)

    os.environ["DATABRICKS_SERVERLESS_COMPUTE_ID"] = "auto"


def pytest_configure(config: pytest.Config):
    """Sessão Spark é criada sob demanda (fixture `spark`), não no início do pytest.

    Assim os testes unitários puros rodam offline (ex.: no GitHub Actions, sem credenciais);
    apenas testes que pedem a fixture `spark` exigem um workspace Databricks configurado.
    """
