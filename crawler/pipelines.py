import os
import sys

# garante que a raiz do projeto está no path (para importar db/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from db.models import Coleta, get_engine, get_session, init_db


class SQLitePipeline:
    """Insere UMA LINHA NOVA por coleta. Nunca sobrescreve -> série temporal."""

    def open_spider(self, spider):
        db_url = os.environ.get("PRICE_DB_URL", "sqlite:///db/precos.db")
        self.engine = get_engine(db_url)
        init_db(self.engine)
        self.session = get_session(self.engine)

    def close_spider(self, spider):
        self.session.close()

    def process_item(self, item, spider):
        registro = Coleta(**{k: item.get(k) for k in item.keys()})
        self.session.add(registro)
        self.session.commit()
        spider.logger.info(f"Salvo: {registro}")
        return item
