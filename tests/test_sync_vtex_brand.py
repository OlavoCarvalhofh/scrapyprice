"""
Testa _extrair_codigo_peca -- heurística que pega o código de peça do
fabricante do texto do nome do produto, pros sites VTEX onde nem "sku"
nem "mpn" trazem esse código (achado real comparando contra a lista
mestre de peças do usuário: sku/mpn bem abaixo de 2%, texto do nome
70-91% nos sites CNH-focados).
"""
from scripts.sync_vtex_brand import _extrair_codigo_peca


def test_codigo_no_fim_antes_da_marca():
    # caso real: agrotrator.com.br
    nome = "Silenciador para Carregadeira New Holland 47699390 CNH"
    assert _extrair_codigo_peca(nome) == "47699390"


def test_codigo_no_fim_apos_hifen():
    # caso real: fornecedoramaquinas.com.br
    nome = "Lâmina Retroescavadeira 3/4 11F - 47572905GF"
    assert _extrair_codigo_peca(nome) == "47572905GF"


def test_codigo_alfanumerico_longo():
    # caso real: fornecedoraagro.com.br
    nome = "Kit Agrícola Hidráulico Frontal R38 T7 - MX BR323QHF01173"
    assert _extrair_codigo_peca(nome) == "BR323QHF01173"


def test_sem_codigo_no_nome_retorna_none():
    # caso real: fornecedoramaquinas.com.br -- linha de ajuste, não é peça
    nome = "Venda consultiva - Diferença de valor"
    assert _extrair_codigo_peca(nome) is None


def test_token_curto_no_fim_e_ignorado():
    # "T10" tem só 3 caracteres -- abaixo do mínimo, não deveria ser
    # confundido com um código de peça
    nome = "Drone Agricola DJI Agras T10"
    assert _extrair_codigo_peca(nome) is None


def test_produto_vazio_retorna_none():
    assert _extrair_codigo_peca(None) is None
    assert _extrair_codigo_peca("") is None


def test_codigo_case_insensitive_normaliza_maiusculo():
    nome = "Peca generica abc123def"
    assert _extrair_codigo_peca(nome) == "ABC123DEF"
