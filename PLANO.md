# Plano — Price Crawler (produção + dashboard)

Status geral: em revisão conjunta, fase por fase. Nada é implementado até combinarmos aqui.

## VPS sugerida
**Hostinger (plano VPS/KVM)** — specs mínimas: 1 vCPU / 1-2GB RAM já atendem (o crawler é leve, roda por lote e não fica em memória o tempo todo). Ubuntu LTS como SO. Só confirmar que é o plano **VPS** (SSH root), não hospedagem compartilhada — é isso que garante rodar cron + Python do jeito que o projeto precisa.
Alternativa: Hostgator VPS, specs parecidas, geralmente um pouco mais caro pro mesmo hardware no Brasil.

---

## Fase 0 — Hardening local (antes de subir)
Deixar o crawler robusto para rodar sem supervisão.
- [ ] Migrar de SQLite para **Supabase (Postgres)**: criar projeto free no Supabase, instalar `psycopg2`, trocar `PRICE_DB_URL` para a connection string do Postgres (o código já usa SQLAlchemy, então a mudança é só configuração + `init_db` criando a tabela `coletas` lá)
- [ ] Log em arquivo com rotação (não só stdout) — `logging` + `RotatingFileHandler` ou redirecionamento no cron com `logrotate`
- [ ] Trava contra execução sobreposta (lockfile) — evitar que um `--lote` rodando ainda quando o próximo cron dispara
- [ ] Fixar versões no `requirements.txt` (trocar `>=` por `==` depois de validar)
- [ ] Backup periódico dos dados (o free tier do Supabase não tem backup automático/PITR — vale um `pg_dump` agendado, mesmo que simples)
- [ ] Testes unitários pros extractors (`_to_float`, cascata JSON-LD/OG/microdata) — a lógica de parsing pt-BR vs en-US (`1.234,56` vs `1,234.56`) é sutil e um bug ali corrompe dado silenciosamente sem ninguém perceber

## Fase 1 — Deploy na VPS
- [ ] Provisionar VPS (Hostinger), Ubuntu LTS, usuário não-root para rodar o crawler
- [ ] **Docker** em vez de venv puro: encapsula as versões fixas da Fase 0, facilita atualizar/recriar o ambiente sem "quebrar" o servidor (troca simplicidade imediata por uma camada a mais pra aprender/manter)
- [ ] Clonar/copiar projeto para a VPS
- [ ] Configurar cron (você já domina) chamando `run.py --lote N` nos horários definidos (dentro do container, se for Docker)
- [ ] Validar timezone do servidor (pra bater com o horário desejado nas coletas)
- [ ] Testar uma coleta manual na VPS antes de deixar no cron

## Fase 2 — Popular dados reais
- [ ] Preencher `urls.txt` com os produtos/concorrentes reais
- [ ] Rodar `--lote` pequeno primeiro (ex: 5) e conferir no banco se os campos vieram certos
- [ ] Mapear os poucos sites que não expõem JSON-LD/OG/microdata e preencher `config/selectors.yaml` para eles
- [ ] Rodar por alguns dias e conferir se o histórico está sendo gravado como esperado (série temporal, sem sobrescrita)
- [ ] Relatório de URLs "quebradas": hoje quando não acha preço só loga um warning e descarta — consolidar numa lista/arquivo das URLs que falharam na última rodada, pra saber quando um site mudou o layout e precisa de novo seletor CSS

## Fase 3 — Dashboard visual
- [ ] Você leva o prompt (já combinado) pra uma IA de design e traz o resultado (imagens/protótipo)
- [ ] Decidir stack de implementação com base no design:
  - Relatório HTML estático (mais simples, sem servidor) — gerado por script que lê o SQLite
  - Streamlit (mais interativo, mas precisa de processo rodando)
- [ ] Implementar o dashboard em cima do Supabase (conexão direta, sem precisar de cópia/sincronização local)
- [ ] Tabela/view de "preço atual" separada do histórico completo — hoje toda consulta de "preço agora" precisa pegar o último registro por URL; uma view materializada facilita o dashboard
- [ ] Export CSV sob demanda, útil pra jogar num Excel/Sheets rápido sem passar pelo dashboard

## Fase 4 — Acesso remoto ao dashboard (opcional, via Cloudflare Pages)
Com o banco já no Supabase (Fase 0), isso fica bem mais simples: não precisa mais sincronizar nada.
- [ ] Publicar o dashboard em **Cloudflare Pages** (estático ou com Pages Functions), conectando direto no Supabase
- Observação: o crawler em si (Scrapy/Twisted) continua rodando só na VPS — Cloudflare Workers não roda Scrapy. O Supabase já resolve o acesso remoto ao dado; o Cloudflare aqui é só pra hospedar a interface visual, se quiser.

## Fase 5 — Monitoramento (opcional, futuro)
- [ ] Alerta de coleta parada (ex: nenhum registro novo há 2 dias) — priorizar isso antes dos alertas de preço, porque "o crawler morreu silenciosamente" é o pior cenário numa VPS sem supervisão visual
- [ ] Alerta simples (e-mail/webhook) quando um preço cair X% ou produto ficar `OutOfStock`

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

## Backlog (não priorizado)
- Proxy/rotação de IP — só se algum site começar a bloquear por IP fixo da VPS; não adiantar agora, é over-engineering enquanto não há sinal de bloqueio.

---

Próximo passo sugerido: começar pela **Fase 0** (hardening) antes de subir pra VPS. Me avisa quando quiser que eu implemente algum item específico.
