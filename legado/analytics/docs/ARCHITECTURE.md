# Arquitetura VMS Edge Worker - Diagrama Mermaid

## Visão Geral do Sistema

```mermaid
graph TB
    subgraph "PC1 - MediaMTX Server"
        MTX[MediaMTX<br/>192.168.0.103:9997]
        CAM1[Câmera 1<br/>RTSP Stream]
        CAM2[Câmera 2<br/>RTSP Stream]
        CAMN[Câmera N<br/>até 20 câmeras]
        
        CAM1 --> MTX
        CAM2 --> MTX
        CAMN --> MTX
    end
    
    subgraph "PC2 - VMS Edge Worker"
        subgraph "Core Container"
            MAIN[FastAPI Main<br/>Port 8001]
            
            subgraph "Core Components"
                CONN[MediaMTX Connector<br/>Descobre Streams]
                ORCH[Orchestrator<br/>Coordena Fluxo]
                LOADER[Plugin Loader<br/>Descobre Serviços]
                REDISBUS[Redis Bus<br/>Message Broker]
            end
            
            subgraph "AI Services - Plugin System"
                AI1[AI Processor<br/>ALPR + OCR<br/>3 Workers]
                AI2[Invasion AI<br/>Detecção Invasão<br/>3 Workers]
                AI3[People Counter<br/>Contador Pessoas<br/>3 Workers]
            end
            
            MAIN --> LOADER
            MAIN --> CONN
            MAIN --> ORCH
            LOADER -.carrega.-> AI1
            LOADER -.carrega.-> AI2
            LOADER -.carrega.-> AI3
            ORCH --> REDISBUS
            REDISBUS -.frames.-> AI1
            REDISBUS -.frames.-> AI2
            REDISBUS -.frames.-> AI3
        end
        
        REDIS[(Redis<br/>Port 6380<br/>Message Queue)]
        
        REDISBUS <--> REDIS
        
        subgraph "Storage"
            SNAP1[snapshots/cam_1/<br/>placa/]
            SNAP2[snapshots/cam_2/<br/>placa/]
            SNAPN[snapshots/cam_N/<br/>placa/]
        end
        
        AI1 --> SNAP1
        AI1 --> SNAP2
        AI1 --> SNAPN
    end
    
    MTX -->|API REST<br/>Descobre Streams| CONN
    MTX -->|RTSP<br/>15 FPS| ORCH
    
    style MTX fill:#e1f5ff
    style REDIS fill:#ffebee
    style AI1 fill:#e8f5e9
    style AI2 fill:#fff3e0
    style AI3 fill:#f3e5f5
    style MAIN fill:#fce4ec
```

## Fluxo de Dados Detalhado

```mermaid
sequenceDiagram
    participant MTX as MediaMTX<br/>(PC1)
    participant CONN as MediaMTX<br/>Connector
    participant ORCH as Orchestrator
    participant REDIS as Redis Queue
    participant AI as AI Processor<br/>(3 Workers)
    participant DISK as Disk Storage
    
    Note over MTX,DISK: Inicialização (Startup)
    CONN->>MTX: GET /v3/paths/list (a cada 30s)
    MTX-->>CONN: Lista de streams online
    CONN->>ORCH: Notifica novos streams
    ORCH->>ORCH: Cria capture_loop por câmera
    
    Note over MTX,DISK: Processamento Contínuo (15 FPS)
    loop A cada 66ms (15 FPS)
        ORCH->>MTX: Captura frame via RTSP
        MTX-->>ORCH: Frame (numpy array)
        ORCH->>REDIS: Publica frame + metadata
        
        par Processamento Paralelo (3 Workers)
            REDIS->>AI: Worker #0 consome frame
            REDIS->>AI: Worker #1 consome frame
            REDIS->>AI: Worker #2 consome frame
        end
        
        AI->>AI: YOLO detecta placas
        
        alt Placa detectada
            AI->>AI: OCR extrai texto
            AI->>AI: Verifica duplicata
            
            alt Placa nova
                AI->>DISK: Salva foto completa
                AI->>DISK: Salva recorte placa
                AI->>DISK: Salva JSON metadata
                AI->>REDIS: Publica resultado
            else Placa já vista
                AI->>AI: Ignora (evita duplicata)
            end
        else Nenhuma placa
            AI->>AI: Descarta frame
        end
    end
```

## Estrutura de Plugins

```mermaid
graph LR
    subgraph "Plugin System - Arquitetura Hexagonal"
        INT[AIServiceInterface<br/>Abstract Base Class]
        
        subgraph "Implementações"
            ALPR[AIProcessorService<br/>YOLOv8 + fast-plate-ocr]
            INV[InvasionDetectionService<br/>YOLOv8n COCO]
            PEO[PeopleCounterService<br/>YOLOv8n COCO]
        end
        
        INT -.implementa.-> ALPR
        INT -.implementa.-> INV
        INT -.implementa.-> PEO
    end
    
    LOADER[Plugin Loader<br/>Auto-Discovery]
    
    LOADER -->|scan services/| INT
    LOADER -->|load| ALPR
    LOADER -->|load| INV
    LOADER -->|load| PEO
    
    style INT fill:#ffeb3b
    style ALPR fill:#4caf50
    style INV fill:#ff9800
    style PEO fill:#9c27b0
```

## Estrutura de Dados - Snapshots

```mermaid
graph TD
    ROOT[snapshots/]
    
    ROOT --> CAM1[cam_1/]
    ROOT --> CAM2[cam_2/]
    ROOT --> CAMN[cam_N/]
    
    CAM1 --> P1[ABC1D23/]
    CAM1 --> P2[XYZ9876/]
    
    P1 --> F1[ABC1D23_20260207_144758.jpg<br/>Foto Completa]
    P1 --> F2[ABC1D23_plate.jpg<br/>Recorte Placa]
    P1 --> F3[ABC1D23_data.json<br/>Metadata]
    
    F3 -.contém.-> META[vehicle_id<br/>plate<br/>camera_id<br/>timestamp<br/>confidence<br/>bbox<br/>model<br/>brand]
    
    style ROOT fill:#e3f2fd
    style P1 fill:#c8e6c9
    style F3 fill:#fff9c4
```

## Configuração e Escalabilidade

```mermaid
graph TB
    subgraph "Configuração"
        ENV[.env<br/>FPS=15<br/>WORKERS=3]
        MTX_CFG[mediamtx_instances.json<br/>Credenciais MediaMTX]
        SVC_CFG[services_config.json<br/>Modelos YOLO<br/>Thresholds]
    end
    
    subgraph "Capacidade"
        CAP1[20 Câmeras<br/>Simultâneas]
        CAP2[15 FPS<br/>por Câmera]
        CAP3[300 Frames/s<br/>Total]
        CAP4[9 Workers<br/>Paralelos]
    end
    
    ENV --> CAP2
    ENV --> CAP4
    MTX_CFG --> CAP1
    SVC_CFG --> CAP2
    
    CAP1 --> TOTAL[Throughput Total:<br/>300 frames/segundo<br/>18.000 frames/minuto]
    CAP2 --> TOTAL
    CAP3 --> TOTAL
    CAP4 --> TOTAL
    
    style TOTAL fill:#4caf50,color:#fff
```

## Tecnologias Utilizadas

```mermaid
mindmap
  root((VMS Edge<br/>Worker))
    Backend
      Python 3.11
      FastAPI
      Uvicorn
      AsyncIO
    AI/ML
      Ultralytics YOLOv8/v11
      PyTorch 2.5.1
      fast-plate-ocr
      OpenCV 4.8
    Infraestrutura
      Docker Compose
      Redis 7
      MediaMTX RTSP
    Arquitetura
      Hexagonal
      Plugin System
      Event-Driven
      Message Queue
```

## Características Principais

- ✅ **Plugin-Based**: Adicione serviços em `/services` - descoberta automática
- ✅ **Multi-Tenant**: Suporta N instâncias MediaMTX com credenciais diferentes
- ✅ **Isolamento**: Cada serviço tem suas próprias dependências
- ✅ **Escalável**: 20 câmeras × 15 FPS = 300 frames/segundo
- ✅ **Resiliente**: Auto-discovery de streams a cada 30s
- ✅ **Portável**: Copie uma pasta de serviço para outro projeto
- ✅ **Zero Duplicatas**: Rastreamento por câmera evita reprocessamento
