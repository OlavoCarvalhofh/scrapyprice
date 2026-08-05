# Plano — Price Crawler (produção + dashboard)

Status geral: em revisão conjunta, fase por fase. Nada é implementado até combinarmos aqui.

## VPS sugerida
Com o Kestra entrando no plano (Fase 1), a conta de recursos mudou:
- **Mínimo confortável agora: 2 vCPU / 4GB RAM** (antes bastava 1-2GB só pro crawler; Kestra +
  Postgres próprio dele + scheduler + webserver pedem mais).
- **Hostinger (plano VPS/KVM)** continua sendo a opção padrão — só ajustar pro plano de specs
  acima em vez do mais básico. Confirmar que é o plano **VPS** (SSH root), não hospedagem
  compartilhada.
- **VPS da empresa**: dá pra usar também, o projeto não depende de nada específico da Hostinger
  (é só Docker + Python + Postgres num Linux qualquer). Antes de assumir que serve, confirmar
  com quem administra: (1) sobra RAM/CPU suficiente considerando o que já roda lá, (2) não tem
  regra de firewall bloqueando tráfego de saída pra sites externos (o crawler faz bastante
  requisição de saída), (3) as portas do Kestra (8080) e do Postgres (5432) não conflitam com
  algo que já esteja em uso.
- Alternativa: Hostgator VPS, specs parecidas, geralmente um pouco mais caro pro mesmo hardware
  no Brasil.

---

## Fase 0 — Hardening local (antes de subir)
Deixar o crawler robusto para rodar sem supervisão.
- [x] Migrar de SQLite para **Postgres self-hosted** (decidido: não vamos usar Supabase) —
      código já era só configuração (`PRICE_DB_URL`, SQLAlchemy). **Validado localmente**: subiu
      o `postgres:16.4` via `docker-compose.yml`, rodou `init_db` (criou a tabela `coletas`) e
      confirmou insert+query reais contra o Postgres. Ainda falta repetir esse mesmo teste já na
      VPS (Fase 1) quando ela existir -- aqui só prova que o caminho de código funciona. Nessa
      validação o Docker Desktop local travou (bug do `vpnkit-bridge`, sem relação com o projeto)
      e a imagem `postgres:16` puxada durante o travamento ficou corrompida (`docker-entrypoint.sh`
      virou um arquivo de 0 bytes, sobrevivendo até a `docker rmi`+re-pull) -- por isso o
      `docker-compose.yml` agora fixa `postgres:16.4` em vez de `postgres:16` (também mais
      consistente com o resto do projeto, que já fixa versões)
- [x] Ativar modo **WAL** do SQLite (`PRAGMA journal_mode=WAL;`) — feito em `db/models.py`
      (`get_engine`), ativado automaticamente a cada conexão via `event.listens_for`. Testado:
      `PRAGMA journal_mode` confirma `wal` num banco temporário
- [x] Log em arquivo com rotação — `crawler/logging_config.py` (`RotatingFileHandler`,
      10MB/5 backups), conectado em `run.py` e `scripts/sync_site.py`. Testado: `logs/`
      captura os logs inclusive do Scrapy internamente, sem conflito
- [x] Trava contra execução sobreposta (lockfile) — `crawler/lockutil.py` (usa `filelock`),
      conectado em `run.py` (trava por arquivo de URLs) e `scripts/sync_site.py` (trava por
      site, permitindo sites diferentes em paralelo). Testado: segunda tentativa de rodar o
      mesmo lock é bloqueada com mensagem clara
- [x] Fixar versões no `requirements.txt` (trocar `>=` por `==`) — usando as versões já
      instaladas e validadas. Testado: `pip install -r requirements.txt` sem conflito, e o
      `Dockerfile` builda normal com as versões fixas
- [x] Backup periódico dos dados — `scripts/backup_postgres.sh` criado (pg_dump + retenção
      configurável de dias, pronto pra agendar via cron ou um flow do Kestra). Ainda não testado
      contra um Postgres real (não existe um rodando ainda) — validar na Fase 1
- [x] Testes unitários pros extractors — `tests/` (pytest, 27 testes: `_to_float` pt-BR/en-US,
      cascata JSON-LD/OG/microdata, `extract_all_products_jsonld`, seletores CSS reais do
      `config/selectors.yaml`). **Achou um bug real**: `_from_microdata` procurava uma chave
      `"properties"` que não existe no formato `uniform=True` do extruct -- o fallback de
      microdata nunca funcionou de verdade em produção, sempre retornava vazio silenciosamente.
      Corrigido e com teste de regressão agora. `requirements-dev.txt` criado (pytest)
- [x] Atualizar `crawler/pipelines.py` (`SQLitePipeline`) e `crawler/middlewares.py`
      (`RotateUserAgentMiddleware`) pro padrão novo do Scrapy 2.17+ (removido o parâmetro
      `spider` obrigatório) — resolvido e testado num banco temporário separado, sem tocar no
      `db/precos.db` real. `ScrapyDeprecationWarning` não aparece mais no log

## Fase 1 — Deploy na VPS (crawler + Postgres + Kestra)
- [ ] Provisionar VPS (Hostinger ou a da empresa — ver specs revisadas acima), Ubuntu LTS, usuário não-root
- [ ] Instalar **Docker + Docker Compose**
- [x] Criar `Dockerfile` do crawler (empacota o projeto + dependências fixas da Fase 0) — feito,
      mais `.dockerignore` e `psycopg2-binary` no `requirements.txt`. **Build testado e validado**:
      imagem constrói sem erro e rodou um crawl de verdade dentro do container (item extraído,
      sem warnings, ~97MB de memória)
- [x] `docker-compose.yml` criado — Postgres (banco `precos` + banco `kestra` separado no mesmo
      container, via `docker/init-postgres-databases.sh`) + Kestra apontando pra ele + serviço
      `crawler` (build-only, é a imagem que o Kestra vai usar pra rodar os flows). `.env.example`
      documentando as variáveis. **Serviço `postgres` testado subindo de verdade localmente**
      (ver item da Fase 0 acima); Kestra ainda não testado
- [ ] Acessar a interface do Kestra (porta 8080) só via **túnel SSH** — não expor direto pra internet sem autenticação na frente
- [x] Criar os **flows YAML** no Kestra — `kestra/flows/sync_site.yaml`: um flow único parametrizado
      (input `site`) em vez de 14 flows duplicados, chamando `python scripts/sync_site.py --site
      <nome>` dentro do container do crawler (`price-crawler:latest`, rede `price-crawler_default`
      pra resolver o hostname `postgres`) via Docker task runner do Kestra. 14 gatilhos de
      agendamento (um por site, escalonados de 20 em 20min a partir das 2h) substituem o cron.
      **Ainda NÃO testado disparando de verdade** -- o Docker Desktop local travou 3 vezes
      seguidas hoje tentando validar isso (erro de `vpnkit-bridge`, cache de imagem corrompido,
      e depois a própria `docker build` clássica travando parada no meio, sem erro) -- parece um
      problema mais profundo no WSL2 dessa máquina, não algo resolvido só reiniciando o app.
      Decisão: não insistir mais localmente por hoje; validar disparo manual de verdade só quando
      a VPS existir (ambiente limpo, Fase 1) ou depois que o Docker Desktop local for investigado
      à parte
- [ ] Investigar a instabilidade do Docker Desktop local (WSL2) -- fora do escopo do projeto em
      si, mas bloqueou a validação local de Postgres+Kestra hoje; se for mexer de novo, considerar
      `wsl --shutdown` seguido de reabrir, ou como último recurso um reset mais profundo (que
      apaga containers/imagens/volumes de TODOS os projetos Docker nessa máquina, não só este)
- [ ] Validar timezone do servidor (pra bater com o horário desejado nas coletas)
- [ ] Testar uma coleta manual (via Kestra, disparo manual do flow) antes de deixar no agendamento automático

## Fase 2 — Popular dados reais
- [x] Sites mapeados e configurados em `config/sites.yaml` (14 lojas já rodadas pelo menos uma vez: agrotrator, fornecedoramaquinas, fornecedoraagro, carpaltratores, pitstop, tratorlin, acamargo, superagrosc, tratormag, jerdrones, prosperadistribuicao, newpecasoficial, engepecas, paccini)
- [x] **agripecas.net mapeado** (plataforma "Loja Integrada"/awsli) — `metodo: html_bulk` porque o
      robots.txt tem um bloco `User-agent: Scrapy` com `Disallow: /` explícito (junto de vários
      outros bots conhecidos: GPTBot, ClaudeBot, CCBot, Diffbot, etc.) que bloquearia
      `metodo: scrapy` via `RobotsTxtMiddleware`; `User-agent: *` (nosso UA de navegador comum)
      permite tudo com `Crawl-delay: 10`, respeitado via `delay: 10` no YAML (novo campo opcional
      por site em `sync_site.py`, antes só existia o padrão fixo por método). Catálogo pequeno
      (347 produtos, 16-18 batem no filtro `[case, new-holland, cnh]` -- peças de plataforma de
      colheitadeira). Rodado de verdade contra o banco: 15 salvos, 3 sem preço (1 é a página de
      categoria da marca, capturada pelo filtro por engano mas inofensiva -- só gera um warning)
- [x] **premierdrones.com.br mapeado** (mesma plataforma "Loja Integrada"/awsli e mesmo bloco
      `User-agent: Scrapy` -> `Disallow: /` do agripecas -- `metodo: html_bulk` + `delay: 10`
      pelo mesmo motivo). Loja de drones (concorrente do projeto de drones, não trator, como o
      `jerdrones`) -- 343 produtos, sem filtro de marca = catálogo inteiro. Teste com 5 produtos:
      5/5 salvos. Rodada completa dos 343 disparada em background
- [x] **goldrones.com.br mapeado** — WordPress/WooCommerce (tema Phlox + Elementor), sem
      JSON-LD/OG/microdata nenhum (nem preço vem estruturado). `metodo: scrapy` (robots.txt
      permissivo, sem bloqueio de bot como agripecas/premierdrones) com `filtro: ["/produto/"]`
      pra ignorar posts/páginas/taxonomias/usuários que o `wp-sitemap.xml` também lista.
      Seletores CSS novos em `config/selectors.yaml` (preço com/sem promoção via `<del>/<ins>`
      vs `<span>` direto num `id` único do bloco de preço; disponibilidade via classe
      instock/outofstock no wrapper do Elementor, não no `<body>` como eu tentei primeiro --
      corrigido depois de testar). 2 testes de regressão novos em `tests/test_custom.py` (36
      testes no total). Loja de drones agrícolas DJI Agras (concorrente do projeto de drones),
      300 produtos, sem filtro de marca. Validado com spider real (2/2 produtos, robots.txt OK).
      Rodada completa disparada em background
- [x] **geotrackconsultoria.com.br mapeado** — mesma plataforma "Loja Integrada"/awsli e mesmo
      bloco robots.txt do agripecas/premierdrones (`metodo: html_bulk` + `delay: 10`). Diferente
      dos outros dois sites de drone: aqui é loja GENERALISTA de topografia/geo (GPS, estação
      total, prisma, tripé) que também vende drones DJI e drones pulverizadores agrícolas
      (JT10L/JT20L/JT40L/JT50L) -- precisou de `filtro: [drone, dji, agras, pulverizador, jt40,
      jt50, jt20, jt10]` pra não trazer equipamento de topografia junto. 244 produtos no
      catálogo, 48 batem no filtro. Microdata igual aos outros "Loja Integrada", sem seletor CSS
      novo. Rodada completa disparada em background
- [x] **worldwidebrasil.com.br mapeado** — mesma plataforma "Loja Integrada"/awsli e mesmo bloco
      robots.txt dos outros três. Loja GENERALISTA de importados/eletrônicos (RC cars, celular,
      câmera, console, perfume...) que também é revendedor grande da linha DJI inteira (Agras
      T10 a T50, Matrice, Mavic/Air/Mini/Avata, Chasing submarino, Autel) -- 1168 produtos no
      catálogo, 171 batem no filtro `["dji-", "-dji", drone, mavic, agras, phantom, avata,
      matrice, chasing, autel]`. Usei `"dji-"`/`"-dji"` em vez de `dji` sozinho porque essa
      substring dava falso positivo em "kurkdjian" (marca de perfume) -- achado testando o
      filtro antes de rodar de verdade. Provavelmente a fonte mais rica pro projeto de drones
      encontrada até agora (linha Agras completa num só lugar). Microdata igual aos outros "Loja
      Integrada", sem seletor CSS novo. Rodada completa disparada em background
- [x] **dronedireto.com.br mapeado** — mesma plataforma "Loja Integrada"/awsli e mesmo bloco
      robots.txt dos outros. Loja especializada em drone/mapeamento aéreo profissional (DJI
      enterprise: Matrice, Zenmuse, Dock; câmeras multiespectrais Micasense/MAPIR; software de
      mapeamento) -- 178 produtos, catálogo inteiro relevante, sem filtro de marca (mesmo padrão
      do jerdrones/premierdrones/dronedireto). Microdata igual aos outros, sem seletor CSS novo.
      Rodada completa disparada em background
- [x] **agroshopbr.com mapeado** — Magento (não "Loja Integrada"). Achei 2 problemas reais
      testando: (1) `descobrir_sitemaps` (`crawler/sitemap_utils.py`) seguia cegamente o sitemap
      declarado no robots.txt, mas esse site declara o de OUTRO domínio (agroshopacamargo.com.br)
      que só lista a home -- corrigido pra somar o `/sitemap.xml` do próprio domínio como fonte
      extra quando existir, sem quebrar sites onde o declarado já é o certo; (2) o JSON-LD desse
      site tem `"offers"` como lista com um item vazio `[]` antes do Offer de verdade -- `_first()`
      pegava o `[]` e nunca achava o preço, corrigido com `_first_dict()` (pula itens que não são
      dict) em `crawler/extractors/structured.py`, com teste de regressão em
      `tests/test_structured.py` (37 testes no total). robots.txt não bloqueia bot, mas disallowa
      `*cat=*` (a URL de busca por categoria que motivou olhar esse site -- não usar esse padrão).
      `metodo: scrapy`, loja generalista agro que também vende a linha DJI Agras -- 21317 URLs no
      catálogo, 33 batem no filtro. Validado com spider real (2/2 produtos). Rodada completa
      disparada em background
- [x] **lojaododrone.com.br mapeado** — plataforma própria (não awsli/Magento), robots.txt
      permissivo. Sitemap simples mistura páginas institucionais com produtos em `/p/<slug>` --
      `filtro: ["/p/"]` restringe só aos produtos. Loja especializada em drone agrícola: DJI Agras
      **e também XAG** (concorrente chinesa da DJI nesse nicho, não vista em nenhum site anterior)
      -- 275 produtos, catálogo inteiro relevante, sem filtro de marca. JSON-LD limpo, sem seletor
      CSS novo. Validado com spider real (2/2 produtos). Rodada completa disparada em background
- [x] **realtrator.com.br mapeado** — volta ao tema trator/CNH (sugestão do usuário: filtrar por
      New Holland e Case IH). robots.txt tem `Disallow: /produto/`, mas as URLs de produto reais
      não usam esse prefixo (`/pecas-para-X/<slug>`) -- não afetado, `ROBOTSTXT_OBEY` permite
      normal. Catálogo enorme: 6482 URLs (13 páginas de sitemap), generalista multi-marca (Massey
      Ferguson, JCB, Valtra, Case, New Holland...) -- 1367 batem no filtro `[case, new-holland,
      newholland, cnh]`. Microdata pronta, sem seletor CSS. Validado com spider real (2/2
      produtos). Rodada grande disparada em background (~3h no delay padrão do scrapy)
- [x] Rodar `newpecasoficial` completo (179 produtos, antes só tinha os 10 do teste inicial) —
      rodado com sucesso via `sync_site.py --site newpecasoficial`
- [x] **Extração de SKU nos 9 sites não-VTEX** (agrotrator/fornecedoraagro/fornecedoramaquinas/
      pitstop/carpaltratores via VTEX já tinham SKU; os outros 9 estavam com a coluna vazia).
      Investigação achou o mesmo padrão de bug das duas vezes anteriores: o campo já vem pronto
      no JSON-LD/microdata de todos os 9 sites (`sku`, `mpn` ou `gtin13`, a depender do site) —
      `_parse_produto_jsonld`/`_from_microdata` em `crawler/extractors/structured.py` simplesmente
      não liam esse campo. Corrigido com `_extrair_sku()` (prioridade sku > mpn > gtin > productID)
      chamado nas duas cascatas; 4 testes de regressão novos em `tests/test_structured.py` (31
      testes no total, todos passando). **Não precisou de seletor CSS nem regex por site** —
      dado já estruturado em 100% dos casos testados (tratorlin, acamargo, tratormag, jerdrones,
      prosperadistribuicao, engepecas, newpecasoficial, superagrosc, paccini)
- [x] Rodar de novo os 9 sites (tratorlin, acamargo, superagrosc, tratormag, jerdrones,
      prosperadistribuicao, newpecasoficial, engepecas, paccini) pra backfill do SKU. 7 de 9
      ficaram com 100% de cobertura de SKU nos registros novos; `tratorlin` ficou parcial (46%
      -- 1443/3111, provavelmente parte do catálogo real mesmo sem SKU no dado estruturado, não
      parece bug); `paccini` sem SKU em nenhum registro (esse site nunca teve SKU no `ItemList`
      JSON-LD, não é regressão de hoje). Registros antigos (antes de hoje) continuam com `sku`
      vazio -- é esperado, a correção só vale daqui pra frente
- [x] **`sku` capturado nos sites VTEX não é o código de peça do fabricante** -- descoberto ao
      tentar bater `precos.sku` com `dm_parts.cd_part_number` no Power BI (só 2,4% batia).
      Investigação: (1) `_extrair_sku()` descartava o campo `mpn` sempre que `sku` já existia --
      corrigido pra capturar os dois como campos SEPARADOS (`sku` e `mpn` novos em
      `crawler/extractors/structured.py`/`items.py`/`db/models.py`); (2) mesmo com `mpn`
      separado, validação contra a lista mestre de peças do usuário (`db/list (4).csv`, 220.851
      códigos) mostrou que nos sites VTEX (agrotrator, carpaltratores, fornecedoramaquinas,
      fornecedoraagro) **nem sku nem mpn têm o código real** -- ele só existe como texto livre
      no nome do produto (ex: "Silenciador ... New Holland 47699390 CNH" -> código é
      "47699390"). Criada coluna nova `codigo_peca` (não sobrescreve `mpn`, que é o valor cru
      declarado pelo site, de origem/confiabilidade diferente) com heurística em
      `scripts/sync_vtex_brand.py` (`_extrair_codigo_peca`): pega o último token do nome que
      parece código (alfanumérico, 4+ chars, com dígito). Validado contra a lista mestre: 78,9%
      agrotrator, 91,4% carpaltratores, 73,3% fornecedoramaquinas, 71,2% fornecedoraagro (pitstop
      só 0,8% -- esse site não embute o código no nome de forma confiável). Backfill rodado nos
      47.315 registros já coletados desses 5 sites via `scripts/backfill_codigo_peca.py` (sem
      re-crawlear, o código já vinha do texto salvo) -- 46.376 atualizados. 7 testes de regressão
      novos em `tests/test_sync_vtex_brand.py` (47 testes no total)
- [x] **Rodada "do zero" completa** (31/07 a 02/08) — os 22 sites de `config/sites.yaml` rodados
      em sequência (batch manual via shell, não Kestra ainda), ~40k+ registros novos no total.
      Achado operacional: a máquina local sofreu vários hiatos de horas (suspensão/hibernação
      do Windows durante a madrugada) que pausaram os crawls por até ~7h de cada vez -- na
      maioria das vezes o processo sobreviveu e retomou sozinho ao acordar, mas uma vez o
      processo morreu de vez (lock travado, precisou matar+limpar+reiniciar manualmente). Reforça
      a prioridade da Fase 1 (VPS), que não teria esse problema. `tratorlin` foi movido pro fim
      da fila a pedido do usuário (catálogo grande, historicamente o mais lento/instável).
- [x] **dronesense.com.br mapeado** — site Astro (SSG), HTML pré-renderizado com JSON-LD Product
      completo, sku legível de verdade (ex: "DJI-AGRAS-T25P", não ID interno opaco). Catálogo
      pequeno de propósito: só 6 páginas de produto (`filtro: ["/drones-agricolas/"]` sobre um
      sitemap de 747 URLs, maioria blog/calendário agrícola). 3 modelos ativos com preço público
      (T25P R$110k, T70P R$180k, T100 R$225k) + 3 gerações antigas descontinuadas sem preço
      (OutOfStock, ignoradas normalmente pelo spider). Sem catálogo de peças avulsas à venda.
- [x] **fontanatratorpecas.com.br mapeado** — plataforma Magazord (React no front, mas SSR/
      pré-renderizado: JSON-LD completo direto no HTML, sem precisar Playwright nem seletor CSS
      apesar da dica inicial do usuário sobre a classe do sku). Loja generalista de peças
      agrícolas (não só CNH -- também Valtra/Valmet, Jacto, Kuhn), 1826 produtos, sem filtro de
      marca. Mesmo padrão dos sites VTEX: `sku` do JSON-LD é ID interno da loja, código real do
      fabricante só existe no texto do nome -- não estendida a heurística `_extrair_codigo_peca`
      pra esse site ainda (só pedido/feito pro fluxo VTEX até agora).
- [x] **engepecas.com.br removido** — ver "Sites bloqueados fora das fases" (não era bloqueio
      deliberado, só 503 pontual no dia; config antiga preservada no histórico do git)
- [ ] Rodar por alguns dias (já na VPS, via Kestra) e conferir se o histórico está sendo gravado como esperado (série temporal, sem sobrescrita)
- [x] Relatório de URLs "quebradas" — `crawler/relatorio_falhas.py`, grava
      `logs/urls_quebradas/<site>.json` (URLs sem preço ou com erro de rede na última rodada,
      sobrescreve por site). Ligado no spider (`price_spider.py`) e no `sync_html_bulk.py`

## Fase 3 — Dashboard visual
- [x] **Versão funcional inicial pronta** (antes do design final, pra já ter algo visível):
      `scripts/gerar_dashboard.py` + `scripts/dashboard_template.html` → gera
      `dashboard/index.html` (self-contained, sem servidor) a partir do banco (hoje SQLite,
      troca pro Postgres só mudando `PRICE_DB_URL` quando migrar). Tem: tiles de resumo
      (produtos/lojas/registros/última coleta), tabela com busca+filtro por loja+ordenação+
      paginação (18.802 produtos, testado com Playwright sem erro de console), e ao clicar
      numa linha abre um gráfico de histórico de preço (SVG, com crosshair+tooltip no hover,
      seguindo a skill de dataviz). Achou e corrigiu 2 bugs reais de CSS: (1) o modal não
      herdava as variáveis de cor (estava fora da `.viz-root` no HTML) e (2) modo escuro
      ficava todo preto/ilegível porque as variáveis estavam escopadas em `.viz-root` em vez
      de `:root` — `body` (ancestral) não enxerga variável definida num descendente. Corrigido
      e validado com Playwright nos dois modos (claro/escuro), sem erro de console
- [ ] Você leva o prompt (já combinado) pra uma IA de design e traz o resultado (imagens/protótipo) — pra refinar o visual da versão funcional acima
- [ ] Rodar `scripts/gerar_dashboard.py` de novo depois que migrar pro Postgres (Fase 0/1)
- [ ] Tabela/view de "preço atual" separada do histórico completo — hoje o script já calcula isso em Python a cada geração; considerar uma view materializada no Postgres se ficar lento com mais dados
- [x] Export CSV sob demanda — `scripts/exportar_csv.py`, exporta todo o histórico de coletas
      (`db/precos.csv` por padrão, `--saida` pra outro caminho). Motivação real: testar consumo
      via Power BI sem precisar de driver ODBC pra SQLite -- CSV/Excel tem conector nativo de
      pasta (inclusive SharePoint/OneDrive), muito mais simples que ODBC + Gateway pessoal

## Fase 4 — Acesso remoto ao dashboard (opcional, via Cloudflare Pages)
- [ ] Publicar o dashboard em **Cloudflare Pages** (estático ou com Pages Functions), conectando direto no Postgres da VPS
- Observação: o crawler (Scrapy/Twisted) e o Kestra continuam rodando só na VPS — Cloudflare Workers/Pages não roda nenhum dos dois (é só função sem estado, não serve pra processo contínuo). O Cloudflare aqui é só pra hospedar a interface visual, se quiser acessar de fora sem VPN/túnel.

## Fase 5 — Monitoramento
Com o Kestra (Fase 1), a parte de "rodou ou não rodou" já vem de graça — a tela dele mostra
histórico de execução por site, sucesso/falha, duração. O que falta é o que é específico do
negócio (preço), que o Kestra não faz sozinho:
- [ ] Alerta simples (e-mail/webhook) quando um preço cair X% ou produto ficar `OutOfStock`
- (Alternativa mais leve, se decidir não seguir com Kestra: healthchecks.io/Cronitor pra saber "rodou ou não rodou" sem precisar hospedar nada)

## Fase 6 — Sites que só mostram preço via JavaScript (Playwright) — fazer por último
Site de exemplo: **rohrmaquinas.com.br** (plataforma "NEO"/jet-neo, front-end Angular).
Motivo de deixar por último: mais lento e incerto que os outros métodos (VTEX API, WooCommerce
JSON-LD) — cada página precisa de navegador headless renderizando JS, não é só uma chamada HTTP.
- [ ] Confirmar (teste rápido) se a página de busca/categoria já lista preço+nome+sku de vários
      produtos de uma vez, ou se cada produto individual precisa ser aberto separadamente
      (isso muda o tempo de coleta de minutos pra possivelmente horas, em milhares de produtos)
- [ ] Adicionar `scrapy-playwright` (ou script standalone com `playwright` puro) só pra domínios
      marcados como "precisa JS" — não mexe nos sites que já funcionam via HTTP puro
- [ ] Ler os dados via `window.dataLayer` (o site já monta isso em JS pro Google Analytics, com
      nome/preço/marca/categoria prontos) em vez de tentar seletor CSS na tela renderizada
- [ ] Site também categoriza por marca **CNH** (mesmo filtro usado no agrotrator) — bom ponto de
      partida quando for a vez de implementar

## Fase 7 — Mercado Livre — bloqueado por enquanto
Investigado em 2026-07-22: dois caminhos tentados, os dois batem numa barreira colocada de
propósito pela plataforma (diferente dos outros sites, onde era só ajuste técnico).
- **API oficial**: registramos app (`monitor-preço-interno`, Client Credentials, só leitura) e
  autenticação funciona (token OK, `/users/me` e `/sites/MLB/categories` respondem). Mas todo
  endpoint de busca/descoberta (`/sites/MLB/search`, `/users/search?nickname=`) devolve 403 —
  a ML restringe isso a aplicativos **certificados**, e o nosso está "não certificado" (padrão
  pra apps novos).
- **Ler HTML direto**: a página de listagem devolve uma página de verificação anti-bot
  (`suspicious-traffic-frontend` no HTML) já na primeira tentativa, sem navegador/sessão real.
- [ ] (Opcional, mais lento) Solicitar certificação do app junto ao suporte de
      desenvolvedores do ML, explicando o uso (monitoramento de preço interno) — sem garantia
      de aprovação pra esse tipo de caso de uso
- Decisão: não vamos tentar contornar o bloqueio anti-bot (proxy, navegador disfarçado, etc.) —
  ao contrário do rohrmaquinas, aqui a plataforma está ativamente barrando de propósito.
- Credenciais já ficaram salvas em `.env` (`ML_CLIENT_ID`/`ML_CLIENT_SECRET`) caso a certificação
  seja aprovada no futuro.

## Sites pendentes para investigar
(nenhum no momento -- agripecas.net mapeado, ver Fase 2)

## Sites bloqueados fora das fases (não perseguir)
- **usaparts.com.br** — preço só visível com login (B2B), fora de escopo pra scraping público
- **msequipamentos.com.br** — desafio ativo Cloudflare ("Just a moment...") bloqueando até a
  home e o robots.txt sem navegador real; barreira deliberada, não perseguir
- **engepecas.com.br** — removido de `config/sites.yaml` e do trigger no Kestra (02/08) a
  pedido do usuário depois que a última rodada falhou com 503 (site fora do ar na hora do
  request ao sitemap, não é bloqueio nem bug nosso). Não é caso de bot-block deliberado como
  os outros dois acima -- se quiser remapear no futuro, é só reaproveitar a config antiga
  (`metodo: html_bulk`, `filtro: [case, cnh, new-holland]`, ver histórico do git).

## Backlog (não priorizado)
- Proxy/rotação de IP — só se algum site começar a bloquear por IP fixo da VPS; não adiantar agora, é over-engineering enquanto não há sinal de bloqueio.

---

Próximo passo sugerido: terminar a **Fase 0** (hardening local) antes de provisionar a VPS com as specs novas (2vCPU/4GB) e montar o Docker Compose da Fase 1. Me avisa quando quiser que eu implemente algum item específico.
