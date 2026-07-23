"""
Descoberta de URLs de produto via sitemap -- compartilhado entre os scripts
de sincronização (evita duplicar a mesma lógica em cada um).

Alguns sites declaram o sitemap num caminho não-padrão só no robots.txt
(ex: engepecas.com.br usa google_sitemap_1.xml), então a descoberta sempre
parte do robots.txt antes de tentar o /sitemap.xml genérico.
"""
import json
import random
import re
import time

import requests

from crawler.middlewares import USER_AGENTS


def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }


def descobrir_sitemaps(domain):
    domain = domain.rstrip("/")
    try:
        r = requests.get(f"{domain}/robots.txt", headers=_headers(), timeout=30)
        r.raise_for_status()
        declarados = re.findall(r"^Sitemap:\s*(\S+)", r.text, re.MULTILINE | re.IGNORECASE)
    except requests.exceptions.RequestException:
        declarados = []
    return declarados or [f"{domain}/sitemap.xml"]


def coletar_urls_sitemap(sitemap_url, visitados=None):
    """Segue sitemapindex recursivamente até achar <url><loc>."""
    visitados = visitados if visitados is not None else set()
    if sitemap_url in visitados:
        return []
    visitados.add(sitemap_url)

    r = requests.get(sitemap_url, headers=_headers(), timeout=60)
    r.raise_for_status()
    texto = r.text

    if "<sitemapindex" in texto:
        urls = []
        for sub in re.findall(r"<loc>(.*?)</loc>", texto):
            urls.extend(coletar_urls_sitemap(sub, visitados))
        return urls

    return re.findall(r"<loc>(.*?)</loc>", texto)


def urls_de_produto(domain, apenas_com=("produto", "product", "sitemap")):
    """Descobre todos os sitemaps do site e retorna a lista completa de URLs.

    apenas_com filtra quais sub-sitemaps olhar quando o índice tem sitemaps
    de outros tipos (categoria, blog, páginas institucionais) -- evita
    perder tempo baixando sitemaps que não têm produto nenhum.
    """
    sitemaps = descobrir_sitemaps(domain)
    urls = []
    for sm in sitemaps:
        urls.extend(coletar_urls_sitemap(sm))
    return list(dict.fromkeys(urls))


def filtrar_por_url(urls, termos):
    if not termos:
        return list(urls)
    termos = [t.strip().lower() for t in termos if t.strip()]
    return [u for u in urls if any(t in u.lower() for t in termos)]


def filtrar_por_titulo_marca(urls, termos, delay=0.25, progresso=None):
    """Visita cada URL e olha o JSON-LD (name + brand) atrás dos termos.

    Mais lento que filtrar_por_url (precisa abrir cada página), mas
    necessário em sites onde a URL do produto não reflete a marca
    (ex: newpecasoficial.com.br usa slugs curtos tipo "/porca").
    """
    if not termos:
        return list(urls)
    termos = [t.strip().lower() for t in termos if t.strip()]

    encontrados = []
    for i, url in enumerate(urls):
        try:
            r = requests.get(url, headers=_headers(), timeout=15)
            blocks = re.findall(r"<script[^>]*ld\+json[^>]*>(.*?)</script>", r.text, re.S)
            for b in blocks:
                try:
                    d = json.loads(b)
                except (json.JSONDecodeError, ValueError):
                    continue
                if d.get("@type") != "Product":
                    continue
                marca = d.get("brand", {})
                marca = marca.get("name", "") if isinstance(marca, dict) else ""
                texto = f"{marca} {d.get('name', '')}".lower()
                if any(t in texto for t in termos):
                    encontrados.append(url)
                break
        except requests.exceptions.RequestException:
            pass
        if progresso and (i + 1) % 100 == 0:
            progresso(i + 1, len(urls))
        time.sleep(delay)
    return encontrados
