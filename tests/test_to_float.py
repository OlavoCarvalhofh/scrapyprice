"""
_to_float é o ponto mais frágil do projeto: converte texto de preço em
float, tratando os dois formatos (pt-BR "1.234,56" e en-US "1,234.56").
Um bug aqui corrompe preço silenciosamente -- por isso testes exaustivos.
"""
from crawler.extractors.structured import _to_float


def test_none_retorna_none():
    assert _to_float(None) is None


def test_string_vazia_retorna_none():
    assert _to_float("") is None
    assert _to_float("   ") is None


def test_numero_ja_float_ou_int():
    assert _to_float(146.0) == 146.0
    assert _to_float(146) == 146.0


def test_pt_br_com_milhar_e_decimal():
    assert _to_float("1.234,56") == 1234.56
    assert _to_float("54.974,22") == 54974.22


def test_pt_br_so_decimal_sem_milhar():
    assert _to_float("146,00") == 146.0
    assert _to_float("0,64") == 0.64


def test_en_us_com_milhar_e_decimal():
    assert _to_float("1,234.56") == 1234.56


def test_en_us_so_ponto_decimal():
    assert _to_float("146.00") == 146.0
    assert _to_float("481.49") == 481.49


def test_com_prefixo_rs_e_espacos():
    assert _to_float("R$ 146,00") == 146.0
    assert _to_float("R$146,00") == 146.0
    assert _to_float("R$ 1.234,56") == 1234.56


def test_inteiro_sem_separador():
    assert _to_float("146") == 146.0


def test_texto_invalido_retorna_none():
    assert _to_float("preço sob consulta") is None
    assert _to_float("N/A") is None


def test_valores_pequenos_pt_br():
    # caso real visto no tratorlin: "R$0,36"
    assert _to_float("R$0,36") == 0.36
