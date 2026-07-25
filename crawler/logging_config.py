"""
Log em arquivo com rotação -- pra não perder o histórico quando roda sem
supervisão (cron/Kestra), diferente de só jogar no stdout (que se perde
quando roda em segundo plano).

Chame configurar_logging() uma vez, no início de cada ponto de entrada
(run.py, scripts/sync_site.py), antes de qualquer coisa que gere log.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

_JA_CONFIGURADO = False


def configurar_logging(nome_arquivo="price-crawler.log", nivel=logging.INFO):
    global _JA_CONFIGURADO
    if _JA_CONFIGURADO:
        return
    _JA_CONFIGURADO = True

    os.makedirs(_LOGS_DIR, exist_ok=True)
    caminho = os.path.join(_LOGS_DIR, nome_arquivo)

    handler = RotatingFileHandler(
        caminho, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    ))
    handler.setLevel(nivel)

    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > nivel:
        root.setLevel(nivel)
