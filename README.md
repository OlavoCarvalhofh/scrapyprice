# Price Crawler

Crawler simples de preços: você adiciona os links, ele extrai preço (e mais)
automaticamente e salva um histórico em banco de dados.

## Como funciona
Para cada URL, tenta extrair dados na ordem:
1. **JSON-LD** (a maioria dos e-commerces expõe) — nome, preço, moeda, estoque, avaliações
2. **OpenGraph** (`product:price:amount`)
3. **Microdata** (`itemprop="price"`)
4. **CSS custom** por domínio (`config/selectors.yaml`) — só para o que faltar

Cada coleta grava uma **linha nova** (nunca sobrescreve) → série temporal de preços.

## Instalar
```bash
pip install -r requirements.txt
```

## Usar
1. Cole os links em `urls.txt` (um por linha).
2. Rode:
```bash
python run.py              # todas as URLs
python run.py --lote 30    # sorteia 30 (distribui a carga pela semana)
python run.py --url URL    # uma URL avulsa
```
3. Os dados vão para `db/precos.db` (SQLite). Abra no DBeaver, ou conecte no Power BI.

## Rodar ao longo da semana (sem ser detectado)
A estratégia anti-detecção já está em `crawler/settings.py`:
delays aleatórios (4–12s), AutoThrottle, headers realistas, rotação de User-Agent,
1 requisição por domínio por vez, respeito ao robots.txt.

Para distribuir a carga, agende `python run.py --lote N` algumas vezes ao dia:
- **Windows**: Agendador de Tarefas → nova tarefa → aciona `python run.py --lote 30`
- **Linux/Mac (cron)**: `0 9,15 * * 1-5  cd /caminho && python run.py --lote 30`

Com 200 produtos e `--lote 30` 2x/dia, cada produto é visto ~a cada 3 dias,
num ritmo que parece humano.

## Sites que renderizam preço via JavaScript
Se um site só monta o preço via JS, o HTML puro não terá o dado. Nesse caso,
instale `scrapy-playwright` e ative-o **só para esse domínio**. Me avise que
te passo o ajuste.

## Adicionar um site que não expõe dado estruturado
Edite `config/selectors.yaml` com o seletor CSS do preço (F12 no navegador →
botão direito no preço → Copiar seletor). Não precisa mexer em código.
