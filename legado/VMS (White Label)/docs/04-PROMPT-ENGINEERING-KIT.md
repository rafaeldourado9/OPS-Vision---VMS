# 04 — GT-Vision · Prompt Engineering Kit
**Prompts para Agentes de IA (Claude Code, Cursor, Copilot) · v1.0**

---

## Instruções de Uso

Este kit contém prompts prontos para usar com agentes de IA no desenvolvimento do GT-Vision.
Cada prompt é autocontido — copie, cole e execute no agente de sua escolha.

**Ordem recomendada de execução:**
1. Setup inicial do projeto (Prompt 1)
2. Modelos White Label e Tenant (Prompt 2)
3. Autenticação (Prompt 3)
4. Câmeras (Prompt 4)
5. Pipeline de Vídeo / MediaMTX (Prompt 5)
6. ROI (Prompt 6)
7. Workers FastAPI (Prompt 7)
8. Frontend (Prompts 8-10)
9. Franquia / Master (Prompt 11)

---

## PROMPT 1 — Setup Inicial do Projeto

```
Você é um engenheiro sênior Python/Django.

Crie a estrutura inicial do projeto GT-Vision (VMS urbano com IA, white label, multi-tenant).

## Contexto importante
- Diretório raiz do projeto: D:\VMS (White Label)\
- Imagem Docker base para workers de IA: ai-base:latest
- A ai-base já está buildada localmente em C:\docker-images\ai-base\
- A ai-base inclui: PyTorch (CPU), OpenCV, ONNX Runtime, Ultralytics YOLOv8, NumPy, Redis, httpx
- Workers que NÃO são de IA usam python:3.11-slim + ffmpeg (imagem separada mais leve)

## Stack
- Django 4.2 + Django REST Framework
- PostgreSQL 15
- Redis 7
- Django Channels (WebSocket)
- JWT via djangorestframework-simplejwt
- pytest-django para testes

## Tarefa 1 — Estrutura Django
1. Gere o `requirements.txt` com todas as dependências necessárias
2. Crie o `settings/base.py` com configurações base seguras
3. Crie o `settings/development.py` e `settings/production.py`
4. Configure o `urls.py` raiz:
   - /api/v1/ → DRF router
   - /master/ → painel de franquia
   - /ws/ → Django Channels
5. Configure o `asgi.py` para HTTP + WebSocket

## Tarefa 2 — docker-compose.yml completo
Gere o arquivo `infra/docker-compose.yml` com os seguintes serviços:

```yaml
# REFERÊNCIA — gere o arquivo completo e funcional

services:
  django:
    build: ../backend-django
    # (configurar env, volumes, ports, depends_on)

  ai-worker:
    build:
      context: ../backend-fastapi/workers/ai_worker
      dockerfile: Dockerfile.ai
    # IMPORTANTE: este worker usa ai-base:latest como imagem base
    # O Dockerfile.ai deve começar com: FROM ai-base:latest
    # Montar volume de modelos: ./models:/app/models:ro
    # (configurar env com RABBITMQ_URL, REDIS_URL, MODEL_PATH, etc.)

  recorder-worker:
    build:
      context: ../backend-fastapi/workers/recorder
      dockerfile: Dockerfile.worker
    # Usa python:3.11-slim + ffmpeg (NÃO usa ai-base)

  frame-grabber:
    build:
      context: ../backend-fastapi/workers/frame_grabber
      dockerfile: Dockerfile.worker

  clip-builder:
    build:
      context: ../backend-fastapi/workers/clip_builder
      dockerfile: Dockerfile.worker

  purge-worker:
    build:
      context: ../backend-fastapi/workers/purge
      dockerfile: Dockerfile.worker

  mediamtx:
    image: bluenviron/mediamtx:latest
    # (configurar ports: 8554 RTSP, 1935 RTMP, 8889 WebRTC, 8888 HLS)

  postgres:
    image: postgres:15-alpine

  redis:
    image: redis:7-alpine

  rabbitmq:
    image: rabbitmq:3-management-alpine
    # (configurar management port 15672)

  nginx:
    image: nginx:alpine
    # (proxy reverso para django e mediamtx)
```

## Tarefa 3 — Dockerfiles
Gere os seguintes Dockerfiles:

### backend-fastapi/workers/ai_worker/Dockerfile.ai
```
FROM ai-base:latest
# ai-base já tem: PyTorch, OpenCV, ONNX Runtime, Ultralytics, NumPy, Redis, httpx, ffmpeg
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "worker"]
```

### backend-fastapi/workers/recorder/Dockerfile.worker
```
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "worker"]
```
(Os outros workers não-IA seguem o mesmo padrão do Dockerfile.worker)

## Tarefa 4 — Makefile
Crie o `Makefile` na raiz com:
- `make dev` → docker-compose up com hot reload
- `make build-ai` → docker build da ai-base + rebuild do ai-worker
- `make test` → roda pytest no container django
- `make migrate` → roda migrations no container django
- `make shell` → abre shell Django
- `make logs-ai` → tail logs do ai-worker

## Regras
- Nunca exponha SECRET_KEY ou credenciais em código (usar python-decouple)
- Toda credencial via variáveis de ambiente
- CORS configurado para aceitar frontend em desenvolvimento
- Volume `./models:/app/models:ro` no ai-worker para servir arquivos .pt/.onnx

Gere todos os arquivos completos e funcionais.
```

---

## PROMPT 2 — Modelos White Label + Multi-Tenant

```
Você é um engenheiro Django especializado em arquiteturas multi-tenant e white label.

Crie os modelos Django para o sistema GT-Vision seguindo as especificações abaixo.

## Modelos a criar

### App: resellers
- Reseller (revendedor/franqueado):
  - id: UUIDField (primary_key, default=uuid4)
  - name, slug (unique), custom_domain (unique)
  - primary_color, secondary_color (HEX)
  - logo_url, favicon_url
  - dark_mode_default: BooleanField
  - terms_url, privacy_url
  - active: BooleanField
  - created_at

### App: tenants
- Tenant (instância de cidade):
  - id: UUIDField
  - reseller: FK → Reseller
  - license: FK → License
  - name, subdomain (unique), active, created_at

### App: franchise
- License:
  - id, reseller FK, max_cameras INT, valid_until DATE, active

### App: auth_app
- User (customizado, herda AbstractBaseUser):
  - id UUID, tenant FK (nullable para super_admin), email, role, active, last_login
  - roles: operator|supervisor|city_admin|reseller_admin|super_admin

## Middlewares a criar

### middleware/tenant.py — TenantMiddleware
- Lê request.META["HTTP_HOST"]
- Consulta Redis primeiro: GET wl:{host}
- Cache miss: busca no banco por custom_domain ou subdomain
- Injeta request.tenant e request.reseller
- Retorna 404 se host desconhecido
- TTL do cache: 5 minutos

### middleware/white_label.py — WhiteLabelMiddleware
- Depende do TenantMiddleware
- Injeta request.theme = dict com cores, logo, favicon

## Regras
- Todos os modelos devem ter Meta.indexes com tenant_id onde aplicável
- Criar migrations completas
- Criar factories (factory_boy) para cada modelo em tests/factories.py
- Criar testes unitários para o TenantMiddleware (mock Redis)
- Seguir TDD: escreva o teste ANTES do código

Gere os arquivos completos com docstrings.
```

---

## PROMPT 3 — Autenticação JWT + RBAC

```
Você é um engenheiro Django especializado em segurança e autenticação.

Implemente o sistema de autenticação do GT-Vision.

## Requisitos
- Login: POST /api/v1/auth/login/ → {access, refresh}
- Refresh: POST /api/v1/auth/refresh/ → {access}
- Logout: POST /api/v1/auth/logout/ (invalida refresh token no Redis)
- Recuperação de senha: POST /api/v1/auth/password-reset/ (envia email)
- Confirm reset: POST /api/v1/auth/password-reset/confirm/

## RBAC
Crie um decorator/mixin `require_role(*roles)` que:
- Verifica se o usuário autenticado tem um dos roles permitidos
- Lança PermissionDenied com mensagem clara se não autorizado

## Segurança
- Após 5 tentativas de login falhas: bloquear conta por 15 minutos (usar Redis)
- Registrar no Redis: rate_limit:login:{email}
- Access token: 15 minutos
- Refresh token: 7 dias, rotacionado a cada uso
- Todo token carrega: user_id, tenant_id, role, reseller_id

## White Label no email
- Email de recuperação de senha deve usar template que lê request.reseller para personalizar:
  - Nome do sistema (não expor GT-Vision)
  - Logo do revendedor
  - Cor primária

## TDD
Escreva PRIMEIRO os testes para:
- Login válido retorna tokens
- Login inválido retorna 401
- Conta bloqueada após 5 falhas retorna 423
- Usuário de tenant A não pode logar em tenant B
- Logout invalida refresh token
- Token expirado retorna 401

Depois implemente o código para passar nos testes.
Gere serializers, views (ViewSet), urls, templates de email.
```

---

## PROMPT 4 — CRUD de Câmeras + Licença

```
Você é um engenheiro Django/DRF.

Implemente o módulo de câmeras do GT-Vision.

## Modelo Camera (app: cameras)
- id UUID, tenant FK, name, address, latitude, longitude
- stream_protocol: rtsp|rtmp
- stream_url (nullable, para RTSP)
- stream_key (nullable, para RTMP — gerado automaticamente UUID)
- retention_days: choices [7, 15, 30]
- ia_enabled: Boolean (default False)
- ia_status: disabled|ia_pending|active (default: disabled)
- online: Boolean, last_seen: DateTime
- created_at

## Regras de negócio
- Ao criar câmera com stream_protocol=rtmp: gerar stream_key automaticamente
- Ao setar ia_enabled=True: mudar ia_status para "ia_pending"
- ia_status só vai para "active" quando pelo menos 1 ROI for configurado
- Antes de criar câmera: verificar se tenant.license.max_cameras foi atingido
  - Se atingido: retornar HTTP 403 com mensagem "Limite de câmeras atingido para esta licença"
- Toda query deve filtrar por request.tenant automaticamente

## Endpoints
- GET /api/v1/cameras/ → listagem com filtros (status, ia_enabled)
- POST /api/v1/cameras/ → criar (requer role: city_admin)
- GET /api/v1/cameras/{id}/ → detalhe
- PATCH /api/v1/cameras/{id}/ → editar (requer role: city_admin)
- DELETE /api/v1/cameras/{id}/ → remover (requer role: city_admin)
- GET /api/v1/cameras/{id}/thumbnail/ → último thumbnail da câmera (do Redis)

## TDD — escreva os testes antes
- Criar câmera RTSP com sucesso
- Criar câmera RTMP gera stream_key
- Habilitar IA muda status para ia_pending
- Limite de licença impede criação (403)
- Operador não pode criar câmera (403)
- Câmera de outro tenant retorna 404

Gere: model, serializer, viewset, urls, migrations, factories, tests.
```

---

## PROMPT 5 — Integração MediaMTX + Recorder Worker

```
Você é um engenheiro especializado em streaming de vídeo e sistemas assíncronos.

Implemente a integração do GT-Vision com MediaMTX e o Recorder Worker.

## Configuração MediaMTX (mediamtx.yml)
Gere o arquivo de configuração do MediaMTX para:
- Aceitar streams RTSP e RTMP de câmeras
- Path pattern: /live/{tenant_id}/{camera_id}
- Habilitar WebRTC (WHEP) para live view com latência < 500ms
- Habilitar HLS para playback de gravações
- Webhook: ao conectar/desconectar câmera, chamar POST /api/v1/internal/camera-status/

## Recorder Worker (FastAPI + asyncio)
Arquivo: backend-fastapi/workers/recorder/service.py

Fluxo:
1. Consome fila RabbitMQ: "recording.start"
2. Inicia gravação do stream MediaMTX em segmentos MP4 de 10 min via FFmpeg
3. Ao finalizar cada segmento:
   - Salva arquivo no storage (local ou S3-compatible)
   - POST /api/v1/internal/segments/ com metadados (câmera, início, fim, path, size)
4. Em caso de queda de câmera: tentar reconectar a cada 30s (max_retries=infinito)
5. Consome fila "recording.stop" para encerrar gravação

## Django — endpoint de status de câmera
POST /api/v1/internal/camera-status/
- Recebe: {camera_id, status: online|offline}
- Atualiza Camera.online e Camera.last_seen
- Apenas chamado internamente (autenticação por API key interna, não JWT)

## Purge Worker
Arquivo: backend-fastapi/workers/purge/tasks.py
- Executado diariamente via scheduler (APScheduler)
- Busca segmentos com expires_at < now() de cada tenant
- Deleta arquivo do storage
- Remove registro do banco via Django REST interno
- NUNCA deleta clips (tabela separada)

## TDD
- Recorder cria metadado de segmento após gravar
- Recorder reconecta após ConnectionError
- Purge deleta apenas segmentos expirados
- Purge nunca toca clips

Gere: código Python completo, dockerfile para o worker, variáveis de ambiente necessárias.
```

---

## PROMPT 6 — Sistema de ROI (Zonas de Interesse)

```
Você é um engenheiro fullstack.

Implemente o módulo de ROI (Region of Interest) do GT-Vision.

## Backend (Django)
Modelo RegionOfInterest:
- id UUID, tenant FK, camera FK
- name: varchar
- polygon: JSONField (lista de [x, y] no espaço normalizado 0-1)
- ia_type: lpr|intrusion|crowd
- active: Boolean
- created_at

Endpoints:
- GET /api/v1/roi/?camera_id={id}
- POST /api/v1/roi/
- PATCH /api/v1/roi/{id}/
- DELETE /api/v1/roi/{id}/

Lógica após criar ROI:
- Se câmera.ia_status == "ia_pending": mudar para "active"
- Publicar mensagem na fila RabbitMQ "roi.updated" com {camera_id, roi_list}

Lógica após deletar último ROI de câmera:
- Mudar câmera.ia_status para "ia_pending"
- Publicar "roi.updated" com lista vazia

## Backend — Frame Snapshot
GET /api/v1/cameras/{id}/snapshot/
- Chama MediaMTX API para capturar frame atual
- Retorna URL da imagem temporária (salva em Redis com TTL 30s)

## Frontend (Vue 3 / React)
Página /zona-de-interesse:

1. Dropdown de seleção de câmera
2. Ao selecionar: carrega snapshot via /api/v1/cameras/{id}/snapshot/
3. Renderiza imagem no canvas (Konva.js ou Fabric.js)
4. Ferramenta de polígono:
   - Clique para adicionar vértice
   - Duplo clique para fechar polígono
   - Polígono fechado exibido em overlay colorido semi-transparente
5. Campo "Nome do ROI" e selector de "Tipo de IA"
6. Botão "Salvar ROI"
7. Lista de ROIs existentes com botão de excluir

## TDD Backend
- Criar ROI muda câmera para active
- Deletar último ROI muda câmera para ia_pending
- ROI com menos de 3 pontos retorna 400
- ROI pertencente a câmera de outro tenant retorna 404

Gere código completo para backend e frontend.
```

---

## PROMPT 7 — AI Worker (LPR)

```
Você é um engenheiro de visão computacional e sistemas distribuídos Python.

Implemente o AI Worker do GT-Vision para reconhecimento de placas (LPR).

## Contexto crítico — imagem Docker
Este worker usa a imagem ai-base:latest como base.
A ai-base já fornece (NÃO instale novamente):
  - torch + torchvision (CPU; trocar URL por cu121 para GPU NVIDIA)
  - opencv-python-headless >= 4.9.0
  - onnxruntime >= 1.18.0
  - ultralytics >= 8.2.0  ← YOLOv8
  - numpy >= 1.26.0
  - redis >= 5.0.1
  - httpx >= 0.27.0
  - ffmpeg (sistema)

O Dockerfile.ai do worker deve ser:
  FROM ai-base:latest
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt  # apenas deps extras
  COPY . .
  CMD ["python", "-m", "worker"]

NÃO use serviços externos de IA (OpenALPR cloud, AWS Rekognition, Google Vision, etc.).
Todo processamento é local, usando modelos .pt ou .onnx montados em /app/models/.

## Arquitetura — 3 processos

### 1. Frame Grabber Worker (Dockerfile.worker — python:3.11-slim + ffmpeg)
- Conecta ao stream HLS de cada câmera ativa com IA via OpenCV
- Captura 1 frame por segundo
- Salva frame em storage temporário
- Publica na fila "ai.frame":
  {camera_id, tenant_id, frame_path, rois: [{id, polygon, ia_type}]}

### 2. AI Worker — LPR (Dockerfile.ai — FROM ai-base:latest)
Pipeline interno:
  a) Consome fila "ai.frame"
  b) Carrega frame com OpenCV
  c) Para cada ROI no payload:
     - Aplica ray casting para verificar se há objeto dentro do polígono
     - Crop do frame no bounding box do ROI
     - Inferência YOLOv8 no crop (modelo: /app/models/plate_detector.pt)
     - Se placa detectada com confidence > 0.7:
       → Segundo crop no bounding box da placa
       → Inferência do char_recognizer (/app/models/char_recognizer.pt)
       → Ordena caracteres detectados por posição X
       → Monta string da placa: "ABC1D23"
  d) Dedup via Redis:
     - Chave: dedup:{camera_id}:{plate_string}
     - TTL: 30 segundos
     - Se chave existe: descartar (evento duplicado)
  e) Se novo evento:
     - Salva snapshot da placa em /app/storage/snapshots/
     - Publica em "ai.events":
       {camera_id, tenant_id, roi_id, event_type: "lpr",
        data: {plate, confidence}, snapshot_path, detected_at}

### 3. Django Event Consumer
- Consome "ai.events"
- Persiste em AIEvent no banco
- Notifica operadores via WebSocket (Django Channels)

## Modelo AIEvent (Django — app: detections)
- id: UUID PK
- tenant_id FK
- camera_id FK
- roi_id FK
- event_type: lpr | intrusion | crowd
- snapshot_path: VARCHAR
- event_data: JSONField  →  {plate, confidence}
- detected_at: DateTime (indexado)
- created_at: DateTime

## Endpoints Django
GET /api/v1/detections/
- Filtra por: camera_id, event_type, start_date, end_date, plate (icontains)
- Paginação: 50 por página, ordenado por detected_at DESC
- Filtra SEMPRE por request.tenant

GET /api/v1/detections/export/?format=csv|pdf
- Exporta resultados filtrados

## WebSocket (Django Channels)
- Canal: ws://host/ws/notifications/{tenant_id}/
- Mensagem ao operador: {type: "ai_event", payload: AIEvent serializado}
- Autenticação via JWT no header da conexão WS

## Variáveis de ambiente do ai-worker
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
REDIS_URL=redis://redis:6379/0
MODEL_PLATE_DETECTOR=/app/models/plate_detector.pt
MODEL_CHAR_RECOGNIZER=/app/models/char_recognizer.pt
STORAGE_PATH=/app/storage
CONFIDENCE_THRESHOLD=0.7
DEDUP_TTL_SECONDS=30
DJANGO_INTERNAL_URL=http://django:8000

## TDD
- LPR detecta placa dentro do ROI (mock YOLOv8)
- LPR ignora frame quando câmera não tem ROI configurado
- Dedup Redis evita evento duplicado dentro de 30s
- Confidence < 0.7 não gera evento
- Evento persistido aparece na API /detections/
- Isolamento: evento de tenant A não visível para tenant B
- Operador recebe notificação WS ao detectar evento

Gere código Python completo, Dockerfile.ai, variáveis .env.example e testes.
```

---

## PROMPT 8 — Frontend: Dashboard + Mapa Tático

```
Você é um engenheiro frontend especializado em Vue 3 e sistemas de monitoramento.

Implemente o Dashboard principal do GT-Vision (Mapa Tático).

## Stack
- Vue 3 + Composition API
- TailwindCSS
- Leaflet.js (mapa)
- Pinia (estado global)
- Axios (HTTP)

## Composable: useWhiteLabel
Criar composable que:
- Chama GET /api/v1/theme/ (sem autenticação, resolvida pelo host)
- Aplica CSS variables no :root: --color-primary, --color-secondary
- Substitui <link rel="icon"> pelo favicon do revendedor
- Atualiza <title> com nome do revendedor

Deve ser chamado em App.vue antes de qualquer render.

## Layout
Sidebar esquerda (w-64, bg-white, shadow):
- Logo do revendedor (via useWhiteLabel)
- Menu de navegação: Dashboard, Câmeras, Detecções, ROI, Gestão
- Contadores: Total, Online (verde), Offline (vermelho), Eventos Hoje
- Filtros: checkbox Status, checkbox Com IA

Área principal (flex-1):
- Mapa Leaflet fullscreen
- Tile layer: OpenStreetMap

## Ícones no Mapa
Para cada câmera do tenant:
- Ícone verde: online
- Ícone vermelho: offline
- Ícone amarelo: ia_pending

Popup ao clicar:
- Thumbnail da câmera (GET /api/v1/cameras/{id}/thumbnail/, refresh a cada 30s)
- Nome, status, endereço
- Botão "Abrir Player" → router.push('/player/{id}')

## Store Pinia: useCameraStore
- cameras: lista completa
- fetchCameras(): GET /api/v1/cameras/
- startThumbnailRefresh(): setInterval 30s
- onCameraStatusChange(ws_event): atualiza status em tempo real

## WebSocket
Conectar em ws://host/ws/notifications/{tenant_id}/
Ao receber ai_event: mostrar toast de notificação

## Regras de qualidade
- Componentes < 200 linhas cada
- Loading skeleton enquanto carrega câmeras
- Mensagem amigável se 0 câmeras cadastradas
- Responsivo (sidebar colapsa em mobile)
- ZERO referência ao "GT-Vision" no código ou UI

Gere os arquivos Vue completos com comentários.
```

---

## PROMPT 9 — Frontend: Player de Vídeo WebRTC

```
Você é um engenheiro frontend especializado em WebRTC e streaming de vídeo.

Implemente o Player de Vídeo do GT-Vision.

## Tecnologias
- Vue 3
- WebRTC (WHEP protocol via MediaMTX)
- HLS.js (fallback e playback histórico)
- TailwindCSS

## Componente VideoPlayer.vue
Props:
- cameraId: String
- mode: 'live' | 'playback'
- startAt: Date (para playback)

### Modo Live (WebRTC)
1. Buscar URL WebRTC: GET /api/v1/cameras/{id}/stream-url/
2. Criar RTCPeerConnection
3. Usar protocolo WHEP para negociação SDP com MediaMTX
4. Exibir stream no elemento <video>
5. Indicador de latência no canto inferior direito
6. Se WebRTC falhar: fallback automático para HLS

### Modo Playback (HLS)
1. Buscar URL HLS do segmento: GET /api/v1/cameras/{id}/hls-url/?start={iso}
2. Inicializar HLS.js
3. Renderizar timeline de gravação abaixo do player:
   - Barra de progresso com segmentos disponíveis (cinza = disponível, vazio = sem gravação)
   - Marcadores coloridos para eventos de IA
   - Seletor de início/fim para geração de clipe

### Controles do Player
- Play/Pause
- Fullscreen
- Volume com mute
- Botão "Ao Vivo" (volta para WebRTC)
- Botão "Snapshot" (captura frame como PNG)
- Botão "Gerar Clipe" (abre modal com in/out selecionados)

### Modal Gerar Clipe
- Exibe início e fim selecionados
- Campo opcional "Nome do clipe"
- POST /api/v1/clips/ ao confirmar
- Toast "Clipe em processamento..."

## Regras
- Player deve funcionar em todos os navegadores modernos
- Graceful degradation: sem WebRTC → HLS automático
- Exibir "Câmera offline" com última thumbnail se stream indisponível
- Não expor URL interna do MediaMTX diretamente ao frontend

Gere o componente completo com tratamento de erros e comentários.
```

---

## PROMPT 10 — Frontend: White Label — Tela de Login

```
Você é um designer/engenheiro frontend.

Implemente a tela de login do GT-Vision com suporte completo a white label.

## Tecnologias
- Vue 3 + TailwindCSS
- Composition API

## Requisito Crítico
A tela de login NÃO deve exibir nenhuma referência ao GT-Vision.
Toda identidade visual vem da configuração do revendedor, carregada via GET /api/v1/theme/.

## Layout
Tela dividida em 2 colunas (desktop) / 1 coluna (mobile):

Coluna esquerda (hidden em mobile):
- Imagem de fundo relacionada a monitoramento urbano
- Overlay com cor primária do revendedor (opacity 80%)
- Tagline configurável do revendedor

Coluna direita:
- Logo do revendedor no topo (src vinda do tema)
- Título: "Acesso ao Sistema" (sem mencionar nome do produto)
- Formulário: email, senha
- Botão "Entrar" com cor primária do revendedor
- Link "Esqueci minha senha"
- Rodapé: Termos de Uso e Política de Privacidade (links do revendedor)

## Loading State
Antes de carregar o tema (chamada à API):
- Exibir spinner neutro
- Não exibir conteúdo do revendedor até ter os dados
- Timeout de 3s: se API falhar, usar tema padrão (cinza neutro)

## Fluxo de Login
1. Usuário submete formulário
2. POST /api/v1/auth/login/
3. Sucesso: salvar tokens, redirect para /dashboard
4. Erro 401: "Email ou senha incorretos"
5. Erro 423: "Conta temporariamente bloqueada. Tente novamente em 15 minutos."

## Acessibilidade
- Todos os inputs com labels apropriados
- Mensagens de erro acessíveis (aria-live)
- Tab order lógico

Gere o componente Login.vue completo.
```

---

## PROMPT 11 — Painel Master de Franquia (Super Admin)

```
Você é um engenheiro Django.

Implemente o painel master do GT-Vision para gerenciamento de revendedores e licenças.

## Acesso
- URL: /master/ (subdomínio separado em produção: master.gt-vision.internal)
- Apenas usuários com role = super_admin
- Revendedores e admins de cidade NÃO têm acesso

## Funcionalidades

### 1. CRUD de Revendedores
POST /master/api/resellers/
- name, slug, custom_domain, primary_color, secondary_color
- logo_url, favicon_url, dark_mode_default
- terms_url, privacy_url

### 2. Configuração de Licença por Revendedor
POST /master/api/licenses/
- reseller_id, max_cameras, valid_until

### 3. CRUD de Tenants (Cidades)
POST /master/api/tenants/
- reseller_id, name, subdomain, license_id, active

### 4. Ativação / Suspensão
PATCH /master/api/tenants/{id}/toggle-active/

### 5. Dashboard de Métricas
GET /master/api/metrics/
Retorna:
- Total de revendedores ativos
- Total de tenants
- Câmeras ativas por tenant
- Eventos de IA por dia (últimos 30 dias)
- Storage utilizado por tenant (em GB)

### 6. Impersonação (suporte técnico)
POST /master/api/impersonate/{tenant_id}/
- Retorna token JWT com claims do super_admin mas com tenant_id alvo
- Token válido por 1 hora
- Log de auditoria: {super_admin_id, tenant_id, timestamp}

## Segurança
- Todas as rotas /master/ verificam role == super_admin
- Impersonação gera log imutável em tabela AuditLog
- Rate limit em /master/api/: 100 req/min por IP

## TDD
- Super admin pode criar revendedor
- Reseller admin não acessa /master/
- Impersonação gera log de auditoria
- Métricas retornam dados corretos

Gere endpoints, serializers, testes.
```
