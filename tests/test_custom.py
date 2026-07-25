"""
Testa extract_custom contra os seletores REAIS de config/selectors.yaml
(regressão: se alguém mudar o YAML e quebrar a sintaxe CSS, esse teste
acusa) -- usando HTML mínimo que reproduz a estrutura real de cada site.
"""
from crawler.extractors.custom import extract_custom


def test_dominio_sem_config_retorna_vazio():
    html = "<html><body><span class='qualquer'>R$ 10,00</span></body></html>"
    assert extract_custom(html, "dominio-nao-cadastrado.com.br") == {}


def test_tratorlin_seletores_reais():
    html = """
    <html><body>
    <h1 class="product-name" itemprop="name">A 77465 - BRONZINA BIELA</h1>
    <p class="product-old-price"><span class="product-scratched-price"></span></p>
    <p class="product-new-price"><span class="product-big-price">R$ 146,00</span></p>
    <span class="desconto_avista">R$ 138,70</span>
    <a itemprop="availability" href="http://schema.org/InStock"></a>
    </body></html>
    """
    data = extract_custom(html, "www.loja.tratorlin.com.br")
    assert data["preco"] == 146.0
    assert data["preco_a_vista"] == 138.70
    assert data["produto"] == "A 77465 - BRONZINA BIELA"
    assert data["disponibilidade"] == "InStock"
    assert data["fonte_extracao"] == "css"
    # preco_de fica vazio (span sem texto) -- não deve aparecer no resultado
    assert "preco_de" not in data


def test_prosperadistribuicao_seletores_reais():
    html = """
    <html><body>
    <h3 class="nome_produto" itemprop="name">DRONE DJI MATRICE 4T</h3>
    <meta itemprop="price" content="54974.22" />
    <meta itemprop="availability" content="https://schema.org/InStock" />
    </body></html>
    """
    data = extract_custom(html, "www.prosperadistribuicao.com.br")
    assert data["preco"] == 54974.22
    assert data["produto"] == "DRONE DJI MATRICE 4T"
    assert data["disponibilidade"] == "InStock"
    assert data["fonte_extracao"] == "css"
