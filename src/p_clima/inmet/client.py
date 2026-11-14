"""Cliente HTTP para as fontes públicas do INMET.

Endpoints validados a partir do serverless do Databricks em 2026-11-14:
  - apitempo  /estacoes/{T|M}          -> 200, JSON, sem token
  - apiprevmet3 /avisos/ativos         -> 200, JSON {"hoje": [...], "futuro": [...]}, sem token
  - portal    /uploads/dadoshistoricos/{ano}.zip -> 200, ZIP com 1 CSV por estação (BDMEP)
  - apitempo  /estacao/{ini}/{fim}/{cod} -> 204 sem token (observações exigem token)

Obs.: o INMET recusa conexões de algumas redes (ex.: a máquina local de dev);
rode a ingestão a partir do Databricks.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_TEMPO = "https://apitempo.inmet.gov.br"
API_ALERTAS = "https://apiprevmet3.inmet.gov.br"
BDMEP_HIST = "https://portal.inmet.gov.br/uploads/dadoshistoricos"

USER_AGENT = "p-clima-ingest/0.1"

TIPOS_ESTACAO = {"T": "Automatica", "M": "Convencional"}


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = USER_AGENT
    return s


@dataclass(frozen=True)
class ArquivoRemoto:
    url: str
    tamanho_bytes: int | None
    last_modified: str | None


class InmetClient:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.http = _session()

    # ---------- Estações ----------
    def estacoes(self, tipo: str) -> list[dict]:
        """tipo: 'T' (automáticas) ou 'M' (convencionais)."""
        if tipo not in TIPOS_ESTACAO:
            raise ValueError(f"tipo inválido: {tipo}")
        r = self.http.get(f"{API_TEMPO}/estacoes/{tipo}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- Avisos ----------
    def avisos_ativos(self) -> dict[str, list[dict]]:
        r = self.http.get(f"{API_ALERTAS}/avisos/ativos", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ---------- Observações (requer token) ----------
    def observacoes_estacao(self, cod_estacao: str, inicio: date, fim: date, token: str) -> list[dict]:
        """Dados horários de uma estação.

        ATENÇÃO: rota com token a confirmar com a documentação recebida do INMET
        (api@inmet.gov.br). Sem token a rota pública devolve 204 (vazio).
        """
        url = f"{API_TEMPO}/token/estacao/{inicio:%Y-%m-%d}/{fim:%Y-%m-%d}/{cod_estacao}/{token}"
        r = self.http.get(url, timeout=self.timeout)
        if r.status_code == 204:
            return []
        r.raise_for_status()
        return r.json()

    # ---------- Histórico BDMEP ----------
    def bdmep_info(self, ano: int) -> ArquivoRemoto | None:
        url = f"{BDMEP_HIST}/{ano}.zip"
        r = self.http.head(url, timeout=self.timeout, allow_redirects=True)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        tam = r.headers.get("content-length")
        return ArquivoRemoto(url, int(tam) if tam else None, r.headers.get("last-modified"))

    def baixar(self, url: str, destino: str) -> None:
        """Download em streaming direto para o destino (ex.: um caminho em /Volumes)."""
        with self.http.get(url, timeout=self.timeout * 10, stream=True) as r:
            r.raise_for_status()
            r.raw.decode_content = True
            with open(destino, "wb") as f:
                shutil.copyfileobj(r.raw, f, length=8 * 1024 * 1024)
