# VMS Backend — Plano Completo até 100%

> Baseado em `plan.md` + `docs/architecture_final.md` + audit do codebase.
> Analytics e Frontend são as últimas fases.

---

## Estado Atual (audit 2026-03-15)

### ✅ Completo
- Django Core API (users, cameras, events, recordings, agents, webhooks, notifications)
- FastAPI async services (webhooks, SSE, ISAPI listener, streaming token verify)
- Agent service local (config poll, ffmpeg streams, heartbeat, graceful shutdown)
- MediaMTX configurado (RTSP, RTMP, HLS, WebRTC, recording 60s segments, hooks)
- Notifications app (NotificationRule, NotificationLog, consumers, webhook dispatch)
- Celery Beat (health check 5min, storage quota 1h, cleanup 1h)
- Docker Compose completo (9 services + nginx)
- Event bus RabbitMQ (topic exchange `vms_events`)
- Redis pubsub (SSE realtime)
- E2E tests (camera flow, event API)

### 🟡 Parcial
- Event normalizers — Hikvision iniciado mas incompleto, Intelbras ausente
- BDD tests — features escritas (16 cenários câmeras, 2 eventos), mas `test_camera_steps.py` só tem `@given`, faltam `@when` e `@then`
- ALPR deduplicação — mencionada no plan.md (Phase 3.3) mas não implementada

### 🔴 Não implementado
- Security hardening (rate limiting, headers, HMAC) — plan.md Phase 5
- Django health check endpoint (`/api/v1/health/`)
- Structured logging (JSON) para produção
- Backup strategy — plan.md Phase 6
- Analytics framework (process_frame_task é stub) — **ÚLTIMA FASE**

---

## Fase 1 — Event Normalizers

**Objetivo:** Normalizar payloads ALPR de diferentes fabricantes para formato único.

### Tarefas

1. **Completar normalizer Hikvision ALPR**
   - Arquivo: `core/apps/events/normalizers.py`
   - Parsing do XML `EventNotificationAlert > ANPR`
   - Retornar `ALPRDetectionInput` padronizado

2. **Adicionar normalizer Intelbras ALPR**
   - Mesmo arquivo
   - Formato JSON da Intelbras (ITSCAM/VIP)
   - Retornar `ALPRDetectionInput` padronizado

3. **Adicionar normalizer genérico (fallback)**
   - Para câmeras que enviam JSON simples `{plate, confidence, timestamp}`

4. **Testes dos normalizers**
   - Novo: `core/apps/events/tests/test_normalizers.py`
   - Testar cada fabricante + fallback + payload inválido + manufacturer desconhecido → `UnsupportedManufacturerError`

### Arquivos
- `core/apps/events/normalizers.py` (editar)
- `core/apps/events/tests/test_normalizers.py` (criar)

### Verificação
- `pytest core/apps/events/tests/test_normalizers.py -v` → todos passam

---

## Fase 2 — ALPR Deduplicação

**Objetivo:** Evitar múltiplos eventos para mesma placa em sequência rápida (câmera lê mesma placa 5x em 10s → 1 evento). Conforme plan.md Phase 3.3.

### Tarefas

1. **Implementar deduplicação por Redis**
   - Em `core/apps/events/services.py` dentro de `process_alpr_detection()`
   - Key: `alpr:dedup:{camera_id}:{plate}` com TTL configurável (default 60s)
   - Se key existe → ignorar (return None)
   - Se não existe → processar e criar key

2. **Configuração do TTL**
   - Setting `ALPR_DEDUP_TTL_SECONDS = 60` em `settings/base.py`

3. **Testes**
   - Novo: `core/apps/events/tests/test_alpr_dedup.py`
   - Primeiro evento → grava
   - Segundo idêntico em <60s → ignorado
   - Evento após TTL → grava novamente
   - Placa diferente, mesma câmera → grava
   - Mesma placa, câmera diferente → grava

### Arquivos
- `core/apps/events/services.py` (editar)
- `core/config/settings/base.py` (adicionar setting)
- `core/apps/events/tests/test_alpr_dedup.py` (criar)

### Verificação
- `pytest core/apps/events/tests/test_alpr_dedup.py -v` → todos passam

---

## Fase 3 — Security Hardening

**Objetivo:** Produção-ready. Conforme plan.md Phase 5.

### Tarefas

1. **Rate limiting em webhooks e auth**
   - Django: `throttle_classes` do DRF em auth views (5/min anonimo, 60/min autenticado)
   - FastAPI: `slowapi` em `/webhooks/*` (100/min por IP)

2. **Security headers via Nginx**
   - Arquivo: `infra/nginx/nginx.conf`
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
   - `X-Frame-Options: DENY`
   - `X-Content-Type-Options: nosniff`
   - `Content-Security-Policy: default-src 'self'`
   - `Referrer-Policy: strict-origin-when-cross-origin`

3. **Webhook HMAC signature (saída)**
   - Em `workers/tasks/notifications.py` no `send_webhook_notification`
   - Header `X-VMS-Signature` com HMAC-SHA256 usando secret do tenant
   - Adicionar campo `webhook_secret` no model `NotificationRule`

4. **Testes**
   - Testar rate limiting (request acima do limite → 429)
   - Testar HMAC signature no webhook (payload + secret → signature válida)

### Arquivos
- `infra/nginx/nginx.conf` (editar)
- `core/apps/notifications/models.py` (adicionar `webhook_secret`)
- `workers/tasks/notifications.py` (editar `send_webhook_notification`)
- `async_services/main.py` (adicionar slowapi middleware)
- Testes novos

### Verificação
- Headers presentes em `curl -I http://localhost/api/v1/cameras/`
- Rate limit funciona em `/webhooks/alpr`
- Webhook enviado inclui header `X-VMS-Signature`

---

## Fase 4 — Testes BDD & Cobertura

**Objetivo:** Completar step definitions BDD, adicionar testes de integração, cobertura >80%.

### Tarefas

1. **Completar BDD camera steps**
   - Arquivo: `core/tests/bdd/step_defs/test_camera_steps.py`
   - Implementar todos os `@when` (create, update, delete camera com parâmetros)
   - Implementar todos os `@then` (assertions de status, lista, MediaMTX path, eventos)
   - Mockar MediaMTX client nos testes

2. **Criar feature BDD para notifications**
   - Feature: `core/tests/bdd/features/notification_rules.feature`
   - Cenários: criar regra webhook, evento dispara notificação, regra inativa ignora
   - Steps: `core/tests/bdd/step_defs/test_notification_steps.py`

3. **Criar feature BDD para agent**
   - Feature: `core/tests/bdd/features/agent_management.feature`
   - Cenários: provisionar agent, poll config retorna câmeras, heartbeat atualiza status
   - Steps: `core/tests/bdd/step_defs/test_agent_steps.py`

4. **Teste de integração: ALPR → Event → Notification**
   - Postar webhook ALPR → verificar Event criado → verificar NotificationLog gerado
   - Arquivo: `core/tests/e2e/test_alpr_notification_flow.py`

5. **Coverage report**
   - `make test-cov` → analisar gaps → adicionar testes onde necessário
   - Target: >80% em todos os apps

### Verificação
- `make test-bdd` → todos os cenários verdes
- `make test-cov` → cobertura >80%

---

## Fase 5 — Infraestrutura & Observabilidade

**Objetivo:** Monitoring básico e resiliência. Conforme plan.md Phase 6.

### Tarefas

1. **Django health check endpoint**
   - `GET /api/v1/health/` → checa DB + Redis + RabbitMQ
   - Response: `{"status": "healthy", "services": {"db": "ok", "redis": "ok", "rabbitmq": "ok"}}`
   - Sem autenticação (usado por load balancers)

2. **Structured logging (JSON)**
   - Configurar `LOGGING` em `settings/prod.py` com JSON formatter
   - Usar `python-json-logger` ou `structlog`
   - Todos os serviços (Django, FastAPI, Celery) logam em JSON em produção

3. **Backup PostgreSQL script**
   - Arquivo: `infra/scripts/backup_db.sh`
   - `pg_dump` comprimido com timestamp
   - Pode ser agendado via cron ou Celery Beat

4. **Documentar política de recordings**
   - Retention automática via `cleanup_task` já existe
   - Documentar que backup de recordings é responsabilidade do operador

### Arquivos
- `core/apps/health/` ou rota direta em `config/urls.py` (criar)
- `core/config/settings/prod.py` (editar logging)
- `infra/scripts/backup_db.sh` (criar)

### Verificação
- `curl http://localhost/api/v1/health/` → 200 + JSON
- Logs em JSON quando `DJANGO_SETTINGS_MODULE=config.settings.prod`

---

## Fase 6 — Documentação

**Objetivo:** Qualquer dev consegue subir, entender e contribuir.

### Tarefas

1. **Atualizar CLAUDE.md**
   - Lições aprendidas reais (MediaMTX grava sozinho, agent usa polling, etc.)
   - Decisões técnicas tomadas (HMAC em webhooks, ALPR dedup por Redis)

2. **Atualizar docs/API_DOCUMENTATION.md**
   - Endpoints de notifications (rules CRUD + history)
   - Endpoints de agents/me/*
   - Exemplos com curl

3. **Atualizar docs/deploy.md**
   - Checklist produção: .env, SSL, DNS, backup, monitoring
   - Como instalar agent no cliente

4. **Criar docs/plugins.md**
   - Como criar um plugin (pasta + plugin.py + herdar AnalyticsPlugin)
   - Exemplo completo de plugin "people_count"

### Verificação
- Dev novo consegue seguir README → `make up` → sistema rodando

---

## Fase 7 — Analytics Framework (PENÚLTIMA)

**Objetivo:** Task `process_frame` carrega plugin real, executa, publica resultado.

### Problema de Deploy
Worker Celery usa imagem `./core`, monta `./core:/app`. Os arquivos em `workers/tasks/` e `plugins/` NÃO ficam acessíveis. `celery.py` só autodiscovers: `apps.cameras`, `apps.events`, `apps.recordings`.

### Problema Async/Sync
`AnalyticsPlugin.process_frame()` é `async` mas Celery tasks são síncronas → `asyncio.run()`.

### Tarefas

1. **Resolver acessibilidade da task**
   - Opção A: Montar `./workers:/app/workers` + `./plugins:/app/plugins` no docker-compose worker + adicionar `workers.tasks` ao autodiscover
   - Opção B: Mover task para `core/apps/events/tasks.py` (já tem tasks analytics lá)
   - **Decisão na hora da implementação**

2. **Implementar process_frame_task**
   - Singleton cache de plugins (discover uma vez, reuse)
   - Buscar plugin por nome
   - `asyncio.run(plugin.process_frame(frame, metadata))`
   - Se resultado != None: `publish_event("analytics.{plugin_name}", {...})`
   - Plugin não encontrado → log error, return None
   - Plugin crashar → log exception, return None

3. **Testes**
   - `test_process_frame_loads_plugin_and_calls`
   - `test_process_frame_publishes_result_when_detected`
   - `test_process_frame_returns_none_when_nothing_detected`
   - `test_process_frame_unknown_plugin_returns_none`
   - `test_process_frame_plugin_exception_handled`
   - `test_plugins_are_cached_after_first_discovery`

4. **Wiring — Celery autodiscover update**
   - Atualizar `celery.py` autodiscover
   - Atualizar `docker-compose.yml` volumes se necessário

### Arquivos
- `workers/tasks/analytics.py` — task to implement
- `plugins/__init__.py` — discover_plugins() already working
- `plugins/base.py` — AnalyticsPlugin ABC
- `core/config/celery.py` — needs autodiscover update
- `docker-compose.yml` — needs volume mounts
- `core/shared/event_bus.py` — publish_event()

### Verificação
- `make test` → todos passam
- Celery worker registra `analytics.process_frame`
- Task com stub plugin → returns None (no crash)
- Task com mock plugin → resultado publicado no event bus

---

## Fase 8 — Frontend / UI/UX (ÚLTIMA)

> Só começa quando backend está 100%.
> Plano detalhado será criado separadamente.

---

## Ordem de Execução

```
Fase 1  Event Normalizers         ██░░░░░░░░  (Hikvision, Intelbras, genérico)
Fase 2  ALPR Deduplicação         █░░░░░░░░░  (Redis SET + TTL)
Fase 3  Security Hardening        ███░░░░░░░  (rate limit, headers, HMAC)
Fase 4  Testes BDD & Cobertura    ████░░░░░░  (steps, features, integração, >80%)
Fase 5  Infra & Observabilidade   ██░░░░░░░░  (health, logging, backup)
Fase 6  Documentação              ██░░░░░░░░  (CLAUDE.md, API docs, deploy, plugins)
Fase 7  Analytics Framework       ███░░░░░░░  (process_frame real + testes)
Fase 8  Frontend                  ██████████  (após backend 100%)
```
