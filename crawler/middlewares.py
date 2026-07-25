import random

# User-Agents de navegadores reais e atuais. Atualize de tempos em tempos
# (basta copiar o UA do seu Chrome/Firefox em chrome://version).
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


class RotateUserAgentMiddleware:
    """Sorteia um User-Agent realista por requisição.

    Sem o parâmetro `spider` (padrão novo do Scrapy 2.17+, evita
    ScrapyDeprecationWarning -- ver crawler/pipelines.py pro mesmo ajuste).
    """

    def process_request(self, request):
        request.headers["User-Agent"] = random.choice(USER_AGENTS)
        return None
