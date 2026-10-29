from relatorio_backlog.regras import aplicar_filtros, classificar_canal, normalizar

from .conftest import caso


def test_normalizar_ignora_acentos_maiusculas_e_espacos():
    assert normalizar("  Área   interna ") == "AREA INTERNA"
    assert normalizar(None) == ""


def test_variacoes_de_escrita_caem_no_mesmo_canal(regras, df):
    dados = df(caso(1, canal="Call Center"), caso(2, canal="CALL-CENTER"), caso(3, canal="central telefônica"))
    assert classificar_canal(dados, regras).tolist() == ["TELEFONE"] * 3


def test_primeira_regra_que_casa_vence(regras, df):
    # Origem "DEFESA DO CONSUMIDOR" casaria com a regra genérica, mas a plataforma pública vem antes.
    dados = df(caso(1, origem="DEFESA DO CONSUMIDOR", canal="PLATAFORMA PÚBLICA DE RECLAMAÇÕES"),
               caso(2, origem="DEFESA DO CONSUMIDOR", canal="ÓRGÃO DE DEFESA"))
    assert classificar_canal(dados, regras).tolist() == ["PLATAFORMA PÚBLICA", "DEFESA DO CONSUMIDOR"]


def test_regra_com_duas_condicoes_exige_as_duas(regras, df):
    dados = df(caso(1, origem="ÓRGÃO REGULADOR", nivel="2º NÍVEL", canal="PORTAL"),
               caso(2, origem="ÓRGÃO REGULADOR", nivel="3º nível", canal="PORTAL"),
               caso(3, origem="ÓRGÃO REGULADOR", nivel="", canal="PORTAL"))
    assert classificar_canal(dados, regras).tolist() == ["REGULADOR N2", "REGULADOR N3", "OUTROS"]


def test_canal_desconhecido_vai_para_o_padrao(regras, df):
    assert classificar_canal(df(caso(1, canal="LOJA FÍSICA")), regras).tolist() == ["OUTROS"]


def test_filtros_removem_status_e_tipos_fora_da_conta(regras, df):
    dados = df(caso(1), caso(2, status="Solicitação"), caso(3, tipo="Elogio"), caso(4, tipo="recurso"))
    assert aplicar_filtros(dados, regras)["Número do caso"].tolist() == [1, 4]
