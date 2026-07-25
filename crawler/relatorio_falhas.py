"""Registra as URLs que falharam na última coleta de um site -- sem preço
extraído ou erro de rede -- pra saber quando um site mudou de layout e
precisa de novo seletor CSS (ver Fase 2 do PLANO.md).

Cada rodada sobrescreve o arquivo do site: reflete só a última tentativa,
não acumula histórico (uma URL corrigida não fica presa na lista pra sempre).
"""
import json
import os
from datetime import datetime, timezone

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "urls_quebradas")


def salvar(site, falhas):
    """falhas: lista de dicts {"url": str, "motivo": str}. Lista vazia remove
    o arquivo do site (site voltou a rodar 100% limpo)."""
    caminho = os.path.join(_DIR, f"{site}.json")
    if not falhas:
        if os.path.exists(caminho):
            os.remove(caminho)
        return
    os.makedirs(_DIR, exist_ok=True)
    payload = {
        "site": site,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total": len(falhas),
        "urls": falhas,
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
