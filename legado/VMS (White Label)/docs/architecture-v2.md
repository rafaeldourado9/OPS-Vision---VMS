# VMS IA — Documentação Técnica v2.0 (Escalabilidade 500 Câmeras)

## 4. Especificação de Componentes

### 4.1 MediaMTX — Servidor de Streaming

| Propriedade | Especificação |
|-------------|---------------|
| Protocolo de entrada | RTSP (H.264, H.265, MJPEG) |
| Protocolos de saída | RTSP, HLS, WebRTC, RTMP |
| Câmeras suportadas por instância | ~170 câmeras |
| Instâncias no cluster | 3 instâncias (N+1 redundância) |
| Balanceamento | Round-robin por faixas de câmeras |
| Geração HLS | Sim, para visualização via browser |
| Autenticação | JWT + API Key por câmera |

**Distribuição de câmeras no cluster MediaMTX:**

| Instância | Câmeras LPR | Câmeras Analytics | Total |
|-----------|-------------|-------------------|-------|
| MediaMTX-1 | 20 câmeras | 150 câmeras | 170 câmeras |
| MediaMTX-2 | 20 câmeras | 150 câmeras | 170 câmeras |
| MediaMTX-3 | 10 câmeras | 150 câmeras | 160 câmeras |
| **TOTAL** | **50 câmeras** | **450 câmeras** | **500 câmeras** |

### 4.2 Frame Grabber Cluster

```mermaid
graph LR
    subgraph FGC["Frame Grabber Cluster"]
        FG1["FG-1\nCameras 1-17\n(asyncio pool)"]
        FG2["FG-2\nCameras 18-34\n(asyncio pool)"]
        FG3["FG-3\nCameras 35-50\n(asyncio pool)"]
    end
    MTX[MediaMTX] --> FG1
    MTX --> FG2
    MTX --> FG3
    FG1 -->|"SET cam:{id}:frame"| RD[(Redis)]
    FG2 -->|"SET cam:{id}:frame"| RD
    FG3 -->|"SET cam:{id}:frame"| RD
    RD -->|PUBLISH| CH[Redis PubSub]
    CH --> RMQ[RabbitMQ]
```

**Implementação assíncrona com Python asyncio:**

```python
async def grab_frames_async(camera_list: List[Camera]):
    tasks = [grab_single_camera(cam) for cam in camera_list]
    await asyncio.gather(*tasks, return_exceptions=True)

async def grab_single_camera(camera: Camera):
    while True:
        frame = await loop.run_in_executor(executor, cv2.VideoCapture.read)
        compressed = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]
        await redis.set(f"cam:{camera.id}:frame", compressed.tobytes(), ex=10)
        await redis.publish(f"cam:{camera.id}:new_frame", camera.id)
```

**Sharding por Hash de Camera ID:**

```python
def get_grabber_instance(camera_id: str) -> int:
    shard = hash(camera_id) % NUM_GRABBER_INSTANCES
    return shard  # 0, 1 ou 2
```

### 4.3 Redis Frame Cache

| Configuração | Valor | Justificativa |
|-------------|-------|---------------|
| TTL dos frames | 10 segundos | Balanceia memória vs freshness |
| Compressão | JPEG quality 85 | Reduz uso de memória 10x |
| Estrutura de chave | `cam:{id}:frame` | Lookup O(1) por câmera |
| Pub/Sub | `cam:{id}:new_frame` | Notifica workers sem polling |
| Memória estimada (500 câmeras) | ~2.5 GB | Frame 1080p JPEG ~5KB x 500 |
| Modo de deployment | Redis Cluster (3 nós) | Alta disponibilidade |

### 4.4 RabbitMQ — Message Broker

**Topologia de Filas:**

| Fila | Producer | Consumer | Prefetch |
|------|----------|----------|----------|
| `ai.frame.lpr` | Frame Grabbers | LPR Workers | 8 |
| `ai.frame.general` | Frame Grabbers | Analytics Workers | 16 |
| `ai.frame.face` | Frame Grabbers | Face Workers | 8 |
| `ai.events` | AI Workers | Event Consumer | 100 |
| `ai.events.dlq` | Sistema (falhas) | DLQ Handler | 10 |

### 4.5 AI Worker Clusters

```mermaid
graph TD
    RMQ[RabbitMQ] --> |ai.frame.lpr| LPR[LPR Worker Cluster]
    RMQ --> |ai.frame.general| GEN[Analytics Worker Cluster]
    RMQ --> |ai.frame.face| FACE[Facial Worker Cluster]
    subgraph LPR["LPR Cluster - 4 instancias - GPU 0,1"]
        L1[Worker LPR-1]
        L2[Worker LPR-2]
        L3[Worker LPR-3]
        L4[Worker LPR-4]
    end
    subgraph GEN["Analytics Cluster - 4 instancias - GPU 2,3"]
        G1[Worker Gen-1]
        G2[Worker Gen-2]
        G3[Worker Gen-3]
        G4[Worker Gen-4]
    end
    subgraph FACE["Facial Cluster - 2 instancias - GPU 0,1"]
        F1[Worker Face-1]
        F2[Worker Face-2]
    end
    LPR --> EVT[ai.events]
    GEN --> EVT
    FACE --> EVT
```

**Configuração dos Workers LPR:**

```python
MAX_CONCURRENT_FRAMES = 8   # vs 4 atual
OCR_WORKERS = 8              # Thread pool para OCR paralelo
GPU_DEVICE = "cuda:0"        # Alocacao GPU dedicada
BATCH_SIZE = 4              # Inference em batch
MODEL = "yolov8n-lpr.pt"   # YOLO otimizado para placas
OCR_ENGINE = "paddleocr"   # Substitui Tesseract
```

**Análise de Capacidade — LPR Workers:**

| Métrica | Anterior | Proposto | Melhoria |
|---------|----------|----------|----------|
| Instâncias | 1 | 4 | 4x |
| Concurrent frames/instância | 4 | 8 | 2x |
| OCR engine | Tesseract (80ms) | PaddleOCR (15ms) | 5.3x mais rápido |
| Throughput total | ~7.5 FPS | ~80 FPS | 10.6x |
| Demanda | 50 FPS | 50 FPS | Margem: 60% |

---

## 5. Pipelines de Processamento

### 5.1 Pipeline Principal

```mermaid
sequenceDiagram
    participant CAM as Camera
    participant MTX as MediaMTX
    participant FG as Frame Grabber
    participant RD as Redis
    participant RMQ as RabbitMQ
    participant WK as AI Worker
    participant EC as Event Consumer
    participant PG as PostgreSQL
    participant WS as WebSocket
    CAM->>MTX: RTSP Stream (H264)
    MTX->>FG: Stream redistribuido
    FG->>RD: SET cam:id:frame (JPEG)
    FG->>RMQ: PUBLISH {camera_id, redis_key}
    RMQ->>WK: Deliver frame task
    WK->>RD: GET cam:id:frame
    WK->>WK: Inferencia GPU
    WK->>RMQ: PUBLISH evento deteccao
    EC->>RMQ: CONSUME evento
    EC->>PG: INSERT evento (batch)
    EC->>WS: Notificar operadores
    WS->>WS: Broadcast para clientes
```

### 5.2 Pipeline LPR Detalhado

```mermaid
graph TD
    F[Frame 1080p] --> ROI[ROI Extraction]
    ROI --> |"Regiao de Interesse"| YOLO[YOLO v8 Plate Detection]
    YOLO --> |"Bounding Boxes"| CROP[Crop Placas]
    CROP --> |"Imagens recortadas"| POOL{Thread Pool OCR}
    POOL --> OCR1[PaddleOCR Thread 1]
    POOL --> OCR2[PaddleOCR Thread 2]
    POOL --> OCR3[PaddleOCR Thread 3]
    POOL --> OCR4[PaddleOCR Thread 4]
    OCR1 --> MERGE[Merge Results]
    OCR2 --> MERGE
    OCR3 --> MERGE
    OCR4 --> MERGE
    MERGE --> VAL[Validacao Regex]
    VAL --> |"Valida"| EVT[Evento LPR]
    VAL --> |"Invalida"| DISC[Descartado]
    EVT --> DB[(PostgreSQL)]
    EVT --> ALERT[Alertas Watchlist]
```

**Latências por Etapa — Pipeline LPR:**

| Etapa | Latência | Componente |
|-------|----------|------------|
| Captura e compressão JPEG | 40ms | Frame Grabber (async) |
| Publicação Redis | 2ms | Redis SET + PUBLISH |
| Queue delay (RabbitMQ) | 5ms | Fila vazia baseline |
| YOLO plate detection | 15ms | GPU inference (batch) |
| Crop + pre-processamento | 5ms | CPU (NumPy) |
| PaddleOCR (6 placas paralelo) | 45ms | Thread pool (15ms x1) |
| Validacao + enrichment | 5ms | CPU (regex + lookup) |
| Event publish + DB insert | 55ms | Event Consumer (batch) |
| **TOTAL ESTIMADO** | **~172ms** | **vs objetivo < 2000ms** |

### 5.3 Pipeline de Analytics Gerais

```mermaid
graph TD
    F[Frame] --> PP[Pre-processamento]
    PP --> YOLO[YOLOv8 Multi-class]
    YOLO --> DET{Deteccoes}
    DET --> |Pessoa| TRACK1[Tracker Pessoa]
    DET --> |Veiculo| TRACK2[Tracker Veiculo]
    DET --> |Objeto| TRACK3[Tracker Objeto]
    TRACK1 --> RULES[Motor de Regras]
    TRACK2 --> RULES
    TRACK3 --> RULES
    RULES --> |"Intrusao"| EVT1[Evento Intrusao]
    RULES --> |"Linha Cruzada"| EVT2[Evento Cruzamento]
    RULES --> |"Loitering"| EVT3[Evento Permanencia]
    RULES --> |"Crowd"| EVT4[Evento Aglomeracao]
    EVT1 --> MQ[ai.events]
    EVT2 --> MQ
    EVT3 --> MQ
    EVT4 --> MQ
```

**Analíticos Suportados:**

| Analítico | Categoria | Latência | Modelo |
|-----------|-----------|----------|--------|
| Detecção de Pessoas | Básico | 20ms | YOLOv8n |
| Detecção de Veículos | Básico | 20ms | YOLOv8n |
| Detecção de Intrusão | Zona | 25ms | YOLOv8n + Rules |
| Linha Cruzada | Zona | 25ms | YOLOv8n + Tracker |
| Loitering (Permanência) | Comportamental | 30ms | YOLOv8n + Timer |
| Objetos Abandonados | Comportamental | 35ms | Background Subtraction |
| Crowd Counting | Estatístico | 30ms | YOLOv8n + Counter |
| Heatmap de Movimento | Estatístico | 40ms | Optical Flow |
| LPR | Avançado | 172ms | YOLOv8 + PaddleOCR |
| Reconhecimento Facial | Avançado | 150ms | RetinaFace + ArcFace |

---

## 6. Planejamento de Infraestrutura

### 6.1 Diagrama de Infraestrutura

```mermaid
graph TD
    subgraph GPU_SERVERS["Servidores GPU (2 servidores)"]
        subgraph SRV1["Server GPU-1 (RTX 4090 x2)"]
            GPU0[GPU 0: LPR Workers 1-2]
            GPU1[GPU 1: LPR Workers 3-4]
        end
        subgraph SRV2["Server GPU-2 (RTX 4090 x2)"]
            GPU2[GPU 2: Analytics Workers 1-2]
            GPU3[GPU 3: Analytics Workers 3-4]
        end
    end
    subgraph APP_SERVERS["Servidores de Aplicacao (3 servidores)"]
        APP1[App-1: Django + Gunicorn]
        APP2[App-2: Django + Gunicorn]
        APP3[App-3: WebSocket + Channels]
    end
    subgraph DATA_SERVERS["Servidores de Dados (3 servidores)"]
        PG1[(PostgreSQL Primary)]
        PG2[(PostgreSQL Replica 1)]
        PG3[(PostgreSQL Replica 2)]
    end
    subgraph INFRA["Infraestrutura de Suporte"]
        RD1[(Redis Cluster Node 1)]
        RD2[(Redis Cluster Node 2)]
        RD3[(Redis Cluster Node 3)]
        RMQ1[RabbitMQ Node 1]
        RMQ2[RabbitMQ Node 2]
        RMQ3[RabbitMQ Node 3]
    end
    subgraph STREAMING["Cluster de Streaming (3 servidores)"]
        MTX1[MediaMTX-1]
        MTX2[MediaMTX-2]
        MTX3[MediaMTX-3]
    end
```

### 6.2 Dimensionamento de Hardware

| Componente | CPU | RAM | GPU | Storage | Qtd |
|------------|-----|-----|-----|---------|-----|
| Servidor GPU (LPR) | 16 cores | 64 GB | 2x RTX 4090 | NVMe 1TB | 1 |
| Servidor GPU (Analytics) | 16 cores | 64 GB | 2x RTX 4090 | NVMe 1TB | 1 |
| App Server | 8 cores | 32 GB | - | SSD 500GB | 3 |
| DB Server | 8 cores | 64 GB | - | NVMe 2TB | 3 |
| Redis Node | 4 cores | 32 GB | - | SSD 200GB | 3 |
| RabbitMQ Node | 4 cores | 16 GB | - | SSD 200GB | 3 |
| MediaMTX Node | 8 cores | 16 GB | - | SSD 200GB | 3 |
| Frame Grabber | 8 cores | 16 GB | - | SSD 200GB | 3 |
| Monitoring (Prometheus+Grafana) | 4 cores | 16 GB | - | SSD 500GB | 1 |

### 6.3 Estimativa de Rede

| Segmento | Bandwidth Estimado | Justificativa |
|----------|-------------------|---------------|
| Câmeras → MediaMTX (ingress) | ~12.5 Gbps | 500 câmeras x 25Mbps médio |
| MediaMTX → Frame Grabbers | ~2.5 Gbps | Apenas fluxo para IA (1 cliente) |
| Frame Grabbers → Redis | ~500 Mbps | 500 câmeras x 1MB/s (5 FPS JPEG) |
| Redis → Workers (GET) | ~300 Mbps | Workers consumindo frames |
| Workers → Event Bus | < 50 Mbps | Apenas metadata JSON |
| DB replication | ~1 Gbps | PostgreSQL streaming replication |

### 6.4 Armazenamento de Vídeo

| Parâmetro | Valor | Cálculo |
|-----------|-------|---------|
| Câmeras totais | 500 | - |
| Resolução média | 1080p H.264 | Bitrate médio: 2 Mbps |
| Retenção de vídeo | 30 dias | Requisito operacional |
| Storage total estimado | ~324 TB | 500 x 2Mbps x 86400s x 30 / 8 |
| Storage + overhead (20%) | ~390 TB | Índices, thumbnails, exports |
| Recomendação | NAS 400TB RAID-6 | Com expansão para 600TB |

---

## 7. Monitoramento e Observabilidade

### 7.1 Stack de Monitoramento

```mermaid
graph TD
    subgraph SERVICES["Servicos"]
        SVC1[Frame Grabbers]
        SVC2[AI Workers]
        SVC3[Event Consumers]
        SVC4[Django API]
    end
    subgraph COLLECT["Coleta"]
        PROM[Prometheus]
        LOKI[Loki]
        TEMPO[Tempo]
    end
    subgraph PRESENT["Apresentacao"]
        GRAFANA[Grafana Dashboards]
        ALERT[AlertManager]
        PD[PagerDuty]
    end
    SVC1 -->|"/metrics"| PROM
    SVC2 -->|"/metrics"| PROM
    SVC3 -->|"/metrics"| PROM
    SVC4 -->|"/metrics"| PROM
    SVC1 -->|logs| LOKI
    SVC2 -->|traces| TEMPO
    PROM --> GRAFANA
    LOKI --> GRAFANA
    TEMPO --> GRAFANA
    PROM --> ALERT
    ALERT --> PD
```

### 7.2 Métricas Prometheus Principais

| Métrica | Tipo | Descrição | Alerta se |
|---------|------|-----------|-----------|
| `lpr_frames_processed_total` | Counter | Total de frames LPR processados | - |
| `lpr_processing_latency_seconds` | Histogram | Latência end-to-end LPR | p99 > 2s |
| `lpr_queue_depth` | Gauge | Profundidade da fila LPR | > 1000 |
| `ocr_success_rate` | Gauge | Taxa de sucesso OCR | < 80% |
| `frame_grabber_fps` | Gauge | FPS atual por câmera | < 1 FPS |
| `ai_worker_gpu_utilization` | Gauge | Uso de GPU por worker | > 95% |
| `event_consumer_lag` | Gauge | Lag do consumer de eventos | > 500 eventos |
| `camera_stream_health` | Gauge | Saúde dos streams (0/1) | < 1 (offline) |

### 7.3 SLOs e SLAs

| SLO | Target | Medição | Janela |
|-----|--------|---------|--------|
| Disponibilidade do sistema | 99.9% | uptime / total_time | Mensal |
| Latência LPR p95 | < 500ms | lpr_latency histogram p95 | Semanal |
| Latência LPR p99 | < 2s | lpr_latency histogram p99 | Semanal |
| Taxa de sucesso OCR | > 85% | ocr_success_rate média | Diário |
| Câmeras online | > 98% | camera_stream_health média | Diário |
| Tempo de detecção eventos | < 2s | event_detection_latency | Semanal |

---

## 8. Planejamento de Sprints

```mermaid
gantt
    title Roadmap de Desenvolvimento VMS IA
    dateFormat  YYYY-MM-DD
    section Sprint 1
    Infraestrutura Base           :s1, 2025-04-01, 14d
    section Sprint 2
    Pipeline de IA                :s2, after s1, 14d
    section Sprint 3
    LPR Escalavel                 :s3, after s2, 14d
    section Sprint 4
    Monitoramento                 :s4, after s3, 14d
    section Sprint 5
    Otimizacao e Load Test        :s5, after s4, 14d
```

### Sprint 1 — Infraestrutura Base (Semanas 1-2)

**Objetivo:** Estabelecer toda a infraestrutura de suporte antes de qualquer desenvolvimento de aplicação.

| Tarefa | Responsável | Estimativa | Prioridade |
|--------|-------------|------------|------------|
| Provisionar servidores GPU | DevOps | 2 dias | P0 |
| Instalar e configurar Docker Swarm / K8s | DevOps | 3 dias | P0 |
| Deploy Redis Cluster (3 nós) | DevOps | 1 dia | P0 |
| Deploy RabbitMQ Cluster (3 nós) | DevOps | 1 dia | P0 |
| Configurar MediaMTX Cluster | DevOps | 2 dias | P0 |
| Deploy PostgreSQL com replicação | DBA | 2 dias | P1 |
| Setup Prometheus + Grafana base | DevOps | 1 dia | P1 |
| Configurar CI/CD pipeline | DevOps | 2 dias | P1 |
| Network: VLANs e firewall rules | NetOps | 2 dias | P0 |

**Entregáveis:** Cluster operacional, serviços HA, CI/CD funcional, monitoramento básico.

**Riscos:** Disponibilidade de hardware GPU (lead time), complexidade K8s em ambiente seguro.

### Sprint 2 — Pipeline de IA Base (Semanas 3-4)

**Objetivo:** Implementar o pipeline assíncrono de frames e workers de analytics gerais.

| Tarefa | Responsável | Estimativa | Prioridade |
|--------|-------------|------------|------------|
| Refatorar Frame Grabber para asyncio | Backend Dev | 3 dias | P0 |
| Implementar sharding de câmeras | Backend Dev | 2 dias | P0 |
| Integrar Redis Frame Cache | Backend Dev | 2 dias | P0 |
| Implementar AI Worker base (asyncio) | ML Dev | 3 dias | P0 |
| Containerizar workers com GPU support | DevOps | 2 dias | P0 |
| Implementar consumer de eventos async | Backend Dev | 2 dias | P1 |
| Testes de integração do pipeline | QA | 2 dias | P1 |
| Métricas Prometheus para todos os componentes | Backend Dev | 1 dia | P1 |

**Entregáveis:** Frame Grabber async, Redis Frame Cache, AI Workers básicos, pipeline end-to-end funcional.

### Sprint 3 — LPR Escalável (Semanas 5-6)

**Objetivo:** Implementar e validar o pipeline LPR com PaddleOCR paralelo, substituindo Tesseract.

| Tarefa | Responsável | Estimativa | Prioridade |
|--------|-------------|------------|------------|
| Substituir Tesseract por PaddleOCR | ML Dev | 3 dias | P0 |
| Implementar thread pool OCR (8 threads) | ML Dev | 2 dias | P0 |
| Otimizar YOLO para detecção de placas | ML Dev | 3 dias | P0 |
| Implementar ROI extraction configurável | ML Dev | 2 dias | P1 |
| Configurar 4 instâncias LPR Worker | DevOps | 1 dia | P0 |
| Implementar validação de placas (regex) | Backend Dev | 1 dia | P1 |
| Integrar watchlist de placas | Backend Dev | 2 dias | P1 |
| Load test: 50 cameras LPR simultâneas | QA | 2 dias | P0 |

**Entregáveis:** Pipeline LPR com PaddleOCR, 50 câmeras validadas, latência < 500ms p95, watchlist funcional.

### Sprint 4 — Monitoramento Avançado (Semanas 7-8)

**Objetivo:** Observabilidade completa, alertas e dashboards operacionais.

| Tarefa | Responsável | Estimativa | Prioridade |
|--------|-------------|------------|------------|
| Dashboards Grafana: Pipeline Overview | DevOps | 2 dias | P0 |
| Dashboard: LPR Performance | DevOps | 2 dias | P0 |
| Dashboard: GPU Utilization | DevOps | 1 dia | P0 |
| Configurar AlertManager + PagerDuty | DevOps | 2 dias | P0 |
| Implementar health checks em todos os serviços | Backend Dev | 2 dias | P1 |
| Distributed tracing com Tempo | Backend Dev | 3 dias | P1 |
| SLO monitoring e relatórios | DevOps | 2 dias | P1 |

### Sprint 5 — Otimização e Load Test (Semanas 9-10)

**Objetivo:** Validar performance em escala real (500 câmeras), corrigir gargalos e preparar para produção.

| Tarefa | Responsável | Estimativa | Prioridade |
|--------|-------------|------------|------------|
| Load test: 500 câmeras simultâneas | QA + DevOps | 3 dias | P0 |
| Profiling e otimização de bottlenecks | Backend Dev | 3 dias | P0 |
| Fine-tuning de parâmetros Redis/RabbitMQ | DevOps | 2 dias | P1 |
| Teste de failover e recovery | DevOps | 2 dias | P0 |
| Documentação de operação | Tech Writer | 2 dias | P1 |
| Runbooks de incidentes | DevOps | 2 dias | P1 |
| Go-live checklist e sign-off | Tech Lead | 1 dia | P0 |

---

## 9. Análise de Riscos

### 9.1 Matriz de Riscos

| Risco | Probabilidade | Impacto | Score | Mitigação |
|-------|--------------|---------|-------|-----------|
| Lead time de GPU > 90 dias | Alta | Alto | 9/10 | Usar cloud GPU temporariamente |
| Performance OCR insuficiente | Média | Alto | 6/10 | Benchmark PaddleOCR antes do sprint 3 |
| Câmeras com streams instáveis | Alta | Médio | 6/10 | Circuit breaker no Frame Grabber |
| Memória Redis insuficiente | Baixa | Alto | 4/10 | Monitorar uso e escalar horizontalmente |
| Latência de rede interna alta | Baixa | Alto | 4/10 | Topologia de rede dedicada para câmeras |
| Falha de nó do cluster | Média | Médio | 4/10 | HA em todos os componentes críticos |
| Throughput RabbitMQ no limite | Baixa | Alto | 4/10 | Migrar para Kafka se > 2000 câmeras |
| Drift de modelo de IA | Média | Médio | 4/10 | Retreinamento periódico + monitoramento |

### 9.2 Erros Arquiteturais a Evitar

**Erro 1: IA Acoplada ao Stream**
```python
# ERRADO: IA conecta diretamente na camera
cap = cv2.VideoCapture("rtsp://camera:554/stream")

# CORRETO: IA consome frames do Redis
frame_data = await redis.get(f"cam:{camera_id}:frame")
```

**Erro 2: Armazenar Frames em Disco** — Redis é 100-1000x mais rápido, TTL 10s é suficiente.

**Erro 3: Worker Monolítico de Analytics** — Cada analítico deve ter seu próprio cluster de workers.

**Erro 4: Sem Controle de Backpressure** — Prefetch no RabbitMQ + batch inserts no PostgreSQL.

---

## 10. Guia de Deployment

### 10.1 Ordem de Deploy

```mermaid
graph TD
    S1[1. Redis Cluster] --> S2[2. RabbitMQ Cluster]
    S2 --> S3[3. PostgreSQL + Replicas]
    S3 --> S4[4. MediaMTX Cluster]
    S4 --> S5[5. Frame Grabber Cluster]
    S5 --> S6[6. AI Workers LPR]
    S6 --> S7[7. AI Workers General]
    S7 --> S8[8. AI Workers Facial]
    S8 --> S9[9. Event Consumer]
    S9 --> S10[10. Django API + WebSocket]
    S10 --> S11[11. Prometheus + Grafana]
    S11 --> S12[12. Load Balancer + SSL]
```

### 10.2 Checklist de Go-Live

| Categoria | Item | Verificado |
|-----------|------|------------|
| Infraestrutura | Todos os servidores com hardware correto | [ ] |
| Infraestrutura | Rede configurada com VLANs corretas | [ ] |
| Infraestrutura | Redundância N+1 em todos os componentes críticos | [ ] |
| Performance | Load test 500 câmeras aprovado | [ ] |
| Performance | Latência LPR p99 < 2s validada | [ ] |
| Performance | Taxa OCR > 85% em condições reais | [ ] |
| Monitoramento | Todos os alertas Prometheus configurados | [ ] |
| Monitoramento | Dashboards Grafana revisados e aprovados | [ ] |
| Segurança | TLS em todos os endpoints | [ ] |
| Segurança | Credenciais em secrets manager (não em código) | [ ] |
| DR | Runbooks de incidentes documentados | [ ] |
| DR | Teste de failover realizado com sucesso | [ ] |
| Backup | Backup automatizado do PostgreSQL configurado | [ ] |

### 10.3 Escalabilidade Futura (> 2000 câmeras)

| Componente Atual | Limite Estimado | Substituto |
|-----------------|-----------------|------------|
| RabbitMQ | ~1000-2000 câmeras | Apache Kafka |
| Redis single-cluster | ~2000 câmeras | Redis Enterprise |
| PostgreSQL single-primary | ~5000 eventos/s | TimescaleDB ou Cassandra |
| Container manual | Escalonamento lento | Kubernetes HPA + GPU device plugin |
| Métricas Prometheus | ~100 serviços | Prometheus Thanos |

---

## 11. Especificação de Microserviços

### 11.1 Mapa de Microserviços

```mermaid
graph TD
    subgraph CORE["Core Services"]
        CAM_SVC[Camera Service\nGestao de cameras]
        STREAM_SVC[Streaming Service\nMediaMTX manager]
        RECORD_SVC[Recording Service\nGravacao continua]
    end
    subgraph AI_SVC["AI Services"]
        GRAB_SVC[Frame Grabber Service]
        LPR_SVC[LPR Service]
        ANALYTIC_SVC[Analytics Service]
        FACE_SVC[Face Recognition Service]
    end
    subgraph EVENT_SVC["Event Services"]
        EVENT_PROC[Event Processor]
        NOTIF_SVC[Notification Service]
        WATCHLIST[Watchlist Service]
    end
    subgraph API_GW["API & Frontend"]
        API[REST API Gateway]
        WS_GW[WebSocket Gateway]
        AUTH[Auth Service]
    end
    CAM_SVC --> STREAM_SVC
    STREAM_SVC --> GRAB_SVC
    GRAB_SVC --> LPR_SVC
    GRAB_SVC --> ANALYTIC_SVC
    GRAB_SVC --> FACE_SVC
    LPR_SVC --> EVENT_PROC
    ANALYTIC_SVC --> EVENT_PROC
    FACE_SVC --> EVENT_PROC
    EVENT_PROC --> NOTIF_SVC
    EVENT_PROC --> WATCHLIST
    API --> CAM_SVC
    WS_GW --> NOTIF_SVC
```

### 11.2 APIs dos Serviços Principais

**LPR Service API:**

| Endpoint | Método | Descrição | Response |
|----------|--------|-----------|----------|
| `/lpr/events` | GET | Listar eventos LPR com filtros | 200 + JSON Array |
| `/lpr/events/{id}` | GET | Evento LPR por ID | 200 + JSON Object |
| `/lpr/watchlist` | GET/POST | Gerenciar watchlist de placas | 200/201 + JSON |
| `/lpr/cameras/{id}/config` | PUT | Configurar ROI por câmera | 200 + JSON |
| `/lpr/metrics` | GET | Métricas de performance LPR | 200 + JSON |

**Camera Service API:**

| Endpoint | Método | Descrição | Response |
|----------|--------|-----------|----------|
| `/cameras` | GET/POST | Listar / Criar câmeras | 200/201 + JSON |
| `/cameras/{id}` | GET/PUT/DELETE | CRUD por câmera | 200/204 + JSON |
| `/cameras/{id}/stream` | GET | URL de stream HLS/RTSP | 200 + JSON |
| `/cameras/{id}/health` | GET | Status de conectividade | 200 + JSON |
| `/cameras/{id}/analytics` | GET/PUT | Configurar analíticos por câmera | 200 + JSON |

---

## 12. Resumo de Performance Esperada

### 12.1 Comparativo Antes vs Depois

| Métrica | Arquitetura Atual | Arquitetura Proposta | Melhoria |
|---------|-------------------|----------------------|----------|
| FPS Frame Grabber (50 cameras) | 0.36 FPS (sequencial) | 50+ FPS (paralelo async) | >138x |
| Throughput AI Workers | ~7.5 FPS (total) | 80 FPS (LPR cluster) | >10x |
| Latência OCR por placa | 80ms (Tesseract) | 15ms (PaddleOCR) | 5.3x mais rápido |
| Latência 6 placas simultâneas | 480ms | 45ms (paralelo) | 10.6x mais rápido |
| Latência end-to-end LPR | >2500ms | ~172ms | 14.5x mais rápido |
| I/O de disco por frame | 15-30ms | 0ms (Redis) | Eliminado |
| Event throughput | 66 eventos/s | 300+ eventos/s | 4.5x |
| Câmeras suportadas | ~10-20 | 500 | 25-50x |

### 12.2 Latência Detalhada — Pipeline LPR

```mermaid
gantt
    title Latencia Pipeline LPR (ms)
    dateFormat X
    axisFormat %Lms
    section Frame Grabber
    Captura e compressao JPEG : 0, 40
    section Redis
    SET + PUBLISH             : 40, 42
    section RabbitMQ
    Queue delay               : 42, 47
    section Worker
    YOLO plate detection      : 47, 62
    Crop + pre-processamento  : 62, 67
    PaddleOCR (paralelo)      : 67, 112
    Validacao + enrichment    : 112, 117
    section Event Consumer
    Batch insert + WebSocket  : 117, 172
```

### 12.3 Recomendações Finais

1. Implementar o Frame Grabber assíncrono como primeira prioridade — é o maior gargalo atual.
2. Migrar para Redis Frame Cache antes de qualquer outro trabalho de escalabilidade.
3. Substituir Tesseract por PaddleOCR para ganhos imediatos de 5x na latência OCR.
4. Configurar 4 instâncias do LPR Worker com MAX_CONCURRENT_FRAMES=8 cada.
5. Implementar monitoramento desde o Sprint 1, não como atividade final.
6. Planejar migração para Kafka quando o sistema ultrapassar 1500 câmeras.
7. Manter margem de 60% de capacidade para absorver picos sem degradação.

---

*VMS com Inteligência Artificial — Documentação Técnica Completa v2.0 — Confidencial — Uso Interno*
