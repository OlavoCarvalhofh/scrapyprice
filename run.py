#!/usr/bin/env python3
"""
Ponto de entrada.

Uso:
    python run.py                 # coleta TODAS as URLs de urls.txt
    python run.py --lote 30       # sorteia 30 URLs (distribui a carga pela semana)
    python run.py --url http://x  # coleta uma URL avulsa

Ideia do cenário "sem pressa, ao longo da semana":
  agende este script (Task Scheduler / cron) várias vezes ao dia com --lote N.
  A cada execução ele pega um subconjunto aleatório, então nenhum domínio
  recebe muitas visitas seguidas. Ex: 200 produtos, --lote 30, 2x ao dia
  -> cada produto é visitado ~a cada 3 dias, num ritmo humano.
"""
import argparse
import os
import random
import sys

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)  # garante que sqlite:///db/precos.db aponta pro lugar certo

# aponta o Scrapy para o settings do projeto
os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "crawler.settings")


def carregar_urls(caminho="urls.txt"):
    if not os.path.exists(caminho):
        return []
    urls = []
    with open(caminho, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                urls.append(linha)
    return urls


def main():
    parser = argparse.ArgumentParser(description="Crawler de preços")
    parser.add_argument("--lote", type=int, default=None,
                        help="sorteia N URLs em vez de rodar todas")
    parser.add_argument("--url", type=str, default=None,
                        help="coleta uma única URL avulsa")
    parser.add_argument("--arquivo", type=str, default="urls.txt",
                        help="arquivo de URLs (padrão: urls.txt)")
    args = parser.parse_args()

    if args.url:
        urls = [args.url]
    else:
        urls = carregar_urls(args.arquivo)
        if args.lote and args.lote < len(urls):
            urls = random.sample(urls, args.lote)

    if not urls:
        print("Nenhuma URL para coletar. Adicione links em urls.txt.")
        return

    random.shuffle(urls)  # ordem aleatória a cada rodada
    print(f"Coletando {len(urls)} URL(s)...")

    process = CrawlerProcess(get_project_settings())
    process.crawl("price", urls=urls)
    process.start()


if __name__ == "__main__":
    main()
