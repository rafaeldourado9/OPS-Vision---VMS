# VMS White Label — Plano de Evolução Arquitetural (10 semanas)

## Contexto

O VMS já tem uma base funcional com 20+ serviços Docker, Frame Grabber HA (3 réplicas, MOG2, Redis cache), YOLO Worker com ByteTrack, LPR (EasyOCR), Facial (InsightFace), 9 workers analíticos CPU, e frontend React completo.

**Problema**: A arquitetura atual não atende os requisitos de produção para highways 24/7 (ALPR), cenas lotadas (facial), e gravação confiável. Analisamos o Viseron e NVRs profissionais (Hikvision, Intelbras) para identificar padrões consolidados que faltam.

**Objetivo**: Elevar o sistema de "funcional" para "production-grade" com foco em ALPR highway-grade (Mercosul), facial em multidões, intrusion/loitering robusto, e infraestrutura de gravação confiável.

---

## Sprint 1: Foundation — Recorder Fix + Detection Masks + Shared Memory (Semanas 1-2)

### Objetivo
Corrigir o recorder quebrado, separar Detection Masks de Analytics Zones (padrão Hikvision/Intelbras), e introduzir shared memory para transporte de frames sem serialização.

### 1.1 Recorder Fix

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T1.1.1 | Debug startup: log completo do comando FFmpeg e URL RTSP | `workers/recorder/worker/service.py` |
| T1.1.2 | Declarar queues antes de consumir + depends_on com healthcheck | `workers/recorder/worker/service.py`, `infra/docker-compose.yml` |
| T1.1.3 | Verificar/criar endpoint interno de registro de segmentos | `backend-django/apps/segments/views.py`, `urls.py` |
| T1.1.4 | Reduzir duração de segmento para 30-60s (env `SEGMENT_DURATION`) | `workers/recorder/worker/service.py` |
| T1.1.5 | Health probe FFmpeg: se não produz output em 30s, restart com backoff | `workers/recorder/worker/service.py` |

### 1.2 Detection Masks (Separação de Conceitos)

**Padrão NVR profissional**: Máscaras definem onde IGNORAR (céu, TVs, árvores). ROIs definem onde ANALISAR.

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T1.2.1 | Modelo `DetectionMask` (tenant, camera, polygon, active) | `backend-django/apps/cameras/models.py` + migration |
| T1.2.2 | CRUD API (ViewSet + Serializer) | `backend-django/apps/cameras/views.py`, `serializers.py` |
| T1.2.3 | Incluir masks em mensagens `roi.updated` | `backend-django/apps/roi/views.py` |
| T1.2.4 | Frame Grabber aplica masks (cv2.fillPoly preto) antes de publicar | `workers/frame_grabber/worker/service.py` |
| T1.2.5 | Frontend: aba "Masks" no ROI Editor (polígonos vermelhos) | `frontend/src/pages/ROIEditorPage.tsx` |

### 1.3 Shared Memory Frame Store

**Inspiração Viseron**: `shared_frames.py` usa `multiprocessing.shared_memory`. Docker `ipc: host`. Feature flag `USE_SHARED_MEMORY=1` com fallback Redis.

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T1.3.1 | Classe `SharedFrameStore` (ring buffer, refcount via Redis, cleanup TTL) | `workers/common/shared_memory.py` (novo) |
| T1.3.2 | Frame Grabber: escrever numpy em shm, publicar `shm_name`+`shape`+`dtype` | `workers/frame_grabber/worker/service.py` |
| T1.3.3 | Universal frame loader: shm → Redis → disco (fallback chain) | `workers/common/shared_memory.py`, `workers/frame_grabber/worker/frame_cache.py` |
| T1.3.4 | Docker IPC: `ipc: host` em todos os workers | `infra/docker-compose.yml` |

### Critérios de Aceite
- Recorder gera segmentos `.mp4` e registra no Django
- Masks criáveis via API e visíveis no frontend
- Frame Grabber aplica masks (regiões pretas) antes de publicar
- Shared memory funciona com flag ativada, Redis como fallback

---

## Sprint 2: ALPR Highway-Grade Mercosul (Semanas 3-4)

### Objetivo
Substituir EasyOCR por PaddleOCR (3-5x mais rápido), validação Mercosul, tracking multi-placa, detecção de direção, e integração com banco de veículos.

### 2.1 OCR Engine: EasyOCR → PaddleOCR

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T2.1.1 | Substituir EasyOCR por PaddleOCR (`use_gpu=True`, batch) | `workers/lpr_worker/worker/service.py` |
| T2.1.2 | Atualizar Dockerfile e requirements | `workers/lpr_worker/Dockerfile.worker`, `requirements.txt` |

### 2.2 Validação Mercosul + Correção OCR

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T2.2.1 | Módulo `PlateValidator`: regex Mercosul `^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$`, correção OCR (O→0, I→1, B→8, S→5) | `workers/lpr_worker/worker/plate_validator.py` (novo) |
| T2.2.2 | Integrar validator no pipeline LPR, rejeitar placas inválidas | `workers/lpr_worker/worker/service.py` |

### 2.3 Multi-Plate Tracking + Direção

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T2.3.1 | Tracking por IoU de bounding boxes entre frames, evento só após 2+ confirmações | `workers/lpr_worker/worker/service.py` |
| T2.3.2 | Detecção de direção (entry/exit) por movimento Y do bbox | `workers/lpr_worker/worker/service.py` |

### 2.4 Banco de Veículos (Allow/Blocklist)

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T2.4.1 | Modelos `VehicleList` + `VehicleEntry` (plate, owner, type) | `backend-django/apps/detections/models.py` + migration |
| T2.4.2 | CRUD API para listas de veículos | `backend-django/apps/detections/views.py`, `serializers.py` |
| T2.4.3 | LPR worker: cache listas em memória, `alert_level: critical` para blocklist | `workers/lpr_worker/worker/service.py` |
| T2.4.4 | Signal `vehicles.updated` → reload cache no worker | `backend-django/apps/detections/signals.py` |

### 2.5 Snapshots Aprimorados

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T2.5.1 | Salvar frame completo (com bbox overlay) + crop da placa | `workers/lpr_worker/worker/service.py` |

### Critérios de Aceite
- PaddleOCR: <25ms/placa em GPU
- Placas Mercosul validadas com correção OCR, accuracy >95%
- Multi-placa: eventos só para placas confirmadas em 2+ frames
- Direção entry/exit corretamente detectada
- CRUD de listas de veículos funcional; LPR worker faz match
- Latência end-to-end LPR <500ms/frame

---

## Sprint 3: Facial Recognition para Multidões (Semanas 5-6)

### Objetivo
Otimizar facial para cenários lotados: batch processing, quality scoring, galeria de desconhecidos com clustering, API de busca por foto, re-ID multi-câmera.

### 3.1 Batch Face Processing

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T3.1.1 | Batch inference: todos os embeddings em single forward pass, 10+ faces <300ms | `workers/facial_worker/worker/analyzers/facial.py` |
| T3.1.2 | Reduzir face mínima, upscaling para faces <112x112px | `workers/facial_worker/worker/analyzers/facial.py` |

### 3.2 Face Quality Scoring

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T3.2.1 | Módulo quality: blur (Laplacian), ângulo, oclusão, tamanho → score 0-1 | `workers/facial_worker/worker/analyzers/quality.py` (novo) |
| T3.2.2 | Filtrar faces low-quality antes do matching; manter melhor face por track_id | `workers/facial_worker/worker/analyzers/facial.py` |

### 3.3 Galeria de Desconhecidos + Clustering

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T3.3.1 | Modelo `UnknownFace` (embedding, snapshot, quality, cluster_id) | `backend-django/apps/persons/models.py` + migration |
| T3.3.2 | Worker salva faces desconhecidas com quality >0.5 | `workers/facial_worker/worker/service.py` |
| T3.3.3 | Management command clustering periódico (DBSCAN) | `backend-django/apps/persons/management/commands/cluster_faces.py` (novo) |
| T3.3.4 | Frontend: aba "Desconhecidos" com clusters, botão "Promover" | `frontend/src/pages/PersonsPage.tsx` |

### 3.4 API de Busca por Foto

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T3.4.1 | Endpoint: upload foto → extrair embedding → buscar nos UnknownFace | `backend-django/apps/persons/views.py` |
| T3.4.2 | Facial worker: consumir queue `facial.search`, retornar top-N | `workers/facial_worker/worker/service.py` |
| T3.4.3 | Frontend: botão "Buscar Pessoa", upload foto, timeline | `frontend/src/pages/PersonsPage.tsx` |

### 3.5 Re-ID Multi-Câmera

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T3.5.1 | Cross-camera tracking via Redis: `{person_id: [(camera, timestamp)]}` | `workers/facial_worker/worker/service.py` |
| T3.5.2 | Novo event type `facial_reidentification` | `backend-django/apps/detections/models.py` |

### Critérios de Aceite
- 10+ faces simultâneas processadas em <300ms/frame
- Quality scoring reduz false matches em >50%
- Galeria de desconhecidos com clusters visíveis no frontend
- Busca por foto retorna aparições com >90% recall
- Re-ID cross-camera vincula mesma pessoa entre 2+ câmeras

---

## Sprint 4: Intrusion/Loitering Robusto + Lookback Recording (Semanas 7-8)

### Objetivo
Ativação por horário, ações de alarme (webhook/email), níveis de sensibilidade, anti-falso-positivo, e gravação com pre-buffer (lookback).

### 4.1 Ativação por Horário (Schedule)

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T4.1.1 | Campo `schedule` no `config` do ROI (dias, horários, timezone) | `backend-django/apps/roi/models.py` |
| T4.1.2 | Método `is_active(roi)` no BaseAnalyticWorker | `workers/analytic_workers/base.py` |
| T4.1.3 | Frontend: campos de horário no config de intrusion/loitering | `frontend/src/pages/ROIEditorPage.tsx` |

### 4.2 Ações de Alarme

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T4.2.1 | Modelo `AlarmAction` (event_types, action_type, config, cooldown) | `backend-django/apps/detections/models.py` + migration |
| T4.2.2 | Dispatcher no event consumer: webhook POST, email async, cooldown Redis | `backend-django/apps/detections/consumer.py` |
| T4.2.3 | CRUD API para alarm actions | `backend-django/apps/detections/views.py`, `serializers.py` |
| T4.2.4 | Frontend: seção "Alarmes" no Settings com teste de webhook | `frontend/src/pages/SettingsPage.tsx` |

### 4.3 Sensibilidade + Anti-Falso-Positivo

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T4.3.1 | Mapeamento sensitivity → confidence (low=0.7, medium=0.5, high=0.3) | `workers/analytic_workers/intrusion.py`, `loitering.py` |
| T4.3.2 | Dwell time mínimo antes de alertar (3 frames = 3s a 1 FPS) | `workers/analytic_workers/intrusion.py` |
| T4.3.3 | Frontend: selector de sensibilidade (Baixa/Média/Alta) | `frontend/src/pages/ROIEditorPage.tsx` |

### 4.4 Lookback / Pre-Buffer Recording

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T4.4.1 | Clip builder: buscar segmentos cobrindo `detected_at - 10s` a `+5s`, concatenar FFmpeg | `workers/clip_builder/worker/service.py` |
| T4.4.2 | Event consumer: publicar `clip.create` para eventos prioritários | `backend-django/apps/detections/consumer.py` |
| T4.4.3 | Vincular clips aos eventos (FK nullable no AIEvent) | `backend-django/apps/detections/models.py` + migration |
| T4.4.4 | Frontend: botão "Ver Clip" nos eventos com playback | `frontend/src/pages/DetectionsPage.tsx` |

### Critérios de Aceite
- Intrusion com schedule só dispara em horários configurados
- Webhooks disparam em <5s após detecção
- Sensibilidade filtra por confidence; dwell time reduz falsos em >60%
- Clips com 10s pre-buffer criados automaticamente
- Clips reproduzíveis no frontend

---

## Sprint 5: Integração, Performance, Monitoring (Semanas 9-10)

### Objetivo
Testes end-to-end, tuning para 500 câmeras, dashboards Grafana, alerting Prometheus, hardening.

### 5.1 Performance Tuning

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T5.1.1 | Event consumer async: `aio_pika` + batch inserts (300+ evt/s) | `backend-django/apps/detections/consumer.py` |
| T5.1.2 | YOLO batch inference: acumular N frames (2-4x throughput) | `workers/yolo_worker/worker/service.py` |
| T5.1.3 | Redis connection pooling compartilhado | `workers/common/redis_pool.py` (novo) |
| T5.1.4 | RabbitMQ prefetch tuning: GPU=2, CPU=16, consumer=64 | Todos os workers |

### 5.2 Monitoring

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T5.2.1 | Dashboard Grafana: Pipeline Overview | `infra/grafana/dashboards/pipeline-overview.json` |
| T5.2.2 | Dashboard Grafana: ALPR Analytics | `infra/grafana/dashboards/alpr-analytics.json` |
| T5.2.3 | Dashboard Grafana: System Resources | `infra/grafana/dashboards/system-resources.json` |
| T5.2.4 | Alertas Prometheus | `infra/prometheus/alerts.yml` |

### 5.3 Production Hardening

| ID | Tarefa | Arquivo |
|----|--------|---------|
| T5.3.1 | Backpressure: skip frames se queue depth > threshold | `workers/frame_grabber/worker/service.py` |
| T5.3.2 | Healthchecks Docker em TODOS os workers (HTTP :9100/health) | `infra/docker-compose.yml` |
| T5.3.3 | Índices compostos no PostgreSQL | `backend-django/apps/segments/models.py`, `detections/models.py` |
| T5.3.4 | Script de teste E2E | `tests/integration/test_pipeline.py` (novo) |

### Critérios de Aceite
- Event consumer sustenta 300+ eventos/s
- Dashboards Grafana com métricas real-time
- Alertas Prometheus disparam corretamente
- Healthchecks em todos os workers com auto-restart
- Teste E2E passa em <60s
- Sistema suporta 50 câmeras LPR + 100 analytics com latência <2s

---

## Resumo

| Sprint | Semanas | Foco | Entregas Chave |
|--------|---------|------|----------------|
| 1 | 1-2 | Foundation | Recorder fix, detection masks, shared memory |
| 2 | 3-4 | ALPR | PaddleOCR, Mercosul, vehicle lists, direction |
| 3 | 5-6 | Facial | Batch, quality score, unknown gallery, search, re-ID |
| 4 | 7-8 | Intrusion/Recording | Schedule, alarms, sensitivity, lookback clips |
| 5 | 9-10 | Integração | Performance, monitoring, hardening, E2E tests |

**Novos arquivos**: ~25 Python, ~5 TypeScript, ~3 JSON (Grafana)
**Arquivos modificados**: ~30 existentes
**Novos modelos Django**: 5 (DetectionMask, VehicleList, VehicleEntry, AlarmAction, UnknownFace)
**Novas queues RabbitMQ**: 3 (facial.search, clip.create, vehicles.updated)

---

## Progresso de Implementação

### Sprint 1.1 — Recorder Fix ✅
- `workers/recorder/worker/service.py` reescrito
- Logging FFmpeg completo, `SEGMENT_DURATION` via env (60s), health probe com backoff exponencial
- Retry no registro de segmentos, queues declaradas antes de consumir
- `docker-compose.yml`: healthcheck + `depends_on: django`

### Sprint 1.2 — Detection Masks 🔄
- **Backend ✅**: Modelo `DetectionMask` + migration, serializer, ViewSet CRUD, URL `/api/v1/detection-masks/`
- **Signals ✅**: `roi.updated` inclui `masks` na mensagem RabbitMQ
- **Frame Grabber ✅**: Recebe masks, aplica `cv2.fillPoly` preto antes de publicar
- **Frontend API ✅**: `maskService` adicionado em `api.ts`
- **Frontend UI ❌**: Aba "Masks" no ROI Editor (polígonos vermelhos) — pendente

### Sprint 1.3 — Shared Memory ❌ Pendente
### Sprint 2 — ALPR ❌ Pendente
### Sprint 3 — Facial ❌ Pendente
### Sprint 4 — Intrusion/Lookback ❌ Pendente
### Sprint 5 — Performance/Monitoring ❌ Pendente
