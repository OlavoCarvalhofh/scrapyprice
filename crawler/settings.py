BOT_NAME = "price-crawler"

SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# ---------------------------------------------------------------------------
# EDUCAÇÃO / ANTI-DETECÇÃO  (cenário: não ser detectado, pode ser lento)
# ---------------------------------------------------------------------------

# Respeita as regras do site. Coloque False só se souber o que está fazendo.
ROBOTSTXT_OBEY = True

# Um domínio por vez, sem paralelismo agressivo.
CONCURRENT_REQUESTS = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 1

# Base de espera entre requisições ao mesmo domínio (em segundos).
DOWNLOAD_DELAY = 8

# Aleatoriza o delay: multiplica DOWNLOAD_DELAY por um fator entre 0.5 e 1.5.
# Ou seja, espera entre ~4s e ~12s. Nunca em intervalo exato = menos "cara de robô".
RANDOMIZE_DOWNLOAD_DELAY = True

# AutoThrottle: ajusta o ritmo sozinho conforme o servidor responde.
# Se o site fica lento, ele desacelera automaticamente.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 8
AUTOTHROTTLE_MAX_DELAY = 60
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# Retenta em falhas transitórias, com paciência (não insiste rápido).
RETRY_ENABLED = True
RETRY_TIMES = 2
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]

# Cache HTTP: em testes, evita re-baixar a mesma página (menos requisições ao site).
HTTPCACHE_ENABLED = False  # ligue (True) enquanto estiver desenvolvendo/testando

# ---------------------------------------------------------------------------
# DISFARCE: headers realistas + rotação de User-Agent
# ---------------------------------------------------------------------------

# Headers completos de um navegador de verdade (header incompleto entrega o bot).
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# Rotação de User-Agent via middleware (ver crawler/middlewares.py).
DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "crawler.middlewares.RotateUserAgentMiddleware": 400,
}

# Mantém cookies/sessão por domínio (parece visitante recorrente, não mil anônimos).
COOKIES_ENABLED = True

# ---------------------------------------------------------------------------
# SAÍDA
# ---------------------------------------------------------------------------

ITEM_PIPELINES = {
    "crawler.pipelines.SQLitePipeline": 300,
}

LOG_LEVEL = "INFO"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
