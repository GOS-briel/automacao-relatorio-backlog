import json

from relatorio_backlog.__main__ import main


def test_cli_gera_relatorio_e_devolve_json(dados_sinteticos, tmp_path, capsys):
    codigo = main(["--base", str(dados_sinteticos), "--saida", str(tmp_path), "gerar", "--data", "2026-10-28", "--json"])
    saida = json.loads(capsys.readouterr().out)
    assert codigo == 0
    assert saida["status"] in {"OK", "ALERTA"}
    assert saida["metricas"]["divergencia"] == 0
    assert (tmp_path / "historico.json").exists()


def test_cli_sai_com_erro_quando_bloqueia(tmp_path, capsys):
    codigo = main(["--base", str(tmp_path / "vazio"), "--saida", str(tmp_path), "gerar", "--data", "2026-10-28"])
    assert codigo == 1
    assert "BLOQUEADO" in capsys.readouterr().out


def test_cli_backfill(dados_sinteticos, tmp_path, capsys):
    assert main(["--base", str(dados_sinteticos), "--saida", str(tmp_path), "backfill", "--dias", "10", "--ate", "2026-10-28"]) == 0
    assert "adicionados" in capsys.readouterr().out
