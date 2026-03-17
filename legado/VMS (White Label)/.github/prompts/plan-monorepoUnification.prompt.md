# VMS Monorepo — Plano de Unificação Completo

> **Projeto**: Unificar VMS White Label (analytics + multi-tenant) + VMS (event-driven + MediaMTX webhooks)  
> **Data**: Março 2026  
> **Meta**: Um monorepo `vms/` completo com gravação nativa MediaMTX, status instantâneo via webhooks, e analytics GPU reconstruídos do zero.

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Decisões Arquiteturais](#2-decisões-arquiteturais)
3. [Diagnóstico: O Que Está Ruim](#3-diagnóstico-o-que-está-ruim)
4. [Estrutura Final do Monorepo](#4-estrutura-final-do-monorepo)
5. [Fase 0 — Scaffolding](#fase-0--scaffolding)
6. [Fase 1 — Backend Django Merge](#fase-1--backend-django-merge)
7. [Fase 2 — MediaMTX Event-Driven](#fase-2--mediamtx-event-driven)
8. [Fase 3 — Async Services (FastAPI)](#fase-3--async-services-fastapi)
9. [Fase 4 — Frame Grabber (Reescrito)](#fase-4--frame-grabber-reescrito)
10. [Fase 5 — Frontend Merge](#fase-5--frontend-merge)
11. [Fase 6 — Infrastructure & Docker Compose](#fase-6--infrastructure--docker-compose)
12. [Fase 7 — Agent Remoto](#fase-7--agent-remoto)
13. [Fase 8 — Analytics: LPR (Primeiro Worker GPU)](#fase-8--analytics-lpr-primeiro-worker-gpu)
14. [Fase 9 — Analytics: Object Detection + Intrusion](#fase-9--analytics-object-detection--intrusion)
15. [Fase 10 — Analytics: Crowd + Queue](#fase-10--analytics-crowd--queue)
16. [Fase 11 — Analytics: Traffic (Line Crossing)](#fase-11--analytics-traffic-line-crossing)
17. [Fase 12 — Analytics: Loitering + Abandoned Object](#fase-12--analytics-loitering--abandoned-object)
18. [Fase 13 — Analytics: Facial Recognition](#fase-13--analytics-facial-recognition)
19. [Fase 14 — Analytics: Heatmap](#fase-14--analytics-heatmap)
20. [Fase 15 — Plugin Framework](#fase-15--plugin-framework)
21. [Fase 16 — Testing & Cleanup Final](#fase-16--testing--cleanup-final)
22. [Checklist Global](#checklist-global)

---

## 1. Visão Geral

```
┌─────────────────────────────────────────────────────────┐
│                    VMS UNIFICADO                        │
│                                                         │
│  VMS (event-driven)          White Label (analytics)    │
│  ├── MediaMTX webhooks       ├── 12 tipos de analytics  │
│  ├── SSE real-time           ├── GPU workers (CUDA)     │
│  ├── ISAPI listener          ├── ROI poligonal          │
│  ├── Agent remoto            ├── Multi-tenant + RBAC    │
│  ├── Gravação nativa         ├── Resellers/Licenses     │
│  ├── ALPR vendor webhooks    ├── ByteTrack tracking     │
│  └── Notifications/webhooks  └── StoragePolicy tiered   │
│                                                         │
│  ══════════════════════════════════════════════════════  │
│                    RESULTADO                            │
│  ├── Detecção de status instantânea (webhook, não poll) │
│  ├── Gravação nativa MediaMTX (sem recorder-worker)     │
│  ├── Analytics GPU reconstruídos 1-por-1 (limpos)       │
│  ├── SSE + WebSocket real-time                          │
│  ├── Multi-tenant + White Label                         │
│  └── Plugin framework extensível                        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Decisões Arquiteturais

| Decisão | Escolha | Motivo |
|---------|---------|--------|
| **Django base** | Merge manual | WL tem multi-tenant/ROI/resellers; VMS tem agents/notifications/events |
| **Frontend base** | White Label | Mais completo (14 pages, form validation, maps, testing) |
| **Workers** | Ambos | GPU workers reconstruídos + Celery tasks do VMS |
| **Gravação** | MediaMTX nativo (record:yes) | Elimina recorder-worker inteiro |
| **Status de câmera** | Webhooks (instant) | Substitui polling a cada 10s |
| **Analytics atuais** | **APAGAR TODOS** | Código cheio de problemas, reconstruir 1-por-1 |
| **ROI atual** | **APAGAR E REFAZER** | Dual-mode confuso, publicação duplicada, logic scattered |
| **Frame transport** | Redis frame cache (key no msg) | Elimina base64 inline (160KB/frame → 50 bytes/msg) |
| **State dos workers** | Redis (checkpoint per camera/roi) | Elimina perda de estado no restart |
| **Dedup** | Redis unificado, TTL por tipo | Estratégia consistente cross-worker |

---

## 3. Diagnóstico: O Que Está Ruim

### 3.1 ROI System — PROBLEMAS CRÍTICOS

- **Dual-mode confuso**: `ia_type` (single) + `ia_types` (list) coexistem sem validação
- **Publicação DUPLICADA**: views.py E signals.py publicam `roi.updated` → race condition
- **Startup sync incompleto**: FG só busca ROIs 1x; restart não re-triggera
- **Expansion em 3 lugares**: frame_grabber, yolo_worker, serializers — nightmare de manutenção
- **Polygon validation zero**: JSONField aceita qualquer coisa, sem min 3 pontos
- **Config validation zero**: `config={}` aceita qualquer JSON, sem schema por ia_type

### 3.2 Frame Grabber — PROBLEMAS CRÍTICOS

- **Base64 inline**: 40KB × 4 queues = 160KB/frame. 500 câmeras × 3 FPS = 240 MB/s em RabbitMQ
- **Redis cache NUNCA USADO**: `RedisFrameCache` existe mas `frame_key: None` (código morto)
- **ROI expansion per-frame**: CPU waste, deveria ser feito 1x no setup
- **Motion gate cego 5s**: Primeiros 5 frames ignorados no startup (falso warm-up)
- **cv2.VideoCapture sequencial**: 50 câmeras × 55ms = 2750ms loop — impossível para 500 câmeras
- **Sem reconnect exponencial**: câmera offline = retry infinito sem backoff

### 3.3 YOLO Worker

- **ROI expansion DUPLICADA**: já foi feita no FG, mas faz de novo
- **Tracker memory leak**: ByteTrack per camera criado a cada ROI, nunca limpo
- **Class set recomputado per-frame**: `needed_classes` deveria ser cache per-ROI
- **Supervision annotations in AI pipeline**: sv.BoundingBoxAnnotator no worker (deveria ser no frontend)
- **Dedup per-ROI in-memory**: restart = todos os dedup timers resetados = flood de eventos duplicados

### 3.4 LPR Worker

- **Sem dedup**: mesma placa detectada 2-3x/sec → 3 eventos para 1 carro
- **Ignora ROIs**: detecta placas em toda a imagem, não na zona configurada
- **Redis miss + retry**: 5 retries de frame porque FG manda base64 em vez de Redis key
- **EasyOCR single-thread**: bloqueia o worker durante OCR (~80ms por placa)
- **Sem validação de placa**: aceita "ABC" como placa válida

### 3.5 Facial Worker

- **Threading + asyncio mixing**: thread daemon pode morrer silenciosamente
- **50K embeddings in-memory**: restart = 30s cold load sem persistence
- **Sem quality checks**: `det_thresh=0.3` aceita reflexos e desenhos como faces
- **Sem rate limiting**: 1 pessoa na frente da câmera = 60 matches/min

### 3.6 Analytics Workers (10 tipos)

- **State lost on restart**: loitering timers, queue counters, abandoned trackers — tudo zerado
- **Dedup inconsistente**: cada analyzer tem sua própria estratégia (alguns in-memory, outros Redis, TTLs diferentes)
- **Heatmap O(N) trim**: `LPUSH` + `LTRIM` per frame per camera — O(N) no Redis
- **Sem cross-ROI awareness**: ROIs sobrepostas = mesma pessoa gera 2+ eventos
- **Base class vazia**: `AnalyzerBase` não oferece nada reusável (dedup, state, lifecycle)

---

## 4. Estrutura Final do Monorepo

```
vms/
├── CLAUDE.md                        # Guia do projeto unificado
├── Makefile                         # dev, build, test, stop targets
├── docker-compose.yml               # Orquestração principal
│
├── backend/                         # Django REST API (merged)
│   ├── manage.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py             # INSTALLED_APPS unificado
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   ├── asgi.py                 # Daphne ASGI (WebSocket)
│   │   ├── celery.py               # ← VMS (3 queues: default, recordings, analytics)
│   │   └── routing.py             # ← WL (Channels routing)
│   ├── apps/
│   │   ├── auth_app/               # ← WL  (User UUID PK, email-based, 5 roles)
│   │   ├── authentication/         # ← WL  (JWT views, permissions, backends)
│   │   ├── tenants/                # ← WL  (Tenant → Reseller → License)
│   │   ├── resellers/              # ← WL  (Reseller model, management)
│   │   ├── franchise/              # ← WL  (License model)
│   │   ├── cameras/                # ← MERGED (WL + VMS manufacturer/agent FK)
│   │   ├── roi/                    # ← REESCRITO (novo, limpo, single-mode)
│   │   ├── detections/             # ← WL  (AIEvent, WebSocket consumers)
│   │   ├── persons/                # ← WL  (KnownPerson, PersonPhoto, embeddings)
│   │   ├── segments/               # ← WL  (Segment, Clip, StoragePolicy, StorageFile)
│   │   ├── dashboard/              # ← WL  (Dashboard stats API)
│   │   ├── agents/                 # ← VMS (Agent model, config, heartbeat API)
│   │   ├── notifications/          # ← VMS (NotificationRule, NotificationLog, HMAC)
│   │   ├── events/                 # ← VMS (Event model para system events)
│   │   ├── webhooks/               # ← VMS (WebhookLog audit trail)
│   │   └── health/                 # ← VMS (HealthCheckView /api/v1/health/)
│   ├── shared/                     # ← VMS (módulos reusáveis)
│   │   ├── mediamtx_client.py      # HTTP client MediaMTX API v3 (CRUD paths)
│   │   ├── event_bus.py            # RabbitMQ publish/subscribe helpers
│   │   ├── cache.py                # Redis camera status cache
│   │   └── pubsub.py              # Redis pub/sub for SSE real-time
│   ├── middleware/                  # ← WL
│   │   ├── tenant.py               # TenantMiddleware (multi-tenant isolation)
│   │   └── white_label.py          # WhiteLabelMiddleware (brand customization)
│   ├── master/                     # ← WL (super admin views)
│   └── templates/emails/           # ← WL
│
├── async_services/                  # ← VMS (FastAPI async layer)
│   ├── main.py                     # FastAPI app (lifespan, CORS, rate limiting)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── routers/
│   │   ├── webhooks.py             # MediaMTX 5 hooks + ALPR vendors (Hik/Intelbras/generic)
│   │   ├── streaming.py            # MediaMTX JWT auth callback (/streaming/token/verify/)
│   │   ├── sse.py                  # SSE real-time (Redis pub/sub → browser)
│   │   └── health.py              # Async health check
│   └── services/
│       ├── webhook_processor.py    # Dispatch MediaMTX events → Celery/Django
│       ├── isapi_listener.py       # ISAPI alertStream (Hikvision/Intelbras XML events)
│       └── stream_manager.py       # MediaMTX path CRUD via API
│
├── workers/
│   ├── frame_grabber/              # ← REESCRITO (Redis cache, async, sem base64)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── worker/
│   │       ├── service.py          # Main loop: async connections, ROI-aware routing
│   │       ├── camera_pool.py      # Pool de câmeras com backoff + reconnect
│   │       └── frame_cache.py      # Redis JPEG cache (TTL 10s, SET + key ref)
│   │
│   ├── lpr_worker/                 # ← REESCRITO (Fase 8)
│   │   ├── Dockerfile              # pytorch CUDA 12.1
│   │   ├── requirements.txt
│   │   └── worker/
│   │       ├── service.py          # YOLO plate_detector + EasyOCR
│   │       ├── plate_validator.py  # Regex Mercosul/antiga + checksum
│   │       └── dedup.py            # Redis dedup (camera:plate, TTL 30s)
│   │
│   ├── yolo_worker/                # ← REESCRITO (Fase 9)
│   │   ├── Dockerfile              # pytorch CUDA 12.1
│   │   ├── requirements.txt
│   │   └── worker/
│   │       ├── service.py          # YOLOv8n + ByteTrack
│   │       ├── tracker_pool.py     # ByteTrack per-camera com cleanup
│   │       └── roi_filter.py       # Polygon containment (sv.PolygonZone)
│   │
│   ├── facial_worker/              # ← REESCRITO (Fase 13)
│   │   ├── Dockerfile              # pytorch CUDA 12.1
│   │   ├── requirements.txt
│   │   └── worker/
│   │       ├── service.py          # insightface buffalo_l
│   │       ├── embedding_store.py  # Redis-backed embedding cache
│   │       └── quality_filter.py   # Face quality checks (size, blur, angle)
│   │
│   ├── analytic_workers/           # ← REESCRITO 1-por-1 (Fases 9-14)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── base.py                 # AnalyzerBase ABC (dedup, state, lifecycle)
│   │   ├── object_detection.py     # Fase 9
│   │   ├── intrusion.py            # Fase 9
│   │   ├── crowd.py                # Fase 10
│   │   ├── queue_analytic.py       # Fase 10
│   │   ├── traffic.py              # Fase 11 (vehicle, human, line_crossing)
│   │   ├── loitering.py            # Fase 12
│   │   ├── abandoned_object.py     # Fase 12
│   │   └── heatmap.py              # Fase 14
│   │
│   ├── clip_builder/               # ← WL (mantido como está)
│   ├── purge/                      # ← WL (adaptado para StoragePolicy)
│   │
│   ├── celery/                     # ← VMS (background tasks)
│   │   └── tasks/
│   │       ├── recording.py        # Segment indexing via MediaMTX webhook (ffprobe)
│   │       ├── notifications.py    # Webhook delivery (HMAC-SHA256, 3 retries)
│   │       └── events.py           # ISAPI/vendor event processing
│   │
│   └── common/                     # Shared across all workers
│       ├── metrics.py              # Prometheus metrics
│       ├── frame_utils.py          # Redis frame get/set helpers
│       ├── dedup.py                # Unified Redis dedup (SET NX EX)
│       └── state.py                # Redis state persistence (per camera/ROI)
│
├── agent/                           # ← VMS (remote network agent)
│   ├── main.py                     # Poll config → sync streams → heartbeat
│   ├── stream_manager.py           # ffmpeg subprocess management (RTSP→RTMP)
│   ├── client.py                   # Django API client
│   └── Dockerfile
│
├── plugins/                         # ← VMS (analytics plugin framework)
│   ├── base.py                     # AnalyticsPlugin ABC
│   ├── fire_detection/             # Stub (YOLOv8 fine-tuned)
│   ├── intrusion_detection/        # Stub
│   └── face_recognition/           # Stub
│
├── frontend/                        # ← WL base + VMS pages
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── pages/                  # 18 merged pages
│       │   ├── AgentsPage.tsx      # ← VMS
│       │   ├── NotificationsPage.tsx # ← VMS
│       │   ├── PlaybackPage.tsx    # ← VMS
│       │   ├── EventsPage.tsx      # ← VMS
│       │   ├── AnalyticsPage.tsx   # ← WL
│       │   ├── CamerasPage.tsx     # ← WL
│       │   ├── CameraDetailPage.tsx # ← WL (+ SSE online status)
│       │   ├── DetectionsPage.tsx   # ← WL
│       │   ├── ROIEditorPage.tsx    # ← WL
│       │   ├── PersonsPage.tsx      # ← WL
│       │   ├── MapPage.tsx          # ← WL
│       │   ├── MosaicPage.tsx       # ← WL
│       │   ├── RecordingsPage.tsx   # ← WL
│       │   ├── ClipsPage.tsx        # ← WL
│       │   ├── DashboardPage.tsx    # ← WL
│       │   ├── LoginPage.tsx        # ← WL
│       │   ├── SettingsPage.tsx     # ← WL
│       │   └── UsersPage.tsx        # ← WL
│       ├── components/
│       │   ├── camera/             # ← WL (AddCameraWizard, CameraCard, DetectionOverlay, VideoPlayer)
│       │   ├── layout/             # ← WL (Header, Layout, Sidebar)
│       │   └── ui/                 # ← WL (Badge, Modal, Spinner)
│       ├── services/
│       │   ├── api.ts              # Unified API client
│       │   ├── sse.ts              # ← NEW: SSE client for real-time
│       │   └── errorHandler.ts
│       ├── hooks/
│       │   ├── useSSE.ts           # ← NEW: SSE React hook
│       │   ├── useErrorHandler.ts
│       │   └── usePermission.ts
│       ├── store/
│       │   ├── authStore.ts        # Zustand auth
│       │   └── themeStore.ts
│       └── types/index.ts          # Unified TypeScript interfaces
│
├── infra/
│   ├── mediamtx/
│   │   └── mediamtx.yml            # ← VMS (record:yes, 5 webhook hooks)
│   ├── nginx/
│   │   └── nginx.conf              # Merged routing rules
│   ├── grafana/                    # ← WL (dashboards)
│   └── prometheus/                 # ← WL (scrape configs)
│
├── models/                          # AI models
│   ├── plate_detector.pt           # LPR (52MB)
│   └── yolov8n.pt                  # COCO detection (6.2MB)
│
├── storage/                         # Runtime storage
│   ├── recordings/                 # MediaMTX native segments
│   ├── snapshots/                  # Detection thumbnails
│   ├── heatmaps/                   # Gaussian blur outputs
│   ├── clips/                      # Composed video clips
│   └── frames/                     # Temporary frame capture
│
├── tests/                           # Merged test suites
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── bdd/
│
└── docs/
    ├── MONOREPO-PLAN.md            # Este documento
    ├── architecture-v3.md          # Arquitetura unificada
    └── ...
```

---

## Fase 0 — Scaffolding

> **Meta**: Criar a estrutura de pastas do monorepo sem quebrar nada.  
> **Depende de**: Nada  
> **Bloqueia**: Todas as fases seguintes  
> **Estimativa de complexidade**: Baixa

### Tarefas

- [ ] Criar pasta raiz do monorepo
- [ ] Criar subpastas: `backend/`, `async_services/`, `workers/`, `agent/`, `plugins/`, `frontend/`, `infra/`, `models/`, `storage/`, `tests/`, `docs/`
- [ ] Criar `workers/` sub-dirs: `frame_grabber/`, `lpr_worker/`, `yolo_worker/`, `facial_worker/`, `analytic_workers/`, `clip_builder/`, `purge/`, `celery/`, `common/`
- [ ] Criar `Makefile` com targets: `dev`, `dev-core`, `dev-app`, `dev-media`, `dev-ai`, `build`, `test`, `stop`, `logs`, `migrate`, `shell`
- [ ] Criar `.gitignore` unificado (Python, Node, Django, storage, models cache)
- [ ] Criar `CLAUDE.md` inicial

### Verificação

- [ ] Estrutura de pastas criada corretamente
- [ ] Makefile válido com todos os targets

---

## Fase 1 — Backend Django Merge

> **Meta**: Um Django unificado rodando com todos os apps de ambos os projetos.  
> **Depende de**: Fase 0  
> **Bloqueia**: Fases 2, 3, 4, 5, 7, 8+

### 1.1 — Copiar base do White Label

- [ ] Copiar `backend-django/` → `backend/`
- [ ] Renomear `gtvision/` → `config/`
- [ ] Atualizar imports em todos os arquivos (`gtvision.settings` → `config.settings`)
- [ ] Verificar: `python manage.py check` sem erros

### 1.2 — Portar apps do VMS

- [ ] **agents/** — Copiar de `vms/core/apps/agents/`
  - [ ] Adaptar models: UUID PK, FK para WL `tenants.Tenant`, `db_table='agents'`
  - [ ] Copiar views: AgentViewSet, AgentMeView, AgentConfigView, AgentHeartbeatView
  - [ ] Copiar serializers, services
  - [ ] Registrar em INSTALLED_APPS
  - [ ] Adicionar URLs em `config/urls.py`
- [ ] **notifications/** — Copiar de `vms/core/apps/notifications/`
  - [ ] Adaptar models: UUID PK, FK para WL `tenants.Tenant`
  - [ ] Copiar views, serializers
  - [ ] Registrar em INSTALLED_APPS + URLs
- [ ] **events/** — Copiar de `vms/core/apps/events/`
  - [ ] Adaptar Event model: UUID PK, FK para WL `tenants.Tenant` e `cameras.Camera`
  - [ ] Copiar normalizers (ALPR vendor-specific)
  - [ ] Registrar em INSTALLED_APPS + URLs
- [ ] **webhooks/** — WebhookLog model para audit trail
- [ ] **health/** — HealthCheckView simples

### 1.3 — Merge Camera Model

Campos WL (manter):
```python
id = UUIDField(primary_key=True)
tenant = FK('tenants.Tenant')
name, address, latitude, longitude
stream_protocol, stream_url, stream_key
retention_days, ia_enabled, ia_status
online, last_seen
```

Campos VMS (adicionar):
```python
manufacturer = CharField(choices=['hikvision','intelbras','dahua','other'], default='other')
agent = FK('agents.Agent', null=True, blank=True, on_delete=SET_NULL)
```

- [ ] Adicionar campo `manufacturer` ao Camera model
- [ ] Adicionar FK `agent` ao Camera model
- [ ] Criar migration
- [ ] Atualizar serializers para incluir novos campos

### 1.4 — APAGAR ROI atual e reescrever

**Por que apagar**: dual-mode `ia_type`/`ia_types`, publicação duplicada, sem validation

Novo modelo limpo:

```python
class RegionOfInterest(models.Model):
    IA_TYPE_CHOICES = [
        ('lpr', 'Reconhecimento de Placas'),
        ('object_detection', 'Detecção de Objetos'),
        ('intrusion', 'Intrusão'),
        ('crowd', 'Aglomeração'),
        ('vehicle_traffic', 'Tráfego de Veículos'),
        ('human_traffic', 'Tráfego Humano'),
        ('line_crossing', 'Cruzamento de Linha'),
        ('loitering', 'Perambulação'),
        ('abandoned_object', 'Objeto Abandonado'),
        ('queue', 'Detecção de Fila'),
        ('facial', 'Reconhecimento Facial'),
        ('heatmap', 'Mapa de Calor'),
    ]

    id = UUIDField(primary_key=True)
    tenant = FK('tenants.Tenant')
    camera = FK('cameras.Camera', related_name='rois')
    name = CharField(max_length=255)
    ia_type = CharField(max_length=20, choices=IA_TYPE_CHOICES)  # SINGLE MODE ONLY
    polygon = JSONField()           # [[x,y], ...] normalized 0-1, min 3 points
    config = JSONField(default=dict) # Type-specific config (validated per ia_type)
    active = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

- [ ] Apagar app `roi/` atual (models, views, serializers, signals, internal_views)
- [ ] Criar novo app `roi/` limpo:
  - [ ] `models.py` — Single `ia_type` (sem `ia_types` list)
  - [ ] `serializers.py` — Com validação de polygon (min 3 pontos, range 0-1)
  - [ ] `validators.py` — Config validation per ia_type (JSON schema)
  - [ ] `views.py` — CRUD ViewSet (publicação de `roi.updated` SOMENTE aqui)
  - [ ] `signals.py` — VAZIO (sem publicação duplicada — tudo na view)
  - [ ] `urls.py`
- [ ] Criar migration (squash old migrations ou reset)

### 1.5 — Portar shared/ do VMS

- [ ] Copiar `vms/core/shared/` → `backend/shared/`
  - [ ] `mediamtx_client.py` — HttpClient(base_url, auth) com list_paths, add_path, edit_path, remove_path, get_path
  - [ ] `event_bus.py` — publish_event(exchange, routing_key, payload), subscribe(queue, callback)
  - [ ] `cache.py` — get_camera_status, set_camera_status, invalidate_camera_status
  - [ ] `pubsub.py` — publish_realtime(channel, message) para SSE
- [ ] Atualizar `cameras/signals.py` para usar `MediaMTXClient` em vez de httpx inline

### 1.6 — Adicionar Celery config

- [ ] Copiar `vms/core/config/celery.py` → `backend/config/celery.py`
- [ ] Configurar 3 queues: `default`, `recordings`, `analytics`
- [ ] Adicionar Celery settings em `config/settings/base.py`:
  ```python
  CELERY_BROKER_URL = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')
  CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://redis:6379/1')
  ```
- [ ] Atualizar `config/__init__.py` com celery app

### 1.7 — Merge URLs

- [ ] Adicionar ao `config/urls.py`:
  ```python
  path('api/v1/agents/', include('apps.agents.urls')),
  path('api/v1/notifications/', include('apps.notifications.urls')),
  path('api/v1/events/', include('apps.events.urls')),
  path('api/v1/health/', include('apps.health.urls')),
  ```

### Verificação Fase 1

- [ ] `python manage.py check` — zero erros
- [ ] `python manage.py makemigrations` — migrations criadas sem conflito
- [ ] `python manage.py migrate` — todas as tables criadas
- [ ] `python manage.py test` — testes WL existentes passam
- [ ] API endpoints respondendo: `/api/v1/cameras/`, `/api/v1/agents/`, `/api/v1/notifications/`, `/api/v1/health/`

---

## Fase 2 — MediaMTX Event-Driven

> **Meta**: MediaMTX grava nativamente e notifica o sistema via webhooks. Status de câmera instantâneo.  
> **Depende de**: Fase 1  
> **Bloqueia**: Fases 3, 4, 6

### 2.1 — Configurar MediaMTX

- [ ] Substituir `infra/mediamtx.yml` com versão event-driven (baseada em `vms/mediamtx/mediamtx.yml`):

```yaml
pathDefaults:
  source: publisher
  maxReaders: 100

  # Gravação nativa
  record: yes
  recordPath: /storage/recordings/%path/%Y/%m/%d/%H-%M-%S.mp4
  recordFormat: fmp4
  recordPartDuration: 10s
  recordSegmentDuration: 60s
  recordDeleteAfter: 7d

  # 5 Webhook hooks
  runOnReady: >-
    curl -s -X POST http://async-services:8001/webhooks/mediamtx/on_ready
    -H "Content-Type: application/json"
    -d '{"path":"$MTX_PATH","source_type":"$MTX_SOURCE_TYPE","source_id":"$MTX_SOURCE_ID"}'
  runOnReadyRestart: no

  runOnNotReady: >-
    curl -s -X POST http://async-services:8001/webhooks/mediamtx/on_not_ready
    -H "Content-Type: application/json"
    -d '{"path":"$MTX_PATH","source_type":"$MTX_SOURCE_TYPE","source_id":"$MTX_SOURCE_ID"}'

  runOnRead: >-
    curl -s -X POST http://async-services:8001/webhooks/mediamtx/on_read
    -H "Content-Type: application/json"
    -d '{"path":"$MTX_PATH","reader_type":"$MTX_READER_TYPE","reader_id":"$MTX_READER_ID"}'
  runOnReadRestart: no

  runOnUnread: >-
    curl -s -X POST http://async-services:8001/webhooks/mediamtx/on_unread
    -H "Content-Type: application/json"
    -d '{"path":"$MTX_PATH","reader_type":"$MTX_READER_TYPE","reader_id":"$MTX_READER_ID"}'

  runOnRecordSegmentComplete: >-
    curl -s -X POST http://async-services:8001/webhooks/mediamtx/record_segment
    -H "Content-Type: application/json"
    -d '{"path":"$MTX_PATH","file_path":"$MTX_SEGMENT_PATH"}'
```

### 2.2 — Eliminar sync_mediamtx --watch

- [ ] Remover modo `--watch` do command `sync_mediamtx`
- [ ] Manter SOMENTE one-shot startup (`sync_mediamtx` sem `--watch`)
- [ ] Remover container `mediamtx-sync` do docker-compose
- [ ] Status de câmera agora vem via webhook `on_ready`/`on_not_ready` → Fase 3

### 2.3 — Eliminar recorder-worker

- [ ] Apagar `workers/recorder/` (todo o diretório)
- [ ] Remover `recording.start` / `recording.stop` dos signals de câmera
- [ ] Remover serviço `recorder` do docker-compose
- [ ] Segment indexing agora vem via webhook `record_segment` → Fase 3

### 2.4 — Storage path alignment

- [ ] MediaMTX grava em `/storage/recordings/{path}/{Y}/{m}/{d}/{H-M-S}.mp4`
- [ ] Alinhar `purge/` worker para respeitar nova estrutura de paths
- [ ] Alinhar `StoragePolicy` model para category `recordings` apontar para `/storage/recordings/`

### Verificação Fase 2

- [ ] MediaMTX inicia com nova config sem erros
- [ ] Adicionar câmera via API → path criado no MediaMTX via `MediaMTXClient`
- [ ] Câmera conecta → arquivo `.mp4` aparece em `/storage/recordings/`
- [ ] Segmentos de 60s são gerados automaticamente
- [ ] Não existe mais container `recorder` nem `mediamtx-sync`

---

## Fase 3 — Async Services (FastAPI)

> **Meta**: FastAPI recebe webhooks do MediaMTX, serve SSE, e gerencia ISAPI listeners.  
> **Depende de**: Fase 1, Fase 2  
> **Bloqueia**: Fases 4, 5 (SSE no frontend)

### 3.1 — Portar async_services

- [ ] Copiar `vms/async_services/` → `async_services/`
- [ ] Atualizar imports para apontar ao novo `backend/`
- [ ] Criar Dockerfile (python:3.12-slim + httpx, fastapi, uvicorn, redis, slowapi)
- [ ] Criar requirements.txt

### 3.2 — Webhook Handlers

5 endpoints do MediaMTX:

- [ ] `POST /webhooks/mediamtx/on_ready`
  - Extrair `camera_id` do path (format: `live/{tenant_id}/{camera_id}`)
  - Atualizar `Camera.online = True` + `Camera.last_seen = now()`
  - Publicar `camera_status` via Redis pub/sub → SSE
  - Iniciar ISAPI listener (se câmera tem manufacturer hikvision/intelbras)
  - Log evento em `events.Event(type='camera.online')`

- [ ] `POST /webhooks/mediamtx/on_not_ready`
  - Atualizar `Camera.online = False`
  - Publicar `camera_status` via Redis pub/sub → SSE
  - Parar ISAPI listener
  - Log evento em `events.Event(type='camera.offline')`

- [ ] `POST /webhooks/mediamtx/on_read` — Log viewer connected (métricas)
- [ ] `POST /webhooks/mediamtx/on_unread` — Log viewer disconnected
- [ ] `POST /webhooks/mediamtx/record_segment`
  - Dispatch Celery task `recording.process_segment`:
    - `ffprobe` → extrair duração
    - Calcular `start_time = end_time - duration`
    - Criar `Segment` model no Django

Endpoints ALPR vendor:

- [ ] `POST /webhooks/alpr` — Payload pré-normalizado
- [ ] `POST /webhooks/alpr/{manufacturer}` — Normalização por vendor (Hikvision/Intelbras)
  - Dispatch Celery task → deduplicate (Redis SET NX EX) → criar `AIEvent`

### 3.3 — SSE (Server-Sent Events)

- [ ] `GET /sse/?token={jwt}` — SSE stream
  - Validar JWT token
  - Subscribe Redis pub/sub channel `vms:realtime:{tenant_id}`
  - Stream eventos: `camera_status`, `detection`, `event`, `notification`
  - Rate limit: 100/min per IP

### 3.4 — ISAPI Listener

- [ ] Portar `isapi_listener.py` do VMS
  - Conecta ao `http://camera/ISAPI/Event/notification/alertStream`
  - Parse XML alerts em real-time (chunked streaming)
  - Mapeia para event types: motion.detected, video.loss, line_crossing, etc.
  - Debounce: 5s entre eventos do mesmo tipo
  - Auto-reconnect com exponential backoff (max 60s)
  - Digest auth extraída da RTSP URL

### 3.5 — Streaming Auth

- [ ] `POST /streaming/token/verify/` — MediaMTX JWT validation callback
  - Valida JWT do frontend
  - Retorna permissions (read/publish) baseado em user.role + tenant

### Verificação Fase 3

- [ ] `POST /webhooks/mediamtx/on_ready` → Camera.online=True no DB
- [ ] `POST /webhooks/mediamtx/on_not_ready` → Camera.online=False no DB
- [ ] `POST /webhooks/mediamtx/record_segment` → Segment criado no DB
- [ ] `GET /sse/` → recebe events em real-time quando camera status muda
- [ ] ALPR webhook → AIEvent criado (com dedup)
- [ ] Rate limiting ativo (429 após 100 requests/min)

---

## Fase 4 — Frame Grabber (Reescrito)

> **Meta**: Frame Grabber eficiente que usa Redis cache em vez de base64, com async connections.  
> **Depende de**: Fase 1 (ROI), Fase 2 (MediaMTX), Fase 3 (webhooks para saber quais câmeras estão online)  
> **Bloqueia**: Fases 8-14 (todos os analytics dependem de frames)

### 4.1 — Arquitetura Nova

```
Camera (RTSP via MediaMTX)
  │
  ▼
Frame Grabber (async, pool de connections)
  │
  ├── cv2.VideoCapture per camera (thread pool)
  │   └── frame bytes (JPEG)
  │
  ├── Redis SET frame:{camera_id}:{timestamp} {jpeg_bytes} EX 10
  │
  └── RabbitMQ publish per ROI:
      {
        "camera_id": "uuid",
        "frame_key": "frame:uuid:1710000000",  // 50 bytes, NÃO 40KB base64
        "timestamp": 1710000000,
        "rois": [{"id":"uuid", "ia_type":"lpr", "polygon":[[x,y],...], "config":{}}]
      }
      → Route to queue by ia_type:
        "lpr"            → ai.frame.lpr
        "facial"         → ai.frame.facial
        "object_detection","intrusion","crowd","queue",
        "vehicle_traffic","human_traffic","line_crossing",
        "loitering","abandoned_object" → ai.frame.yolo
        "heatmap"        → ai.frame.heatmap
```

### 4.2 — Implementação

- [ ] **service.py** — Main loop:
  - Startup: fetch all cameras + ROIs from Django API (`/api/internal/roi-sync/`)
  - Consume `roi.updated` and `camera.activated` from RabbitMQ
  - Per camera: spawn a capture thread via ThreadPoolExecutor
  - Rate: 1 FPS per camera (configurable via env)

- [ ] **camera_pool.py** — Pool de câmeras:
  - Dict[camera_id, CameraCapture]
  - Add/remove cameras dynamically (from RabbitMQ messages)
  - Per camera: `cv2.VideoCapture` with TCP transport
  - Reconnect with exponential backoff (1s, 2s, 4s, 8s, 16s, 32s, max 60s)
  - Health check: if no frame in 30s → reconnect

- [ ] **frame_cache.py** — Redis frame cache:
  - `store(camera_id, timestamp, jpeg_bytes)` → `SET frame:{camera_id}:{timestamp} {jpeg_bytes} EX 10`
  - `get(frame_key)` → `GET frame_key` → bytes
  - Compression: JPEG quality 85 (configurable)
  - TTL: 10 seconds (sufficient for all workers to process)

- [ ] **ROI routing** — Pre-compute per camera:
  - On startup + on `roi.updated`: build `Dict[camera_id, List[ROI]]`
  - Group ROIs by target queue (lpr, facial, yolo, heatmap)
  - Per frame: publish 1 message per queue group (NOT per ROI)
  - Include all applicable ROIs in the message

### 4.3 — Diferenças vs Atual

| Aspecto | Atual (quebrado) | Novo |
|---------|-------------------|------|
| Frame transport | base64 inline (40KB/msg) | Redis key ref (50 bytes/msg) |
| RabbitMQ bandwidth | 240 MB/s (500 cam) | 1.5 MB/s (500 cam) |
| ROI expansion | Per frame (CPU waste) | Per camera, cached on setup |
| Reconnect | Sem backoff | Exponential backoff (max 60s) |
| Motion gate | 5s cego no startup | Nenhum gate artificial |
| Redis cache | Código morto | Usado de verdade |

### Verificação Fase 4

- [ ] Frame Grabber conecta a câmeras via MediaMTX RTSP
- [ ] Frames armazenados no Redis (`frame:{camera_id}:{ts}`) com TTL 10s
- [ ] Mensagens no RabbitMQ contêm `frame_key` (não base64)
- [ ] ROI refresh funciona via `roi.updated` message
- [ ] Câmera offline → reconnect com backoff → reconecta quando volta
- [ ] Bandwidth do RabbitMQ < 5 MB/s com 50 câmeras

---

## Fase 5 — Frontend Merge

> **Meta**: Frontend unificado com todas as pages + SSE real-time.  
> **Depende de**: Fase 1 (APIs), Fase 3 (SSE endpoint)  
> **Bloqueia**: Nada (cosmético)

### 5.1 — Base do White Label

- [ ] Copiar `frontend/` → `frontend/` (já é a base)
- [ ] Verificar build: `npm run build` sem erros

### 5.2 — Portar pages do VMS

- [ ] Copiar e adaptar de `vms/frontend/src/pages/`:
  - [ ] `AgentsPage.tsx` — Gerenciamento de agents remotos
  - [ ] `NotificationsPage.tsx` — Regras de notificação + logs
  - [ ] `PlaybackPage.tsx` — Playback de gravações (adaptar para MediaMTX segments)
  - [ ] `EventsPage.tsx` — System events log (camera online/offline, etc.)

### 5.3 — SSE Integration

- [ ] Criar `services/sse.ts`:
  ```typescript
  // EventSource client for /sse/?token={jwt}
  // Auto-reconnect with backoff
  // Parse JSON events: camera_status, detection, event, notification
  ```
- [ ] Criar `hooks/useSSE.ts`:
  ```typescript
  // React hook wrapping SSE service
  // useSSE<T>(eventType: string): T | null
  // Auto-subscribe on mount, cleanup on unmount
  ```
- [ ] Integrar SSE em:
  - [ ] `CamerasPage.tsx` — Badge online/offline atualiza em real-time
  - [ ] `CameraDetailPage.tsx` — Status indicator live
  - [ ] `MosaicPage.tsx` — Grid com status real-time
  - [ ] `DashboardPage.tsx` — Stats atualizados via SSE
  - [ ] `DetectionsPage.tsx` — New detections aparecem sem refresh

### 5.4 — Atualizar Navigation

- [ ]`Sidebar.tsx` — Adicionar links:
  - Agents (ícone: Server)
  - Notifications (ícone: Bell)
  - Events (ícone: Activity)
  - Playback (ícone: Play)

### 5.5 — Atualizar API client e types

- [ ] `services/api.ts` — Adicionar methods:
  - `getAgents()`, `createAgent()`, `deleteAgent()`
  - `getNotificationRules()`, `createNotificationRule()`
  - `getNotificationLogs()`
  - `getEvents(filters)`
  - `getHealth()`
- [ ] `types/index.ts` — Adicionar interfaces:
  - `Agent`, `NotificationRule`, `NotificationLog`, `SystemEvent`, `HealthStatus`

### Verificação Fase 5

- [ ] `npm run build` — build sem erros
- [ ] Todas 18 pages renderizam corretamente
- [ ] SSE conecta e recebe events de camera status
- [ ] Camera online/offline atualiza no frontend sem refresh
- [ ] Navigation Sidebar mostra todos os links

---

## Fase 6 — Infrastructure & Docker Compose

> **Meta**: Docker Compose unificado com todos os serviços.  
> **Depende de**: Fases 1-5  
> **Bloqueia**: Fases 7-16 (tudo precisa rodar)

### 6.1 — Docker Compose Layered

**docker-compose.core.yml** (infra base):
```yaml
services:
  postgres:    # PostgreSQL 16 — port 5432
  redis:       # Redis 7 — port 6379
  rabbitmq:    # RabbitMQ 3 — ports 5672, 15672
  mediamtx:    # MediaMTX — ports 8554, 1935, 8888, 8889, 9997
               # volumes: ./infra/mediamtx/mediamtx.yml:/mediamtx.yml
               #          ./storage/recordings:/storage/recordings
```

**docker-compose.app.yml** (application):
```yaml
services:
  django:          # Django Daphne @ 8000
                   # command: migrate + sync_mediamtx + consume_ai_events + daphne
  async-services:  # FastAPI Uvicorn @ 8001 (webhooks, SSE, streaming)
  celery-worker:   # Celery worker (3 queues: default, recordings, analytics)
  celery-beat:     # Celery scheduler
  frontend:        # React + Nginx (build stage)
  nginx:           # Reverse proxy @ 80
```

**docker-compose.media.yml** (media workers):
```yaml
services:
  frame-grabber:   # Frame capture → Redis → RabbitMQ
  clip-builder:    # Video clip composition
  purge:           # Storage cleanup
```

**docker-compose.ai.yml** (GPU workers):
```yaml
services:
  yolo-worker:     # GPU — COCO detection
  lpr-worker:      # GPU — Plate recognition (replicas: 2)
  facial-worker:   # GPU — Face recognition
  analytic-workers: # CPU — Unified analytics
```

### 6.2 — Serviços REMOVIDOS

- [ ] ~~recorder~~ → Substituído por MediaMTX `record: yes`
- [ ] ~~mediamtx-sync~~ → Substituído por webhooks on_ready/on_not_ready
- [ ] ~~ai-worker (monolítico)~~ → Substituído por workers especializados

### 6.3 — Nginx Config Merge

```nginx
# Django REST API
location /api/ { proxy_pass http://django:8000; }
location /admin/ { proxy_pass http://django:8000; }
location /ws/ { proxy_pass http://django:8000; }  # WebSocket (Daphne)

# FastAPI Async Services
location /webhooks/ { proxy_pass http://async-services:8001; }
location /sse/ { proxy_pass http://async-services:8001; }
location /streams/ { proxy_pass http://async-services:8001; }

# MediaMTX
location /hls/ { proxy_pass http://mediamtx:8888; }
location /webrtc/ { proxy_pass http://mediamtx:8889; }

# Static/Media
location /media/ { alias /storage/; }
location /static/ { alias /staticfiles/; }

# Frontend SPA (catch-all)
location / { try_files $uri /index.html; }
```

### 6.4 — Network & Volumes

- [ ] Network: `vms` (bridge)
- [ ] Volumes compartilhados:
  - `./storage` → Django, async-services, frame-grabber, clip-builder, purge, MediaMTX
  - `django-static` → Django staticfiles para Nginx
  - `ai-model-cache` → YOLO model cache
  - `ai-insightface-cache` → insightface buffalo_l
  - `postgres-data`, `redis-data`, `rabbitmq-data`

### 6.5 — Environment Variables (padronizado)

```env
# Database
POSTGRES_DB=vms
POSTGRES_USER=vms
POSTGRES_PASSWORD=<secret>
DATABASE_URL=postgres://vms:<secret>@postgres:5432/vms

# Redis
REDIS_URL=redis://redis:6379/0

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/

# MediaMTX
MEDIAMTX_API_URL=http://mediamtx:9997
MEDIAMTX_RTSP_URL=rtsp://mediamtx:8554

# Django
DJANGO_SETTINGS_MODULE=config.settings.development
SECRET_KEY=<secret>
ALLOWED_HOSTS=*

# Storage
STORAGE_PATH=/storage
```

### Verificação Fase 6

- [ ] `docker-compose up --build` — todos os serviços iniciam
- [ ] `docker-compose ps` — todos healthy
- [ ] Nginx routing: `/api/` → Django, `/webhooks/` → async-services, `/hls/` → MediaMTX
- [ ] Frontend acessível em `http://localhost`
- [ ] RabbitMQ UI em `http://localhost:15672`

---

## Fase 7 — Agent Remoto

> **Meta**: Agent que roda na rede do cliente, puxa RTSP e empurra RTMP para o MediaMTX cloud.  
> **Depende de**: Fase 1 (agents app), Fase 6 (docker-compose)  
> **Bloqueia**: Nada (independente)

### Tarefas

- [ ] Copiar `vms/agent/` → `agent/`
- [ ] Adaptar `client.py` para apontar ao novo Django API:
  - `GET /api/v1/agents/me/config/` → lista de câmeras + RTMP push URLs
  - `POST /api/v1/agents/me/heartbeat/` → health status
- [ ] Stream Manager: `ffmpeg -nostdin -rtsp_transport tcp -i {rtsp_url} -c copy -f flv {rtmp_push_url}`
- [ ] Restart logic: exponential backoff (1s → 60s max)
- [ ] Criar Dockerfile standalone (python:3.12-slim + ffmpeg)
- [ ] Documentar install instructions para clientes

### Verificação Fase 7

- [ ] Agent inicia, busca config do Django, inicia streams
- [ ] Câmeras do agent aparecem no MediaMTX
- [ ] Heartbeat chega ao Django a cada 30s
- [ ] Agent restart → reconecta todas as câmeras

---

## Fase 8 — Analytics: LPR (Primeiro Worker GPU)

> **Meta**: LPR worker limpo, com dedup, ROI-aware, validação de placa.  
> **Depende de**: Fase 4 (Frame Grabber com Redis cache)  
> **Bloqueia**: Nada (analytics são independentes entre si)

### 8.1 — Por que reescrever

| Problema Atual | Solução |
|----------------|---------|
| Sem dedup (mesma placa 2-3x/sec) | Redis SET NX EX (camera:plate, TTL 30s) |
| Ignora ROIs (toda a imagem) | sv.PolygonZone per ROI |
| Base64 5 retries | Redis frame_key (1 GET) |
| EasyOCR single-thread | ThreadPoolExecutor(2) |
| Aceita "ABC" como placa | Regex Mercosul + antiga |

### 8.2 — Implementação

- [ ] **service.py** — Pipeline:
  ```
  Consume ai.frame.lpr
    → GET frame from Redis (frame_key)
    → YOLO plate_detector.pt (batch inference if multiple frames)
    → For each detected plate:
      → Filter by ROI polygon (is plate centroid inside zone?)
      → Crop plate region
      → EasyOCR (ThreadPoolExecutor)
      → Validate plate format (plate_validator.py)
      → Dedup check (Redis SET NX: camera:{cam_id}:plate:{text} EX 30)
      → If new: publish to ai.events
  ```

- [ ] **plate_validator.py**:
  ```python
  # Mercosul: ABC1D23 (3 letras + 1 dígito + 1 letra + 2 dígitos)
  # Antiga:   ABC-1234 (3 letras + 4 dígitos)
  # Min confidence: 0.6
  # Min characters: 7
  ```

- [ ] **dedup.py**:
  ```python
  def is_duplicate(camera_id: str, plate: str, ttl: int = 30) -> bool:
      key = f"dedup:lpr:{camera_id}:{plate}"
      return not redis.set(key, "1", nx=True, ex=ttl)
  ```

- [ ] Dockerfile: `pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime`
- [ ] Model: `/models/plate_detector.pt` (52MB, volume mount)

### 8.3 — Evento de saída

```json
{
  "event_type": "lpr",
  "camera_id": "uuid",
  "roi_id": "uuid",
  "tenant_id": "uuid",
  "snapshot_path": "/storage/snapshots/lpr/...",
  "event_data": {
    "plate": "ABC1D23",
    "confidence": 0.92,
    "plate_bbox": [x1, y1, x2, y2],
    "vehicle_bbox": [x1, y1, x2, y2]
  },
  "detected_at": "2026-03-15T10:00:00Z"
}
```

### Verificação Fase 8

- [ ] Câmera com ROI tipo `lpr` → placa detectada → AIEvent criado no DB
- [ ] Mesma placa na mesma câmera em < 30s → NÃO duplica evento
- [ ] Placa fora do polygon ROI → NÃO gera evento
- [ ] "ABC" não passa na validação (min 7 chars)
- [ ] Latência end-to-end < 500ms (frame → event)
- [ ] Redis frame GET: 1 tentativa (sem retries)

---

## Fase 9 — Analytics: Object Detection + Intrusion

> **Meta**: YOLO worker que filtra por ROI polygon e classes configuradas.  
> **Depende de**: Fase 4 (Frame Grabber)  

### 9.1 — YOLO Worker (reescrito)

- [ ] **service.py** — Pipeline:
  ```
  Consume ai.frame.yolo
    → GET frame from Redis
    → YOLOv8n inference (batch support)
    → ByteTrack tracking (per camera, com cleanup timer LRU)
    → For each ROI in message:
      → Filter detections by polygon (sv.PolygonZone)
      → Filter by configured classes (ROI config.classes)
      → Route to specific analyzer based on ia_type
  ```

- [ ] **tracker_pool.py**:
  - Dict[camera_id, (ByteTrack, last_used_ts)]
  - Cleanup: remove trackers idle > 5min
  - Max trackers: 100 (LRU eviction)

- [ ] **roi_filter.py**:
  - `filter_by_polygon(detections, polygon)` → detections inside zone
  - `filter_by_classes(detections, classes)` → detections of specific COCO classes
  - Pre-compute `sv.PolygonZone` on ROI load (cache, not per-frame)

### 9.2 — Object Detection Analyzer

- [ ] Detecção de objetos específicos (classes COCO) dentro de uma zona
- [ ] Dedup: `dedup:object:{camera_id}:{roi_id}:{class}` TTL 30s
- [ ] Config: `{"classes": ["person", "car", "truck"]}` — obrigatório

### 9.3 — Intrusion Analyzer

- [ ] Detecta QUALQUER objeto dentro de zona proibida
- [ ] Dedup: `dedup:intrusion:{camera_id}:{roi_id}` TTL 30s
- [ ] Config: `{"classes": ["person"]}` — opcional, default=all
- [ ] Gera evento com snapshot + bounding boxes

### Verificação Fase 9

- [ ] ROI tipo `object_detection` com classes `["person"]` → eventos quando pessoa entra na zona
- [ ] ROI tipo `intrusion` → evento quando qualquer coisa entra na zona
- [ ] Tracker IDs consistentes (mesmo objeto = mesmo track_id entre frames)
- [ ] Dedup funciona: mesmo objeto parado na zona não gera 1 evento/sec

---

## Fase 10 — Analytics: Crowd + Queue

> **Meta**: Contagem de pessoas em zona com alertas de threshold.  
> **Depende de**: Fase 9 (YOLO worker)

### 10.1 — Crowd Analyzer

- [ ] Conta pessoas dentro do polygon ROI
- [ ] Se count > `config.threshold` → gera alerta
- [ ] Dedup: `dedup:crowd:{camera_id}:{roi_id}` TTL 60s
- [ ] Config: `{"threshold": 10}`
- [ ] Evento inclui `current_count` e `threshold`

### 10.2 — Queue Analyzer

- [ ] Profundidade de fila (contagem de pessoas na zona)
- [ ] Tempo médio de espera estimado (baseado em velocidade de saída)
- [ ] State: Redis hash `queue:{camera_id}:{roi_id}` com counters
- [ ] Config: `{"max_queue_length": 15, "alert_wait_time_seconds": 300}`
- [ ] Alerta quando: queue_length > max OU wait_time > alert_wait_time

### Verificação Fase 10

- [ ] ROI tipo `crowd` com threshold=5 → alerta quando 6+ pessoas na zona
- [ ] ROI tipo `queue` → eventos com queue_length e estimated_wait_time
- [ ] State sobrevive restart (Redis)
- [ ] Contagens estáveis (sem oscilação +/-1 entre frames consecutivos)

---

## Fase 11 — Analytics: Traffic (Line Crossing)

> **Meta**: Contagem de veículos/pessoas cruzando uma linha com direção.  
> **Depende de**: Fase 9 (YOLO + ByteTrack)

### 11.1 — Vehicle Traffic

- [ ] sv.LineZone para contagem de veículos cruzando linha
- [ ] Direção (in/out) baseada em track trajectory
- [ ] Classes: car, truck, bus, motorcycle
- [ ] Config: `{"line": [[x1,y1],[x2,y2]], "direction": "both|in|out"}`
- [ ] State: Redis `traffic:{camera_id}:{roi_id}` → in_count, out_count

### 11.2 — Human Traffic

- [ ] Mesmo que vehicle_traffic mas para pessoas
- [ ] Classes: person
- [ ] Config: mesmo formato

### 11.3 — Line Crossing (genérico)

- [ ] Qualquer classe cruzando linha bidirecional
- [ ] Gera evento por cada cruzamento individual (não aggregated)
- [ ] Config: `{"line": [[x1,y1],[x2,y2]], "classes": ["person","car"]}`

### Verificação Fase 11

- [ ] ROI tipo `vehicle_traffic` → conta carros in/out
- [ ] ROI tipo `human_traffic` → conta pessoas in/out
- [ ] ROI tipo `line_crossing` → evento individual por cruzamento
- [ ] Direção correta (in vs out baseado em trajetória)
- [ ] Counters incrementais armazenados no Redis

---

## Fase 12 — Analytics: Loitering + Abandoned Object

> **Meta**: Detecção temporal — alerta após X segundos de permanência.  
> **Depende de**: Fase 9 (YOLO + ByteTrack)

### 12.1 — Loitering

- [ ] Pessoa na zona por mais de X segundos → alerta
- [ ] Usa track_id do ByteTrack para rastrear persistência
- [ ] State: Redis hash `loiter:{camera_id}:{roi_id}:{track_id}` → first_seen timestamp
- [ ] Config: `{"max_seconds": 30, "classes": ["person"]}`
- [ ] Cleanup: remove tracks que saíram da zona
- [ ] Dedup: 1 alerta por track_id por permanência

### 12.2 — Abandoned Object

- [ ] Objeto estático (sem owner) por mais de X segundos → alerta
- [ ] Detecção: objeto sem pessoa associada num raio de N pixels
- [ ] State: Redis hash `abandoned:{camera_id}:{roi_id}:{track_id}` → first_seen
- [ ] Config: `{"max_seconds": 60, "classes": ["backpack","suitcase","handbag"]}`

### Verificação Fase 12

- [ ] Pessoa parada 35s em zona com `max_seconds=30` → alerta loitering
- [ ] Pessoa sai da zona → timer resetado (sem falso alerta)
- [ ] State sobrevive restart do worker
- [ ] Mochila sem dono por 65s com `max_seconds=60` → alerta abandoned

---

## Fase 13 — Analytics: Facial Recognition

> **Meta**: Reconhecimento facial com quality checks, Redis-backed embeddings, e rate limiting.  
> **Depende de**: Fase 4 (Frame Grabber)

### 13.1 — Melhorias vs Atual

| Problema Atual | Solução |
|----------------|---------|
| 50K embeddings in-memory | Redis-backed store com lazy load |
| Restart = 30s cold load | Redis persist, incremental sync |
| det_thresh=0.3 (lixo) | Quality filter (size > 80px, blur, angle) |
| Sem rate limit | 1 match/pessoa/60s (Redis dedup) |
| Thread daemon silencioso | Async proper (não mixing threading+asyncio) |

### 13.2 — Implementação

- [ ] **service.py**:
  ```
  Consume ai.frame.facial
    → GET frame from Redis
    → insightface detect + embed
    → Quality filter (min face size, blur score, pose angle)
    → Compare vs known embeddings (cosine similarity > 0.5)
    → Dedup: dedup:facial:{camera_id}:{roi_id}:{person_id} TTL 60s
    → If match & new: publish facial_match event
    → If unknown & quality ok: publish facial_unknown event
  ```

- [ ] **embedding_store.py**:
  - Redis hash `embeddings:{tenant_id}` → {person_id: embedding_bytes}
  - `sync_from_django()` — Fetch all active persons + photos, compute embeddings, store in Redis
  - Consume `persons.updated` from RabbitMQ → incremental update
  - Max 50K embeddings per tenant

- [ ] **quality_filter.py**:
  - Min face size: 80x80 pixels
  - Max blur (Laplacian variance < threshold → reject)
  - Max pose angle: yaw < 45°, pitch < 30°
  - Min detection confidence: 0.5 (not 0.3)

### Verificação Fase 13

- [ ] Pessoa cadastrada reconhecida → facial_match event
- [ ] Pessoa desconhecida → facial_unknown event (com snapshot)
- [ ] Foto borrada/pequena → rejeitada (sem evento)
- [ ] Mesma pessoa na câmera → max 1 match/60s (dedup)
- [ ] Restart do worker → embeddings loaded from Redis (< 2s, não 30s)

---

## Fase 14 — Analytics: Heatmap

> **Meta**: Mapa de calor acumulativo por zona, gerado periodicamente.  
> **Depende de**: Fase 9 (YOLO detections)

### 14.1 — Implementação

- [ ] **heatmap.py**:
  - Acumula centroids de detecções em Redis bitmap
  - Formato: `heatmap:{camera_id}:{roi_id}:{hour}` → binary array (width × height)
  - Per frame: increment bucket at (x, y) centroid
  - Periodicamente (every 5 min): render → Gaussian blur → save PNG to `/storage/heatmaps/`

- [ ] Query: aggregar heatmaps por hora/dia/semana
- [ ] Config: `{"resolution": [64, 48], "render_interval_seconds": 300}`
- [ ] Cleanup: purge old heatmaps via `purge/` worker

### Verificação Fase 14

- [ ] ROI tipo `heatmap` → PNG gerado em `/storage/heatmaps/`
- [ ] Heatmap mostra zonas quentes onde pessoas ficam mais tempo
- [ ] Aggregation por período funciona (1h, 1d, 1w)
- [ ] Redis memory razoável (< 1MB/câmera/dia em 64x48 resolution)

---

## Fase 15 — Plugin Framework

> **Meta**: Framework para plugins de analytics customizados (fire detection, etc.)  
> **Depende de**: Fases 8-14 (analytics base completos)  
> **Bloqueia**: Nada

### Tarefas

- [ ] Copiar `vms/plugins/` → `plugins/`
- [ ] Refinar `base.py` AnalyticsPlugin ABC:
  ```python
  class AnalyticsPlugin(ABC):
      @property
      def name(self) -> str: ...
      @property
      def version(self) -> str: ...
      @property
      def required_models(self) -> list[str]: ...

      async def process_frame(self, frame: bytes, metadata: dict) -> dict | None: ...
      def on_load(self): ...
      def on_unload(self): ...
  ```
- [ ] Plugin discovery: scan `plugins/*/` for `__init__.py` with `Plugin` class
- [ ] Plugin registry no `analytic_workers/` unified worker
- [ ] ROI config: `ia_type="plugin:{plugin_name}"` para analytics via plugin

### Verificação Fase 15

- [ ] Plugin stub (fire_detection) registrado e processando frames
- [ ] Plugin pode ser adicionado sem modificar código core
- [ ] ROI com `ia_type="plugin:fire_detection"` → frames roteados ao plugin

---

## Fase 16 — Testing & Cleanup Final

> **Meta**: Merge test suites, cobertura > 90%, cleanup de código obsoleto.  
> **Depende de**: Todas as fases anteriores

### 16.1 — Merge Tests

- [ ] Copiar testes WL: test_ai_worker, test_authentication, test_cameras, test_rbac
- [ ] Copiar testes VMS: BDD tests (356 tests), unit, integration, e2e
- [ ] Adaptar fixtures para models unificados
- [ ] Criar novos testes:
  - [ ] test_mediamtx_webhooks.py — Testar on_ready/on_not_ready/record_segment
  - [ ] test_roi_new.py — Testar novo ROI (single-mode, validação)
  - [ ] test_frame_grabber_new.py — Testar Redis cache, ROI routing
  - [ ] test_lpr_dedup.py — Testar deduplicação de placas
  - [ ] test_sse.py — Testar SSE endpoints

### 16.2 — Cleanup

- [ ] Deletar `backend-django/` (movido para `backend/`)
- [ ] Deletar `backend-fastapi/` (workers movidos para `workers/`)
- [ ] Deletar `vms/` (totalmente integrado)
- [ ] Deletar `infra/docker-compose.*.yml` antigos (substituídos por novos)
- [ ] Remover código morto:
  - [ ] `sync_mediamtx --watch` mode
  - [ ] `recorder/` worker
  - [ ] `ai_worker/` monolítico antigo
  - [ ] ROI `ia_types` (list mode)
  - [ ] Frame Grabber base64 encoding
  - [ ] ByteTrack annotation rendering (sv.BoundingBoxAnnotator)

### 16.3 — Documentação

- [ ] Atualizar `CLAUDE.md` com estrutura definitiva
- [ ] Criar `docs/architecture-v3.md` com diagramas atualizados
- [ ] Criar `docs/DEPLOYMENT.md` com instruções de produção
- [ ] Criar `docs/AGENT-INSTALL.md` para instalação do agent em clientes

### Verificação Fase 16

- [ ] `pytest tests/ -v` — 100% pass
- [ ] Cobertura > 90%
- [ ] Zero imports quebrados (nenhum módulo referencia diretórios deletados)
- [ ] `docker-compose up --build` — build limpo, sem warnings de código morto
- [ ] Documentação completa e atualizada

---

## Checklist Global

### Infraestrutura
- [ ] **Fase 0**: Scaffolding criado
- [ ] **Fase 6**: Docker Compose funcional, todos os serviços healthy

### Backend
- [ ] **Fase 1**: Django merge completo, todos apps rodando
- [ ] **Fase 2**: MediaMTX event-driven, gravação nativa
- [ ] **Fase 3**: Async Services (webhooks, SSE, ISAPI)

### Workers
- [ ] **Fase 4**: Frame Grabber reescrito (Redis cache, sem base64)

### Frontend
- [ ] **Fase 5**: Frontend merge + SSE integration

### Agent
- [ ] **Fase 7**: Agent remoto funcional

### Analytics (1-por-1)
- [ ] **Fase 8**: LPR ✓ (primeiro worker GPU)
- [ ] **Fase 9**: Object Detection + Intrusion ✓
- [ ] **Fase 10**: Crowd + Queue ✓
- [ ] **Fase 11**: Traffic (Vehicle, Human, Line Crossing) ✓
- [ ] **Fase 12**: Loitering + Abandoned Object ✓
- [ ] **Fase 13**: Facial Recognition ✓
- [ ] **Fase 14**: Heatmap ✓

### Extensibility
- [ ] **Fase 15**: Plugin Framework ✓

### Quality
- [ ] **Fase 16**: Tests merged, cobertura > 90%, cleanup final ✓

---

## Grafo de Dependências

```
Fase 0 (Scaffolding)
  └─── Fase 1 (Django Merge)
         ├─── Fase 2 (MediaMTX Event-Driven)
         │      └─── Fase 3 (Async Services)
         │             └─── Fase 4 (Frame Grabber Reescrito)
         │                    ├─── Fase 8  (LPR)
         │                    ├─── Fase 9  (Object Detection + Intrusion)
         │                    │      ├─── Fase 10 (Crowd + Queue)
         │                    │      ├─── Fase 11 (Traffic)
         │                    │      ├─── Fase 12 (Loitering + Abandoned)
         │                    │      └─── Fase 14 (Heatmap)
         │                    └─── Fase 13 (Facial Recognition)
         │
         ├─── Fase 5 (Frontend Merge) ← depende de Fase 3 (SSE)
         ├─── Fase 6 (Docker Compose) ← depende de Fases 1-5
         └─── Fase 7 (Agent Remoto)   ← independente

Fase 15 (Plugin Framework) ← depende de Fases 8-14
Fase 16 (Testing + Cleanup) ← depende de TUDO
```

---

## Ordem de Execução Recomendada

```
  1. Fase 0  — Scaffolding
  2. Fase 1  — Django Merge
  3. Fase 2  — MediaMTX Event-Driven
  4. Fase 3  — Async Services
  5. Fase 6  — Docker Compose (para poder testar tudo junto)
  6. Fase 4  — Frame Grabber Reescrito
  7. Fase 5  — Frontend Merge
  8. Fase 7  — Agent Remoto
  9. Fase 8  — LPR (primeiro analytics)
 10. Fase 9  — Object Detection + Intrusion
 11. Fase 10 — Crowd + Queue
 12. Fase 11 — Traffic
 13. Fase 12 — Loitering + Abandoned
 14. Fase 13 — Facial Recognition
 15. Fase 14 — Heatmap
 16. Fase 15 — Plugin Framework
 17. Fase 16 — Testing + Cleanup
```
