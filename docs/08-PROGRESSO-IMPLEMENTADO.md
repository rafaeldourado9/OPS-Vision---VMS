# 08 — Progresso Implementado
**VMS White Label · Estado atual da implementação · v1.0**

> Última atualização: 2026-03-09

---

## Resumo Executivo

O sistema foi implementado do zero em 4 frentes simultâneas:

| Frente | Estado | Observações |
|--------|--------|-------------|
| **Infra (Docker/Compose)** | ✅ Completo | 9 serviços orquestrados |
| **Backend Django** | ✅ Base completa | Auth, Câmeras, ROI, Detecções, Persons, Dashboard |
| **Workers FastAPI (IA + Vídeo)** | ✅ Completo | 5 workers + 12 analíticos de IA |
| **Frontend React** | ✅ Completo | 14 páginas + ROI editor canvas |

---

## 1. Infraestrutura

### `infra/docker-compose.yml` — 9 serviços

| Serviço | Imagem Base | Porta(s) |
|---------|-------------|----------|
| `django` | Dockerfile próprio | 8000 (interno) |
| `ai-worker` | `pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime` | — |
| `recorder-worker` | `python:3.11-slim` + ffmpeg | — |
| `frame-grabber` | `python:3.11-slim` + ffmpeg | — |
| `clip-builder` | `python:3.11-slim` + ffmpeg | — |
| `purge-worker` | `python:3.11-slim` | — |
| `mediamtx` | `bluenviron/mediamtx:latest` | 8554 RTSP, 1935 RTMP, 8888 HLS, 8889 WebRTC |
| `postgres` | `postgres:15-alpine` | 5432 |
| `redis` | `redis:7-alpine` | 6379 |
| `rabbitmq` | `rabbitmq:3-management-alpine` | 5672, 15672 (UI) |
| `frontend` | Node 20 → Nginx Alpine | 80 |

### Volumes persistentes
- `postgres-data` — dados do banco
- `redis-data` — cache e heatmap points
- `rabbitmq-data` — filas
- `django-static` — arquivos estáticos servidos pelo nginx
- `../storage` — segmentos MP4, clips, snapshots, heatmaps (bind mount)
- `../models` — modelos YOLO (bind mount, read-only)

---

## 2. Backend Django

### Apps implementados

#### `apps/authentication`
- Model `User` customizado (AbstractBaseUser)
- JWT com SimpleJWT (access 15min, refresh 7 dias)
- Endpoints: `/auth/login/`, `/auth/logout/`, `/auth/me/`, `/auth/token/refresh/`
- `TenantMiddleware` — resolve tenant por `Host` header
- Roles: `operator` < `supervisor` < `city_admin` < `reseller_admin` < `super_admin`

#### `apps/cameras`
- Model `Camera` — nome, endereço, lat/lng, protocolo, stream_url/key, retenção, IA
- Model `ROI` (RegionOfInterest) — 12 tipos de analítico, polygon_points (normalizado), config JSON
- `CameraViewSet` com filtro automático por tenant
- Endpoint `/cameras/{id}/stream-url/` — retorna URL HLS da MediaMTX
- Endpoint `/cameras/{id}/snapshot/` — frame atual via MediaMTX API
- Publicação RabbitMQ `roi.updated` ao salvar/deletar ROI

#### `apps/detections`
- Model `AIEvent` — 12 tipos de evento, confiança, metadata JSON, thumbnail_url
- Consumer RabbitMQ `ai.events` → persiste eventos
- `DetectionViewSet` com filtros: camera_id, event_type, date range, paginação

#### `apps/persons`
- Model `KnownPerson` — nome, foto (ImageField), notes, active, tenant FK
- CRUD via `KnownPersonViewSet` com upload de foto
- Endpoint interno `/api/v1/internal/persons/` protegido por `X-Internal-Key`
- Publicação RabbitMQ `persons.updated` ao criar/atualizar/deletar

#### `apps/dashboard`
- `GET /dashboard/stats/` — total câmeras, online/offline, detecções hoje, clips, eventos por tipo
- `GET /dashboard/detections-by-hour/` — últimas 24h agrupadas por hora
- `GET /analytics/traffic-by-hour/` — tráfego humano ou veicular por hora
- `GET /analytics/traffic-by-day/` — últimas 2 semanas por dia
- `GET /analytics/events-by-type/` — distribuição de eventos (últimos N dias)
- `GET /analytics/queue-stats/` — alertas de fila com contagem e tempo médio
- `GET /cameras/{id}/heatmap/` — serve JPEG do heatmap do disco

#### `apps/recordings` (segmentos + clips)
- Model `RecordingSegment` — metadados de cada arquivo MP4
- Model `Clip` — status `pending→processing→ready/error`, file_url
- Consumer `clip.request` → publica para clip-builder worker

---

## 3. Workers FastAPI

### `frame-grabber`
- Captura frames das câmeras via HLS (1 frame/seg)
- Salva thumbnail no Redis (TTL 60s)
- Publica frame na fila `ai.frame` para câmeras com IA ativa

### `recorder-worker`
- Consome fila `recording.start`
- Grava segmentos MP4 de 10 min via FFmpeg
- Registra metadados via API interna Django
- Reconexão com backoff exponencial

### `clip-builder`
- Consome fila `clip.request`
- Concatena segmentos MP4 com FFmpeg
- Atualiza status do Clip via API interna

### `purge-worker`
- Job periódico — remove segmentos expirados respeitando `retention_days`
- Nunca apaga Clips marcados como `keep`

### `ai-worker` ← **Foco principal da IA**

**Base image:** `pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime` + CUDA 12.1
**Dependências extras:** `easyocr`, `insightface`, `aio-pika`, `pika`

#### Módulos de Análise

| Arquivo | Classe | Analíticos |
|---------|--------|------------|
| `analyzers/lpr.py` | `LPRAnalyzer` | Reconhecimento de Placa (`lpr`) |
| `analyzers/general.py` | `GeneralAnalyzer` | Multidão (`crowd`), Intrusão (`intrusion`), Objeto (`object_detected`) |
| `analyzers/tracking.py` | `TrackingAnalyzer` + `CentroidTracker` | Tráfego Humano, Tráfego Veicular, Cruzamento de Linha, Perambulação, Objeto Abandonado, Fila |
| `analyzers/facial.py` | `FacialAnalyzer` | Reconhecimento Facial (`facial_match`, `facial_unknown`) |
| `analyzers/heatmap.py` | `HeatmapAnalyzer` | Mapa de Calor (acumula em Redis → JPEG) |

#### Detalhes técnicos

**LPR:**
- Modelo YOLO custom (`plate_detector.pt`) — Precision 99.77%, Recall 100%, mAP@50 99.5%
- Pré-processamento: filtro bilateral + resize 2x + EasyOCR
- Deduplicação Redis (TTL 30s por `{camera_id}:{plate}`)

**General (COCO):**
- YOLOv8n COCO para crowd/intrusion/object_detected
- Ray-casting polygon para checar se detecção está dentro do ROI

**Tracking:**
- `CentroidTracker` próprio (sem dependências externas)
- Greedy distance-matrix matching, `max_disappeared=10`
- `line_side()` via produto vetorial para cruzamento de linha

**Facial:**
- `insightface` `buffalo_l` executando em CPU (`ctx_id=-1`)
- Embeddings ArcFace pré-computados na memória por tenant
- Recarga via queue `persons.updated`
- Similaridade coseno (`np.dot` em vetores normalizados)

**Heatmap:**
- Centroids normalizados armazenados em Redis list (max 10.000 pts, TTL 24h)
- `GaussianBlur` sobre mapa acumulado → `applyColorMap(JET)` → salva `{camera_id}.jpg`
- Atualizado a cada `HEATMAP_UPDATE_FRAMES` frames (padrão: 30)

---

## 4. Frontend React

### Stack
- React 18 + TypeScript + Vite
- Tailwind CSS (dark mode only)
- Zustand (auth store + theme store)
- Axios com interceptor de refresh JWT automático
- Recharts (gráficos)
- HLS.js (player de vídeo)
- `@react-google-maps/api` (mapa tático)
- `react-hot-toast` (notificações)
- `date-fns` + `lucide-react`

### Tema Visual
- Dark mode exclusivo, inspirado em Veza/Cluebase
- CSS variables: `--bg #0A0A0F`, `--surface #111118`, `--elevated #1A1A24`, `--border #252530`
- Cor primária (`--accent`) dinâmica via API `/theme/` — branding do revendedor
- Logo do revendedor carregado dinamicamente na sidebar

### Páginas implementadas

| Rota | Componente | Funcionalidades |
|------|-----------|-----------------|
| `/login` | `LoginPage` | JWT login, carrega tema do revendedor |
| `/dashboard` | `DashboardPage` | 5 stat cards, AreaChart 24h, eventos por tipo, cameras recentes |
| `/cameras` | `CamerasPage` | Grid/lista, busca, filtro status, wizard de adição, delete |
| `/cameras/:id` | `CameraDetailPage` | 5 abas: ao vivo, info (edit), ROIs (toggle), eventos, clips |
| `/cameras/:id/roi` | `ROIEditorPage` | Canvas com snapshot, desenho polygon/linha, 12 tipos, salvar/remover |
| `/mosaic` | `MosaicPage` | 6 layouts (1x1→4x4, 1+3, 2+4), select câmera por slot, HLS player |
| `/recordings` | `RecordingsPage` | Timeline 24h, segmentos, player HLS, modal criação de clip |
| `/detections` | `DetectionsPage` | Tabela paginada, 4 filtros, exportação CSV, modal detalhe |
| `/analytics` | `AnalyticsPage` | 5 abas: Visão Geral, Tráfego, Eventos, Heatmap, Filas |
| `/map` | `MapPage` | Google Maps dark style, pins por status/IA, InfoWindow |
| `/persons` | `PersonsPage` | Grid com fotos, upload, CRUD, toggle ativo |
| `/clips` | `ClipsPage` | Grid de clips, player embutido, download, filtros |
| `/users` | `UsersPage` | Tabela com roles, CRUD hierárquico, gerenciamento de permissões |
| `/settings` | `SettingsPage` | Aparência (logo/cor), conta, notificações, info do sistema |

### Componentes reutilizáveis

| Componente | Descrição |
|-----------|-----------|
| `VideoPlayer` | HLS.js com play/pause/mute/fullscreen, loading/error states |
| `CameraCard` | Card com thumbnail, hover overlay, status badge, IA badge |
| `AddCameraWizard` | Wizard 4 etapas: protocolo → conexão → configuração → analíticos |
| `Modal` | Portal-based, ESC/overlay close, tamanhos sm/md/lg/xl/full, footer slot |
| `Badge` | Colorido com variantes: success/warning/danger/info + dot indicator |
| `Spinner` / `PageSpinner` | Loading states |
| `Sidebar` | Colapsível (56px/224px), logo dinâmico, filtro de acesso por role |
| `Header` | Título dinâmico por rota, sino, avatar com nome/role |

### Arquivos de configuração

| Arquivo | Propósito |
|---------|-----------|
| `vite.config.ts` | Alias `@/` → `./src`, proxy `/api` → Django |
| `tailwind.config.js` | CSS variables como cores Tailwind, animações fade-in/slide-in |
| `tsconfig.app.json` | Path alias `@/*` |
| `frontend/Dockerfile` | Multi-stage: Node 20 build → Nginx Alpine serve |
| `frontend/nginx.conf` | SPA fallback, proxy `/api/` → Django, `/hls/` → MediaMTX |
| `frontend/.env.example` | `VITE_GOOGLE_MAPS_KEY`, `VITE_API_URL` |

### Stores (Zustand)

| Store | Estado | Funções |
|-------|--------|---------|
| `authStore` | `user`, `accessToken`, `refreshToken` | `setAuth()`, `logout()`, `isAuthenticated()` |
| `themeStore` | `theme` | `setTheme()` — aplica `--accent` CSS var, favicon, title |

### Permissões (`usePermission`)

```
operator(1) < supervisor(2) < city_admin(3) < reseller_admin(4) < super_admin(5)
```

- `hasRole(role)` — verifica se usuário tem nível ≥ ao role pedido
- Conveniências: `isCityAdmin`, `isSuperAdmin`
- Sidebar e botões filtrados automaticamente por role

---

## 5. Próximos Passos

### P0 — Crítico para funcionar (sem isso o sistema não roda)

1. **`backend-django/.env`** — criar com as variáveis:
   ```
   SECRET_KEY=<chave-django>
   DB_HOST=postgres
   DB_NAME=gtvision
   DB_USER=gtvision
   DB_PASSWORD=gtvision123
   RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
   REDIS_URL=redis://redis:6379/0
   INTERNAL_API_KEY=<chave-interna>
   ALLOWED_HOSTS=*
   DEBUG=False
   MEDIA_ROOT=/app/media
   ```

2. **`backend-fastapi/workers/ai_worker/.env`** — criar com:
   ```
   RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
   REDIS_URL=redis://redis:6379/0
   DJANGO_INTERNAL_URL=http://django:8000
   INTERNAL_API_KEY=<mesma chave acima>
   MODEL_PLATE_DETECTOR=/app/models/plate_detector.pt
   STORAGE_PATH=/app/storage
   AI_DEVICE=cuda
   ```

3. **Modelo YOLO** — colocar `plate_detector.pt` em `D:\VMS (White Label)\models\`

4. **Build da imagem base**:
   ```
   docker build -t ai-base:latest C:\docker-images\ai-base\
   ```

5. **Subir o sistema**:
   ```
   cd "D:\VMS (White Label)\infra"
   docker-compose up --build
   ```

---

### P1 — Funcionalidades importantes pendentes

6. **WebSocket tempo real** — Django Channels para notificações de eventos em tempo real no frontend (toast ao detectar intrusão, LPR, etc.)

7. **Painel de Franquia (Super Admin)** — CRUD de Resellers e Tenants, impersonação com log de auditoria

8. **Licenciamento de câmeras** — limite de câmeras por tenant conforme licença contratada

9. **Relatórios** — PDF/CSV de eventos por período, relatório de uso de storage

10. **Exportação de detecções** — endpoint Django + botão no frontend já está preparado (`detectionService.exportCsv()`)

---

### P2 — Melhorias de qualidade

11. **Testes automatizados** — pytest para Django (cobertura ≥ 85%), pytest para workers

12. **WebSocket no player** — status online/offline em tempo real no mosaico e mapa (sem precisar recarregar)

13. **Notificações push** — WebSocket event → toast no frontend para intrusões/multidões

14. **Rate limiting** — django-ratelimit no login (5 tentativas → bloqueio)

15. **Headers de segurança** — CSP, HSTS no nginx de produção

16. **Cypress E2E** — fluxos críticos: login → câmera → ROI → detecção → clip

17. **CI/CD** — GitHub Actions: build Docker + testes a cada PR

---

### P3 — Infraestrutura de produção

18. **SSL/TLS** — Certbot/Let's Encrypt no nginx

19. **S3/Object Storage** — substituir storage local por S3 para escala horizontal

20. **Kubernetes** — manifests para deploy em cluster (HPA para ai-worker)

21. **Monitoramento** — Prometheus + Grafana para métricas dos workers

22. **Backup** — pg_dump agendado + upload S3

---

## 6. Estrutura de Diretórios Final

```
D:\VMS (White Label)\
├── docs/                       ← Documentação do projeto
│   ├── 01-REQUISITOS.md
│   ├── 02-SYSTEM-DESIGN.md
│   ├── 07-SPRINTS.md
│   └── 08-PROGRESSO-IMPLEMENTADO.md   ← Este arquivo
│
├── infra/
│   ├── docker-compose.yml      ← Orquestra todos os 9 serviços
│   └── mediamtx.yml            ← Configuração do MediaMTX
│
├── backend-django/
│   ├── Dockerfile
│   ├── apps/
│   │   ├── authentication/     ← JWT + multi-tenant
│   │   ├── cameras/            ← Camera + ROI
│   │   ├── detections/         ← AIEvent
│   │   ├── dashboard/          ← Stats + Analytics endpoints
│   │   ├── persons/            ← KnownPerson (facial)
│   │   └── recordings/         ← Segment + Clip
│   └── gtvision/
│       ├── settings/
│       └── urls.py
│
├── backend-fastapi/workers/
│   ├── ai_worker/
│   │   ├── Dockerfile.ai       ← FROM pytorch:2.3.0-cuda12.1-cudnn8-runtime
│   │   └── worker/
│   │       ├── service.py      ← Orquestrador (roteamento por ia_type)
│   │       └── analyzers/
│   │           ├── lpr.py      ← YOLO custom + EasyOCR
│   │           ├── general.py  ← YOLOv8n COCO
│   │           ├── tracking.py ← CentroidTracker + 6 analíticos
│   │           ├── facial.py   ← insightface buffalo_l
│   │           └── heatmap.py  ← Redis accumulation + OpenCV
│   ├── frame_grabber/
│   ├── recorder/
│   ├── clip_builder/
│   └── purge/
│
├── frontend/
│   ├── Dockerfile              ← Node 20 build → Nginx serve
│   ├── nginx.conf              ← SPA fallback + proxy /api/
│   ├── src/
│   │   ├── App.tsx             ← React Router + auth guard
│   │   ├── types/index.ts      ← Todos os tipos TypeScript
│   │   ├── services/api.ts     ← Axios + interceptors + todos os services
│   │   ├── store/              ← Zustand (auth + theme)
│   │   ├── hooks/usePermission.ts
│   │   ├── components/
│   │   │   ├── layout/         ← Sidebar, Header, Layout
│   │   │   ├── ui/             ← Modal, Badge, Spinner
│   │   │   └── camera/         ← VideoPlayer, CameraCard, AddCameraWizard
│   │   └── pages/              ← 14 páginas
│   └── .env.example
│
├── models/                     ← Modelos YOLO (plate_detector.pt)
└── storage/                    ← Segmentos MP4, clips, heatmaps
```

---

## 7. Comandos Úteis

```bash
# Buildar imagem base de IA (uma vez)
docker build -t ai-base:latest C:\docker-images\ai-base\

# Subir todo o sistema
cd "D:\VMS (White Label)\infra"
docker-compose up --build

# Subir apenas o frontend
docker-compose up --build frontend

# Ver logs do AI worker
docker-compose logs -f ai-worker

# Rodar migrations
docker-compose exec django python manage.py migrate

# Criar superusuário
docker-compose exec django python manage.py createsuperuser

# Acesso aos serviços
# Frontend:     http://localhost
# Django Admin: http://localhost/api/admin/
# RabbitMQ UI:  http://localhost:15672 (guest/guest)
# HLS streams:  http://localhost:8888/{stream_key}/index.m3u8
```
