"""Histórico diário de indicadores, usado no gráfico de tendência."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

MAX_PONTOS = 31


class Historico:
    """Um ponto por dia em um JSON simples. Gravar o mesmo dia de novo substitui (não duplica)."""

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)

    def carregar(self) -> list[dict]:
        if not self.caminho.exists():
            return []
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            return dados if isinstance(dados, list) else []
        except json.JSONDecodeError:
            return []

    def dias_registrados(self) -> set[str]:
        return {p["data"] for p in self.carregar()}

    def registrar(self, dia: date, entradas: int, fechados: int, backlog: int) -> None:
        pontos = [p for p in self.carregar() if p["data"] != dia.isoformat()]
        pontos.append({"data": dia.isoformat(), "entradas": entradas, "fechados": fechados, "backlog": backlog})
        pontos.sort(key=lambda p: p["data"])
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(json.dumps(pontos[-MAX_PONTOS:], ensure_ascii=False, indent=2), encoding="utf-8")

    def serie(self, ate: date | None = None) -> list[dict]:
        pontos = self.carregar()
        if ate:
            pontos = [p for p in pontos if p["data"] <= ate.isoformat()]
        return pontos[-MAX_PONTOS:]
