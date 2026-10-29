"""Carregamento das regras de negócio e classificação de canal."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

RAIZ = Path(__file__).resolve().parent.parent
REGRAS_PADRAO = RAIZ / "config" / "regras.yaml"


def normalizar(valor) -> str:
    """Maiúsculas, sem acentos e sem espaços extras: 'Área  interna ' -> 'AREA INTERNA'."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.upper().split())


@dataclass
class Regras:
    colunas: dict[str, str]
    marcador_cabecalho: str
    excluir_status: list[str]
    tipos_validos: list[str]
    canais: list[dict]
    canal_padrao: str
    alertas: dict[str, float] = field(default_factory=dict)

    @classmethod
    def carregar(cls, caminho: str | Path | None = None) -> "Regras":
        dados = yaml.safe_load(Path(caminho or REGRAS_PADRAO).read_text(encoding="utf-8"))
        return cls(
            colunas=dados["colunas"],
            marcador_cabecalho=dados["marcador_cabecalho"],
            excluir_status=dados["filtros"].get("excluir_status", []),
            tipos_validos=dados["filtros"].get("tipos_validos", []),
            canais=dados["canais"],
            canal_padrao=dados.get("canal_padrao", "OUTROS"),
            alertas=dados.get("alertas", {}),
        )

    def col(self, chave: str) -> str:
        """Nome real da coluna no export a partir da chave lógica ('abertura' -> 'Data de abertura')."""
        return self.colunas[chave]


def classificar_canal(df: pd.DataFrame, regras: Regras) -> pd.Series:
    """Devolve, para cada linha, o canal do relatório segundo as regras (primeira que casar)."""
    chaves = {chave for regra in regras.canais for chave in regra["quando"]}
    normalizados = {
        chave: df[regras.col(chave)].map(normalizar) if regras.col(chave) in df.columns
        else pd.Series("", index=df.index)
        for chave in chaves
    }

    resultado = pd.Series(regras.canal_padrao, index=df.index, dtype="object")
    ja_classificado = pd.Series(False, index=df.index)
    for regra in regras.canais:
        mascara = pd.Series(True, index=df.index)
        for chave, esperado in regra["quando"].items():
            valores = esperado if isinstance(esperado, list) else [esperado]
            mascara &= normalizados[chave].isin({normalizar(v) for v in valores})
        novos = mascara & ~ja_classificado
        resultado[novos] = regra["nome"]
        ja_classificado |= novos
    return resultado


def aplicar_filtros(df: pd.DataFrame, regras: Regras) -> pd.DataFrame:
    """Remove status excluídos e mantém só os tipos de caso válidos."""
    df = df.dropna(how="all")
    col_status, col_tipo = regras.col("status"), regras.col("tipo")
    if col_status in df.columns and regras.excluir_status:
        excluir = {normalizar(s) for s in regras.excluir_status}
        df = df[~df[col_status].map(normalizar).isin(excluir)]
    if col_tipo in df.columns and regras.tipos_validos:
        validos = {normalizar(t) for t in regras.tipos_validos}
        df = df[df[col_tipo].map(normalizar).isin(validos)]
    return df.copy()
