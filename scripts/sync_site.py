#!/usr/bin/env python3
"""
Ponto de entrada único pra sincronizar qualquer site cadastrado em
config/sites.yaml -- decide sozinho qual método usar (VTEX API, Scrapy
padrão ou requests puro) e aplica o filtro de marca configurado.

Uso:
    python scripts/sync_site.py --site agrotrator
    python scripts/sync_site.py --site tratorlin
    python scripts/sync_site.py --listar
"""
import argparse
import os
import sys

import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)
os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "crawler.settings")

from crawler.lockutil import adquirir_lock
from crawler.logging_config import configurar_logging

configurar_logging()

_SITES_CONFIG_PATH = os.path.join(BASE_DIR, "config", "sites.yaml")


def _carregar_sites():
    with open(_SITES_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _rodar_vtex(cfg, delay):
    from db.models import get_engine, get_session, init_db
    from scripts.sync_vtex_brand import sincronizar, sincronizar_busca

    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)
    try:
        if cfg.get("busca"):
            salvos = sincronizar_busca(cfg["domain"], cfg["busca"], delay, session)
        else:
            salvos = sincronizar(cfg["domain"], cfg.get("marca"), delay, session)
        print(f"Concluído: {salvos} registros salvos.")
    finally:
        session.close()


def _rodar_html_bulk(cfg, delay):
    from db.models import get_engine, get_session, init_db
    from scripts.sync_html_bulk import sincronizar

    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)
    try:
        salvos, sem_preco = sincronizar(cfg["domain"], delay, session, filtro=cfg.get("filtro"))
        print(f"Concluído: {salvos} registros salvos, {sem_preco} sem preço extraído.")
    finally:
        session.close()


def _rodar_itemlist_bulk(cfg, delay):
    from db.models import get_engine, get_session, init_db
    from scripts.sync_itemlist_bulk import sincronizar

    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    engine = get_engine(db_url)
    init_db(engine)
    session = get_session(engine)
    try:
        salvos = sincronizar(cfg["domain"], delay, session, filtro=cfg.get("filtro"))
        print(f"Concluído: {salvos} produtos salvos.")
    finally:
        session.close()


def _rodar_scrapy(cfg, delay):
    from crawler.sitemap_utils import (
        descobrir_sitemaps,
        coletar_urls_sitemap,
        filtrar_por_url,
        filtrar_por_titulo_marca,
    )

    domain = cfg["domain"]
    filtro = cfg.get("filtro")
    modo = cfg.get("filtro_modo", "url")

    print("Descobrindo sitemap...")
    sitemaps = descobrir_sitemaps(domain)
    urls = []
    for sm in sitemaps:
        urls.extend(coletar_urls_sitemap(sm))
    urls = list(dict.fromkeys(urls))
    print(f"{len(urls)} URL(s) de produto no total.")

    if filtro:
        if modo == "titulo":
            print(f"Filtrando por título/marca (mais lento, abre cada página)... termos={filtro}")

            def _progresso(feito, total):
                print(f"  {feito}/{total} checados...")

            urls = filtrar_por_titulo_marca(urls, filtro, progresso=_progresso)
        else:
            urls = filtrar_por_url(urls, filtro)
    print(f"{len(urls)} URL(s) após filtro.")

    if not urls:
        print("Nenhuma URL após o filtro -- nada a fazer.")
        return

    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    settings = get_project_settings()
    if delay is not None:
        settings.set("DOWNLOAD_DELAY", delay)
    process = CrawlerProcess(settings)
    process.crawl("price", urls=urls)
    process.start()


_DISPATCH = {
    "vtex": _rodar_vtex,
    "html_bulk": _rodar_html_bulk,
    "itemlist_bulk": _rodar_itemlist_bulk,
    "scrapy": _rodar_scrapy,
}


def main():
    parser = argparse.ArgumentParser(description="Sincroniza um site cadastrado em config/sites.yaml")
    parser.add_argument("--site", help="chave cadastrada em config/sites.yaml")
    parser.add_argument("--listar", action="store_true", help="lista os sites cadastrados e sai")
    parser.add_argument("--delay", type=float, default=None, help="segundos entre requisições (usa o padrão do método se omitido)")
    args = parser.parse_args()

    sites = _carregar_sites()

    if args.listar:
        for nome, cfg in sites.items():
            print(f"{nome:25s} [{cfg['metodo']}]  {cfg['domain']}")
        return

    if not args.site:
        raise SystemExit("Informe --site <nome> ou --listar. Ver config/sites.yaml")

    if args.site not in sites:
        disponiveis = ", ".join(sites)
        raise SystemExit(f"Site '{args.site}' não está em config/sites.yaml. Disponíveis: {disponiveis}")

    cfg = sites[args.site]
    metodo = cfg["metodo"]
    if metodo not in _DISPATCH:
        raise SystemExit(f"Método '{metodo}' desconhecido (site {args.site})")

    padrao_delay = {"vtex": 1.5, "html_bulk": 1.5, "itemlist_bulk": 1.0, "scrapy": None}
    delay = args.delay if args.delay is not None else padrao_delay[metodo]

    lock = adquirir_lock(f"sync_{args.site}")
    try:
        _DISPATCH[metodo](cfg, delay)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
