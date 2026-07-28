from crawler.extractors.structured import (
    _norm_availability,
    extract_all_products_jsonld,
    extract_structured,
)

URL = "https://loja.exemplo.com.br/produto-x"


def _html_com_jsonld(json_ld_str):
    return f"""
    <html><head>
    <script type="application/ld+json">{json_ld_str}</script>
    </head><body></body></html>
    """


# ---- _norm_availability ----

def test_norm_availability_instock():
    assert _norm_availability("https://schema.org/InStock") == "InStock"


def test_norm_availability_outofstock():
    assert _norm_availability("http://schema.org/OutOfStock") == "OutOfStock"


def test_norm_availability_none():
    assert _norm_availability(None) is None
    assert _norm_availability("") is None


# ---- JSON-LD (caso mais comum: 1 Product por página) ----

def test_jsonld_product_simples():
    html = _html_com_jsonld("""
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "Filtro Hidraulico CNH",
      "image": "https://exemplo.com/img.jpg",
      "offers": {
        "@type": "Offer",
        "priceCurrency": "BRL",
        "price": "481.49",
        "availability": "https://schema.org/InStock"
      }
    }
    """)
    data = extract_structured(html, URL)
    assert data["preco"] == 481.49
    assert data["produto"] == "Filtro Hidraulico CNH"
    assert data["moeda"] == "BRL"
    assert data["disponibilidade"] == "InStock"
    assert data["fonte_extracao"] == "jsonld"


def test_jsonld_sem_offers_nao_extrai_preco():
    # caso real: usaparts.com.br -- offers existe mas sem campo "price" (login-gated)
    html = _html_com_jsonld("""
    {
      "@type": "Product",
      "name": "Peca sem preco publico",
      "offers": {"@type": "Offer", "priceCurrency": "BRL", "availability": "https://schema.org/InStock"}
    }
    """)
    data = extract_structured(html, URL)
    assert data == {}


def test_jsonld_offers_lista_com_item_vazio_antes_do_offer_real():
    # caso real: agroshopbr.com -- "offers" vem como [[], {...Offer...}], um
    # item vazio antes do de verdade (JSON-LD malformado do lado do site).
    # _first() sozinho pegaria o [] e nunca acharia o preço.
    html = _html_com_jsonld("""
    {
      "@type": "Product",
      "name": "Drone T50 DJI",
      "offers": [[], {"@type": "Offer", "priceCurrency": "BRL", "price": 110000, "availability": "http://schema.org/InStock"}]
    }
    """)
    data = extract_structured(html, URL)
    assert data["preco"] == 110000.0
    assert data["produto"] == "Drone T50 DJI"
    assert data["fonte_extracao"] == "jsonld"


def test_jsonld_website_nao_e_confundido_com_product():
    # caso real: tratorlin.com.br -- JSON-LD só de WebSite, sem Product
    html = _html_com_jsonld("""
    {"@context": "http://schema.org", "@type": "WebSite", "url": "https://exemplo.com.br"}
    """)
    data = extract_structured(html, URL)
    assert data == {}


# ---- OpenGraph (fallback quando não há JSON-LD com preço) ----

def test_opengraph_fallback():
    html = """
    <html><head>
    <meta property="og:title" content="Produto Teste">
    <meta property="product:price:amount" content="99.90">
    <meta property="product:price:currency" content="BRL">
    <meta property="og:image" content="https://exemplo.com/img.jpg">
    </head></html>
    """
    data = extract_structured(html, URL)
    assert data["preco"] == 99.90
    assert data["produto"] == "Produto Teste"
    assert data["fonte_extracao"] == "opengraph"


# ---- Microdata (último fallback da cascata) ----

def test_microdata_fallback():
    html = """
    <html><body>
    <div itemscope itemtype="https://schema.org/Product">
      <span itemprop="name">Produto Microdata</span>
      <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
        <span itemprop="price">55.00</span>
      </div>
    </div>
    </body></html>
    """
    data = extract_structured(html, URL)
    assert data["preco"] == 55.00
    assert data["fonte_extracao"] == "microdata"


# ---- Cascata: JSON-LD tem prioridade sobre OpenGraph ----

def test_cascata_prioriza_jsonld_sobre_opengraph():
    html = f"""
    <html><head>
    <script type="application/ld+json">
    {{"@type": "Product", "name": "Via JSON-LD", "offers": {{"price": "10.00"}}}}
    </script>
    <meta property="product:price:amount" content="999.99">
    </head></html>
    """
    data = extract_structured(html, URL)
    assert data["preco"] == 10.00
    assert data["fonte_extracao"] == "jsonld"


# ---- extract_all_products_jsonld (ItemList com vários produtos, ex: paccini.com.br) ----

def test_itemlist_com_multiplos_produtos():
    html = _html_com_jsonld("""
    {
      "@context": "https://schema.org",
      "@type": "ItemList",
      "itemListElement": [
        {
          "@type": "Product",
          "name": "Peca A",
          "url": "https://exemplo.com.br/produto/peca-a",
          "offers": {"@type": "Offer", "price": "100.00"}
        },
        {
          "@type": "Product",
          "name": "Peca B",
          "url": "https://exemplo.com.br/produto/peca-b",
          "offers": {"@type": "Offer", "price": "200.00"}
        }
      ]
    }
    """)
    produtos = extract_all_products_jsonld(html, URL)
    assert len(produtos) == 2
    nomes = {p["produto"] for p in produtos}
    assert nomes == {"Peca A", "Peca B"}
    urls = {p["url"] for p in produtos}
    assert urls == {"https://exemplo.com.br/produto/peca-a", "https://exemplo.com.br/produto/peca-b"}


def test_itemlist_ignora_produto_sem_preco():
    html = _html_com_jsonld("""
    {
      "@type": "ItemList",
      "itemListElement": [
        {"@type": "Product", "name": "Com preco", "url": "https://x.com/a", "offers": {"price": "10.00"}},
        {"@type": "Product", "name": "Sem preco", "url": "https://x.com/b"}
      ]
    }
    """)
    produtos = extract_all_products_jsonld(html, URL)
    assert len(produtos) == 1
    assert produtos[0]["produto"] == "Com preco"


def test_itemlist_vazio_retorna_lista_vazia():
    html = _html_com_jsonld('{"@type": "ItemList", "itemListElement": []}')
    assert extract_all_products_jsonld(html, URL) == []


def test_html_sem_dado_estruturado_retorna_vazio():
    html = "<html><body><h1>Produto sem dado estruturado</h1></body></html>"
    assert extract_structured(html, URL) == {}
    assert extract_all_products_jsonld(html, URL) == []


# ---- SKU/código de peça (caso real: tratormag.com.br embute "sku" no Product) ----

def test_jsonld_extrai_sku():
    html = _html_com_jsonld("""
    {
      "@type": "Product",
      "name": "Cinta de Freio Komatsu D50",
      "sku": "13010B2870",
      "offers": {"price": "192.78"}
    }
    """)
    data = extract_structured(html, URL)
    assert data["sku"] == "13010B2870"


def test_jsonld_sku_prioriza_sku_sobre_mpn_e_gtin():
    # caso real: acamargo.com -- Product tem sku, mpn e gtin13 juntos
    html = _html_com_jsonld("""
    {
      "@type": "Product",
      "name": "Polia Tensora",
      "sku": "3038055",
      "mpn": "149159",
      "gtin13": "7890003038055",
      "offers": {"price": "140.30"}
    }
    """)
    data = extract_structured(html, URL)
    assert data["sku"] == "3038055"


def test_jsonld_extrai_sku_e_mpn_como_campos_separados():
    # mesmo caso real do teste acima (acamargo.com), mas verificando que
    # "mpn" -- o código de peça do fabricante, usado pra bater com
    # dm_parts.cd_part_number no Power BI -- não é mais descartado quando
    # "sku" (o ID interno da loja) também está presente
    html = _html_com_jsonld("""
    {
      "@type": "Product",
      "name": "Polia Tensora",
      "sku": "3038055",
      "mpn": "149159",
      "gtin13": "7890003038055",
      "offers": {"price": "140.30"}
    }
    """)
    data = extract_structured(html, URL)
    assert data["sku"] == "3038055"
    assert data["mpn"] == "149159"


def test_jsonld_sem_mpn_nao_preenche_campo():
    html = _html_com_jsonld("""
    {
      "@type": "Product",
      "name": "Peca sem mpn",
      "sku": "123",
      "offers": {"price": "10.00"}
    }
    """)
    data = extract_structured(html, URL)
    assert "mpn" not in data


def test_jsonld_sku_cai_para_mpn_quando_sem_sku():
    html = _html_com_jsonld("""
    {
      "@type": "Product",
      "name": "Peca sem sku formal",
      "mpn": "MPN123",
      "offers": {"price": "50.00"}
    }
    """)
    data = extract_structured(html, URL)
    assert data["sku"] == "MPN123"


def test_microdata_extrai_sku():
    # caso real: tratorlin.com.br -- sku vem no microdata, não no JSON-LD
    html = """
    <html><body>
    <div itemscope itemtype="https://schema.org/Product">
      <span itemprop="name">Bucha</span>
      <span itemprop="sku">8500173</span>
      <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
        <span itemprop="price">75.30</span>
      </div>
    </div>
    </body></html>
    """
    data = extract_structured(html, URL)
    assert data["sku"] == "8500173"


def test_microdata_extrai_sku_e_mpn_como_campos_separados():
    html = """
    <html><body>
    <div itemscope itemtype="https://schema.org/Product">
      <span itemprop="name">Bucha</span>
      <span itemprop="sku">8500173</span>
      <span itemprop="mpn">149159</span>
      <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
        <span itemprop="price">75.30</span>
      </div>
    </div>
    </body></html>
    """
    data = extract_structured(html, URL)
    assert data["sku"] == "8500173"
    assert data["mpn"] == "149159"
