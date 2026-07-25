import logging
import os
import sys

# garante que a raiz do projeto está no path (para importar db/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from db.models import Coleta, get_engine, get_session, init_db

logger = logging.getLogger(__name__)


class SQLitePipeline:
    """Insere UMA LINHA NOVA por coleta. Nunca sobrescreve -> série temporal.

    Sem o parâmetro `spider` nos métodos (padrão novo do Scrapy 2.17+) --
    o antigo `open_spider(self, spider)` etc. gera ScrapyDeprecationWarning
    porque o spider deixará de ser passado automaticamente em versões futuras.
    """

    def open_spider(self):
        db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
        self.engine = get_engine(db_url)
        init_db(self.engine)
        self.session = get_session(self.engine)

    def close_spider(self):
        self.session.close()

    def process_item(self, item):
        registro = Coleta(**{k: item.get(k) for k in item.keys()})
        self.session.add(registro)
        self.session.commit()
        logger.info(f"Salvo: {registro}")
        return item
