#!/usr/bin/env python3
"""
Exporta todo o histórico de coletas pra CSV -- útil pra abrir num Excel/
Sheets, ou subir num SharePoint/OneDrive e consumir via Power BI (conector
nativo de pasta, sem precisar de driver ODBC pra SQLite).

Uso:
    python scripts/exportar_csv.py
    python scripts/exportar_csv.py --saida db/precos.csv
"""
import argparse
import csv
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from db.models import get_engine, get_session, Coleta

CAMPOS = (
    "id", "url", "loja", "produto", "sku", "mpn", "codigo_peca", "categoria",
    "preco", "preco_de", "preco_a_vista", "moeda",
    "parcelas", "parcela_valor", "parcela_sem_juros",
    "disponibilidade", "vendedor", "avaliacao_nota", "avaliacao_qtd",
    "imagem_url", "fonte_extracao", "coletado_em",
)


def exportar(saida):
    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    engine = get_engine(db_url)
    session = get_session(engine)
    try:
        registros = session.query(Coleta).order_by(Coleta.coletado_em.asc()).all()
    finally:
        session.close()

    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(CAMPOS)
        for r in registros:
            writer.writerow([getattr(r, campo) for campo in CAMPOS])

    return len(registros)


def main():
    parser = argparse.ArgumentParser(description="Exporta o histórico de coletas pra CSV")
    parser.add_argument("--saida", default="db/precos.csv", help="caminho do CSV de saída (padrão: db/precos.csv)")
    args = parser.parse_args()

    total = exportar(args.saida)
    print(f"Exportado: {total} registros -> {args.saida}")


if __name__ == "__main__":
    main()
