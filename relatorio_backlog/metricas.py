"""Cálculo dos indicadores do relatório."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

import pandas as pd

from .regras import Regras, aplicar_filtros, classificar_canal

COL_CANAL = "_canal"
FAIXAS_IDADE = [(0, 5, "0–5 dias"), (6, 10, "6–10 dias"), (11, 30, "11–30 dias"), (31, None, "+30 dias")]


@dataclass
class LinhaCanal:
    canal: str
    backlog_hoje: int
    backlog_ontem: int
    entradas: int
    fechados: int

    @property
    def variacao(self) -> int:
        return self.backlog_hoje - self.backlog_ontem

    @property
    def variacao_pct(self) -> float | None:
        return None if self.backlog_ontem == 0 else round(self.variacao / self.backlog_ontem * 100, 1)


@dataclass
class Metricas:
    data: date
    data_anterior: date
    backlog_hoje: int
    backlog_ontem: int
    entradas: int
    fechados: int
    backlog_ontem_calculado: int
    idade_media: float
    casos_criticos: int
    faixas_idade: list[tuple[str, int]]
    canais: list[LinhaCanal]
    top_assuntos: dict[str, list[tuple[str, int]]] = field(default_factory=dict)

    @property
    def variacao(self) -> int:
        return self.backlog_hoje - self.backlog_ontem

    @property
    def variacao_pct(self) -> float:
        return 0.0 if self.backlog_ontem == 0 else round(self.variacao / self.backlog_ontem * 100, 1)

    @property
    def divergencia(self) -> int:
        """Diferença entre o backlog anterior real e o que a conta entradas/fechados prevê."""
        return self.backlog_ontem - self.backlog_ontem_calculado

    def resumo(self) -> dict:
        """Versão serializável (para log, histórico ou um agente de IA consumir)."""
        dados = asdict(self)
        dados.update(data=self.data.isoformat(), data_anterior=self.data_anterior.isoformat(),
                     variacao=self.variacao, variacao_pct=self.variacao_pct, divergencia=self.divergencia)
        return dados


def preparar(df: pd.DataFrame, regras: Regras) -> pd.DataFrame:
    """Aplica os filtros de negócio e adiciona a coluna de canal classificada."""
    for chave in regras.colunas:  # um export vazio pode vir sem colunas; garante o formato esperado
        if regras.col(chave) not in df.columns:
            df = df.assign(**{regras.col(chave): pd.NaT if chave in ("abertura", "fechamento") else None})
    df = aplicar_filtros(df, regras)
    df[COL_CANAL] = classificar_canal(df, regras)
    return df


def _na_janela(serie: pd.Series, inicio: date, fim: date) -> pd.Series:
    """True para datas no intervalo (inicio, fim] — depois do snapshot anterior, até o atual."""
    dias = serie.dt.date
    return serie.notna() & (dias > inicio) & (dias <= fim)


def calcular(df_hoje: pd.DataFrame, df_ontem: pd.DataFrame, df_fechados: pd.DataFrame,
             data: date, data_anterior: date, regras: Regras) -> Metricas:
    """Recebe os DataFrames já preparados (filtrados e com canal) e calcula os indicadores."""
    num, abertura, fechamento = regras.col("numero"), regras.col("abertura"), regras.col("fechamento")

    fechados = df_fechados[_na_janela(df_fechados[fechamento], data_anterior, data)]
    fechados = fechados.drop_duplicates(subset=num)

    # Entrada = caso aberto entre os dois snapshots. Ele pode estar no backlog de hoje
    # ou já ter sido fechado no mesmo intervalo (entrou e saiu no mesmo dia).
    novos_abertos = df_hoje[_na_janela(df_hoje[abertura], data_anterior, data)]
    novos_fechados = fechados[_na_janela(fechados[abertura], data_anterior, data)]
    entradas = pd.concat([novos_abertos, novos_fechados]).drop_duplicates(subset=num)

    canais_presentes = (set(df_hoje[COL_CANAL]) | set(df_ontem[COL_CANAL])
                        | set(entradas[COL_CANAL]) | set(fechados[COL_CANAL]))
    contar = lambda df: df[COL_CANAL].value_counts()  # noqa: E731
    c_hoje, c_ontem, c_ent, c_fec = contar(df_hoje), contar(df_ontem), contar(entradas), contar(fechados)
    linhas = [
        LinhaCanal(c, int(c_hoje.get(c, 0)), int(c_ontem.get(c, 0)), int(c_ent.get(c, 0)), int(c_fec.get(c, 0)))
        for c in canais_presentes
    ]
    linhas.sort(key=lambda l: (-l.backlog_hoje, l.canal))

    idade = (pd.Timestamp(data) - df_hoje[abertura]).dt.days
    faixas = []
    for minimo, maximo, rotulo in FAIXAS_IDADE:
        mascara = idade >= minimo if maximo is None else idade.between(minimo, maximo)
        faixas.append((rotulo, int(mascara.sum())))
    critica = regras.alertas.get("idade_critica_dias", 30)

    top = {"TODOS": list(df_hoje[regras.col("assunto")].value_counts().head(10).items())}
    for canal, grupo in df_hoje.groupby(COL_CANAL):
        top[canal] = list(grupo[regras.col("assunto")].value_counts().head(10).items())

    return Metricas(
        data=data,
        data_anterior=data_anterior,
        backlog_hoje=len(df_hoje),
        backlog_ontem=len(df_ontem),
        entradas=len(entradas),
        fechados=len(fechados),
        backlog_ontem_calculado=len(df_hoje) - len(entradas) + len(fechados),
        idade_media=round(float(idade.mean()), 1) if len(idade) else 0.0,
        casos_criticos=int((idade > critica).sum()),
        faixas_idade=faixas,
        canais=linhas,
        top_assuntos={k: [(str(a), int(n)) for a, n in v] for k, v in top.items()},
    )
