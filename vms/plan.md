# VMS Backend Roadmap (Post-Assessment)

Este roadmap organiza as próximas implementações na ordem mais eficiente para concluir o backend do VMS antes da construção do frontend.

O objetivo é deixar o sistema **100% funcional com câmeras reais**.

Arquitetura atual já implementada:

- Django Core API
- FastAPI async services
- MediaMTX streaming server
- PostgreSQL
- Redis
- RabbitMQ
- Celery workers
- SSE realtime events

---

# Phase 1 — RTMP Push Support (Immediate)

Objetivo: permitir que câmeras enviem vídeo diretamente para o servidor, semelhante ao modelo da Camerite.

## 1.1 Configurar MediaMTX para RTMP Push

Câmeras irão publicar stream via:


rtmp://SERVER/live/{camera_path}


Exemplo:


rtmp://localhost:1935/live/tenant-1-cam-1


Mapeamento interno MediaMTX:


tenant-1/cam-1


O pipeline existente permanece:

- recording automático
- hooks (on_ready, on_not_ready, record_segment)
- HLS playback
- WebRTC playback

---

## 1.2 Gerar URL RTMP no Backend

Criar função no serviço de câmeras:


generate_rtmp_push_url(camera_id, tenant_id)


Retorno esperado:


rtmp://STREAM_HOST/live/tenant-{tenant_id}-cam-{camera_id}


Exemplo:


rtmp://localhost:1935/live/tenant-1-cam-1


---

## 1.3 Endpoint de Configuração da Câmera

Criar endpoint:


GET /api/v1/cameras/{id}/push-config


Resposta:

```json
{
  "rtmp_url": "rtmp://localhost:1935/live",
  "stream_key": "tenant-1-cam-1",
  "full_url": "rtmp://localhost:1935/live/tenant-1-cam-1"
}

Esse endpoint permite que o frontend ou operador copie facilmente as configurações para a câmera.

1.4 Teste com Câmera Local

Configuração típica na câmera:

Server:
rtmp://SERVER/live

Stream key:
tenant-1-cam-1

Verificação:

logs do MediaMTX

endpoint /v3/paths/list

disparo de webhook on_ready

Phase 2 — ALPR Webhook via Ngrok

Objetivo: permitir que câmeras ALPR enviem eventos para o backend local.

2.1 Criar Endpoint ALPR

Endpoint:

POST /webhooks/alpr

Payload esperado:

{
  "plate": "ABC1234",
  "confidence": 0.92,
  "timestamp": "2026-03-15T10:20:00Z",
  "image_url": "http://camera/snapshot.jpg",
  "camera_id": 1
}

Fluxo:

Camera
  ↓
HTTP POST
  ↓
FastAPI /webhooks/alpr
  ↓
process_alpr_detection
  ↓
Event model
2.2 Expor Backend com Ngrok

Rodar:

ngrok http 80

Exemplo de URL gerada:

https://abc123.ngrok.io
2.3 Configurar na Câmera ALPR

Campo Cliente / Push Server:

https://abc123.ngrok.io/webhooks/alpr
2.4 Fluxo Final
Camera ALPR
   │
HTTP POST
   ▼
ngrok tunnel
   ▼
FastAPI webhook
   ▼
Event service
   ▼
PostgreSQL
Phase 3 — Event Processing Improvements

Objetivo: consolidar o sistema de eventos.

3.1 Consumers RabbitMQ

Criar consumidores para:

camera.*
detection.*

Exemplo de eventos:

camera.online
camera.offline
detection.alpr
motion.detected
3.2 Realtime SSE Completo

Eventos enviados para clientes:

camera.online
camera.offline
motion.detected
alpr.detected
recording.created
3.3 Agrupamento de Eventos ALPR

Evitar múltiplas leituras consecutivas da mesma placa.

Exemplo:

ABC1234
ABC1234
ABC1234

→ evento único consolidado.

Phase 4 — Analytics Pipeline

Objetivo: permitir analíticos próprios.

4.1 Criar Analytics Worker

Novo serviço:

analytics_worker

Fluxo:

MediaMTX stream
     ↓
frame extractor
     ↓
plugin pipeline
     ↓
event bus
4.2 Plugin Loader

Implementar carregamento automático de plugins em:

plugins/
4.3 Plugins Iniciais

Possíveis plugins:

person detection

vehicle detection

face recognition

fire detection

intrusion detection

Phase 5 — Security Hardening

Antes de produção.

5.1 Rate Limiting

Aplicar limites em:

/webhooks/*
/auth/*

Prevenção de ataques DOS.

5.2 Security Headers

Adicionar:

Strict-Transport-Security
Content-Security-Policy
X-Frame-Options
X-Content-Type-Options
5.3 Webhook Signature

Assinatura HMAC opcional para webhooks.

Phase 6 — Infrastructure & Monitoring
6.1 Backup Strategy

Implementar:

backup PostgreSQL

backup recordings

export/import configuração

6.2 Monitoring

Usar métricas do MediaMTX:

Prometheus
Grafana