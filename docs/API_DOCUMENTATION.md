# VMS API Documentation

> Última atualização: 2026-03-16 — Fase 8 Analytics Service

## Índice

1. [Autenticação](#1-autenticação)
2. [Câmeras](#2-câmeras)
3. [Notificações](#3-notificações)
4. [Agents](#4-agents)
5. [Eventos](#5-eventos)
6. [Gravações](#6-gravações)
7. [Health Check](#7-health-check)
8. [Analytics](#8-analytics)

---

## 1. Autenticação

Todos os endpoints (exceto `/api/v1/health/`) requerem autenticação. Dois esquemas são usados:

| Esquema | Header | Usado por |
|---------|--------|-----------|
| JWT Bearer | `Authorization: Bearer <token>` | Usuários humanos (admin, operador) |
| Agent Key | `Authorization: Agent <api_key>` | Agent service local (máquina) |

### 1.1 Obter Token JWT

`
POST /api/v1/auth/token/
`

`ash
curl -s -X POST http://localhost/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "senha123"}' | jq .
`

`json
{
  "access": "eyJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiJ9..."
}
`

### 1.2 Renovar Token

`
POST /api/v1/auth/token/refresh/
`

`ash
curl -s -X POST http://localhost/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}' | jq .
`

**Rate limits:** 5 req/min por IP (anônimo) · 60 req/min por usuário autenticado

### 1.3 Usar Token nas Requisições

`ash
# Salvar token em variável
TOKEN={"username":["Este campo ├® obrigat├│rio."],"password":["Este campo ├® obrigat├│rio."]}

# Usar nas requisições
curl -H "Authorization: Bearer " http://localhost/api/v1/cameras/
`

---

## 2. Câmeras

Base URL: `/api/v1/cameras/`

### 2.1 Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id` | int | leitura | ID auto-gerado |
| `name` | string | sim | Nome da câmera |
| `location` | string | sim | Localização física |
| `rtsp_url` | URL | sim | Endereço RTSP da câmera |
| `manufacturer` | enum | não | `hikvision`, `intelbras`, `dahua`, `axis`, `other` (default: `other`) |
| `retention_days` | enum | não | `7`, `15`, `30`, `60`, `90` (default: `7`) |
| `is_online` | bool | leitura | Status atual (atualizado pelo MediaMTX via webhook) |
| `tenant` | int | leitura | ID do tenant (setado automaticamente) |
| `created_at` | datetime | leitura | |
| `updated_at` | datetime | leitura | |

### 2.2 Listar Câmeras

`
GET /api/v1/cameras/
`

`ash
curl -s http://localhost/api/v1/cameras/ \
  -H "Authorization: Bearer " | jq .
`

`json
[
  {
    "id": 1,
    "name": "Portaria Principal",
    "location": "Entrada Bloco A",
    "rtsp_url": "rtsp://192.168.1.100:554/stream1",
    "manufacturer": "hikvision",
    "retention_days": 30,
    "is_online": true,
    "tenant": 1,
    "created_at": "2026-03-15T10:00:00Z",
    "updated_at": "2026-03-15T10:05:00Z"
  }
]
`

### 2.3 Criar Câmera

`
POST /api/v1/cameras/
`

`ash
curl -s -X POST http://localhost/api/v1/cameras/ \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Estacionamento",
    "location": "Bloco B, subsolo",
    "rtsp_url": "rtsp://192.168.1.101:554/stream1",
    "manufacturer": "intelbras",
    "retention_days": 15
  }' | jq .
`

### 2.4 Atualizar Câmera (parcial)

`
PATCH /api/v1/cameras/{id}/
`

`ash
curl -s -X PATCH http://localhost/api/v1/cameras/1/ \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{"retention_days": 30}' | jq .
`

### 2.5 Deletar Câmera

`
DELETE /api/v1/cameras/{id}/
`

`ash
curl -s -X DELETE http://localhost/api/v1/cameras/1/ \
  -H "Authorization: Bearer "
# → 204 No Content
`

> **Nota:** Deleção é best-effort. Se o MediaMTX estiver indisponível, a câmera é deletada do banco mesmo assim e o evento `camera.deleted` é publicado no event bus.

### 2.6 URL de Streaming

`
GET /api/v1/cameras/{id}/live/
`

`ash
curl -s http://localhost/api/v1/cameras/1/live/ \
  -H "Authorization: Bearer " | jq .
`

`json
{
  "camera_id": 1,
  "is_online": true,
  "hls_url": "http://localhost:8888/tenant-1/cam-1/index.m3u8",
  "webrtc_url": "http://localhost:8889/tenant-1/cam-1/whep",
  "token": "",
  "expires_at": null
}
`

---

## 3. Notificações

Base URL: `/api/v1/notifications/`

Disparo automático de webhooks quando um evento publicado no event bus corresponde ao padrão da regra. O matching usa `fnmatch` (suporta wildcards `*` e `?`).

### 3.1 Regras de Notificação

Base URL: `/api/v1/notifications/rules/`

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id` | int | leitura | |
| `name` | string | sim | Nome descritivo da regra |
| `event_type_pattern` | string | sim | Padrão fnmatch. Ex: `detection.alpr`, `camera.*`, `*` |
| `channel` | enum | sim | `webhook` (único suportado) |
| `destination` | URL | sim | Endpoint que receberá o POST |
| `webhook_secret` | string | não | Se definido, assina o payload com HMAC-SHA256 |
| `is_active` | bool | não | `true` (default). Regras inativas são ignoradas. |
| `created_at` | datetime | leitura | |
| `updated_at` | datetime | leitura | |

#### Listar regras

`ash
curl -s http://localhost/api/v1/notifications/rules/ \
  -H "Authorization: Bearer " | jq .
`

`json
[
  {
    "id": 1,
    "name": "Alerta ALPR Estacionamento",
    "event_type_pattern": "detection.alpr",
    "channel": "webhook",
    "destination": "https://central.exemplo.com/vms-hook",
    "is_active": true,
    "created_at": "2026-03-15T09:00:00Z",
    "updated_at": "2026-03-15T09:00:00Z"
  }
]
`

#### Criar regra

`
POST /api/v1/notifications/rules/
`

`ash
curl -s -X POST http://localhost/api/v1/notifications/rules/ \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alerta câmera offline",
    "event_type_pattern": "camera.offline",
    "channel": "webhook",
    "destination": "https://central.exemplo.com/offlines",
    "webhook_secret": "meu-segredo-32chars-minimo"
  }' | jq .
`

#### Criar regra com wildcard

`ash
# Captura TODOS os eventos do tenant
curl -s -X POST http://localhost/api/v1/notifications/rules/ \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Todos os eventos",
    "event_type_pattern": "*",
    "channel": "webhook",
    "destination": "https://central.exemplo.com/all-events"
  }' | jq .
`

#### Atualizar regra (parcial)

`
PATCH /api/v1/notifications/rules/{id}/
`

`ash
# Desativar sem deletar
curl -s -X PATCH http://localhost/api/v1/notifications/rules/1/ \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
`

#### Deletar regra

`
DELETE /api/v1/notifications/rules/{id}/
`

`ash
curl -s -X DELETE http://localhost/api/v1/notifications/rules/1/ \
  -H "Authorization: Bearer "
# → 204 No Content
`

#### Verificação de Assinatura HMAC

Quando `webhook_secret` está definido, cada requisição HTTP do VMS inclui o header:

`
X-VMS-Signature: <hmac-sha256-hex>
`

O body do POST é JSON com `sort_keys=True`. Verificação no receptor (Python):

`python
import hashlib
import hmac

def verify_vms_signature(secret: str, body: bytes, signature: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
`

### 3.2 Logs de Notificação

Base URL: `/api/v1/notifications/logs/`

Somente leitura. Registra cada tentativa de despacho de webhook.

#### Campos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | int | |
| `rule` | int | ID da regra disparada |
| `rule_name` | string | Nome da regra |
| `event_id` | int | ID do evento que disparou |
| `event_type` | string | Tipo do evento |
| `status` | string | `success` ou `failed` |
| `response_code` | int | HTTP status retornado pelo receptor |
| `response_body` | string | Corpo da resposta (truncado para debug) |
| `created_at` | datetime | |

#### Listar logs

`
GET /api/v1/notifications/logs/
`

`ash
curl -s http://localhost/api/v1/notifications/logs/ \
  -H "Authorization: Bearer " | jq .
`

`json
[
  {
    "id": 42,
    "rule": 1,
    "rule_name": "Alerta ALPR Estacionamento",
    "event_id": 123,
    "event_type": "detection.alpr",
    "status": "success",
    "response_code": 200,
    "response_body": "ok",
    "created_at": "2026-03-15T10:31:00Z"
  }
]
`

#### Ver log específico

`
GET /api/v1/notifications/logs/{id}/
`

### 3.3 Padrões de event_type_pattern

| Padrão | Eventos que casam |
|--------|--------------------|
| `detection.alpr` | Detecção de placa (Fluxo A — câmera inteligente) |
| `analytics.lpr.detection` | OCR server-side (Fluxo B — câmera burra) |
| `analytics.intrusion.detected` | Intrusão em zona virtual |
| `analytics.people.count` | Contagem de pessoas |
| `analytics.vehicle.count` | Contagem de veículos |
| `analytics.weapon.detected` | Detecção de arma |
| `analytics.face.recognized` | Reconhecimento facial |
| `camera.online` | Câmera ficou online |
| `camera.offline` | Câmera ficou offline |
| `camera.created` | Nova câmera cadastrada |
| `camera.deleted` | Câmera removida |
| `agent.created` | Novo agent criado |
| `agent.revoked` | Agent revogado |
| `camera.*` | Qualquer evento de câmera |
| `analytics.*` | Qualquer evento de analytics |
| `*` | Todos os eventos do tenant |

---

## 4. Agents

Os agents são processos locais que rodam na rede do cliente. Eles fazem pull de configuração (polling a cada 30s) e push de streams RTMP para o MediaMTX na nuvem.

**Dois tipos de autenticação:**
- Endpoints de gestão: JWT Bearer (usuário admin)
- Endpoints do agent: `Authorization: Agent <api_key>`

### 4.1 Gestão de Agents (JWT)

Base URL: `/api/v1/agents/`

#### Listar agents

`
GET /api/v1/agents/
`

`ash
curl -s http://localhost/api/v1/agents/ \
  -H "Authorization: Bearer " | jq .
`

`json
[
  {
    "id": 1,
    "name": "Agent Sede SP",
    "tenant": 1,
    "status": "online",
    "last_heartbeat": "2026-03-15T10:29:55Z",
    "version": "1.2.0",
    "metadata": {},
    "created_at": "2026-03-10T08:00:00Z",
    "updated_at": "2026-03-15T10:29:55Z"
  }
]
`

#### Criar agent

`
POST /api/v1/agents/
`

`ash
curl -s -X POST http://localhost/api/v1/agents/ \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{"name": "Agent Sede SP"}' | jq .
`

`json
{
  "id": 1,
  "name": "Agent Sede SP",
  "api_key": "vms_AgAbCdEfGhIjKlMnOpQrStUvWxYz123456",
  "status": "pending",
  "created_at": "2026-03-15T10:00:00Z"
}
`

> ⚠️ **A `api_key` é exibida APENAS UMA VEZ.** Copie e guarde imediatamente.
> Não há como recuperá-la depois. Se perder, revogue e crie um novo agent.

#### Revogar agent

`
DELETE /api/v1/agents/{id}/
`

`ash
curl -s -X DELETE http://localhost/api/v1/agents/1/ \
  -H "Authorization: Bearer "
# → 204 No Content
`

O agent revogado perderá autenticação imediatamente no próximo request.

### 4.2 Endpoints do Agent

Usados pelo processo agent rodando na rede do cliente. Não requerem JWT — apenas a api_key.

#### Dados do próprio agent

`
GET /api/v1/agents/me/
Authorization: Agent <api_key>
`

`ash
API_KEY="vms_AgAbCdEfGhIjKlMnOpQrStUvWxYz123456"

curl -s http://localhost/api/v1/agents/me/ \
  -H "Authorization: Agent " | jq .
`

`json
{
  "id": 1,
  "name": "Agent Sede SP",
  "tenant": 1,
  "status": "online",
  "last_heartbeat": "2026-03-15T10:29:55Z",
  "version": "1.2.0",
  "metadata": {},
  "created_at": "2026-03-10T08:00:00Z",
  "updated_at": "2026-03-15T10:29:55Z"
}
`

#### Configuração de câmeras

`
GET /api/v1/agents/me/config/
Authorization: Agent <api_key>
`

`ash
curl -s http://localhost/api/v1/agents/me/config/ \
  -H "Authorization: Agent " | jq .
`

`json
{
  "agent_id": 1,
  "tenant_id": 1,
  "poll_interval_seconds": 30,
  "cameras": [
    {
      "id": 3,
      "name": "Portaria",
      "rtsp_url": "rtsp://192.168.1.100:554/stream1",
      "rtmp_push_url": "rtmp://vms.exemplo.com:1935/tenant-1/cam-3",
      "enabled": true
    }
  ]
}
`

O agent usa `rtmp_push_url` para iniciar ffmpeg em modo pass-through (sem reencoding):

`ash
ffmpeg -rtsp_transport tcp \
  -i "rtsp://192.168.1.100:554/stream1" \
  -c copy \
  -f flv "rtmp://vms.exemplo.com:1935/tenant-1/cam-3"
`

> ⚠️ Use sempre `-c copy`. Reencoding gera carga de CPU inaceitável.

#### Enviar heartbeat

`
POST /api/v1/agents/me/heartbeat/
Authorization: Agent <api_key>
`

`ash
curl -s -X POST http://localhost/api/v1/agents/me/heartbeat/ \
  -H "Authorization: Agent " \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.2.0",
    "uptime_seconds": 3600,
    "cameras": {
      "3": {"status": "streaming", "fps": 25}
    }
  }' | jq .
`

`json
{"status": "ok"}
`

O heartbeat atualiza `last_heartbeat` e `status` do agent para `online`. Um Celery Beat job verifica a cada 5 minutos agentes sem heartbeat recente e os marca como `offline`.

---

## 5. Eventos

Base URL: `/api/v1/events/`

### 5.1 Listar Eventos

`ash
curl -s "http://localhost/api/v1/events/" \
  -H "Authorization: Bearer " | jq .
`

### 5.2 Filtros Disponíveis

| Parâmetro | Exemplo | Descrição |
|-----------|---------|-----------|
| `event_type` | `detection.alpr` | Filtrar por tipo de evento |
| `camera` | `1` | Filtrar por câmera |
| `plate` | `ABC1D23` | Filtrar por placa (ALPR) |
| `created_at__gte` | `2026-03-15T00:00:00Z` | A partir de (ISO 8601) |
| `created_at__lte` | `2026-03-15T23:59:59Z` | Até (ISO 8601) |

`ash
# Buscar detecções ALPR de uma câmera específica hoje
curl -s "http://localhost/api/v1/events/?event_type=detection.alpr&camera=1&created_at__gte=2026-03-15T00:00:00Z" \
  -H "Authorization: Bearer " | jq .
`

### 5.3 Webhook ALPR — Câmera Inteligente (Fluxo A)

Câmeras Hikvision/Intelbras enviam detecções para o FastAPI:

`
POST /webhooks/alpr/{manufacturer}/
`

Fabricantes suportados: `hikvision`, `intelbras`, `generic`

`ash
# Simular detecção Hikvision
curl -s -X POST http://localhost/webhooks/alpr/hikvision/ \
  -H "Content-Type: application/json" \
  -d '{
    "ipAddress": "192.168.1.100",
    "dateTime": "2026-03-15T10:30:00+00:00",
    "ANPR": {
      "licensePlate": "ABC1D23",
      "country": "BR",
      "confidence": 95
    }
  }'

# Simular detecção Intelbras
curl -s -X POST http://localhost/webhooks/alpr/intelbras/ \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-03-15T10:30:00",
    "camera_id": "CAM001",
    "plate": "ABC1D23",
    "confidence": 0.95
  }'
`

> **Rate limit:** 100 req/min por IP no endpoint `/webhooks/*`

---

## 6. Gravações

Base URL: `/api/v1/recordings/`

As gravações são geradas automaticamente pelo MediaMTX em segmentos de 60 segundos (fMP4). Não há API para iniciar/parar gravação — isso é configurado no MediaMTX.

### 6.1 Listar Segmentos

`ash
# Todos os segmentos de uma câmera
curl -s "http://localhost/api/v1/recordings/?camera=1" \
  -H "Authorization: Bearer " | jq .
`

### 6.2 Timeline de Gravações

`ash
curl -s "http://localhost/api/v1/cameras/1/timeline/?start=2026-03-15T00:00:00Z&end=2026-03-15T23:59:59Z" \
  -H "Authorization: Bearer " | jq .
`

### 6.3 Gerar Clipe

`ash
curl -s -X POST http://localhost/api/v1/recordings/clips/ \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{
    "camera": 1,
    "start_time": "2026-03-15T10:00:00Z",
    "end_time": "2026-03-15T10:05:00Z",
    "title": "Incidente portaria"
  }' | jq .
`

---

## 7. Health Check

Não requer autenticação. Use para monitoramento externo (uptime robots, load balancers, alertas).

`
GET /api/v1/health/
`

`ash
curl -s http://localhost/api/v1/health/ | jq .
`

**Resposta 200 — todos os serviços operacionais:**

`json
{
  "status": "healthy",
  "services": {
    "db": "ok",
    "redis": "ok",
    "rabbitmq": "ok"
  }
}
`

**Resposta 503 — algum serviço degradado:**

`json
{
  "status": "degraded",
  "services": {
    "db": "ok",
    "redis": "error",
    "rabbitmq": "ok"
  }
}
`

Use em alertas de uptime:

`ash
# Retorna 0 se saudável, 1 se degradado
curl -s -o /dev/null -w "%{http_code}" http://localhost/api/v1/health/ | grep -q 200
`

---

## 8. Analytics

Base URL: `/api/v1/analytics/`

O módulo analytics é composto por dois subsistemas:
- **ROI + DwellEvents** — CRUD e leitura para usuários (JWT)
- **Ingest + ROI internos** — usados pelo `analytics_service` (API key interna)

### 8.1 Esquema de Autenticação Interna

O `analytics_service` autentica usando um header customizado:

```
Authorization: Analytics <ANALYTICS_SERVICE_API_KEY>
```

A chave deve ser idêntica nos dois containers. Configure em `.env`:

```bash
ANALYTICS_SERVICE_API_KEY=sua-chave-secreta-longa
```

> Estes endpoints (`/ingest/` e `/internal/rois/`) recusam JWT. São exclusivos para comunicação máquina-a-máquina.

---

### 8.2 Regions of Interest (ROI)

Base URL: `/api/v1/analytics/rois/`
Auth: JWT Bearer

ROIs são zonas desenhadas sobre o campo de visão de uma câmera. Cada ROI tem um `ia_type` que define qual plugin de analytics a processa.

#### Campos

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id` | int | leitura | |
| `camera` | int | sim | ID da câmera |
| `name` | string | sim | Nome descritivo (ex: "Vaga VIP 1") |
| `ia_type` | enum | sim | Tipo de análise (ver tabela abaixo) |
| `polygon_points` | array | sim | `[[x, y], ...]` normalizados 0.0–1.0 |
| `config` | object | não | Parâmetros extras do plugin |
| `is_active` | bool | não | `true` (default) |
| `created_at` | datetime | leitura | |
| `updated_at` | datetime | leitura | |

**Valores de `ia_type`:**

| Valor | Descrição | Plugin |
|-------|-----------|--------|
| `vehicle_dwell` | Permanência veicular | `vehicle_dwell` |
| `intrusion` | Intrusão em zona proibida | `intrusion_detection` |
| `human_traffic` | Contagem de pessoas | `people_count` |
| `vehicle_traffic` | Contagem de veículos | `vehicle_count` |
| `lpr` | Leitura de placas server-side | `lpr_parking` |
| `facial` | Reconhecimento facial (LGPD opt-in) | `face_recognition` |

#### Listar ROIs

```
GET /api/v1/analytics/rois/
GET /api/v1/analytics/rois/?camera=5
```

```bash
curl -s "http://localhost/api/v1/analytics/rois/?camera=5" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

```json
[
  {
    "id": 3,
    "camera": 5,
    "name": "Vaga VIP 1",
    "ia_type": "vehicle_dwell",
    "polygon_points": [[0.1, 0.2], [0.4, 0.2], [0.4, 0.8], [0.1, 0.8]],
    "config": {},
    "is_active": true,
    "created_at": "2026-03-16T09:00:00Z",
    "updated_at": "2026-03-16T09:00:00Z"
  }
]
```

#### Criar ROI

```
POST /api/v1/analytics/rois/
```

```bash
curl -s -X POST http://localhost/api/v1/analytics/rois/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "camera": 5,
    "name": "Vaga VIP 1",
    "ia_type": "vehicle_dwell",
    "polygon_points": [
      [0.1, 0.2],
      [0.4, 0.2],
      [0.4, 0.8],
      [0.1, 0.8]
    ],
    "config": {}
  }' | jq .
```

> **Coordenadas normalizadas:** `x` e `y` são frações da largura e altura do frame (0.0 = borda esquerda/superior, 1.0 = borda direita/inferior). O frontend ROI Editor converte coordenadas de pixel para normalizadas automaticamente.

#### Atualizar ROI (parcial)

```
PATCH /api/v1/analytics/rois/{id}/
```

```bash
# Desativar ROI sem deletar
curl -s -X PATCH http://localhost/api/v1/analytics/rois/3/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

#### Deletar ROI

```
DELETE /api/v1/analytics/rois/{id}/
```

---

### 8.3 Dwell Events

Base URL: `/api/v1/analytics/dwell-events/`
Auth: JWT Bearer — somente leitura

Eventos de permanência veicular gerados pelo plugin `vehicle_dwell`. Um evento é criado quando um veículo entra em uma ROI e atualizado quando sai.

#### Campos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | int | |
| `camera` | int | ID da câmera |
| `camera_name` | string | Nome da câmera |
| `tenant` | int | ID do tenant |
| `roi` | int \| null | ID da ROI onde ocorreu |
| `roi_name` | string \| null | Nome da ROI |
| `track_id` | int | ID do veículo pelo tracker |
| `entered_at` | datetime | Momento de entrada na ROI |
| `exited_at` | datetime \| null | Momento de saída (null = em andamento) |
| `dwell_seconds` | int \| null | Duração em segundos |
| `frame_path` | string | Caminho do snapshot de entrada |
| `is_valid` | bool \| null | `true` = 60–240s; `false` = fora do range; `null` = em andamento |
| `created_at` | datetime | |

#### Listar eventos

```
GET /api/v1/analytics/dwell-events/
```

**Filtros disponíveis:**

| Parâmetro | Exemplo | Descrição |
|-----------|---------|-----------|
| `camera` | `5` | Filtrar por câmera |
| `is_valid` | `true` | Apenas permanências válidas (60–240s) |
| `date_from` | `2026-03-16` | A partir de (data, YYYY-MM-DD) |
| `date_to` | `2026-03-16` | Até (data, YYYY-MM-DD) |

```bash
# Permanências válidas de hoje
curl -s "http://localhost/api/v1/analytics/dwell-events/?is_valid=true&date_from=2026-03-16" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "camera": 5,
      "camera_name": "Estacionamento B2",
      "tenant": 1,
      "roi": 3,
      "roi_name": "Vaga VIP 1",
      "track_id": 42,
      "entered_at": "2026-03-16T10:00:00Z",
      "exited_at": "2026-03-16T10:02:30Z",
      "dwell_seconds": 150,
      "frame_path": "/recordings/snapshots/cam5_track42.jpg",
      "is_valid": true,
      "created_at": "2026-03-16T10:00:01Z"
    }
  ]
}
```

```bash
# Veículos ainda estacionados (sem saída registrada)
curl -s "http://localhost/api/v1/analytics/dwell-events/?is_valid=null" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### 8.4 Dashboard Analytics

Auth: JWT Bearer

#### Estatísticas gerais

```
GET /api/v1/dashboard/stats/
```

```bash
curl -s http://localhost/api/v1/dashboard/stats/ \
  -H "Authorization: Bearer $TOKEN" | jq .
```

```json
{
  "total_cameras": 12,
  "online_cameras": 10,
  "offline_cameras": 2,
  "total_events_today": 47,
  "dwell_events_today": 8,
  "total_clips": 0,
  "events_by_type_today": {
    "detection.alpr": 31,
    "analytics.vehicle.dwell": 8,
    "camera.offline": 2
  }
}
```

#### Eventos por hora (últimas 24h)

```
GET /api/v1/dashboard/events-by-hour/
```

```bash
curl -s http://localhost/api/v1/dashboard/events-by-hour/ \
  -H "Authorization: Bearer $TOKEN" | jq .
```

```json
[
  {"hour": "08h", "events": 0},
  {"hour": "09h", "events": 5},
  {"hour": "10h", "events": 12},
  ...
]
```

---

### 8.5 Ingest (uso interno — analytics_service)

```
POST /api/v1/analytics/ingest/
Authorization: Analytics <ANALYTICS_SERVICE_API_KEY>
```

Endpoint usado exclusivamente pelo `analytics_service` para enviar resultados de plugins ao Django. Não deve ser chamado por usuários.

**Body:**

```json
{
  "plugin":     "vehicle_dwell",
  "camera_id":  5,
  "tenant_id":  1,
  "event_type": "analytics.vehicle.dwell",
  "payload": {
    "track_id":      42,
    "roi_id":         3,
    "entered_at":    "2026-03-16T10:00:00+00:00",
    "exited_at":     "2026-03-16T10:02:30+00:00",
    "dwell_seconds": 150,
    "frame_path":    "/recordings/snapshots/cam5_track42.jpg",
    "is_valid":      true
  }
}
```

**Respostas:**

| Status | Situação |
|--------|----------|
| `202 Accepted` | Evento recebido e processado |
| `400 Bad Request` | Campos obrigatórios ausentes |
| `401 Unauthorized` | API key ausente ou inválida |
| `422 Unprocessable Entity` | Plugin desconhecido |

---

### 8.6 ROIs internas (uso interno — analytics_service)

```
GET /api/v1/analytics/internal/rois/?camera={camera_id}
Authorization: Analytics <ANALYTICS_SERVICE_API_KEY>
```

Retorna ROIs ativas de uma câmera para consumo pelo `analytics_service`. Não requer JWT.

```bash
# analytics_service chama internamente:
curl -s "http://django:8000/api/v1/analytics/internal/rois/?camera=5" \
  -H "Authorization: Analytics $ANALYTICS_SERVICE_API_KEY" | jq .
```

```json
[
  {
    "id": 3,
    "name": "Vaga VIP 1",
    "ia_type": "vehicle_dwell",
    "polygon_points": [[0.1, 0.2], [0.4, 0.2], [0.4, 0.8], [0.1, 0.8]],
    "config": {}
  }
]
```

---

### 8.7 SSE — Eventos de analytics em tempo real

Eventos de analytics são publicados no canal Redis `vms:realtime` e chegam ao frontend via SSE. Conecte ao stream da mesma forma que outros eventos:

```javascript
const es = new EventSource(`/sse/?token=${jwt}`);
es.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'dwell_event') {
    console.log('Novo evento de dwell:', data);
    // { type, tenant_id, camera_id, track_id, event_id, is_valid, dwell_seconds }
  }
};
```

---

## Apêndice A — Mapa de Endpoints

| Método | Endpoint | Auth | Descrição |
|--------|----------|------|-----------|
| POST | `/api/v1/auth/token/` | — | Obter JWT |
| POST | `/api/v1/auth/token/refresh/` | — | Renovar JWT |
| GET | `/api/v1/health/` | — | Health check |
| GET | `/api/v1/cameras/` | JWT | Listar câmeras |
| POST | `/api/v1/cameras/` | JWT | Criar câmera |
| GET | `/api/v1/cameras/{id}/` | JWT | Detalhe |
| PUT/PATCH | `/api/v1/cameras/{id}/` | JWT | Atualizar |
| DELETE | `/api/v1/cameras/{id}/` | JWT | Deletar |
| GET | `/api/v1/cameras/{id}/live/` | JWT | URLs de streaming |
| GET | `/api/v1/cameras/{id}/timeline/` | JWT | Timeline de gravações |
| GET | `/api/v1/events/` | JWT | Listar eventos |
| GET | `/api/v1/recordings/` | JWT | Listar segmentos |
| POST | `/api/v1/recordings/clips/` | JWT | Gerar clipe |
| GET | `/api/v1/notifications/rules/` | JWT | Listar regras |
| POST | `/api/v1/notifications/rules/` | JWT | Criar regra |
| GET/PUT/PATCH | `/api/v1/notifications/rules/{id}/` | JWT | Detalhe/atualizar |
| DELETE | `/api/v1/notifications/rules/{id}/` | JWT | Deletar regra |
| GET | `/api/v1/notifications/logs/` | JWT | Listar logs |
| GET | `/api/v1/notifications/logs/{id}/` | JWT | Detalhe do log |
| GET | `/api/v1/agents/` | JWT | Listar agents |
| POST | `/api/v1/agents/` | JWT | Criar agent |
| DELETE | `/api/v1/agents/{id}/` | JWT | Revogar agent |
| GET | `/api/v1/agents/me/` | Agent | Dados do agent |
| GET | `/api/v1/agents/me/config/` | Agent | Config de câmeras |
| POST | `/api/v1/agents/me/heartbeat/` | Agent | Enviar heartbeat |
| POST | `/webhooks/alpr/{manufacturer}/` | — | ALPR câmera inteligente |
| GET | `/sse/` | JWT (query param) | Server-Sent Events |
| GET | `/api/v1/analytics/rois/` | JWT | Listar ROIs |
| POST | `/api/v1/analytics/rois/` | JWT | Criar ROI |
| GET/PUT/PATCH | `/api/v1/analytics/rois/{id}/` | JWT | Detalhe/atualizar ROI |
| DELETE | `/api/v1/analytics/rois/{id}/` | JWT | Deletar ROI |
| GET | `/api/v1/analytics/dwell-events/` | JWT | Listar eventos de dwell |
| GET | `/api/v1/analytics/dwell-events/{id}/` | JWT | Detalhe do evento |
| GET | `/api/v1/dashboard/stats/` | JWT | Estatísticas do dashboard |
| GET | `/api/v1/dashboard/events-by-hour/` | JWT | Eventos por hora (24h) |
| POST | `/api/v1/analytics/ingest/` | Analytics key | Ingest interno (analytics_service) |
| GET | `/api/v1/analytics/internal/rois/` | Analytics key | ROIs internas (analytics_service) |
