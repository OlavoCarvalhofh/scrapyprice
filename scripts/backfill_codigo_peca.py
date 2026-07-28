#!/usr/bin/env python3
"""
Backfill de codigo_peca nos registros já coletados dos sites VTEX --
não precisa re-crawlear, o código já está no texto de "produto" salvo,
só reaplica _extrair_codigo_peca() e faz UPDATE.

Uso:
    python scripts/backfill_codigo_peca.py
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from db.models import get_engine, get_session, Coleta
from scripts.sync_vtex_brand import _extrair_codigo_peca

SITES_VTEX = (
    "www.agrotrator.com.br",
    "loja.carpaltratores.com.br",
    "www.fornecedoramaquinas.com.br",
    "www.fornecedoraagro.com.br",
    "www.pitstop.com.br",
)


def main():
    db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
    engine = get_engine(db_url)
    session = get_session(engine)
    try:
        registros = (
            session.query(Coleta)
            .filter(Coleta.loja.in_(SITES_VTEX), Coleta.codigo_peca.is_(None))
            .all()
        )
        atualizados = 0
        for r in registros:
            codigo = _extrair_codigo_peca(r.produto)
            if codigo:
                r.codigo_peca = codigo
                atualizados += 1
        session.commit()
        print(f"{len(registros)} registros verificados, {atualizados} atualizados com codigo_peca.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
