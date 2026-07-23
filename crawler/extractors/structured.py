"""
Extração em cascata de dados estruturados.

Ordem de tentativa (a maioria dos e-commerces expõe pelo menos um):
  1. JSON-LD   (<script type="application/ld+json"> @type Product) -- o mais rico
  2. OpenGraph (<meta property="product:price:amount">)
  3. Microdata (itemprop="price")

Retorna um dict parcial + a fonte de onde veio o dado. O que faltar,
o fallback de seletores CSS (custom.py) tenta completar.
"""
import extruct
from w3lib.html import get_base_url


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # normaliza "1.234,56" (pt-BR) e "1,234.56" (en)
    s = s.replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):        # vírgula é o decimal -> pt-BR
            s = s.replace(".", "").replace(",", ".")
        else:                                   # ponto é o decimal -> en
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _first(v):
    """Campos de schema.org às vezes vêm como lista."""
    if isinstance(v, list):
        return v[0] if v else None
    return v


def _norm_availability(raw):
    if not raw:
        return None
    raw = str(raw).lower()
    if "outofstock" in raw or "soldout" in raw:
        return "OutOfStock"
    if "preorder" in raw or "presale" in raw:
        return "PreOrder"
    if "instock" in raw or "available" in raw:
        return "InStock"
    return raw


def _walk_jsonld_products(node):
    """Percorre blocos JSON-LD atrás de qualquer @type Product, em qualquer
    profundidade -- inclui produtos aninhados dentro de um ItemList (comum em
    páginas de "peças compatíveis com este veículo", ex: paccini.com.br)."""
    if isinstance(node, dict):
        t = node.get("@type", "")
        t = " ".join(t) if isinstance(t, list) else str(t)
        if "Product" in t:
            yield node
        for v in node.values():
            yield from _walk_jsonld_products(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_jsonld_products(item)


def _parse_produto_jsonld(product):
    offers = _first(product.get("offers"))
    out = {"produto": product.get("name"), "url": product.get("url")}

    img = product.get("image")
    out["imagem_url"] = _first(img) if img else None

    if isinstance(offers, dict):
        out["preco"] = _to_float(offers.get("price") or offers.get("lowPrice"))
        out["moeda"] = offers.get("priceCurrency") or "BRL"
        out["disponibilidade"] = _norm_availability(offers.get("availability"))
        seller = _first(offers.get("seller"))
        if isinstance(seller, dict):
            out["vendedor"] = seller.get("name")

    rating = _first(product.get("aggregateRating"))
    if isinstance(rating, dict):
        out["avaliacao_nota"] = _to_float(rating.get("ratingValue"))
        qtd = rating.get("reviewCount") or rating.get("ratingCount")
        out["avaliacao_qtd"] = int(_to_float(qtd)) if qtd else None

    if out.get("preco") is not None:
        out["fonte_extracao"] = "jsonld"
    return {k: v for k, v in out.items() if v is not None}


def _from_jsonld(data):
    """Retorna o primeiro produto com preço encontrado (caso comum: 1 produto por página)."""
    for product in _walk_jsonld_products(data):
        out = _parse_produto_jsonld(product)
        if out.get("preco") is not None:
            out.pop("url", None)  # aqui o item mantém a URL da página visitada
            return out
    return {}


def extract_all_products_jsonld(html, url):
    """Retorna TODOS os produtos com preço encontrados no JSON-LD da página --
    útil quando a página lista várias peças de uma vez (ItemList), não só um
    Product isolado. Cada item mantém sua própria URL (quando presente no
    JSON-LD), em vez da URL da página onde foi encontrado."""
    base_url = get_base_url(html, url)
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"], uniform=True)
    except Exception:
        return []

    resultados = []
    vistos = set()
    for node in data.get("json-ld", []):
        for product in _walk_jsonld_products(node):
            out = _parse_produto_jsonld(product)
            if out.get("preco") is None:
                continue
            chave = out.get("url") or out.get("produto")
            if chave in vistos:
                continue
            vistos.add(chave)
            out.setdefault("url", url)
            resultados.append(out)
    return resultados


def _from_opengraph(og_list):
    """extruct (uniform=True) devolve uma lista de dicts (um por grupo de tags
    og:*), com uma chave "@context" que não é dado -- juntamos tudo num dict só."""
    og = {}
    for grupo in og_list or []:
        for k, v in grupo.items():
            if k != "@context":
                og[k] = v
    out = {}
    if "product:price:amount" in og:
        out["preco"] = _to_float(og["product:price:amount"])
        out["moeda"] = og.get("product:price:currency", "BRL")
    if "og:title" in og:
        out["produto"] = og["og:title"]
    if "og:image" in og:
        out["imagem_url"] = og["og:image"]
    avail = og.get("product:availability") or og.get("og:availability")
    if avail:
        out["disponibilidade"] = _norm_availability(avail)
    if out.get("preco") is not None:
        out["fonte_extracao"] = "opengraph"
    return {k: v for k, v in out.items() if v is not None}


def _from_microdata(items):
    for it in items or []:
        props = it.get("properties", {})
        if "price" in props or "offers" in props:
            out = {"produto": _first(props.get("name"))}
            offers = _first(props.get("offers"))
            price = None
            if isinstance(offers, dict):
                price = offers.get("properties", {}).get("price")
            price = price or props.get("price")
            out["preco"] = _to_float(_first(price))
            if out.get("preco") is not None:
                out["fonte_extracao"] = "microdata"
                return {k: v for k, v in out.items() if v is not None}
    return {}


def extract_structured(html, url):
    """Roda a cascata. Retorna o primeiro dict com preço encontrado."""
    base_url = get_base_url(html, url)
    try:
        data = extruct.extract(
            html, base_url=base_url,
            syntaxes=["json-ld", "opengraph", "microdata"],
            uniform=True,
        )
    except Exception:
        return {}

    for parser, key in (
        (_from_jsonld, "json-ld"),
        (_from_opengraph, "opengraph"),
        (_from_microdata, "microdata"),
    ):
        result = parser(data.get(key))
        if result.get("preco") is not None:
            return result
    return {}
