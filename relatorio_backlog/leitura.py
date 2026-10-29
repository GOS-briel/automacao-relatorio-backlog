"""Localização dos arquivos do dia e leitura dos exports do CRM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .regras import Regras, normalizar

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

PALAVRA_BACKLOG = "backlog"
PALAVRA_FECHADOS = "fechados"
DIAS_PROCURA_ANTERIOR = 7  # quantos dias voltar para achar o "ontem" (pula fim de semana e feriado)

_DATA_NO_NOME = re.compile(r"(\d{2})[-_.](\d{2})[-_.](\d{4})")


def pasta_do_dia(base: str | Path, dia: date) -> Path:
    """Estrutura criada pela automação de e-mail: <base>/<Mês>/<DD-MM>/"""
    return Path(base) / MESES[dia.month - 1] / dia.strftime("%d-%m")


def data_no_nome(nome: str) -> date | None:
    """Extrai a data DD-MM-AAAA embutida no nome do arquivo, se houver."""
    achado = _DATA_NO_NOME.search(nome)
    if not achado:
        return None
    dia, mes, ano = map(int, achado.groups())
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def achar_arquivo(pasta: Path, palavra: str) -> Path | None:
    """Primeiro .xlsx da pasta cujo nome contém a palavra-chave (ignora temporários do Excel)."""
    if not pasta.is_dir():
        return None
    candidatos = sorted(
        p for p in pasta.iterdir()
        if p.suffix.lower() in {".xlsx", ".xls"}
        and not p.name.startswith("~$")
        and palavra in normalizar(p.stem).lower()
    )
    return candidatos[0] if candidatos else None


@dataclass
class ArquivosDoDia:
    data: date
    backlog_hoje: Path | None
    fechados: Path | None
    data_anterior: date | None
    backlog_ontem: Path | None


def localizar_arquivos(base: str | Path, dia: date) -> ArquivosDoDia:
    """Acha os 3 arquivos que o relatório de `dia` precisa: backlog de hoje, fechados e backlog anterior."""
    pasta = pasta_do_dia(base, dia)
    data_anterior, backlog_ontem = None, None
    for recuo in range(1, DIAS_PROCURA_ANTERIOR + 1):
        candidato = dia - timedelta(days=recuo)
        arquivo = achar_arquivo(pasta_do_dia(base, candidato), PALAVRA_BACKLOG)
        if arquivo:
            data_anterior, backlog_ontem = candidato, arquivo
            break
    return ArquivosDoDia(
        data=dia,
        backlog_hoje=achar_arquivo(pasta, PALAVRA_BACKLOG),
        fechados=achar_arquivo(pasta, PALAVRA_FECHADOS),
        data_anterior=data_anterior,
        backlog_ontem=backlog_ontem,
    )


def detectar_linha_cabecalho(caminho: Path, marcador: str, max_linhas: int = 40) -> int:
    """
    O export do CRM traz um número VARIÁVEL de linhas de filtro antes da tabela.
    Fixar header=N quebra quando alguém muda um filtro; aqui procuramos a linha
    que contém o marcador (ex.: 'Número do caso').
    """
    bruto = pd.read_excel(caminho, header=None, nrows=max_linhas)
    alvo = normalizar(marcador)
    for i, linha in bruto.iterrows():
        if any(normalizar(v) == alvo for v in linha.tolist()):
            return int(i)
    raise ValueError(f"Cabeçalho com '{marcador}' não encontrado nas primeiras {max_linhas} linhas de {caminho.name}")


def ler_export(caminho: Path, regras: Regras) -> pd.DataFrame:
    """Lê o export detectando o cabeçalho e convertendo as colunas de data."""
    linha = detectar_linha_cabecalho(caminho, regras.marcador_cabecalho)
    df = pd.read_excel(caminho, header=linha).dropna(how="all")
    for chave in ("abertura", "fechamento"):
        coluna = regras.col(chave)
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce", dayfirst=True)
    return df
