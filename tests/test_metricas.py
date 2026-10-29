from datetime import date

from relatorio_backlog.metricas import calcular, preparar

from .conftest import caso

HOJE, ONTEM = date(2026, 10, 28), date(2026, 10, 27)


def _calcular(regras, df, hoje, ontem, fechados):
    return calcular(preparar(df(*hoje), regras), preparar(df(*ontem), regras),
                    preparar(df(*fechados), regras), HOJE, ONTEM, regras)


def test_conciliacao_fecha_quando_os_exports_sao_consistentes(regras, df):
    ontem = [caso(1, abertura="2026-10-20"), caso(2, abertura="2026-10-25"), caso(3, abertura="2026-10-26")]
    hoje = [caso(1, abertura="2026-10-20"), caso(4, abertura="2026-10-28")]          # 2 e 3 saíram, 4 entrou
    fechados = [caso(2, abertura="2026-10-25", fechamento="2026-10-28", status="Fechado"),
                caso(3, abertura="2026-10-26", fechamento="2026-10-28", status="Fechado"),
                caso(5, abertura="2026-10-28", fechamento="2026-10-28", status="Fechado"),  # entrou e saiu hoje
                caso(9, abertura="2026-10-01", fechamento="2026-10-15", status="Fechado")]  # fora da janela
    m = _calcular(regras, df, hoje, ontem, fechados)

    assert (m.backlog_hoje, m.backlog_ontem, m.entradas, m.fechados) == (2, 3, 2, 3)
    assert m.backlog_ontem_calculado == m.backlog_ontem
    assert m.divergencia == 0


def test_divergencia_aparece_quando_falta_caso_no_export(regras, df):
    ontem = [caso(1), caso(2)]
    hoje = [caso(1)]  # o caso 2 sumiu, mas não está nos fechados
    m = _calcular(regras, df, hoje, ontem, [])
    assert m.divergencia == 1


def test_variacao_e_contagem_por_canal(regras, df):
    ontem = [caso(1, canal="CHAT"), caso(2, canal="E-MAIL")]
    hoje = [caso(1, canal="CHAT"), caso(2, canal="E-MAIL"), caso(3, canal="CHAT", abertura="2026-10-28")]
    m = _calcular(regras, df, hoje, ontem, [])
    chat = next(l for l in m.canais if l.canal == "CHAT")
    assert (chat.backlog_hoje, chat.backlog_ontem, chat.variacao, chat.variacao_pct, chat.entradas) == (2, 1, 1, 100.0, 1)
    assert m.canais[0].canal == "CHAT"  # ordenado pelo maior backlog


def test_faixas_de_idade_e_casos_criticos(regras, df):
    hoje = [caso(1, abertura="2026-10-27"), caso(2, abertura="2026-10-20"),
            caso(3, abertura="2026-10-10"), caso(4, abertura="2026-09-01")]
    m = _calcular(regras, df, hoje, hoje, [])
    assert dict(m.faixas_idade) == {"0–5 dias": 1, "6–10 dias": 1, "11–30 dias": 1, "+30 dias": 1}
    assert m.casos_criticos == 1
