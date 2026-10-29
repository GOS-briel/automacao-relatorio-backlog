from datetime import date

import pandas as pd

from relatorio_backlog.leitura import data_no_nome, detectar_linha_cabecalho, ler_export, localizar_arquivos, pasta_do_dia

from .conftest import caso


def _export(caminho, linhas_topo):
    with pd.ExcelWriter(caminho, engine="openpyxl") as w:
        pd.DataFrame({"": linhas_topo}).to_excel(w, index=False, header=False)
        pd.DataFrame([caso(1), caso(2)]).to_excel(w, index=False, startrow=len(linhas_topo))


def test_cabecalho_e_encontrado_com_qualquer_numero_de_linhas_de_filtro(tmp_path, regras):
    for n in (0, 3, 9):
        arquivo = tmp_path / f"export_{n}.xlsx"
        _export(arquivo, [f"Filtro {i}" for i in range(n)])
        assert detectar_linha_cabecalho(arquivo, regras.marcador_cabecalho) == n
        assert len(ler_export(arquivo, regras)) == 2


def test_data_no_nome_do_arquivo():
    assert data_no_nome("Backlog 28-10-2026.xlsx") == date(2026, 10, 28)
    assert data_no_nome("Backlog_31.02.2026.xlsx") is None  # data impossível
    assert data_no_nome("Backlog.xlsx") is None


def test_ontem_pula_o_fim_de_semana(tmp_path):
    for dia in (date(2026, 10, 23), date(2026, 10, 26)):  # sexta e segunda
        pasta = pasta_do_dia(tmp_path, dia)
        pasta.mkdir(parents=True)
        (pasta / f"Backlog {dia:%d-%m-%Y}.xlsx").touch()
    arq = localizar_arquivos(tmp_path, date(2026, 10, 26))
    assert arq.data_anterior == date(2026, 10, 23)


def test_ignora_arquivo_temporario_do_excel(tmp_path):
    pasta = pasta_do_dia(tmp_path, date(2026, 10, 28))
    pasta.mkdir(parents=True)
    (pasta / "~$Backlog 28-10-2026.xlsx").touch()
    assert localizar_arquivos(tmp_path, date(2026, 10, 28)).backlog_hoje is None
