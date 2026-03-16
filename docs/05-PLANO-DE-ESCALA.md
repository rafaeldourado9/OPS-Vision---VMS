# 05 — GT-Vision · Plano de Escala
**Infraestrutura e Estratégia de Escalabilidade · v1.0**

---

## 1. Fases de Crescimento

```
Fase 1 — Startup       →  até 300 câmeras   (1 cidade piloto)
Fase 2 — Expansão      →  até 500 câmeras   (2-3 cidades)
Fase 3 — Regional      →  até 1.500 câmeras (10+ cidades)
Fase 4 — Nacional      →  5.000+ câmeras    (50+ cidades)
```

---

## 2. Fase 1 — 300 Câmeras (Piloto)

### Topologia
```
Servidor Único (ou 2 VMs)

VM-1 (Aplicação):
├── Nginx (reverse proxy + SSL termination)
├── Django (Gunicorn, 4 workers)
├── FastAPI Workers (recorder × 6, ai_worker × 2, frame_grabber × 2)
└── Frontend (static files via Nginx)

VM-2 (Dados + Media):
├── MediaMTX (1 instância — até 300 streams RTSP/RTMP)
├── PostgreSQL 15
├── Redis 7
└── RabbitMQ 3.12

Storage:
└── NFS / S3-compatible (MinIO on-prem ou AWS S3)
```

### Dimensionamento de Workers Fase 1
```
Gravação contínua:
- 300 câmeras ÷ 50 câmeras/worker = 6 Recorder Workers

IA (LPR):
- Assumindo 30% das câmeras com IA = 90 câmeras
- 1 GPU mid-range processa ~20 câmeras em tempo real
- 2 AI Workers com GPU (ou 5 workers CPU se sem GPU)

Frame Grabber:
- 1 frame/segundo × 90 câmeras = 90 frames/s
- 2 Frame Grabber Workers

MediaMTX:
- 1 instância suporta 300 streams RTSP + WebRTC com 8 vCPU / 16 GB RAM
```

### Estimativa de Storage — Fase 1
```
Bitrate médio por câmera: 2 Mbps (1080p H.264)
Por câmera por dia: 2 Mbps × 86.400s ÷ 8 ÷ 1024 = ~21 GB/dia

Distribuição de retenção (assumindo):
- 40% câmeras × 30 dias: 120 câmeras × 21 GB × 30 = 75.600 GB
- 40% câmeras × 15 dias: 120 câmeras × 21 GB × 15 = 37.800 GB
- 20% câmeras × 7 dias:   60 câmeras × 21 GB ×  7 =  8.820 GB
                                          TOTAL ≈ 122 TB

Recomendação: 150 TB de storage (com 25% de margem)
Compressão H.265 reduz em ~50%: efetivo ~75 TB

Clipes e snapshots: +5 TB estimado
```

### Custo Estimado Fase 1 (Cloud)
| Recurso | Especificação | Custo/mês estimado |
|---|---|---|
| VM Aplicação | 8 vCPU, 32 GB RAM | ~$400 |
| VM Media/Dados | 16 vCPU, 64 GB RAM | ~$800 |
| VM AI Workers (GPU) | NVIDIA T4, 16 GB RAM | ~$500 |
| Storage S3 | 150 TB | ~$3.450 |
| Bandwidth egress | ~50 TB/mês | ~$4.500 |
| **Total estimado** | | **~$9.650/mês** |

---

## 3. Fase 2 — 500 Câmeras (2-3 Cidades)

### Mudanças na Arquitetura
```
Separação de serviços:
- Django: 2 instâncias com load balancer (Nginx ou HAProxy)
- FastAPI Workers: escalonado horizontalmente por cidade
- MediaMTX: 1 instância por cidade (500 câmeras = 2 instâncias de 250)
- PostgreSQL: primário + réplica de leitura
- Redis: Redis Sentinel (3 nós) para HA
- RabbitMQ: cluster de 3 nós

Novo componente:
- Celery Beat: agendamento de tarefas (purge diário, relatórios)
```

### Configuração MediaMTX para Multi-Cidade
```yaml
# mediamtx-cidade-sp.yml
paths:
  "live/{tenant_id}/{camera_id}":
    source: publisher
    maxReaders: 100

# Cada cidade tem seu próprio MediaMTX
# Roteado por subdomínio via Nginx
# rtsp.saopaulo.cidadesegura.com.br → MediaMTX-SP
# rtsp.rio.cidadesegura.com.br      → MediaMTX-RJ
```

---

## 4. Fase 3 — 1.500 Câmeras (10+ Cidades)

### Arquitetura Kubernetes
```
Namespace por cidade (tenant isolation):

namespace: tenant-saopaulo
├── deployment/django (3 replicas)
├── deployment/fastapi-workers (autoscaled)
├── deployment/mediamtx (2 replicas)
└── pvc/storage (via StorageClass S3)

namespace: tenant-rio
└── ... (mesma estrutura)

Shared (namespace: platform):
├── deployment/postgres (com pgBouncer)
├── deployment/redis-cluster
├── deployment/rabbitmq-cluster
└── deployment/nginx-ingress
```

### HPA (Horizontal Pod Autoscaler) para Workers
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-worker
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: External
    external:
      metric:
        name: rabbitmq_queue_messages
        selector:
          matchLabels:
            queue: ai.frame
      target:
        type: AverageValue
        averageValue: "50"  # escala se fila > 50 mensagens por pod
```

### Banco de Dados — Estratégia de Particionamento
```sql
-- Particionar recording_segments por tenant e mês (crucial com 1.500 câmeras)
CREATE TABLE recording_segments (
    id UUID,
    tenant_id UUID,
    started_at TIMESTAMP,
    ...
) PARTITION BY LIST (tenant_id);

-- Partições por tenant criadas automaticamente ao provisionar cidade

-- Adicionar particionamento por data dentro de cada tenant
CREATE TABLE recording_segments_tenant_sp
PARTITION OF recording_segments
FOR VALUES IN ('uuid-sao-paulo')
PARTITION BY RANGE (started_at);
```

---

## 5. Fase 4 — 5.000+ Câmeras (Nacional)

### Arquitetura Multi-Região
```
Região Brasil-SE (São Paulo):
└── Cidades: SP, RJ, BH, Curitiba, POA

Região Brasil-NE (Salvador ou Fortaleza):
└── Cidades: SSA, FOR, REC, MAN, BEL

Shared Global:
├── PostgreSQL (Aurora ou CockroachDB) — global
├── CDN (CloudFront) — thumbnails e clipes para download
└── Observability: Grafana + Prometheus + Loki
```

### Estratégia de Storage em Escala Nacional
```
Por câmera/ano (H.265, 2 Mbps): ~4 TB

5.000 câmeras × média 20 dias retenção:
5.000 × 2 Mbps × 86.400s × 20 ÷ 8 ÷ 1024³ ≈ 2 PB

Lifecycle policies no S3:
- Segmentos < 7 dias: S3 Standard
- Segmentos 7-30 dias: S3 Standard-IA
- Clipes manuais: S3 Standard
- Snapshots > 90 dias: S3 Glacier Instant Retrieval
```

---

## 6. Monitoramento e Observabilidade

### Stack de Monitoramento
```
Prometheus → Coleta métricas
Grafana    → Dashboards
Loki       → Logs centralizados
Alertmanager → Alertas (PagerDuty / Slack)
```

### Métricas Críticas a Monitorar

**Pipeline de Vídeo:**
```
cameras_online_total{tenant_id}
cameras_offline_total{tenant_id}
recorder_segment_duration_seconds{camera_id}
recorder_reconnect_total{camera_id}
stream_latency_ms{camera_id}
```

**Workers de IA:**
```
ai_frames_processed_total{worker_id}
ai_detections_total{event_type, tenant_id}
rabbitmq_queue_depth{queue_name}
ai_processing_latency_ms{worker_id}
```

**Infraestrutura:**
```
storage_used_bytes{tenant_id}
storage_available_bytes
db_query_duration_ms{query_type}
redis_hit_rate
```

### Alertas Críticos
```yaml
- alert: CameraOfflineTooLong
  expr: cameras_offline_total > 0
  for: 5m
  annotations:
    summary: "{{ $value }} câmeras offline por mais de 5 minutos"

- alert: RecorderQueueBacklog
  expr: rabbitmq_queue_depth{queue="recording.start"} > 20
  for: 2m
  annotations:
    summary: "Fila de gravação com backlog — verificar workers"

- alert: StorageAbove90Percent
  expr: storage_used_bytes / storage_available_bytes > 0.9
  annotations:
    summary: "Storage acima de 90% — expandir urgente"

- alert: AIWorkerDown
  expr: up{job="ai-worker"} == 0
  for: 1m
  annotations:
    summary: "AI Worker fora do ar"
```

---

## 7. Estratégia de Backup

```
PostgreSQL:
- pg_dump diário (incremental via WAL streaming)
- Backup completo semanal para S3 Glacier
- RPO: 1 hora, RTO: 4 horas

Redis:
- RDB snapshot a cada 1h + AOF habilitado
- Replicação Sentinel para HA

Segmentos de vídeo:
- Replicação assíncrona entre zonas de disponibilidade
- Clipes manuais: replicação síncrona (críticos)

Configuração white label:
- Versionamento no banco + backup em S3
```

---

## 8. SLA por Componente

| Componente | SLA Alvo | Estratégia |
|---|---|---|
| Live View (WebRTC) | 99.5% | MediaMTX HA + reconexão automática |
| Gravação Contínua | 99.9% | Workers com retry infinito |
| API (Django) | 99.9% | Multi-instância + health check |
| Detecções IA | 99.0% | Queue buffer RabbitMQ |
| Dashboard | 99.5% | CDN + cache agressivo |
| Storage | 99.99% | S3 com replicação |
