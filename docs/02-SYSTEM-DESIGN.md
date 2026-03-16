# 02 — GT-Vision · System Design
**Arquitetura do Sistema VMS Urbano com IA — White Label · v1.0**

> **Diretório do projeto:** `D:\VMS (White Label)`
> **Imagem Docker base para workers de IA:** `ai-base:latest` (localizada em `C:\docker-images\ai-base\`)
> Os workers de IA do VMS estendem diretamente a `ai-base` — não há dependência de serviço externo de IA.

---

## 1. Visão Geral da Arquitetura

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        GT-Vision — Arquitetura Geral                       │
│                                                                            │
│  Câmeras IP (RTSP/RTMP)                                                    │
│       │                                                                    │
│       ▼                                                                    │
│  ┌─────────────┐     ┌──────────────────────────────────────────────────┐ │
│  │  MediaMTX   │────►│              FastAPI Workers                     │ │
│  │ (Ingestão   │     │  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │ │
│  │  RTSP/RTMP  │     │  │ Recorder │  │  Frame   │  │   AI Worker   │  │ │
│  │  WebRTC HLS)│     │  │  Worker  │  │ Grabber  │  │  (LPR, etc.)  │  │ │
│  └──────┬──────┘     │  └────┬─────┘  └────┬─────┘  └──────┬────────┘  │ │
│         │            │       │              │               │            │ │
│         │            └───────┼──────────────┼───────────────┼────────────┘ │
│         │                    │              │               │            │
│         │             ┌──────▼──────────────▼───────────────▼──────┐    │
│         │             │               RabbitMQ                      │    │
│         │             │  [recording] [ai.events] [clips] [notify]   │    │
│         │             └──────────────────────────────────────────────┘    │
│         │                                                            │
│  ┌──────▼──────┐     ┌──────────────┐    ┌────────────────────────┐ │
│  │  Storage    │     │   Django     │    │   Frontend             │ │
│  │  (MP4 segs) │     │  (Admin/Auth │◄──►│  Vue 3 / React         │ │
│  │  (Clips)    │     │   REST API   │    │  TailwindCSS            │ │
│  │  (Snapshots)│     │   WebSocket) │    │  White Label Theme      │ │
│  └─────────────┘     └──────┬───────┘    └────────────────────────┘ │
│                             │                                         │
│                      ┌──────┴──────┐                                  │
│                      │ PostgreSQL  │  ┌──────────┐                    │
│                      │  (Dados     │  │  Redis   │                    │
│                      │   + Tenant) │  │ (Cache / │                    │
│                      └─────────────┘  │  Session)│                    │
│                                       └──────────┘                    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Componentes e Responsabilidades

### 2.1 Frontend (Vue 3 + TailwindCSS)

**Responsabilidade:** Interface do operador e do administrador da cidade.

**Módulos:**
- Resolução de tema white label ao iniciar (`/api/v1/theme` via host header)
- Mapa tático (Leaflet.js)
- Player WebRTC / HLS
- Canvas ROI (Fabric.js ou Konva.js)
- Dashboard de detecções
- Painel de gestão

**Comunicação:**
- REST API Django para dados
- WebSocket Django para notificações em tempo real
- WebRTC direto com MediaMTX para vídeo ao vivo

---

### 2.2 Django (Backend Principal)

**Responsabilidade:** Regras de negócio, autenticação, REST API, Admin.

**Apps Django:**
```
apps/
  auth_app/         → login, JWT, RBAC, recuperação de senha
  tenants/          → modelo Tenant, middleware multi-tenant
  resellers/        → modelo Reseller, white label config
  cameras/          → CRUD câmeras, status, ROI
  recordings/       → metadados de segmentos e clipes
  detections/       → eventos de IA (LPR, etc.)
  reports/          → geração de relatórios PDF/CSV
  notifications/    → WebSocket consumers (Django Channels)
  franchise/        → painel master, licenças
```

**Middlewares obrigatórios:**
- `TenantMiddleware` — resolve `tenant_id` pelo host header e injeta em `request.tenant`
- `WhiteLabelMiddleware` — resolve `Reseller` pelo host e injeta tema em `request.reseller`

---

### 2.3 FastAPI (Backend Assíncrono)

**Responsabilidade:** Workers de processamento de vídeo e IA — todos rodando on-premise, sem serviço externo.

**Separação de imagens Docker:**

```
workers/
  recorder/      → Dockerfile.worker   (python:3.11-slim + ffmpeg)
  frame_grabber/ → Dockerfile.worker   (python:3.11-slim + ffmpeg)
  clip_builder/  → Dockerfile.worker   (python:3.11-slim + ffmpeg)
  purge/         → Dockerfile.worker   (python:3.11-slim + ffmpeg)
  ai_worker/     → Dockerfile.ai       (FROM ai-base:latest ← C:\docker-images\ai-base\)
```

**Por que ai_worker usa imagem separada:**
A `ai-base:latest` já inclui PyTorch, OpenCV, ONNX Runtime e Ultralytics (YOLOv8).
Os outros workers só precisam de FFmpeg — não faz sentido carregar PyTorch neles.

**O ai_worker é 100% on-premise:**
- Carrega modelo `.pt` / `.onnx` / `.torchscript` do storage local
- Processa frames via GPU/CPU local
- Publica resultados no RabbitMQ interno
- Zero chamadas para APIs externas de IA

**Comunicação:**
- Consome e publica em filas RabbitMQ
- Publica eventos no Django via HTTP interno (`/api/v1/internal/`)
- Lê configuração de ROI do PostgreSQL

---

### 2.4 MediaMTX

**Responsabilidade:** Ingestão e redistribuição de streams de vídeo.

**Paths configurados:**
```
/live/{tenant_id}/{camera_id}    → stream ao vivo WebRTC/HLS
/rtmp/{tenant_id}/{stream_key}   → ingestão RTMP de câmeras
/record/{tenant_id}/{camera_id}  → stream para recorder worker
```

**Protocolos suportados:**
- Entrada: RTSP, RTMP
- Saída: WebRTC (latência < 500ms), HLS (playback)

---

### 2.5 RabbitMQ — Filas

| Fila | Produtor | Consumidor | Payload |
|---|---|---|---|
| `recording.start` | Django (ao ativar câmera) | Recorder Worker | `{camera_id, tenant_id, stream_url}` |
| `recording.stop` | Django (ao desativar câmera) | Recorder Worker | `{camera_id}` |
| `ai.frame` | Frame Grabber | AI Worker | `{camera_id, tenant_id, frame_path, roi}` |
| `ai.events` | AI Worker | Django Consumer | `{camera_id, tenant_id, event_type, data}` |
| `clip.request` | Django (usuário solicita clipe) | Clip Builder | `{camera_id, tenant_id, start, end, user_id}` |
| `clip.ready` | Clip Builder | Django Consumer | `{clip_id, path, user_id}` |
| `notify.operator` | Django Consumer | WebSocket Broadcaster | `{tenant_id, message, event}` |
| `purge.segments` | Scheduler (diário) | Purge Worker | `{tenant_id}` |

---

### 2.6 PostgreSQL — Modelo de Dados

#### Tabelas Principais

```sql
-- Revendedor (White Label)
resellers (
  id UUID PK,
  name VARCHAR,
  slug VARCHAR UNIQUE,           -- usado na resolução por domínio
  primary_color VARCHAR,
  secondary_color VARCHAR,
  logo_url VARCHAR,
  favicon_url VARCHAR,
  custom_domain VARCHAR UNIQUE,  -- ex: app.cidadesegura.com.br
  terms_url VARCHAR,
  privacy_url VARCHAR,
  dark_mode_default BOOLEAN,
  active BOOLEAN,
  created_at TIMESTAMP
)

-- Licença
licenses (
  id UUID PK,
  reseller_id UUID FK resellers,
  max_cameras INTEGER,
  valid_until DATE,
  active BOOLEAN
)

-- Tenant (Instância de Cidade)
tenants (
  id UUID PK,
  reseller_id UUID FK resellers,
  license_id UUID FK licenses,
  name VARCHAR,
  subdomain VARCHAR UNIQUE,
  active BOOLEAN,
  created_at TIMESTAMP
)

-- Usuários
users (
  id UUID PK,
  tenant_id UUID FK tenants,
  email VARCHAR,
  password_hash VARCHAR,
  role VARCHAR,   -- operator|supervisor|city_admin|reseller_admin|super_admin
  active BOOLEAN,
  last_login TIMESTAMP
)

-- Câmeras
cameras (
  id UUID PK,
  tenant_id UUID FK tenants,
  name VARCHAR,
  address VARCHAR,
  latitude DECIMAL,
  longitude DECIMAL,
  stream_protocol VARCHAR,   -- rtsp|rtmp
  stream_url VARCHAR,
  stream_key VARCHAR,        -- para RTMP
  retention_days INTEGER,    -- 7|15|30
  ia_enabled BOOLEAN,
  ia_status VARCHAR,         -- disabled|ia_pending|active
  online BOOLEAN,
  last_seen TIMESTAMP,
  created_at TIMESTAMP
)

-- ROI (Zonas de Interesse)
regions_of_interest (
  id UUID PK,
  tenant_id UUID FK tenants,
  camera_id UUID FK cameras,
  name VARCHAR,
  polygon JSONB,             -- [[x,y], [x,y], ...]
  ia_type VARCHAR,           -- lpr|intrusion|crowd
  active BOOLEAN,
  created_at TIMESTAMP
)

-- Segmentos de Gravação
recording_segments (
  id UUID PK,
  tenant_id UUID FK tenants,
  camera_id UUID FK cameras,
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  duration_seconds INTEGER,
  file_path VARCHAR,
  file_size_bytes BIGINT,
  expires_at TIMESTAMP,      -- calculado com base em retention_days
  created_at TIMESTAMP
)

-- Clipes Manuais
clips (
  id UUID PK,
  tenant_id UUID FK tenants,
  camera_id UUID FK cameras,
  created_by UUID FK users,
  started_at TIMESTAMP,
  ended_at TIMESTAMP,
  file_path VARCHAR,
  file_size_bytes BIGINT,
  status VARCHAR,            -- processing|ready|error
  created_at TIMESTAMP
)

-- Eventos de IA (Detecções)
ai_events (
  id UUID PK,
  tenant_id UUID FK tenants,
  camera_id UUID FK cameras,
  roi_id UUID FK regions_of_interest,
  event_type VARCHAR,        -- lpr|intrusion|crowd
  snapshot_path VARCHAR,
  event_data JSONB,          -- {plate, model, color, confidence, ...}
  detected_at TIMESTAMP,
  created_at TIMESTAMP
)
```

#### Índices Críticos
```sql
CREATE INDEX idx_cameras_tenant ON cameras(tenant_id);
CREATE INDEX idx_segments_tenant_camera ON recording_segments(tenant_id, camera_id);
CREATE INDEX idx_segments_expires ON recording_segments(expires_at);
CREATE INDEX idx_events_tenant ON ai_events(tenant_id, detected_at DESC);
CREATE INDEX idx_clips_tenant ON clips(tenant_id);
```

---

### 2.7 Redis

| Key Pattern | Uso | TTL |
|---|---|---|
| `wl:{host}` | Config white label por domínio | 5 min |
| `session:{user_id}` | Dados de sessão JWT | 7 dias |
| `camera:thumb:{camera_id}` | Thumbnail mais recente | 60s |
| `tenant:stats:{tenant_id}` | Contadores do dashboard | 30s |
| `rate_limit:login:{email}` | Controle de tentativas de login | 15 min |

---

## 3. Pipeline de Vídeo

### 3.1 Gravação 24/7
```
Câmera RTSP/RTMP
      │
      ▼
  MediaMTX
  (restream para /record/{tenant}/{camera})
      │
      ▼
  Recorder Worker (FastAPI)
  - Lê stream HLS de MediaMTX
  - Segmenta em MP4 de 10min com FFmpeg
  - Salva no storage
  - Insere metadado em recording_segments
  - Calcula expires_at conforme retention_days
```

### 3.2 Live View (WebRTC)
```
Câmera RTSP/RTMP
      │
      ▼
  MediaMTX
  (transcodifica para WebRTC)
      │
      ▼
  Frontend (WebRTC via WHEP)
  Latência < 500ms
```

### 3.3 Pipeline de IA (On-Premise)

```
Câmera → MediaMTX
              │
              ▼
        Frame Grabber Worker
        (captura 1 frame/segundo via OpenCV)
              │
              ▼
        Fila: ai.frame (RabbitMQ)
        payload: {camera_id, tenant_id, frame_path, roi_polygon}
              │
              ▼
        AI Worker  ← container baseado em ai-base:latest
        ┌─────────────────────────────────────────────┐
        │  • Carrega modelo local (.pt/.onnx)          │
        │  • Crop do frame no polígono ROI             │
        │  • Inferência YOLOv8 via Ultralytics/ONNX    │
        │  • Dedup via Redis TTL (evita evento duplo)  │
        │  • Se detecção: salva snapshot + evento      │
        └─────────────────────────────────────────────┘
              │
              ▼
        Fila: ai.events (RabbitMQ)
              │
              ▼
        Django Consumer
        - Persiste em ai_events
        - Notifica operadores via WebSocket
```

**Dependências do ai_worker (herdadas da ai-base):**
```
torch + torchvision  → inferência TorchScript
opencv-python-headless → leitura e crop de frames
onnxruntime          → inferência ONNX (alternativa ao TorchScript)
ultralytics          → API YOLOv8 (treino + exportação + inferência)
numpy                → manipulação de arrays/polígonos
redis                → dedup de eventos (TTL por câmera+placa)
httpx                → comunicação interna com Django API
ffmpeg (sistema)     → disponível na imagem base
```

---

## 4. Resolução White Label

```
Requisição HTTP chega com Host: saopaulo.cidadesegura.com.br
        │
        ▼
TenantMiddleware (Django)
- Consulta Redis: GET wl:saopaulo.cidadesegura.com.br
- Cache miss → consulta PostgreSQL: SELECT reseller, tenant WHERE domain = host
- Armazena no Redis com TTL 5min
- Injeta request.tenant e request.reseller
        │
        ▼
WhiteLabelMiddleware
- Injeta request.theme = {primary_color, logo_url, ...}
        │
        ▼
Frontend recebe tema via /api/v1/theme
- Aplica CSS variables: --color-primary, --color-secondary
- Substitui logo e favicon dinamicamente
```

---

## 5. Estrutura de Diretórios do Projeto

> **Raiz do projeto:** `D:\VMS (White Label)\`

```
D:\VMS (White Label)\
│
├── backend-django/
│   ├── config/               # settings, urls, wsgi, asgi
│   ├── apps/
│   │   ├── auth_app/
│   │   ├── tenants/
│   │   ├── resellers/        # white label
│   │   ├── cameras/
│   │   ├── recordings/
│   │   ├── detections/
│   │   ├── reports/
│   │   ├── notifications/    # Django Channels
│   │   └── franchise/
│   ├── middleware/
│   │   ├── tenant.py
│   │   └── white_label.py
│   ├── Dockerfile            # python:3.11-slim
│   └── requirements.txt
│
├── backend-fastapi/
│   ├── workers/
│   │   ├── recorder/
│   │   │   └── Dockerfile.worker   # python:3.11-slim + ffmpeg
│   │   ├── frame_grabber/
│   │   │   └── Dockerfile.worker
│   │   ├── ai_worker/
│   │   │   └── Dockerfile.ai       # FROM ai-base:latest
│   │   ├── clip_builder/
│   │   │   └── Dockerfile.worker
│   │   └── purge/
│   │       └── Dockerfile.worker
│   ├── core/
│   │   ├── rabbitmq.py
│   │   ├── storage.py
│   │   └── ffmpeg.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── composables/
│   │   │   └── useWhiteLabel.js
│   │   ├── views/
│   │   │   ├── Dashboard.vue
│   │   │   ├── Cameras.vue
│   │   │   ├── Player.vue
│   │   │   ├── Detections.vue
│   │   │   ├── ROI.vue
│   │   │   └── Management.vue
│   │   └── components/
│   └── tailwind.config.js
│
├── media-server/
│   └── mediamtx.yml
│
├── models/                   # modelos de IA (.pt, .onnx, .torchscript)
│   ├── plate_detector.pt
│   └── char_recognizer.pt
│
├── infra/
│   ├── docker-compose.yml    # referencia ai-base:latest
│   ├── docker-compose.dev.yml
│   ├── nginx/
│   └── kubernetes/           # para escala
│
└── docs/
    └── kit/                  # este kit
```

---

## 6. Infraestrutura Recomendada (Produção — 300 câmeras)

| Serviço | Imagem Base | CPU | RAM | Disco | Observação |
|---|---|---|---|---|---|
| Django | python:3.11-slim | 4 vCPU | 8 GB | 50 GB | Horizontal com load balancer |
| Workers (recorder/grabber/clip/purge) | python:3.11-slim + ffmpeg | 8 vCPU | 16 GB | — | 1 instância por 50 câmeras |
| **AI Worker (LPR/IA)** | **ai-base:latest** | **8 vCPU** | **16 GB** | **—** | **GPU opcional — 1 inst. por 50 câmeras com IA** |
| MediaMTX | mediamtx oficial | 8 vCPU | 16 GB | — | 1 instância por 100 câmeras |
| PostgreSQL | postgres:15 | 4 vCPU | 16 GB | 200 GB SSD | Com réplica de leitura |
| Redis | redis:7-alpine | 2 vCPU | 4 GB | — | Redis Sentinel para HA |
| RabbitMQ | rabbitmq:3-management | 2 vCPU | 4 GB | 20 GB | Cluster de 3 nós |
| Storage (MP4) | — | — | — | 20 TB | Object Storage (S3-compatible) |

> **Nota sobre ai-base:** A imagem `ai-base:latest` está em `C:\docker-images\ai-base\` e deve ser buildada localmente antes do `docker-compose up`. Ver seção de docker-compose no `04-PROMPT-ENGINEERING-KIT.md`.
