# Sprint 2 - Integração MediaMTX e Primeiro Serviço de IA

**Duração**: 2 semanas  
**Objetivo**: Conectar com MediaMTX e implementar primeiro serviço de detecção

## 🎯 Objetivos

1. Implementar conector MediaMTX
2. Criar orquestrador de frames
3. Desenvolver serviço `invasion_ai`
4. Integração end-to-end funcionando

## 📋 User Stories

### US-2.1: Conector MediaMTX
**Como** sistema  
**Quero** conectar em múltiplas instâncias MediaMTX  
**Para** obter streams de vídeo de diferentes clientes

**Critérios de Aceite**:
- [ ] Suporta N instâncias MediaMTX simultâneas
- [ ] Autenticação via Basic Auth
- [ ] Descobre streams via API `/v3/paths/list`
- [ ] Captura frames via RTSP
- [ ] Configuração por instância (URL, credenciais)
- [ ] Retry automático em caso de falha

**Arquivos**:
- `core/mediamtx_connector.py`

**Exemplo de Configuração**:
```python
MEDIAMTX_INSTANCES = [
    {
        'id': 'gtvision_vms',
        'api_url': 'http://192.168.0.102:9997/v3/paths/list',
        'username': 'mediamtx_api_user',
        'password': 'GtV!sionMed1aMTX$2025'
    },
    {
        'id': 'cliente_abc',
        'api_url': 'http://10.0.0.50:9997/v3/paths/list',
        'username': 'user',
        'password': 'pass'
    }
]
```

---

### US-2.2: Orquestrador de Frames
**Como** sistema  
**Quero** coordenar captura e distribuição de frames  
**Para** alimentar os serviços de IA de forma eficiente

**Critérios de Aceite**:
- [ ] Captura frames de todos os streams ativos
- [ ] Controle de FPS configurável
- [ ] Distribui frames para todos os serviços via Redis
- [ ] Workers assíncronos por serviço
- [ ] Monitoramento de filas
- [ ] Graceful shutdown

**Arquivos**:
- `core/orchestrator.py`

**Fluxo**:
```
MediaMTX → Capture Loop → Redis Queue → Service Worker → Process Frame
```

---

### US-2.3: Serviço Invasion AI
**Como** cliente  
**Quero** detectar invasões em áreas restritas  
**Para** receber alertas em tempo real

**Critérios de Aceite**:
- [ ] Implementa `AIServiceInterface`
- [ ] Usa YOLO para detecção de pessoas
- [ ] Configuração de threshold de confiança
- [ ] Retorna bounding boxes das detecções
- [ ] Dockerfile isolado
- [ ] Requirements.txt próprio
- [ ] Health check funcional

**Arquivos**:
- `services/invasion_ai/__init__.py`
- `services/invasion_ai/Dockerfile`
- `services/invasion_ai/requirements.txt`

**Saída Esperada**:
```json
{
  "service": "invasion_ai",
  "version": "1.0.0",
  "camera_id": "gtvision_vms_camera01",
  "timestamp": 1704067200.0,
  "detections": [
    {
      "class": "person",
      "confidence": 0.87,
      "bbox": {"x1": 100, "y1": 200, "x2": 300, "y2": 500}
    }
  ],
  "total_detections": 1
}
```

---

### US-2.4: Endpoints de Monitoramento
**Como** operador  
**Quero** visualizar streams e status de processamento  
**Para** monitorar o sistema em produção

**Critérios de Aceite**:
- [ ] Endpoint `/streams` - Lista streams ativos
- [ ] Endpoint `/services` - Status de cada serviço
- [ ] Endpoint `/health` - Saúde do orquestrador
- [ ] Métricas de fila por serviço

**Arquivos**:
- `main.py` (atualização)

---

## 🏗️ Tarefas Técnicas

### T-2.1: MediaMTX API Client
- [ ] Implementar cliente HTTP assíncrono (aiohttp)
- [ ] Parser de resposta da API v3
- [ ] Construção de URLs RTSP
- [ ] Tratamento de timeouts

### T-2.2: Captura de Vídeo
- [ ] Integração OpenCV com RTSP
- [ ] Captura assíncrona (run_in_executor)
- [ ] Controle de FPS
- [ ] Liberação de recursos

### T-2.3: YOLO Integration
- [ ] Setup Ultralytics
- [ ] Carregamento de modelo
- [ ] Inferência otimizada
- [ ] Post-processing de detecções

### T-2.4: Docker para Serviços
- [ ] Dockerfile base para serviços de IA
- [ ] Suporte a GPU (NVIDIA)
- [ ] Otimização de imagem

---

## 🧪 Testes

### Testes Unitários
- [ ] `test_mediamtx_connector.py` - Mock de API
- [ ] `test_orchestrator.py` - Coordenação de tasks
- [ ] `test_invasion_ai.py` - Detecção com frames mock

### Testes de Integração
- [ ] MediaMTX real → Captura de frame
- [ ] Orchestrator → Redis → Service
- [ ] End-to-end: Stream → Detecção → Resultado

### Testes de Performance
- [ ] Latência de processamento <200ms
- [ ] Throughput >30 FPS por stream
- [ ] Uso de memória estável

---

## 📊 Definição de Pronto (DoD)

- [ ] Código implementado e revisado
- [ ] Testes passando (>80% cobertura)
- [ ] Documentação atualizada
- [ ] Testado com MediaMTX real
- [ ] Docker Compose funcional
- [ ] Logs estruturados
- [ ] Métricas de performance validadas

---

## 🚀 Entregáveis

1. **Código**:
   - MediaMTX Connector funcional
   - Orchestrator operacional
   - Serviço invasion_ai completo
   - Integração end-to-end

2. **Documentação**:
   - Guia de configuração MediaMTX
   - Tutorial de criação de serviços
   - Troubleshooting guide

3. **Infraestrutura**:
   - Docker Compose com todos os serviços
   - Configuração de GPU (opcional)

---

## 🎓 Aprendizados Esperados

- Integração com APIs REST externas
- Processamento de vídeo em tempo real
- YOLO e detecção de objetos
- Orquestração de workers assíncronos
- Otimização de performance

---

## 📈 Métricas de Sucesso

- ✅ Conecta em 10+ instâncias MediaMTX
- ✅ Processa 5 FPS por stream
- ✅ Detecção com latência <200ms
- ✅ Zero perda de frames em 1 hora de operação
- ✅ Uso de memória <2GB por serviço

---

## 🐛 Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Latência RTSP alta | Média | Alto | Buffer e skip de frames |
| Modelo YOLO lento | Baixa | Alto | Usar modelo otimizado (yolov8n) |
| Redis overflow | Média | Médio | Limite de fila + monitoramento |
| MediaMTX indisponível | Alta | Alto | Retry + circuit breaker |

---

## 🔄 Próxima Sprint

**Sprint 3**: Segundo serviço de IA e otimizações de performance
