from urllib.parse import urlparse

import scrapy

from crawler.items import ProductItem
from crawler.extractors.structured import extract_structured
from crawler.extractors.custom import extract_custom


class PriceSpider(scrapy.Spider):
    name = "price"

    def __init__(self, urls=None, *args, **kwargs):
        """
        urls pode vir:
          - do run.py (lista Python), ou
          - da linha de comando: -a urls="http://a,http://b"
        """
        super().__init__(*args, **kwargs)
        if isinstance(urls, str):
            self.start_urls = [u.strip() for u in urls.split(",") if u.strip()]
        elif urls:
            self.start_urls = list(urls)
        else:
            self.start_urls = []

    def parse(self, response):
        html = response.text
        domain = urlparse(response.url).netloc

        # 1) cascata de dados estruturados (JSON-LD > OG > microdata)
        data = extract_structured(html, response.url)

        # 2) fallback/complemento por CSS (config/selectors.yaml)
        custom = extract_custom(html, domain)
        for k, v in custom.items():
            # só preenche o que faltou; se o CSS achou preço e o structured não,
            # o CSS assume também a fonte_extracao
            if k not in data or data.get(k) is None:
                data[k] = v

        if data.get("preco") is None:
            self.logger.warning(f"Sem preço extraído: {response.url}")
            return

        item = ProductItem()
        item["url"] = response.url
        item["loja"] = domain
        item["moeda"] = data.get("moeda", "BRL")
        for field in (
            "produto", "sku", "categoria", "preco", "preco_de", "preco_a_vista",
            "parcelas", "parcela_valor", "parcela_sem_juros", "disponibilidade",
            "vendedor", "avaliacao_nota", "avaliacao_qtd", "imagem_url",
            "fonte_extracao",
        ):
            if data.get(field) is not None:
                item[field] = data[field]

        yield item
