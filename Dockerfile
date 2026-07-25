FROM python:3.12-slim

# libxml2/libxslt: exigidos pelo lxml (usado por extruct/parsel/scrapy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev \
    libxslt1-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# usuário não-root, mesma prática que já vale pra VPS (Fase 1 do PLANO.md)
RUN useradd --create-home crawler && chown -R crawler:crawler /app
USER crawler

# sem CMD fixo -- o Kestra (ou você via `docker run`) decide o que rodar,
# ex: python run.py --lote 30
#     python scripts/sync_site.py --site agrotrator
