"""Orquestração: localizar → validar → ler → calcular → avaliar → registrar → gerar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from . import metricas as mt
from .historico import Historico
from .leitura import ArquivosDoDia, ler_export, localizar_arquivos
from .regras import Regras
from .validacao import Diagnostico, avaliar_resultado, validar_arquivos, validar_colunas

COLUNAS_BACKLOG = ["numero", "status", "tipo", "origem", "canal", "assunto", "abertura"]
COLUNAS_FECHADOS = COLUNAS_BACKLOG + ["fechamento"]


@dataclass
class Resultado:
    data: date
    diagnostico: Diagnostico
    metricas: mt.Metricas | None = None
    html: Path | None = None
    pdf: Path | None = None

    @property
    def status(self) -> str:
        return self.diagnostico.status


def calcular_dia(arq: ArquivosDoDia, regras: Regras) -> tuple[Diagnostico, mt.Metricas | None]:
    """Valida e calcula as métricas de um dia, sem gerar arquivos."""
    diag = validar_arquivos(arq)
    if diag.bloqueado:
        return diag, None

    df_hoje = ler_export(arq.backlog_hoje, regras)
    df_ontem = ler_export(arq.backlog_ontem, regras)
    df_fechados = ler_export(arq.fechados, regras)

    for nome, df, chaves in (("Backlog de hoje", df_hoje, COLUNAS_BACKLOG),
                             ("Backlog anterior", df_ontem, COLUNAS_BACKLOG),
                             ("Casos fechados", df_fechados, COLUNAS_FECHADOS)):
        diag.erros += validar_colunas(nome, df, regras, chaves)
    if diag.bloqueado:
        return diag, None

    m = mt.calcular(mt.preparar(df_hoje, regras), mt.preparar(df_ontem, regras),
                    mt.preparar(df_fechados, regras), arq.data, arq.data_anterior, regras)

    avaliacao = avaliar_resultado(m, regras)
    diag.erros += avaliacao.erros
    diag.avisos += avaliacao.avisos
    diag.destaques += avaliacao.destaques
    return diag, (None if diag.bloqueado else m)


def executar(base: str | Path, dia: date, regras: Regras, historico: Historico,
             saida: str | Path, pdf: bool = False) -> Resultado:
    """Roda o pipeline completo de um dia e gera o relatório se nada bloquear."""
    from .relatorio import gerar_html, gerar_pdf  # import tardio: o cálculo não depende do HTML

    diag, m = calcular_dia(localizar_arquivos(base, dia), regras)
    resultado = Resultado(data=dia, diagnostico=diag, metricas=m)
    if m is None:
        return resultado

    historico.registrar(dia, m.entradas, m.fechados, m.backlog_hoje)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    resultado.html = gerar_html(m, diag, historico.serie(ate=dia), saida / f"relatorio_backlog_{dia:%Y-%m-%d}.html",
                                idade_critica=int(regras.alertas.get("idade_critica_dias", 30)))
    if pdf:
        resultado.pdf = gerar_pdf(resultado.html)
    return resultado


def backfill(base: str | Path, ate: date, dias: int, regras: Regras, historico: Historico) -> list[date]:
    """Preenche o histórico dos últimos `dias` que ainda não estão registrados (não sobrescreve)."""
    ja_existem = historico.dias_registrados()
    preenchidos = []
    for recuo in range(dias, 0, -1):
        dia = ate - timedelta(days=recuo)
        if dia.isoformat() in ja_existem:
            continue
        arq = localizar_arquivos(base, dia)
        if arq.backlog_hoje is None:  # fim de semana, feriado ou dia sem export
            continue
        diag, m = calcular_dia(arq, regras)
        if m is not None:
            historico.registrar(dia, m.entradas, m.fechados, m.backlog_hoje)
            preenchidos.append(dia)
    return preenchidos
