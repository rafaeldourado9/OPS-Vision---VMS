# VMS White-Label — Guia Completo: Do Zero ao Deploy

> Documentação de todas as fases do projeto, desde a configuração do ambiente
> de desenvolvimento até o deploy final em produção.

---

## Índice

1. [Fase 1 — Pré-requisitos e Ambiente](#fase-1--pré-requisitos-e-ambiente)
2. [Fase 2 — Configuração do Projeto](#fase-2--configuração-do-projeto)
3. [Fase 3 — Subindo o Ambiente de Desenvolvimento](#fase-3--subindo-o-ambiente-de-desenvolvimento)
4. [Fase 4 — Banco de Dados e Migrations](#fase-4--banco-de-dados-e-migrations)
5. [Fase 5 — Validação dos Serviços](#fase-5--validação-dos-serviços)
6. [Fase 6 — Configuração das Câmeras](#fase-6--configuração-das-câmeras)
7. [Fase 7 — Streaming e Gravação](#fase-7--streaming-e-gravação)
8. [Fase 8 — Eventos e Webhooks](#fase-8--eventos-e-webhooks)
9. [Fase 9 — Frontend](#fase-9--frontend)
10. [Fase 10 — Testes e Qualidade](#fase-10--testes-e-qualidade)
11. [Fase 11 — Preparação para Produção](#fase-11--preparação-para-produção)
12. [Fase 12 — Deploy em Produção](#fase-12--deploy-em-produção)
13. [Fase 13 — Monitoramento e Manutenção](#fase-13--monitoramento-e-manutenção)
14. [Apêndice A — Mapa de Portas](#apêndice-a--mapa-de-portas)
15. [Apêndice B — Variáveis de Ambiente](#apêndice-b--variáveis-de-ambiente)
16. [Apêndice C — Troubleshooting](#apêndice-c--troubleshooting)

---

## Fase 1 — Pré-requisitos e Ambiente

### 1.1 Requisitos de Software

| Software | Versão mínima | Uso |
|----------|---------------|-----|
| Docker | 24.x | Containerização de todos os serviços |
| Docker Compose | 2.20+ | Orquestração dos 10 containers |
| Git | 2.40+ | Controle de versão |
| Make | 4.x | Automação de comandos |

> **Nota:** Node.js e Python **não** precisam estar instalados na máquina host.
> Tudo roda dentro dos containers Docker.

### 1.2 Requisitos de Hardware (Desenvolvimento)

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disco | 20 GB livres | 50 GB (SSD) |

### 1.3 Requisitos de Hardware (Produção)

| Recurso | Para 10 câmeras | Para 50 câmeras | Para 100+ câmeras |
|---------|-----------------|-----------------|-------------------|
| CPU | 4 cores | 8 cores | 16 cores |
| RAM | 8 GB | 16 GB | 32 GB |
| Disco | 500 GB SSD | 2 TB SSD | 4+ TB SSD/HDD |
| Rede | 100 Mbps | 1 Gbps | 1 Gbps+ |

> **Regra de cálculo de storage:**
> Cada câmera a 4 Mbps = ~42 GB/dia. Para 10 câmeras com 7 dias de retenção: ~2.9 TB.

### 1.4 Requisitos de Rede

```
Portas que precisam estar acessíveis:

Porta 80       → Frontend + API (nginx)
Porta 8554     → RTSP (receber streams das câmeras)
Porta 1935     → RTMP (alternativa ao RTSP)
Porta 8889     → WebRTC (player no browser)
Porta 8888     → HLS (player no browser, fallback)
```

---

## Fase 2 — Configuração do Projeto

### 2.1 Clonar o Repositório

```bash
git clone <url-do-repositorio> vms
cd vms
```

### 2.2 Configurar Variáveis de Ambiente

```bash
cp .env.example .env
```

Editar `.env` com valores reais. **Variáveis obrigatórias para alterar:**

```bash
# SEGURANÇA — trocar TODOS esses valores
DJANGO_SECRET_KEY=<gerar-chave-segura-64-chars>
JWT_SECRET=<gerar-chave-segura-64-chars>
POSTGRES_PASSWORD=<senha-forte>
RABBITMQ_PASSWORD=<senha-forte>

# REDE — ajustar para o IP/domínio do servidor
DJANGO_ALLOWED_HOSTS=seu-dominio.com,IP-DO-SERVIDOR
CORS_ORIGINS=http://seu-dominio.com,https://seu-dominio.com
MEDIAMTX_HLS_BASE_URL=http://IP-DO-SERVIDOR:8888
MEDIAMTX_WEBRTC_BASE_URL=http://IP-DO-SERVIDOR:8889
```

Para gerar chaves seguras:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
# ou
openssl rand -base64 64
```

### 2.3 Estrutura de Serviços

```
┌─────────────────────────────────────────────────────────────────┐
│                        docker compose                           │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │  nginx   │  │  Django   │  │ FastAPI  │  │   MediaMTX    │   │
│  │   :80    │  │  :8000    │  │  :8001   │  │  RTSP :8554   │   │
│  └──────────┘  └──────────┘  └──────────┘  │  HLS  :8888   │   │
│                                             │  WRT  :8889   │   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  API  :9997   │   │
│  │ Frontend │  │  Worker   │  │   Beat   │  └───────────────┘   │
│  │  :3000   │  │ (Celery)  │  │ (Celery) │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │PostgreSQL│  │  Redis   │  │ RabbitMQ │                      │
│  │  :5432   │  │  :6379   │  │  :5672   │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Fase 3 — Subindo o Ambiente de Desenvolvimento

### 3.1 Build das Imagens

```bash
make build
```

Isso compila 4 imagens Docker:
- `vms-django` (Python 3.12 + Django + dependências)
- `vms-fastapi` (Python 3.12 + FastAPI)
- `vms-worker` (mesmo do Django, executa Celery)
- `vms-frontend` (Node 20 + Next.js)

### 3.2 Subir Todos os Serviços

```bash
make up
```

Docker Compose sobe **10 containers** na ordem correta:
1. `postgres` → aguarda health check (pg_isready)
2. `redis` → aguarda health check (redis-cli ping)
3. `rabbitmq` → aguarda health check (rabbitmq-diagnostics)
4. `mediamtx` → aguarda health check (API disponível em :9997)
5. `django` → depende de postgres, redis, rabbitmq
6. `fastapi` → depende de redis, rabbitmq
7. `worker` → depende de django, rabbitmq
8. `beat` → depende de worker, rabbitmq
9. `frontend` → depende de django
10. `nginx` → depende de django, fastapi, frontend

### 3.3 Verificar se Tudo Subiu

```bash
docker compose ps
```

Todos os 10 serviços devem estar `Up (healthy)`:

```
NAME         STATUS              PORTS
postgres     Up (healthy)        5432
redis        Up (healthy)        6379
rabbitmq     Up (healthy)        5672, 15672
mediamtx     Up (healthy)        8554, 1935, 8888, 8889, 9997
django       Up                  8000
fastapi      Up                  8001
worker       Up                  —
beat         Up                  —
frontend     Up                  3000
nginx        Up                  80
```

### 3.4 Ver Logs

```bash
# Todos os serviços
make logs

# Serviço específico
make logs s=django
make logs s=fastapi
make logs s=worker
make logs s=mediamtx
```

---

## Fase 4 — Banco de Dados e Migrations

### 4.1 Rodar Migrations

```bash
make migrate
```

Cria as tabelas para os 4 apps Django:
- `users` → Tenant, User (custom com multi-tenant)
- `cameras` → Camera (com choices de Manufacturer, RetentionDays)
- `events` → Event (com EventType choices)
- `recordings` → Recording, RecordingSegment, Clip

### 4.2 Criar Superusuário

```bash
docker compose exec django python manage.py createsuperuser
```

### 4.3 Popular com Dados de Teste (opcional)

```bash
make seed
```

Cria: 1 tenant "Demo", 1 usuário admin, 10 câmeras de exemplo.

### 4.4 Acessar o Banco Diretamente

```bash
make dbshell
# Conecta via: psql -U vms -d vms

# Verificar tabelas criadas
\dt

# Verificar extensões
\dx
# → uuid-ossp, pg_trgm
```

---

## Fase 5 — Validação dos Serviços

Após subir tudo, validar que cada serviço está operacional.

### 5.1 Django API

```bash
# Health check
curl http://localhost:8000/api/v1/

# Obter token JWT
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"suasenha"}'

# Resposta esperada:
# {"access":"eyJ...","refresh":"eyJ..."}

# Listar câmeras (autenticado)
curl http://localhost:8000/api/v1/cameras/ \
  -H "Authorization: Bearer <access_token>"
```

### 5.2 FastAPI

```bash
# Health check
curl http://localhost:8001/health

# Documentação automática (Swagger)
# Abrir no browser: http://localhost:8001/docs
```

### 5.3 MediaMTX

```bash
# Listar paths configurados
curl http://localhost:9997/v3/paths/list

# Listar configuração
curl http://localhost:9997/v3/config/paths/list
```

### 5.4 RabbitMQ

```bash
# Management UI
# Abrir no browser: http://localhost:15672
# Usuário: vms
# Senha: (valor de RABBITMQ_PASSWORD no .env)
```

### 5.5 Django Admin

```bash
# Abrir no browser: http://localhost:8000/admin/
# Usar o superusuário criado na Fase 4.2
```

### 5.6 Frontend

```bash
# Abrir no browser: http://localhost:3000
# Ou via nginx:    http://localhost
```

---

## Fase 6 — Configuração das Câmeras

### 6.1 Adicionar Câmera via API

```bash
TOKEN="<access_token>"

curl -X POST http://localhost:8000/api/v1/cameras/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Entrada Principal",
    "location": "Portaria",
    "rtsp_url": "rtsp://192.168.1.100:554/stream1",
    "manufacturer": "intelbras",
    "retention_days": 7
  }'
```

O que acontece internamente:
1. Django cria a câmera no PostgreSQL
2. Django registra o path no MediaMTX via API (`POST /v3/config/paths/add/tenant-1/cam-1`)
3. Django publica evento `camera.created` no RabbitMQ
4. MediaMTX começa a puxar o stream RTSP da câmera

### 6.2 Adicionar Câmera via Frontend

1. Acessar `http://localhost/cameras`
2. Clicar em **"+ Add Camera"**
3. Preencher: Nome, Local, Fabricante, RTSP URL
4. Clicar em **"Adicionar"**

### 6.3 Verificar Câmera no MediaMTX

```bash
# Listar paths ativos
curl http://localhost:9997/v3/paths/list

# Verificar path específico
curl http://localhost:9997/v3/config/paths/get/tenant-1/cam-1
```

### 6.4 Fluxo de Status (Online/Offline)

```
Camera envia RTSP → MediaMTX recebe stream
                   → MediaMTX POST /webhooks/mediamtx/on_ready
                   → FastAPI dispara task cameras.set_online(id, True)
                   → Django atualiza DB + Redis + publica via PubSub
                   → SSE notifica frontend → badge muda para "Online"

Camera para RTSP → MediaMTX detecta queda
                  → MediaMTX POST /webhooks/mediamtx/on_not_ready
                  → FastAPI dispara task cameras.set_online(id, False)
                  → Status muda para "Offline"
```

### 6.5 Health Check Automático

O Celery Beat roda a cada **5 minutos** (configurável):
- Task `cameras.health_check_all` consulta o MediaMTX
- Para cada câmera, verifica se o path está ativo
- Atualiza status online/offline no banco e no cache Redis

---

## Fase 7 — Streaming e Gravação

### 7.1 Assistir Stream ao Vivo

**Via Frontend:**
- Acessar `/live` para ver grid de todas as câmeras
- Acessar `/cameras/<id>` para ver uma câmera específica
- Player usa HLS (hls.js) com fallback para WebRTC

**Via URL Direta:**
```bash
# HLS (browser)
http://localhost:8888/tenant-1/cam-1/

# WebRTC (browser)
http://localhost:8889/tenant-1/cam-1/

# RTSP (VLC, ffplay)
rtsp://localhost:8554/tenant-1/cam-1

# RTMP (OBS, ffplay)
rtmp://localhost:1935/tenant-1/cam-1
```

### 7.2 Autenticação de Stream

Streams são protegidos por token JWT:
1. Frontend chama `GET /api/v1/cameras/<id>/live/`
2. Django gera um stream token (válido por 30 minutos)
3. Frontend passa o token na URL: `?token=<jwt>`
4. MediaMTX valida o token via `POST /streaming/token/verify/` no FastAPI

### 7.3 Gravação Automática

O MediaMTX grava automaticamente em segmentos MP4:

```
Configuração (mediamtx.yml):
  Formato:    fMP4 (fragmented MP4)
  Segmento:   60 segundos
  Retenção:   7 dias (auto-cleanup pelo MediaMTX)
  Path:       /recordings/<path>/<ano>/<mes>/<dia>/<hora-min-seg>.mp4
```

Quando um segmento é concluído:
1. MediaMTX faz `POST /webhooks/mediamtx/record_segment`
2. FastAPI dispara task `recordings.process_segment`
3. Worker usa `ffprobe` para indexar o MP4 (duração, tamanho)
4. Salva `RecordingSegment` no banco

### 7.4 Criar Clips

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/recordings/clips/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": 1,
    "started_at": "2026-03-14T10:00:00Z",
    "ended_at": "2026-03-14T10:05:00Z"
  }'
```

O Worker usa `ffmpeg` para extrair o trecho dos segmentos gravados (stream copy, sem re-encode).

### 7.5 Controle de Storage

```bash
# Ver uso de storage do tenant
curl http://localhost:8000/api/v1/recordings/storage/ \
  -H "Authorization: Bearer $TOKEN"

# Resposta:
# {
#   "used_bytes": 34359738368,
#   "quota_bytes": 107374182400,
#   "usage_ratio": 0.32,
#   "over_quota": false
# }
```

Celery Beat verifica a cada **1 hora**:
- `recordings.check_storage_quota` — alerta se > 80%
- `recordings.cleanup_task` — remove segmentos antigos conforme `retention_days`

---

## Fase 8 — Eventos e Webhooks

### 8.1 Tipos de Evento

| Evento | Trigger | Payload |
|--------|---------|---------|
| `camera.online` | MediaMTX on_ready | camera_id |
| `camera.offline` | MediaMTX on_not_ready | camera_id |
| `camera.created` | API POST /cameras/ | camera_id, tenant_id |
| `camera.deleted` | API DELETE /cameras/ | camera_id, tenant_id |
| `alpr.detected` | Webhook ALPR | plate, confidence, camera_id |
| `recording.started` | Worker inicia gravação | camera_id, segment_id |
| `recording.stopped` | Worker para gravação | camera_id, segment_id |

### 8.2 Configurar Webhook ALPR na Câmera

Para câmeras com LPR integrado (Intelbras, Hikvision, Dahua):

1. Acesse o painel web da câmera (ex: `http://192.168.1.100`)
2. Vá em **Configuração → Evento → ALPR/LPR → Notificação HTTP**
3. Configure o endpoint:

```
URL:    http://<IP-DO-SERVIDOR>/webhooks/alpr
Método: POST
Formato: JSON
```

4. O payload deve conter (ou ser adaptado via normalizer):

```json
{
  "plate": "ABC-1D23",
  "camera_id": 1,
  "confidence": 0.95,
  "timestamp": "2026-03-14T10:30:00Z",
  "image_url": "http://camera/snapshot.jpg"
}
```

### 8.3 Fluxo de Processamento ALPR

```
Camera detecta placa
  → POST /webhooks/alpr (FastAPI)
  → FastAPI publica no RabbitMQ (routing key: alpr.detected)
  → FastAPI dispara task process_alpr_detection_task (Celery)
  → Worker cria Event no banco
  → Worker publica no Redis PubSub (canal: vms:realtime)
  → SSE envia para frontend
  → Frontend mostra notificação + incrementa badge
```

### 8.4 Webhooks Personalizados por Fabricante

Se o formato do webhook da câmera não segue o padrão esperado, crie um **normalizer** em `async_services/services/webhook_processor.py`:

```python
# Exemplo: Intelbras envia formato diferente
def normalize_intelbras_alpr(raw_payload: dict) -> dict:
    return {
        "plate": raw_payload["PlateNumber"],
        "camera_id": raw_payload["ChannelID"],
        "confidence": raw_payload["Confidence"] / 100,
        "timestamp": raw_payload["DateTime"],
    }
```

### 8.5 SSE (Server-Sent Events)

O frontend mantém conexão SSE persistente para receber eventos em tempo real:

```
GET /sse/?token=<jwt>

Eventos recebidos:
  - camera_status  → atualiza online/offline na UI
  - new_event      → incrementa badge de notificação
```

O SSE é gerenciado pelo FastAPI via Redis PubSub:
- Django/Workers publicam em `vms:realtime`
- FastAPI lê do Redis e faz streaming para o browser
- Filtrado por `tenant_id` (multi-tenant)

---

## Fase 9 — Frontend

### 9.1 Páginas Implementadas

| Rota | Descrição |
|------|-----------|
| `/login` | Login com usuário e senha, erro inline, sessão via AuthContext |
| `/live` | Grid de câmeras ao vivo com players HLS |
| `/cameras` | Lista de câmeras com cards (nome, status, fabricante, local, abrir, deletar) |
| `/cameras/[id]` | Detalhe da câmera com player grande + info cards |
| `/cameras/[id]/timeline` | Timeline de gravações com playback e criação de clips |
| `/events` | Tabela de eventos (tipo, câmera, placa, confiança, timestamp) |
| `/recordings` | Lista de clips (ID, câmera, início, fim, status, download) + barra de storage |

### 9.2 Sidebar

Menu lateral expansível com:
- Logo "V" + "VMS"
- Ao Vivo, Câmeras, Eventos, Gravações
- Avatar + nome do usuário
- Botão "Sair" (logout)
- Botão "Recolher" (colapsa para modo ícone)

### 9.3 Autenticação

1. Login envia `POST /api/v1/auth/token/`
2. Recebe `{ access, refresh }` tokens JWT
3. Tokens salvos no `localStorage`
4. Toda request inclui `Authorization: Bearer <access>`
5. 401 → auto-logout e redirect para `/login`

### 9.4 Build de Produção

```bash
# Dentro do container
cd frontend && npm run build

# Ou via Dockerfile multi-stage (produção)
docker build -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_URL=https://seu-dominio.com/api/v1 \
  -t vms-frontend:prod ./frontend
```

---

## Fase 10 — Testes e Qualidade

### 10.1 Rodar Testes

```bash
# Testes unitários (rápido)
make test

# Todos os testes (unitário + integração)
make test-all

# Testes BDD
make test-bdd

# Testes E2E
make test-e2e

# Com cobertura (gera HTML em htmlcov/)
make test-cov
```

### 10.2 Linting e Type Check

```bash
make lint
# Roda:
#   ruff check .          → linting
#   ruff format --check . → formatação
#   mypy apps/            → type checking
```

### 10.3 CI Completa (tudo junto)

```bash
make ci
# = make lint + make test-all
```

### 10.4 Pipeline CI (GitHub Actions)

Automaticamente executado em push para `main` ou PR para `main`:

```
Job 1: lint-and-test
  Services: postgres:16, redis:7
  Steps:
    1. Checkout
    2. Setup Python 3.12
    3. pip install -e ".[test]"
    4. ruff check .
    5. ruff format --check .
    6. mypy apps/
    7. pytest -m "unit or bdd" --cov=apps

Job 2: frontend
  Steps:
    1. Checkout
    2. Setup Node 20
    3. npm ci
    4. npm run build
```

### 10.5 Checklist Antes de Commit

```
[ ] make test       → testes passam
[ ] make lint       → sem warnings
[ ] Commit atômico  → uma feature/fix por commit
[ ] Sem print()     → sem debug esquecido
[ ] Sem secrets     → nada hardcoded
```

---

## Fase 11 — Preparação para Produção

### 11.1 Checklist de Segurança

```
[ ] DJANGO_SECRET_KEY é aleatório e único
[ ] JWT_SECRET é aleatório e único
[ ] POSTGRES_PASSWORD é forte (16+ chars)
[ ] RABBITMQ_PASSWORD é forte
[ ] DJANGO_DEBUG=false
[ ] CORS_ORIGINS lista apenas domínios autorizados
[ ] DJANGO_ALLOWED_HOSTS lista apenas domínios autorizados
[ ] Portas internas (5432, 6379, 5672) NÃO expostas externamente
[ ] MediaMTX API (9997) protegida por senha
[ ] HTTPS configurado via certificado SSL
```

### 11.2 Criar docker-compose.prod.yml

```yaml
# docker-compose.prod.yml — Override para produção
services:
  django:
    command: gunicorn config.wsgi:application -b 0.0.0.0:8000 --workers 4 --timeout 120
    environment:
      - DJANGO_SETTINGS_MODULE=config.settings.prod
    restart: unless-stopped

  fastapi:
    command: uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
    restart: unless-stopped

  worker:
    command: celery -A config.celery worker -l info -Q default,recordings,analytics --concurrency 4
    restart: unless-stopped

  beat:
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        NEXT_PUBLIC_API_URL: https://seu-dominio.com/api/v1
    command: node server.js
    restart: unless-stopped

  postgres:
    ports: []  # Não expor em produção

  redis:
    ports: []  # Não expor em produção

  rabbitmq:
    ports:
      - "15672:15672"  # Apenas management, se necessário
    # Remover 5672 da exposição externa

  mediamtx:
    restart: unless-stopped
```

### 11.3 Settings de Produção (Django)

O arquivo `core/config/settings/prod.py` já configura:

```python
DEBUG = False
SECURE_SSL_REDIRECT = True        # Força HTTPS
SESSION_COOKIE_SECURE = True      # Cookie só via HTTPS
CSRF_COOKIE_SECURE = True         # CSRF só via HTTPS
SECURE_HSTS_SECONDS = 31536000    # HSTS por 1 ano
```

### 11.4 Configurar HTTPS

**Opção 1 — Certbot (Let's Encrypt) no servidor:**

```bash
# Instalar certbot
apt install certbot python3-certbot-nginx

# Gerar certificado
certbot --nginx -d seu-dominio.com
```

**Opção 2 — Cloudflare/CDN:**
- Apontar DNS para o IP do servidor
- Configurar SSL no Cloudflare (Full Strict)

**Opção 3 — Traefik como reverse proxy:**
- Substituir nginx por Traefik
- Certificados automáticos via ACME

### 11.5 Configurar Nginx para HTTPS

Adicionar ao `infra/nginx/nginx.conf`:

```nginx
server {
    listen 80;
    server_name seu-dominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name seu-dominio.com;

    ssl_certificate     /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com/privkey.pem;

    # ... demais locations (api, sse, webhooks, frontend)
}
```

### 11.6 Backup do Banco

```bash
# Backup manual
docker compose exec postgres pg_dump -U vms vms > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260314.sql | docker compose exec -T postgres psql -U vms vms
```

Configurar backup automático com cron:

```bash
# /etc/cron.d/vms-backup
0 2 * * * root docker compose -f /opt/vms/docker-compose.yml exec -T postgres pg_dump -U vms vms | gzip > /backups/vms_$(date +\%Y\%m\%d).sql.gz
```

---

## Fase 12 — Deploy em Produção

### 12.1 Deploy no Servidor

```bash
# 1. Conectar no servidor
ssh user@servidor

# 2. Clonar o repositório
git clone <url> /opt/vms
cd /opt/vms

# 3. Configurar ambiente
cp .env.example .env
nano .env   # Editar com valores de produção

# 4. Build com perfil de produção
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 5. Subir serviços
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 6. Rodar migrations
docker compose exec django python manage.py migrate

# 7. Criar superusuário
docker compose exec django python manage.py createsuperuser

# 8. Coletar static files
docker compose exec django python manage.py collectstatic --noinput

# 9. Verificar
docker compose ps
curl http://localhost/api/v1/
```

### 12.2 Deploy com Atualizações (CI/CD)

```bash
# No servidor
cd /opt/vms

# 1. Puxar atualizações
git pull origin main

# 2. Rebuild se necessário
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# 3. Rodar migrations
docker compose exec django python manage.py migrate

# 4. Reiniciar serviços atualizados
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 5. Verificar logs
docker compose logs --tail=50 django
docker compose logs --tail=50 fastapi
```

### 12.3 Deploy Zero-Downtime (Avançado)

Para deploy sem interrupção:

```bash
# 1. Build novas imagens
docker compose build

# 2. Rodar migrations (compatíveis com versão anterior)
docker compose exec django python manage.py migrate

# 3. Rolling restart
docker compose up -d --no-deps django
docker compose up -d --no-deps fastapi
docker compose up -d --no-deps worker
docker compose up -d --no-deps frontend
```

### 12.4 Rollback

```bash
# Voltar para commit anterior
git log --oneline -10
git checkout <hash-do-commit-anterior>

# Rebuild e restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Fase 13 — Monitoramento e Manutenção

### 13.1 Logs

```bash
# Todos os serviços
docker compose logs -f

# Serviço específico
docker compose logs -f django
docker compose logs -f worker
docker compose logs -f mediamtx

# Últimas N linhas
docker compose logs --tail=100 django
```

### 13.2 Métricas do MediaMTX

```bash
# Prometheus metrics
curl http://localhost:9998/metrics

# Métricas úteis:
#   mediamtx_paths_total          → total de câmeras
#   mediamtx_paths_active         → câmeras com stream ativo
#   mediamtx_readers_total        → viewers conectados
```

### 13.3 Monitorar Storage

```bash
# Via API
curl http://localhost/api/v1/recordings/storage/ \
  -H "Authorization: Bearer $TOKEN"

# Via disco
du -sh /var/lib/docker/volumes/vms_recordings/_data/
```

### 13.4 Monitorar Filas RabbitMQ

```bash
# Via Management UI
# http://servidor:15672

# Via CLI
docker compose exec rabbitmq rabbitmqctl list_queues name messages consumers
```

### 13.5 Health Checks Automatizados

O Celery Beat já roda automaticamente:

| Task | Intervalo | O que faz |
|------|-----------|-----------|
| `cameras.health_check_all` | 5 min | Verifica status de cada câmera no MediaMTX |
| `recordings.check_storage_quota` | 1 hora | Alerta se storage > 80% |
| `recordings.cleanup_task` | 1 hora | Remove gravações antigas (por retention_days) |

### 13.6 Manutenção do Banco

```bash
# Vacuum (liberar espaço)
docker compose exec postgres psql -U vms -d vms -c "VACUUM ANALYZE;"

# Ver tamanho das tabelas
docker compose exec postgres psql -U vms -d vms -c "
  SELECT relname, pg_size_pretty(pg_relation_size(relid))
  FROM pg_stat_user_tables
  ORDER BY pg_relation_size(relid) DESC;
"
```

### 13.7 Atualizar Imagens Base

```bash
# Atualizar imagens do Docker Hub
docker compose pull postgres redis rabbitmq mediamtx

# Recriar containers com novas imagens
docker compose up -d
```

---

## Apêndice A — Mapa de Portas

| Porta | Serviço | Protocolo | Expor em Produção? |
|-------|---------|-----------|-------------------|
| 80 | nginx | HTTP | Sim (redireciona para 443) |
| 443 | nginx | HTTPS | Sim |
| 3000 | frontend | HTTP | Não (via nginx) |
| 5432 | postgres | TCP | Não |
| 6379 | redis | TCP | Não |
| 5672 | rabbitmq | AMQP | Não |
| 8000 | django | HTTP | Não (via nginx) |
| 8001 | fastapi | HTTP | Não (via nginx) |
| 8554 | mediamtx | RTSP | Sim (câmeras enviam stream) |
| 1935 | mediamtx | RTMP | Opcional |
| 8888 | mediamtx | HLS | Sim (player browser) |
| 8889 | mediamtx | WebRTC | Sim (player browser) |
| 9997 | mediamtx | HTTP API | Não |
| 9998 | mediamtx | Metrics | Não (apenas monitoramento interno) |
| 15672 | rabbitmq | HTTP | Opcional (management) |

---

## Apêndice B — Variáveis de Ambiente

### Obrigatórias (trocar em produção)

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DJANGO_SECRET_KEY` | Chave secreta do Django | `x7k9m2...` (64 chars) |
| `JWT_SECRET` | Chave de assinatura JWT | `p4n8q1...` (64 chars) |
| `POSTGRES_PASSWORD` | Senha do PostgreSQL | `S3nh@F0rt3!` |
| `RABBITMQ_PASSWORD` | Senha do RabbitMQ | `R@bb1tS3gur0` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos | `vms.empresa.com` |
| `CORS_ORIGINS` | Origens CORS permitidas | `https://vms.empresa.com` |

### Configuráveis

| Variável | Default | Descrição |
|----------|---------|-----------|
| `DJANGO_DEBUG` | `false` | Debug mode |
| `STREAM_TOKEN_TTL_SECONDS` | `1800` | Validade do token de stream (30 min) |
| `STORAGE_QUOTA_BYTES_PER_TENANT` | `107374182400` | Cota de storage (100 GB) |
| `STORAGE_QUOTA_WARN_THRESHOLD` | `0.8` | Alerta em 80% de uso |
| `CAMERA_HEALTH_CHECK_INTERVAL` | `300` | Health check a cada 5 min |
| `STORAGE_QUOTA_CHECK_INTERVAL` | `3600` | Verificar cota a cada 1h |
| `RECORDINGS_CLEANUP_INTERVAL` | `3600` | Limpeza a cada 1h |
| `MEDIAMTX_HLS_BASE_URL` | `http://localhost:8888` | URL pública do HLS |
| `MEDIAMTX_WEBRTC_BASE_URL` | `http://localhost:8889` | URL pública do WebRTC |

### URLs Internas (não alterar em setup padrão)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `POSTGRES_HOST` | `postgres` | Hostname do container |
| `REDIS_URL` | `redis://redis:6379/0` | URL do Redis |
| `RABBITMQ_HOST` | `rabbitmq` | Hostname do RabbitMQ |
| `MEDIAMTX_API_URL` | `http://mediamtx:9997` | API interna do MediaMTX |
| `DJANGO_INTERNAL_URL` | `http://django:8000` | Django internamente |

---

## Apêndice C — Troubleshooting

### Problema: Container não sobe

```bash
# Ver logs do container
docker compose logs <servico>

# Causas comuns:
# - Porta já em uso → parar outro serviço na mesma porta
# - Health check falhando → verificar dependências
# - .env com valor errado → revisar variáveis
```

### Problema: Câmera não fica online

```bash
# 1. Verificar se o stream RTSP funciona
ffplay rtsp://192.168.1.100:554/stream1

# 2. Verificar se o MediaMTX consegue puxar
curl http://localhost:9997/v3/paths/list | python -m json.tool

# 3. Verificar logs do MediaMTX
docker compose logs -f mediamtx | grep "tenant-1/cam-1"

# Causas comuns:
# - IP da câmera inacessível do servidor Docker
# - Credenciais RTSP incorretas (user:pass na URL)
# - Formato: rtsp://usuario:senha@192.168.1.100:554/stream1
# - Firewall bloqueando porta 554
```

### Problema: Webhooks não chegam

```bash
# 1. Testar endpoint manualmente
curl -X POST http://localhost:8001/webhooks/alpr \
  -H "Content-Type: application/json" \
  -d '{"plate":"TEST-1234","camera_id":1,"confidence":0.99,"timestamp":"2026-03-14T10:00:00Z"}'

# 2. Verificar logs do FastAPI
docker compose logs -f fastapi | grep webhook

# 3. Verificar fila no RabbitMQ
# http://localhost:15672 → Queues
```

### Problema: SSE não funciona

```bash
# 1. Testar conexão SSE
curl -N "http://localhost:8001/sse/?token=<jwt>"

# 2. Verificar se Redis pubsub está ativo
docker compose exec redis redis-cli
> SUBSCRIBE vms:realtime

# Causas comuns:
# - Token expirado
# - nginx com buffering ativado (deve ser off para SSE)
# - CORS bloqueando a conexão
```

### Problema: Gravações não aparecem

```bash
# 1. Verificar se o MediaMTX está gravando
ls -la /var/lib/docker/volumes/vms_recordings/_data/

# 2. Verificar webhook de segmento
docker compose logs fastapi | grep record_segment

# 3. Verificar task do worker
docker compose logs worker | grep process_recording

# Causas comuns:
# - Volume recordings não montado
# - ffprobe não instalado no container worker
# - Permissões de escrita no volume
```

### Problema: Frontend não conecta na API

```bash
# 1. Verificar variáveis do frontend
docker compose exec frontend env | grep NEXT_PUBLIC

# 2. Testar API diretamente
curl http://localhost/api/v1/

# Causas comuns:
# - NEXT_PUBLIC_API_URL apontando para URL errada
# - CORS bloqueando (verificar CORS_ORIGINS no .env)
# - nginx não roteando corretamente
```

### Comandos Úteis

```bash
# Restart de um serviço
docker compose restart django

# Recriar um serviço (rebuild)
docker compose up -d --build --no-deps django

# Shell interativo no container
docker compose exec django bash
docker compose exec django python manage.py shell

# Ver uso de recursos
docker stats

# Limpar tudo (cuidado: apaga volumes)
docker compose down -v
```

---

> **Última atualização:** 2026-03-14
>
> Este documento deve ser atualizado conforme o projeto evolui.
> Sempre que uma nova decisão de deploy for tomada, documente aqui.
