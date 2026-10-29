import shutil
from datetime import date

from relatorio_backlog.historico import Historico
from relatorio_backlog.leitura import localizar_arquivos, pasta_do_dia
from relatorio_backlog.pipeline import backfill, calcular_dia, executar

DIA = date(2026, 10, 28)


def test_relatorio_completo_de_ponta_a_ponta(dados_sinteticos, regras, tmp_path):
    r = executar(dados_sinteticos, DIA, regras, Historico(tmp_path / "h.json"), tmp_path)
    assert r.status in {"OK", "ALERTA"}
    assert r.metricas.divergencia == 0
    html = r.html.read_text(encoding="utf-8")
    assert "Backlog de reclamações" in html and "28/10/2026" in html
    assert "cdn.jsdelivr" not in html  # o gráfico vai embutido: o relatório funciona offline


def test_conciliacao_fecha_em_todos_os_dias_simulados(dados_sinteticos, regras):
    for recuo in range(12):
        dia = date.fromordinal(DIA.toordinal() - recuo)
        arq = localizar_arquivos(dados_sinteticos, dia)
        if arq.backlog_hoje and arq.backlog_ontem:
            _, m = calcular_dia(arq, regras)
            assert m.divergencia == 0, dia


def test_bloqueia_e_explica_quando_falta_arquivo(dados_sinteticos, regras, tmp_path):
    copia = tmp_path / "dados"
    shutil.copytree(dados_sinteticos, copia)
    next(pasta_do_dia(copia, DIA).glob("Casos fechados*")).unlink()

    r = executar(copia, DIA, regras, Historico(tmp_path / "h.json"), tmp_path / "saida")
    assert r.status == "BLOQUEADO"
    assert r.html is None
    assert any("fechados" in e for e in r.diagnostico.erros)


def test_backfill_preenche_sem_duplicar(dados_sinteticos, regras, tmp_path):
    hist = Historico(tmp_path / "h.json")
    primeira = backfill(dados_sinteticos, DIA, 15, regras, hist)
    segunda = backfill(dados_sinteticos, DIA, 15, regras, hist)
    assert len(primeira) >= 8 and segunda == []
    datas = [p["data"] for p in hist.carregar()]
    assert datas == sorted(set(datas))
