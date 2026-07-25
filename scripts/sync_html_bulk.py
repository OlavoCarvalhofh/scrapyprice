#!/usr/bin/env python3
"""
Coleta em massa via requests puro (sem Scrapy), para sites onde o Scrapy/Twisted
é bloqueado por impressão digital de conexão mas uma requisição HTTP comum passa
normalmente (ex: engepecas.com.br -- confirmado que `requests` com os mesmos
headers do Scrapy recebe 200, enquanto o Scrapy recebe 403).

Descobre as URLs de produto pelo sitemap declarado no robots.txt (não pelo
caminho padrão /sitemap.xml, que alguns sites não usam), e roda os mesmos
extractors do spider principal (JSON-LD/OG/microdata + CSS custom).

Uso:
    python scripts/sync_html_bulk.py --domain https://engepecas.com.br
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
from crawler.extractors.structured import extract_structured
from crawler.extractors.custom import extract_custom
from crawler.sitemap_utils import descobrir_sitemaps, coletar_urls_sitemap, filtrar_por_url
from crawler import relatorio_falhas
from db.models import Coleta, get_engine, get_session, init_db

CAMPOS = (
    "produto", "sku", "categoria", "preco", "preco_de", "preco_a_vista",
    "parcelas", "parcela_valor", "parcela_sem_juros", "disponibilidade",
    "vendedor", "avaliacao_nota", "avaliacao_qtd", "imagem_url",
    "fonte_extracao",
)


def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
    }


def _para_registro(url, html, netloc):
    data = extract_structured(html, url)
    custom = extract_custom(html, netloc)
    for k, v in custom.items():
        if k not in data or data.get(k) is None:
            data[k] = v

    if data.get("preco") is None:
        return None

    registro = {"url": url, "loja": netloc, "moeda": data.get("moeda", "BRL")}
    for campo in CAMPOS:
        if data.get(campo) is not None:
            registro[campo] = data[campo]
    return registro


def sincronizar(domain, delay, session, limite=None, filtro=None):
    domain = domain.rstrip("/")
    netloc = urlparse(domain).netloc

    print("Descobrindo sitemap via robots.txt...")
    sitemaps = descobrir_sitemaps(domain)
    print(f"Sitemap(s): {sitemaps}")

    urls = []
    for sm in sitemaps:
        urls.extend(coletar_urls_sitemap(sm))
    urls = list(dict.fromkeys(urls))  # remove duplicatas preservando ordem

    if filtro:
        termos = filtro.split(",") if isinstance(filtro, str) else filtro
        urls = filtrar_por_url(urls, termos)

    if limite:
        urls = urls[:limite]
    print(f"{len(urls)} URL(s) de produto encontradas.")

    salvos = 0
    sem_preco = 0
    falhas = []
    for i, url in enumerate(urls, start=1):
        try:
            resp = requests.get(url, headers=_headers(), timeout=30)
            resp.raise_for_status()
            registro = _para_registro(url, resp.text, netloc)
            motivo = "sem_preco"
        except requests.exceptions.RequestException as e:
            print(f"  AVISO: falha ao buscar {url} ({e}) -- pulando")
            registro = None
            motivo = f"erro_rede: {e}"

        if registro is None:
            sem_preco += 1
            falhas.append({"url": url, "motivo": motivo})
        else:
            session.add(Coleta(**registro))
            salvos += 1

        if i % 50 == 0 or i == len(urls):
            session.commit()
            print(f"  {i}/{len(urls)} processados ({salvos} salvos, {sem_preco} sem preço)")

        time.sleep(delay * random.uniform(0.7, 1.3))

    session.commit()
    return salvos, sem_preco, falhas


def main():
    parser = argparse.ArgumentParser(description="Coleta em massa via requests puro (sites que bloqueiam Scrapy)")
    parser.add_argument("--domain", required=True, help="ex: https://engepecas.com.br")
    parser.add_argument("--delay", type=float, default=1.5, help="segundos entre requisições (padrão 1.5)")
    parser.add_argument("--limite", type=int, default=None, help="testar só com as N primeiras URLs")
    parser.add_argument("--filtro", type=str, default=None,
                         help="só processa URLs que contenham um destes termos (separados por vírgula), ex: 'case,cnh,new-holland'")
    args = parser.parse_args()

    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    os.chdir(BASE_DIR)
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)

    try:
        salvos, sem_preco, falhas = sincronizar(args.domain, args.delay, session, args.limite, args.filtro)
        relatorio_falhas.salvar(urlparse(args.domain).netloc, falhas)
        print(f"Concluído: {salvos} registros salvos, {sem_preco} sem preço extraído.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
