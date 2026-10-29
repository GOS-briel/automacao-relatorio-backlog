"""
Gera exports FICTÍCIOS de uma central de atendimento, no mesmo formato que
um CRM entrega por e-mail: um backlog por dia útil e um relatório de casos
fechados nos últimos 30 dias, com linhas de filtro variáveis no topo.

Nenhum dado real é usado. A simulação acompanha cada caso do início ao fim
(abertura → fechamento), então os números dos relatórios conciliam entre si.

Uso:
    python scripts/gerar_dados_sinteticos.py --dias 45 --saida dados
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from relatorio_backlog.leitura import pasta_do_dia  # noqa: E402

# canal do relatório: (origem, [variações de canal como chegam do CRM], nível, casos/dia, dias médios até fechar)
PERFIS = {
    "REGULADOR N2": ("ÓRGÃO REGULADOR", ["PORTAL DO REGULADOR"], "2º NÍVEL", 5.0, 9),
    "REGULADOR N3": ("ÓRGÃO REGULADOR", ["PORTAL DO REGULADOR"], "3º NÍVEL", 1.2, 16),
    "PLATAFORMA PÚBLICA": ("DEFESA DO CONSUMIDOR", ["PLATAFORMA PÚBLICA DE RECLAMAÇÕES"], "", 4.5, 8),
    "DEFESA DO CONSUMIDOR": ("DEFESA DO CONSUMIDOR", ["ÓRGÃO DE DEFESA"], "", 2.5, 12),
    "TELEFONE": ("ATENDIMENTO", ["CENTRAL TELEFÔNICA", "Call Center", "CALL-CENTER"], "", 13.0, 4),
    "E-MAIL": ("ATENDIMENTO", ["E-MAIL", "Email"], "", 7.0, 5),
    "CHAT": ("ATENDIMENTO", ["CHAT", "WhatsApp"], "", 6.5, 2),
    "REDES SOCIAIS": ("ATENDIMENTO", ["REDES SOCIAIS"], "", 2.5, 3),
    "ÁREA INTERNA": ("ATENDIMENTO", ["Área Interna"], "", 1.5, 6),
    "OUTROS": ("ATENDIMENTO", ["LOJA FÍSICA"], "", 0.8, 5),
}

ASSUNTOS = {
    "Cobrança indevida": 18, "Demora na solução": 15, "Cancelamento não efetuado": 10,
    "Reembolso não realizado": 9, "Falha no serviço": 9, "Prazo de instalação": 7,
    "Informação incorreta": 6, "Qualidade do atendimento": 6, "Alteração cadastral": 5,
    "Visita técnica não realizada": 5, "Contestação de multa": 4, "Portabilidade": 3,
    "Acesso ao aplicativo": 3,
}
TIPOS = {"Reclamação": 80, "Reclamação reaberta": 7, "Recurso": 5, "Elogio": 4, "Sugestão": 4}
STATUS_ABERTOS = {"Em análise": 55, "Aguardando cliente": 20, "Encaminhado à área técnica": 25}


def _escolher(pesos: dict[str, float], rng: random.Random) -> str:
    return rng.choices(list(pesos), weights=list(pesos.values()))[0]


def _proximo_dia_util(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


@dataclass
class Caso:
    numero: str
    canal_relatorio: str
    origem: str
    canal: str
    nivel: str
    tipo: str
    assunto: str
    status_aberto: str
    abertura: datetime
    fechamento: datetime | None

    def linha(self, aberto: bool) -> dict:
        return {
            "Número do caso": self.numero,
            "Status": self.status_aberto if aberto else "Fechado",
            "Tipo do caso": self.tipo,
            "Origem": self.origem,
            "Canal de entrada": self.canal,
            "Nível": self.nivel,
            "Assunto": self.assunto,
            "Data de abertura": self.abertura,
            "Data de fechamento": None if aberto else self.fechamento,
        }


def simular(inicio: date, fim: date, rng: random.Random) -> list[Caso]:
    casos: list[Caso] = []
    contador = 1_000_000

    def novo_caso(canal_rel: str, aberto_em: datetime) -> Caso:
        nonlocal contador
        contador += rng.randint(1, 9)
        origem, variacoes, nivel, _, dias_medios = PERFIS[canal_rel]
        tipo = _escolher(TIPOS, rng)
        status = _escolher(STATUS_ABERTOS, rng)
        if rng.random() < 0.05:  # pedidos de serviço: não são reclamação e ficam fora da conta
            tipo, status = "Solicitação de serviço", "Solicitação"
        duracao = rng.lognormvariate(0, 0.8) * dias_medios
        fecha_em = _proximo_dia_util((aberto_em + timedelta(days=duracao)).date())
        fechamento = datetime.combine(fecha_em, datetime.min.time()) + timedelta(hours=rng.uniform(8, 18))
        return Caso(f"CS-{contador}", canal_rel, origem, rng.choice(variacoes), nivel, tipo,
                    _escolher(ASSUNTOS, rng), status, aberto_em, fechamento)

    # Estoque inicial: casos abertos antes do período, para o backlog não começar vazio.
    for _ in range(260):
        canal_rel = _escolher({k: v[3] for k, v in PERFIS.items()}, rng)
        aberto = datetime.combine(inicio, datetime.min.time()) - timedelta(days=rng.uniform(1, 60))
        caso = novo_caso(canal_rel, aberto)
        if caso.fechamento.date() <= inicio:  # garante que ainda estava aberto no início
            caso.fechamento = datetime.combine(_proximo_dia_util(inicio + timedelta(days=rng.randint(1, 25))),
                                               datetime.min.time()) + timedelta(hours=10)
        casos.append(caso)

    total_dias = (fim - inicio).days
    for i in range(total_dias + 1):
        dia = inicio + timedelta(days=i)
        fator = 0.45 if dia.weekday() >= 5 else 1.0
        fator *= 1 + 0.25 * (i / max(total_dias, 1))       # demanda crescendo ao longo do período
        if i == total_dias:
            fator *= 2.0                                    # pico no último dia: o relatório de exemplo tem o que destacar
        for canal_rel, (_, _, _, por_dia, _) in PERFIS.items():
            for _ in range(_poisson(por_dia * fator, rng)):
                aberto = datetime.combine(dia, datetime.min.time()) + timedelta(hours=rng.uniform(0, 23.9))
                casos.append(novo_caso(canal_rel, aberto))
    return casos


def _poisson(media: float, rng: random.Random) -> int:
    limite, k, p = pow(2.718281828, -media), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


CABECALHOS = {
    "backlog": ["Relatório: Backlog de casos em aberto", "Filtros aplicados:",
                "    Status diferente de Fechado", "    Data de abertura: todas",
                "    Unidade: Central de Atendimento", "    Ordenado por: Data de abertura"],
    "fechados": ["Relatório: Casos fechados (últimos 30 dias)", "Filtros aplicados:",
                 "    Status igual a Fechado", "    Data de fechamento: últimos 30 dias",
                 "    Unidade: Central de Atendimento"],
}


def escrever_export(df: pd.DataFrame, caminho: Path, tipo: str, gerado_em: datetime, rng: random.Random) -> None:
    """Grava o .xlsx com um número variável de linhas de filtro antes da tabela, como o CRM faz."""
    linhas_topo = CABECALHOS[tipo][: rng.randint(3, len(CABECALHOS[tipo]))]
    linhas_topo += [f"Gerado em: {gerado_em:%d/%m/%Y %H:%M}", ""]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(caminho, engine="openpyxl", datetime_format="DD/MM/YYYY HH:MM") as writer:
        pd.DataFrame({"": linhas_topo}).to_excel(writer, index=False, header=False)
        df.to_excel(writer, index=False, startrow=len(linhas_topo))


def gerar(saida: Path, dias: int, fim: date, semente: int) -> int:
    rng = random.Random(semente)
    inicio = fim - timedelta(days=dias)
    casos = simular(inicio, fim, rng)
    arquivos = 0
    for i in range(dias + 1):
        dia = inicio + timedelta(days=i)
        if dia.weekday() >= 5:
            continue
        corte = datetime.combine(dia, datetime.max.time())
        gerado_em = datetime.combine(dia, datetime.min.time()) + timedelta(hours=23, minutes=30)
        abertos = [c.linha(True) for c in casos if c.abertura <= corte and c.fechamento > corte]
        fechados = [c.linha(False) for c in casos
                    if corte - timedelta(days=30) < c.fechamento <= corte and c.abertura <= corte]
        pasta = pasta_do_dia(saida, dia)
        rotulo = dia.strftime("%d-%m-%Y")
        colunas = list(casos[0].linha(True))
        escrever_export(pd.DataFrame(abertos, columns=colunas).sort_values("Data de abertura"),
                        pasta / f"Backlog {rotulo}.xlsx", "backlog", gerado_em, rng)
        escrever_export(pd.DataFrame(fechados, columns=colunas).sort_values("Data de fechamento"),
                        pasta / f"Casos fechados {rotulo}.xlsx", "fechados", gerado_em, rng)
        arquivos += 2
    return arquivos


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera exports fictícios de backlog para testar o relatório.")
    parser.add_argument("--saida", default="dados", help="pasta base (padrão: dados)")
    parser.add_argument("--dias", type=int, default=45, help="quantos dias simular (padrão: 45)")
    parser.add_argument("--fim", default=None, help="último dia, AAAA-MM-DD (padrão: último dia útil)")
    parser.add_argument("--semente", type=int, default=42, help="semente aleatória, para resultados reprodutíveis")
    args = parser.parse_args()

    fim = date.fromisoformat(args.fim) if args.fim else date.today() - timedelta(days=1)
    while fim.weekday() >= 5:
        fim -= timedelta(days=1)
    total = gerar(Path(args.saida), args.dias, fim, args.semente)
    print(f"{total} arquivos gerados em '{args.saida}/' (até {fim:%d/%m/%Y}).")


if __name__ == "__main__":
    main()
