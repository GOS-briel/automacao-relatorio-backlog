"""
Checagens antes e depois do cálculo.

A diferença entre um script e um agente começa aqui: em vez de gerar o
relatório com o que tiver, o pipeline confere a entrada e PODE RECUSAR,
explicando o motivo. Um relatório errado enviado para a liderança custa
mais do que um relatório atrasado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .leitura import ArquivosDoDia, data_no_nome
from .metricas import Metricas
from .regras import Regras


@dataclass
class Diagnostico:
    erros: list[str] = field(default_factory=list)     # impedem a geração
    avisos: list[str] = field(default_factory=list)    # suspeitos, mas não bloqueiam
    destaques: list[str] = field(default_factory=list)  # o que a liderança deve olhar

    @property
    def bloqueado(self) -> bool:
        return bool(self.erros)

    @property
    def status(self) -> str:
        if self.erros:
            return "BLOQUEADO"
        return "ALERTA" if (self.avisos or self.destaques) else "OK"


def validar_arquivos(arq: ArquivosDoDia) -> Diagnostico:
    diag = Diagnostico()
    dia = arq.data.strftime("%d/%m/%Y")
    if arq.backlog_hoje is None:
        diag.erros.append(f"Backlog de {dia} não encontrado.")
    if arq.fechados is None:
        diag.erros.append(f"Relatório de casos fechados de {dia} não encontrado.")
    if arq.backlog_ontem is None:
        diag.erros.append(f"Nenhum backlog anterior a {dia} nos últimos dias; sem ele não há comparação.")

    for rotulo, caminho, esperado in (("backlog de hoje", arq.backlog_hoje, arq.data),
                                      ("casos fechados", arq.fechados, arq.data),
                                      ("backlog anterior", arq.backlog_ontem, arq.data_anterior)):
        if caminho is None:
            continue
        data_arquivo = data_no_nome(caminho.name)
        if data_arquivo and esperado and data_arquivo != esperado:
            diag.avisos.append(f"O arquivo de {rotulo} ({caminho.name}) tem data diferente da pasta.")
    return diag


def validar_colunas(nome: str, df: pd.DataFrame, regras: Regras, chaves: list[str]) -> list[str]:
    faltando = [regras.col(c) for c in chaves if regras.col(c) not in df.columns]
    return [f"{nome}: coluna(s) ausente(s): {', '.join(faltando)}."] if faltando else []


def avaliar_resultado(m: Metricas, regras: Regras) -> Diagnostico:
    """Olha os números calculados e aponta o que merece atenção."""
    diag = Diagnostico()
    lim_var = regras.alertas.get("variacao_backlog_pct", 10)
    lim_div = regras.alertas.get("divergencia_conciliacao_pct", 2)

    if m.backlog_hoje == 0:
        diag.erros.append("O backlog de hoje ficou vazio depois dos filtros. Confira se o export veio completo.")
        return diag

    if m.backlog_ontem and abs(m.divergencia) / m.backlog_ontem * 100 > lim_div:
        diag.avisos.append(
            f"Conciliação não fecha: backlog anterior real = {m.backlog_ontem}, mas entradas e fechados "
            f"indicam {m.backlog_ontem_calculado} (diferença de {m.divergencia:+}). "
            "Pode haver casos reclassificados ou um export incompleto."
        )

    if abs(m.variacao_pct) >= lim_var:
        sentido = "cresceu" if m.variacao > 0 else "caiu"
        pct = f"{abs(m.variacao_pct):.1f}".replace(".", ",")
        diag.destaques.append(f"O backlog {sentido} {pct}% em relação ao dia anterior.")

        crescimento = [l for l in m.canais if l.variacao > 0]
        if m.variacao > 0 and crescimento:
            pior = max(crescimento, key=lambda l: l.variacao)
            diag.destaques.append(f"Quem mais puxou a alta foi {pior.canal}: {pior.variacao:+} casos.")

    lim_criticos = regras.alertas.get("pct_casos_criticos", 5)
    if m.casos_criticos / m.backlog_hoje * 100 >= lim_criticos:
        limite = regras.alertas.get("idade_critica_dias", 30)
        diag.destaques.append(
            f"{m.casos_criticos} casos ({m.casos_criticos / m.backlog_hoje:.0%} do backlog) "
            f"estão abertos há mais de {limite} dias."
        )
    return diag
