#!/usr/bin/env python3
"""
Coleta em massa via requests puro, para sites onde uma única página lista
VÁRIOS produtos ao mesmo tempo num JSON-LD ItemList -- em vez de 1 produto
por página (ex: paccini.com.br, páginas de "peças compatíveis com este
veículo" listam de 0 a vários produtos por página).

Diferente do sync_html_bulk.py (que espera 1 produto por página), aqui cada
página visitada pode gerar 0, 1 ou N registros no banco.

Uso:
    python scripts/sync_itemlist_bulk.py --domain https://www.paccini.com.br --filtro veiculos/case,veiculos/new-holland
"""
import argparse
import os
import random
import sys
import time
from urllib.parse import urlparse

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from crawler.middlewares import USER_AGENTS
from crawler.extractors.structured import extract_all_products_jsonld
from crawler.sitemap_utils import descobrir_sitemaps, coletar_urls_sitemap, filtrar_por_url
from db.models import Coleta, get_engine, get_session, init_db


def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }


def sincronizar(domain, delay, session, filtro=None, limite=None):
    domain = domain.rstrip("/")
    netloc = urlparse(domain).netloc

    print("Descobrindo sitemap...")
    sitemaps = descobrir_sitemaps(domain)
    urls = []
    for sm in sitemaps:
        urls.extend(coletar_urls_sitemap(sm))
    urls = list(dict.fromkeys(urls))

    if filtro:
        termos = filtro.split(",") if isinstance(filtro, str) else filtro
        urls = filtrar_por_url(urls, termos)
    if limite:
        urls = urls[:limite]
    print(f"{len(urls)} página(s) a visitar.")

    salvos = 0
    paginas_com_item = 0
    vistos_global = set()

    for i, url in enumerate(urls, start=1):
        try:
            resp = requests.get(url, headers=_headers(), timeout=30)
            resp.raise_for_status()
            produtos = extract_all_products_jsonld(resp.text, url)
        except requests.exceptions.RequestException as e:
            print(f"  AVISO: falha ao buscar {url} ({e}) -- pulando")
            produtos = []

        if produtos:
            paginas_com_item += 1
        for p in produtos:
            chave = p.get("url")
            if chave in vistos_global:
                continue
            vistos_global.add(chave)
            registro = {"loja": netloc, "moeda": p.get("moeda", "BRL")}
            for campo in (
                "url", "produto", "preco", "disponibilidade", "vendedor",
                "imagem_url", "avaliacao_nota", "avaliacao_qtd", "fonte_extracao",
            ):
                if p.get(campo) is not None:
                    registro[campo] = p[campo]
            session.add(Coleta(**registro))
            salvos += 1

        if i % 100 == 0 or i == len(urls):
            session.commit()
            print(f"  {i}/{len(urls)} páginas ({paginas_com_item} com produto, {salvos} produtos únicos salvos)")

        time.sleep(delay * random.uniform(0.7, 1.3))

    session.commit()
    return salvos


def main():
    parser = argparse.ArgumentParser(description="Coleta em massa de páginas com múltiplos produtos (ItemList JSON-LD)")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--delay", type=float, default=1.0, help="segundos entre páginas (padrão 1.0)")
    parser.add_argument("--filtro", type=str, default=None, help="termos separados por vírgula, filtra a URL da página")
    parser.add_argument("--limite", type=int, default=None)
    args = parser.parse_args()

    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    os.chdir(BASE_DIR)
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)

    try:
        salvos = sincronizar(args.domain, args.delay, session, args.filtro, args.limite)
        print(f"Concluído: {salvos} produtos salvos.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
