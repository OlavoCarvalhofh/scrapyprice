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
- [ ] Migrar de SQLite para **Postgres self-hosted na própria VPS** (decidido: não vamos usar Supabase) — instalar `psycopg2`, trocar `PRICE_DB_URL` para a connection string do Postgres local (o código já usa SQLAlchemy, então a mudança é só configuração + `init_db` criando a tabela `coletas` lá)
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
      documentando as variáveis. Ainda não testado subindo de verdade (falta Docker Desktop
      rodando aqui, ou testar direto na VPS)
- [ ] Acessar a interface do Kestra (porta 8080) só via **túnel SSH** — não expor direto pra internet sem autenticação na frente
- [ ] Criar os **flows YAML** no Kestra — um por site (ou um flow com tarefas paralelas), cada um chamando `python scripts/sync_site.py --site <nome>` dentro do container do crawler, com gatilho de agendamento (substitui o cron)
- [ ] Validar timezone do servidor (pra bater com o horário desejado nas coletas)
- [ ] Testar uma coleta manual (via Kestra, disparo manual do flow) antes de deixar no agendamento automático

## Fase 2 — Popular dados reais
- [x] Sites mapeados e configurados em `config/sites.yaml` (14 lojas já rodadas pelo menos uma vez: agrotrator, fornecedoramaquinas, fornecedoraagro, carpaltratores, pitstop, tratorlin, acamargo, superagrosc, tratormag, jerdrones, prosperadistribuicao, newpecasoficial, engepecas, paccini)
- [ ] Rodar `newpecasoficial` completo (179 produtos) — hoje só tem os 10 do teste inicial
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
- [ ] Rodar de novo os 9 sites acima pra backfill do SKU nos registros já coletados (a correção
      só vale pra coletas novas — os registros antigos ficam com `sku` vazio até rodar de novo)
- [ ] Rodar por alguns dias (já na VPS, via Kestra) e conferir se o histórico está sendo gravado como esperado (série temporal, sem sobrescrita)
- [ ] Relatório de URLs "quebradas": hoje quando não acha preço só loga um warning e descarta — consolidar numa lista/arquivo das URLs que falharam na última rodada, pra saber quando um site mudou o layout e precisa de novo seletor CSS

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
- [ ] Export CSV sob demanda, útil pra jogar num Excel/Sheets rápido sem passar pelo dashboard

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
- **agripecas.net** — plataforma "Loja Integrada" (ainda não testada nesse projeto), sitemap em
  https://www.agripecas.net/sitemap.xml — investigar quando retomar mapeamento de sites

## Sites bloqueados fora das fases (não perseguir)
- **usaparts.com.br** — preço só visível com login (B2B), fora de escopo pra scraping público
- **msequipamentos.com.br** — desafio ativo Cloudflare ("Just a moment...") bloqueando até a
  home e o robots.txt sem navegador real; barreira deliberada, não perseguir

## Backlog (não priorizado)
- Proxy/rotação de IP — só se algum site começar a bloquear por IP fixo da VPS; não adiantar agora, é over-engineering enquanto não há sinal de bloqueio.

---

Próximo passo sugerido: terminar a **Fase 0** (hardening local) antes de provisionar a VPS com as specs novas (2vCPU/4GB) e montar o Docker Compose da Fase 1. Me avisa quando quiser que eu implemente algum item específico.
