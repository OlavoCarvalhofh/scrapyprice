"""
Modelo de banco de dados.

Regra de ouro: NUNCA sobrescrever. Cada coleta insere uma linha nova,
formando uma série temporal. É isso que permite ver a curva de preço
da concorrência ao longo das semanas.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Coleta(Base):
    __tablename__ = "coletas"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # identificação
    url = Column(String, nullable=False, index=True)
    loja = Column(String, index=True)          # domínio (ex: loja.caseih.com.br)
    produto = Column(String)                   # nome do produto
    sku = Column(String)                       # variação, quando existir
    categoria = Column(String)                 # breadcrumb / categoria

    # preço em profundidade
    preco = Column(Float)                       # preço "por" (o vigente)
    preco_de = Column(Float)                    # preço "de" (riscado), se houver
    preco_a_vista = Column(Float)               # à vista / PIX, se houver
    moeda = Column(String, default="BRL")
    parcelas = Column(Integer)                  # nº de parcelas
    parcela_valor = Column(Float)               # valor de cada parcela
    parcela_sem_juros = Column(Boolean)         # True se anunciado sem juros

    # mercado / disponibilidade
    disponibilidade = Column(String)            # InStock / OutOfStock / PreOrder
    vendedor = Column(String)                   # marca oficial vs terceiro
    avaliacao_nota = Column(Float)              # nota média
    avaliacao_qtd = Column(Integer)             # nº de avaliações
    imagem_url = Column(String)

    # de onde veio o dado (rastreabilidade da extração)
    fonte_extracao = Column(String)             # jsonld / opengraph / microdata / css

    # metadado essencial: sem isso não há histórico
    coletado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<Coleta {self.loja} {self.produto} R${self.preco} @ {self.coletado_em}>"


def get_engine(db_url="sqlite:///db/precos.db"):
    engine = create_engine(db_url, echo=False, future=True)

    if db_url.startswith("sqlite"):
        # WAL permite ler e escrever ao mesmo tempo sem erro de "database is
        # locked" -- importante já que rodamos vários sites em paralelo.
        @event.listens_for(engine, "connect")
        def _ativar_wal(conexao_dbapi, _):
            cursor = conexao_dbapi.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()

    return engine


def init_db(engine):
    Base.metadata.create_all(engine)


def get_session(engine):
    return sessionmaker(bind=engine, future=True)()
