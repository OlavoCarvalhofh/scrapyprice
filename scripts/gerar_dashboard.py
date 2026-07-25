#!/usr/bin/env python3
"""
Gera um dashboard HTML estático (self-contained, sem servidor) a partir do
banco de dados -- versão funcional inicial da Fase 3, antes do design final.

Uso:
    python scripts/gerar_dashboard.py
    python scripts/gerar_dashboard.py --saida dashboard/index.html
"""
import argparse
import json
import os
import sys
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from db.models import get_engine, get_session, Coleta

TEMPLATE_PATH = os.path.join(BASE_DIR, "scripts", "dashboard_template.html")


def coletar_dados():
    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    engine = get_engine(db_url)
    session = get_session(engine)
    try:
        linhas = session.query(
            Coleta.url, Coleta.loja, Coleta.produto, Coleta.preco,
            Coleta.preco_de, Coleta.disponibilidade, Coleta.coletado_em,
        ).filter(Coleta.preco.isnot(None)).order_by(Coleta.coletado_em.asc()).all()
    finally:
        session.close()
    return linhas


def montar_estruturas(linhas):
    historico = defaultdict(list)
    ultimo = {}

    for url, loja, produto, preco, preco_de, disponibilidade, coletado_em in linhas:
        ts = coletado_em.strftime("%Y-%m-%dT%H:%M:%S")
        historico[url].append([ts, preco])
        ultimo[url] = {
            "loja": loja,
            "produto": produto or "",
            "url": url,
            "preco": preco,
            "preco_de": preco_de,
            "disponibilidade": disponibilidade or "",
            "atualizado": ts,
        }

    produtos = list(ultimo.values())
    lojas = sorted({p["loja"] for p in produtos})
    ultima_coleta = max((p["atualizado"] for p in produtos), default="")

    resumo = {
        "total_produtos": len(produtos),
        "total_lojas": len(lojas),
        "total_registros": sum(len(v) for v in historico.values()),
        "ultima_coleta": ultima_coleta,
    }
    return produtos, dict(historico), lojas, resumo


def _json_seguro_para_script(obj):
    """json.dumps não escapa '</script>' -- se algum texto (ex: nome de
    produto) tiver essa sequência, quebraria o HTML. Escapa '</' pra
    '<\\/' (JSON/JS válido) só por segurança."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def gerar_html(produtos, historico, lojas, resumo, caminho_saida):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    html = (
        template
        .replace("__PRODUTOS_JSON__", _json_seguro_para_script(produtos))
        .replace("__HISTORICO_JSON__", _json_seguro_para_script(historico))
        .replace("__LOJAS_JSON__", _json_seguro_para_script(lojas))
        .replace("__RESUMO_JSON__", _json_seguro_para_script(resumo))
    )

    os.makedirs(os.path.dirname(caminho_saida) or ".", exist_ok=True)
    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description="Gera o dashboard HTML estático")
    parser.add_argument("--saida", default="dashboard/index.html")
    args = parser.parse_args()

    print("Lendo dados do banco...")
    linhas = coletar_dados()
    produtos, historico, lojas, resumo = montar_estruturas(linhas)
    print(f"{resumo['total_produtos']} produtos, {resumo['total_lojas']} lojas, "
          f"{resumo['total_registros']} registros no histórico.")

    gerar_html(produtos, historico, lojas, resumo, args.saida)
    print(f"Dashboard gerado em: {args.saida}")


if __name__ == "__main__":
    main()
