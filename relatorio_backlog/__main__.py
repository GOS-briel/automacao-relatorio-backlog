"""
Linha de comando.

    python -m relatorio_backlog gerar                  # último dia útil com arquivos
    python -m relatorio_backlog gerar --data 2026-10-28 --pdf
    python -m relatorio_backlog backfill --dias 30     # preenche a tendência com dias antigos
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

from .historico import Historico
from .leitura import localizar_arquivos
from .pipeline import backfill, executar
from .regras import Regras


def _ultimo_dia_com_arquivos(base: str, limite: int = 15) -> date:
    hoje = date.today()
    for recuo in range(limite):
        dia = hoje - timedelta(days=recuo)
        if localizar_arquivos(base, dia).backlog_hoje:
            return dia
    return hoje


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="relatorio_backlog", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default="dados", help="pasta com <Mês>/<DD-MM>/ (padrão: dados)")
    parser.add_argument("--saida", default="saida", help="onde gravar relatórios e histórico (padrão: saida)")
    parser.add_argument("--regras", default=None, help="arquivo de regras (padrão: config/regras.yaml)")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_gerar = sub.add_parser("gerar", help="gera o relatório de um dia")
    p_gerar.add_argument("--data", type=date.fromisoformat, help="AAAA-MM-DD (padrão: último dia com arquivos)")
    p_gerar.add_argument("--pdf", action="store_true", help="também gera o PDF")
    p_gerar.add_argument("--json", action="store_true", help="imprime o resultado em JSON (para outra automação ou um agente)")

    p_back = sub.add_parser("backfill", help="preenche o histórico de tendência")
    p_back.add_argument("--dias", type=int, default=30)
    p_back.add_argument("--ate", type=date.fromisoformat, default=None, help="AAAA-MM-DD (padrão: hoje)")

    args = parser.parse_args(argv)
    regras = Regras.carregar(args.regras)
    historico = Historico(f"{args.saida}/historico.json")

    if args.comando == "backfill":
        dias = backfill(args.base, args.ate or date.today(), args.dias, regras, historico)
        print(f"{len(dias)} dia(s) adicionados ao histórico.")
        return 0

    dia = args.data or _ultimo_dia_com_arquivos(args.base)
    backfill(args.base, dia, 30, regras, historico)  # garante a tendência mesmo na primeira execução
    r = executar(args.base, dia, regras, historico, args.saida, pdf=args.pdf)

    if args.json:
        print(json.dumps({
            "status": r.status, "data": dia.isoformat(),
            "erros": r.diagnostico.erros, "avisos": r.diagnostico.avisos, "destaques": r.diagnostico.destaques,
            "metricas": r.metricas.resumo() if r.metricas else None,
            "html": str(r.html) if r.html else None, "pdf": str(r.pdf) if r.pdf else None,
        }, ensure_ascii=False, indent=2, default=str))
        return 1 if r.diagnostico.bloqueado else 0

    print(f"[{r.status}] Relatório de {dia:%d/%m/%Y}")
    for erro in r.diagnostico.erros:
        print(f"  ✗ {erro}")
    for aviso in r.diagnostico.avisos:
        print(f"  ! {aviso}")
    for destaque in r.diagnostico.destaques:
        print(f"  ▲ {destaque}")
    if r.html:
        print(f"  → {r.html}")
    if r.pdf:
        print(f"  → {r.pdf}")
    return 1 if r.diagnostico.bloqueado else 0


if __name__ == "__main__":
    sys.exit(main())
