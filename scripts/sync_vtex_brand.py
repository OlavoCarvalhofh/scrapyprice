#!/usr/bin/env python3
"""
Sincronização em lote via API pública do VTEX, filtrando por marca.

Sites VTEX expõem um endpoint de busca paginado que já devolve preço,
estoque e disponibilidade em JSON -- pra catálogos grandes, isso é muito
mais rápido e mais leve pro servidor do que visitar página por página
com o spider (crawler/spiders/price_spider.py).

A API clássica do VTEX trava em 2500 itens por consulta (_from não pode
passar de 2500), então quando marca+catálogo excede isso, o script desce
na árvore de categorias (descoberta via sitemap) e divide a consulta em
categoria+marca, recursivamente, até cada fatia caber no limite.

Uso:
    python scripts/sync_vtex_brand.py --site agrotrator
    python scripts/sync_vtex_brand.py --domain https://www.agrotrator.com.br --marca cnh

Sites cadastrados ficam em config/sites.yaml (registro único do projeto,
usado também pelo scripts/sync_site.py) -- prefira `python scripts/sync_site.py
--site <nome>` no dia a dia; os flags daqui servem pra testar um domínio novo
antes de cadastrar. Se o site já é 100% de uma marca (loja especializada, ex:
só peças CNH), deixe "marca" de fora do YAML pra extrair tudo em vez de
filtrar por um atributo de marca que pode não estar marcado em todos os
produtos.
"""
import argparse
import os
import random
import re
import sys
import time
from urllib.parse import urlparse

import requests
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from crawler.middlewares import USER_AGENTS
from db.models import Coleta, get_engine, get_session, init_db

PAGE_SIZE = 50
LIMITE_VTEX = 2500
_SITES_CONFIG_PATH = os.path.join(BASE_DIR, "config", "sites.yaml")


def _carregar_site(nome):
    with open(_SITES_CONFIG_PATH, "r", encoding="utf-8") as f:
        sites = yaml.safe_load(f) or {}
    if nome not in sites or sites[nome].get("metodo") != "vtex":
        disponiveis = ", ".join(n for n, c in sites.items() if c.get("metodo") == "vtex")
        raise SystemExit(f"Site '{nome}' não está em config/sites.yaml como VTEX. Disponíveis: {disponiveis}")
    return sites[nome]["domain"], sites[nome].get("marca")


def _headers():
    return {"User-Agent": random.choice(USER_AGENTS)}


def _get_com_retry(url, params, tentativas=6):
    """VTEX às vezes devolve 500/502 passageiro -- tenta de novo com espera crescente."""
    for tentativa in range(1, tentativas + 1):
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        if resp.status_code in (200, 206):
            return resp
        if tentativa == tentativas:
            resp.raise_for_status()
        time.sleep(min(3 * tentativa, 20))
    return resp


def _descobrir_arvore_categorias(domain):
    """Lê o sitemap.xml e monta o mapa categoria-pai -> subcategorias diretas."""
    r = requests.get(f"{domain}/sitemap.xml", headers=_headers(), timeout=30)
    r.raise_for_status()
    sub_sitemaps = re.findall(r"<loc>(.*?)</loc>", r.text)
    sitemaps_categoria = [u for u in sub_sitemaps if "category" in u]

    caminhos = set()
    for sm_url in sitemaps_categoria:
        r = requests.get(sm_url, headers=_headers(), timeout=30)
        r.raise_for_status()
        for loc in re.findall(r"<loc>(.*?)</loc>", r.text):
            partes = tuple(urlparse(loc).path.strip("/").split("/"))
            if partes and partes[0]:
                caminhos.add(partes)

    filhos = {}
    for caminho in caminhos:
        for i in range(len(caminho)):
            pai = caminho[:i]
            filho = caminho[: i + 1]
            if filho != pai:
                filhos.setdefault(pai, set()).add(filho)
    return filhos


def _contar(domain, marca, categoria_path):
    partes = list(categoria_path) + ([marca] if marca else [])
    mapa = ",".join(["c"] * len(categoria_path) + (["b"] if marca else []))
    if partes:
        seg = "/".join(partes)
        url = f"{domain}/api/catalog_system/pub/products/search/{seg}?map={mapa}"
    else:
        url = f"{domain}/api/catalog_system/pub/products/search"
    r = requests.get(url, headers=_headers(), params={"_from": 0, "_to": 0}, timeout=30)
    if r.status_code not in (200, 206):
        return url, 0
    faixa = r.headers.get("resources", "")
    total = int(faixa.split("/")[-1]) if "/" in faixa else 0
    return url, total


def _planejar_fatias(domain, marca, arvore_categorias, categoria_path=()):
    """Retorna lista de (url_base, total) já dentro do limite de 2500 cada."""
    url, total = _contar(domain, marca, categoria_path)
    if total == 0:
        return []
    if total <= LIMITE_VTEX:
        return [(url, total)]

    filhos = arvore_categorias.get(categoria_path)
    if not filhos:
        rotulo = "/".join(categoria_path) or marca or "catálogo inteiro"
        print(f"  AVISO: '{rotulo}' tem {total} itens e não "
              f"dá pra dividir mais (sem subcategorias) -- só os 2500 primeiros serão pegos.")
        return [(url, LIMITE_VTEX)]

    fatias = []
    for filho in sorted(filhos):
        fatias.extend(_planejar_fatias(domain, marca, arvore_categorias, filho))
    return fatias


def _melhor_categoria(categorias):
    if not categorias:
        return None
    return categorias[0].strip("/").split("/")[-1] or None


def _preco_a_vista(installments):
    for inst in installments or []:
        if inst.get("PaymentSystemGroupName") == "instantPaymentPaymentGroup":
            return inst.get("Value")
    return None


def _parcelamento_sem_juros(installments):
    """Maior nº de parcelas sem juros no cartão de crédito, se houver."""
    melhor = None
    for inst in installments or []:
        if (
            inst.get("PaymentSystemGroupName") == "creditCardPaymentGroup"
            and inst.get("InterestRate") == 0.0
            and inst.get("NumberOfInstallments", 1) > 1
        ):
            if melhor is None or inst["NumberOfInstallments"] > melhor["NumberOfInstallments"]:
                melhor = inst
    if not melhor:
        return None, None, None
    n = melhor["NumberOfInstallments"]
    valor_total = melhor.get("TotalValuePlusInterestRate", melhor.get("Value"))
    return n, round(valor_total / n, 2), True


_TOKEN_CODIGO_RE = re.compile(r"[^A-Za-z0-9]+")


def _extrair_codigo_peca(nome_produto):
    """Heurística: pega o último "token" do nome do produto que parece um
    código de peça (alfanumérico, 4+ caracteres, com pelo menos um dígito).

    Motivo de existir: nos sites VTEX, nem "sku" (ID interno da loja) nem
    "mpn" (quando existe) trazem o código de peça real do fabricante --
    ele só aparece como texto livre no nome do produto, geralmente no fim
    (ex: "Silenciador para Carregadeira New Holland 47699390 CNH" -> o
    código é "47699390", não "CNH"). Validado contra a lista mestre de
    peças do usuário: 71-91% de acerto nos sites CNH-focados (agrotrator,
    carpaltratores, fornecedoramaquinas, fornecedoraagro); baixo em sites
    que não embutem o código no nome de forma consistente (ex: pitstop).
    """
    if not nome_produto:
        return None
    tokens = _TOKEN_CODIGO_RE.split(nome_produto.upper())
    for tok in reversed(tokens):
        if len(tok) >= 4 and any(c.isdigit() for c in tok):
            return tok
    return None


def _item_para_registro(produto, netloc):
    sku = produto.get("items", [{}])[0]
    seller = sku.get("sellers", [{}])[0]
    offer = seller.get("commertialOffer", {})

    preco = offer.get("Price")
    if preco is None:
        return None

    list_price = offer.get("ListPrice")
    preco_de = list_price if list_price and list_price > preco else None

    parcelas, parcela_valor, parcela_sem_juros = _parcelamento_sem_juros(
        offer.get("Installments")
    )

    imagens = sku.get("images") or []
    nome_produto = produto.get("productName")

    return {
        "url": produto.get("link"),
        "loja": netloc,
        "produto": nome_produto,
        "sku": str(sku.get("itemId")) if sku.get("itemId") else None,
        "codigo_peca": _extrair_codigo_peca(nome_produto),
        "categoria": _melhor_categoria(produto.get("categories")),
        "preco": preco,
        "preco_de": preco_de,
        "preco_a_vista": _preco_a_vista(offer.get("Installments")),
        "moeda": "BRL",
        "parcelas": parcelas,
        "parcela_valor": parcela_valor,
        "parcela_sem_juros": parcela_sem_juros,
        "disponibilidade": "InStock" if offer.get("IsAvailable") else "OutOfStock",
        "vendedor": seller.get("sellerName"),
        "imagem_url": imagens[0]["imageUrl"] if imagens else None,
        "fonte_extracao": "vtex_api",
    }


def sincronizar_busca(domain, termos, delay, session):
    """Alternativa a marca/categoria: busca por texto livre (map=ft).

    Útil quando o site não marca os produtos com um atributo de marca
    específico, mas o termo aparece no nome/descrição (ex: "new holland"
    numa loja generalista de autopeças que também vende peça de trator).
    Cada termo é uma busca separada, com dedup por productId entre elas.
    """
    domain = domain.rstrip("/")
    netloc = urlparse(domain).netloc

    vistos = set()
    salvos = 0

    for termo in termos:
        url_base = f"{domain}/api/catalog_system/pub/products/search/{termo}?map=ft"
        r = requests.get(url_base, headers=_headers(), params={"_from": 0, "_to": 0}, timeout=30)
        faixa = r.headers.get("resources", "")
        total = int(faixa.split("/")[-1]) if "/" in faixa else 0
        total = min(total, LIMITE_VTEX)
        print(f"Busca '{termo}': {total} produto(s)")

        inicio = 0
        while inicio < total:
            fim = min(inicio + PAGE_SIZE - 1, total - 1)
            produtos = _get_com_retry(url_base, {"_from": inicio, "_to": fim}).json()
            for produto in produtos:
                pid = produto.get("productId")
                if pid in vistos:
                    continue
                vistos.add(pid)
                registro = _item_para_registro(produto, netloc)
                if registro is None:
                    continue
                session.add(Coleta(**registro))
                salvos += 1
            session.commit()
            inicio += PAGE_SIZE
            time.sleep(delay * random.uniform(0.7, 1.3))

    return salvos


def sincronizar(domain, marca, delay, session):
    domain = domain.rstrip("/")
    netloc = urlparse(domain).netloc

    print("Descobrindo árvore de categorias via sitemap...")
    arvore = _descobrir_arvore_categorias(domain)

    alvo = f"marca '{marca}'" if marca else "catálogo inteiro"
    print(f"Planejando fatias de consulta pra {alvo} (limite VTEX: {LIMITE_VTEX})...")
    fatias = _planejar_fatias(domain, marca, arvore)
    total_esperado = sum(t for _, t in fatias)
    print(f"{len(fatias)} fatia(s), ~{total_esperado} produtos no total.")

    vistos = set()
    salvos = 0

    for url_base, total_fatia in fatias:
        inicio = 0
        while inicio < total_fatia:
            fim = min(inicio + PAGE_SIZE - 1, total_fatia - 1)
            params = {"_from": inicio, "_to": fim}
            try:
                produtos = _get_com_retry(url_base, params).json()
            except requests.exceptions.HTTPError:
                # página inteira falhando de forma persistente -- provavelmente um
                # produto quebrado no site (ex: erro 500 do próprio VTEX) em algum
                # ponto dela; busca item a item pra isolar e pular só o que quebrar
                produtos = []
                for pos in range(inicio, fim + 1):
                    try:
                        produtos.extend(_get_com_retry(url_base, {"_from": pos, "_to": pos}, tentativas=2).json())
                    except requests.exceptions.HTTPError:
                        print(f"  AVISO: produto na posição {pos} está quebrado no site (erro 500 persistente) -- pulando")

            for produto in produtos:
                pid = produto.get("productId")
                if pid in vistos:
                    continue
                vistos.add(pid)
                registro = _item_para_registro(produto, netloc)
                if registro is None:
                    continue
                session.add(Coleta(**registro))
                salvos += 1

            session.commit()
            inicio += PAGE_SIZE
            time.sleep(delay * random.uniform(0.7, 1.3))

        print(f"  fatia concluída ({total_fatia} itens) -- {salvos} salvos até agora")

    return salvos


def main():
    parser = argparse.ArgumentParser(description="Sincroniza produtos de uma marca via API VTEX")
    parser.add_argument("--site", help="chave cadastrada em config/vtex_sites.yaml")
    parser.add_argument("--domain", help="ex: https://www.agrotrator.com.br (ignora --site)")
    parser.add_argument("--marca", help="slug da marca, ex: cnh (ignora --site). Omita pra pegar o catálogo inteiro")
    parser.add_argument("--delay", type=float, default=1.5, help="segundos entre páginas (padrão 1.5)")
    args = parser.parse_args()

    if args.domain:
        domain, marca = args.domain, args.marca
    elif args.site:
        domain, marca = _carregar_site(args.site)
    else:
        raise SystemExit("Informe --site <nome> (ver config/vtex_sites.yaml) ou --domain + --marca")

    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    os.chdir(BASE_DIR)
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)

    try:
        salvos = sincronizar(domain, marca, args.delay, session)
        print(f"Concluído: {salvos} registros salvos.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
