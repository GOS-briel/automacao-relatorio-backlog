import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from relatorio_backlog.regras import Regras  # noqa: E402


@pytest.fixture(scope="session")
def regras() -> Regras:
    return Regras.carregar()


def caso(numero, canal="E-MAIL", origem="ATENDIMENTO", nivel="", tipo="Reclamação", status="Em análise",
         assunto="Cobrança indevida", abertura="2026-10-20", fechamento=None) -> dict:
    return {
        "Número do caso": numero, "Status": status, "Tipo do caso": tipo, "Origem": origem,
        "Canal de entrada": canal, "Nível": nivel, "Assunto": assunto,
        "Data de abertura": pd.Timestamp(abertura),
        "Data de fechamento": pd.Timestamp(fechamento) if fechamento else pd.NaT,
    }


@pytest.fixture
def df():
    return lambda *linhas: pd.DataFrame(list(linhas))


@pytest.fixture(scope="session")
def dados_sinteticos(tmp_path_factory) -> Path:
    """Gera uma vez, para a sessão inteira, 20 dias de exports fictícios."""
    from scripts.gerar_dados_sinteticos import gerar

    base = tmp_path_factory.mktemp("dados")
    gerar(base, dias=20, fim=date(2026, 10, 28), semente=7)
    return base
