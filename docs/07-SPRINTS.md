# 07 — GT-Vision · Planejamento de Sprints
**Roadmap de Desenvolvimento — 12 Semanas · v1.0**

---

## Visão Geral do Roadmap

```
Sprint 1  (semanas 1-2)  → Fundação: Setup, Tenant, White Label, Auth
Sprint 2  (semanas 3-4)  → Câmeras: CRUD, Licença, MediaMTX básico
Sprint 3  (semanas 5-6)  → Pipeline de Vídeo: Gravação, Live View WebRTC
Sprint 4  (semanas 7-8)  → IA: ROI, Frame Grabber, LPR Worker
Sprint 5  (semanas 9-10) → Frontend: Dashboard, Mapa, Player, Detecções
Sprint 6  (semanas 11-12)→ Finalização: Relatórios, Clipes, Franquia, Testes E2E
```

---

## SPRINT 1 — Fundação (Semanas 1-2)

**Meta:** Sistema funcionando com login white label e usuário autenticado acessando dashboard vazio.

### Backlog

**Setup e Infraestrutura**
- [ ] Criar repositório Git com estrutura de monorepo em `D:\VMS (White Label)\`
- [ ] Buildar imagem `ai-base:latest` localmente: `docker build -t ai-base:latest C:\docker-images\ai-base\`
- [ ] Criar `infra/docker-compose.yml` com todos os serviços:
  - django, postgres, redis, rabbitmq, mediamtx, nginx
  - ai-worker (`FROM ai-base:latest`)
  - recorder-worker, frame-grabber, clip-builder, purge-worker (`FROM python:3.11-slim`)
- [ ] Criar `Dockerfile.ai` para ai_worker (`FROM ai-base:latest`)
- [ ] Criar `Dockerfile.worker` para workers não-IA (`FROM python:3.11-slim + ffmpeg`)
- [ ] Criar `Makefile` com: `make dev`, `make build-ai`, `make test`, `make migrate`, `make logs-ai`
- [ ] Configurar CI/CD básico (GitHub Actions): lint + testes a cada PR
- [ ] Configurar pre-commit hooks: black, flake8, isort

**App: resellers (White Label)**
- [ ] Escrever testes para modelo Reseller
- [ ] Criar model Reseller com todos os campos de white label
- [ ] Criar migration
- [ ] Criar factory ResellerFactory

**App: tenants (Multi-Tenant)**
- [ ] Escrever testes para TenantMiddleware (resolução por host)
- [ ] Criar model Tenant
- [ ] Implementar TenantMiddleware com cache Redis
- [ ] Implementar WhiteLabelMiddleware
- [ ] Testes de isolamento: host desconhecido retorna 404
- [ ] Criar factory TenantFactory

**App: franchise (Licenças)**
- [ ] Criar model License
- [ ] Criar factory LicenseFactory

**App: auth_app (Autenticação)**
- [ ] Escrever testes de login, logout, refresh, bloqueio
- [ ] Criar User model customizado (AbstractBaseUser)
- [ ] Implementar JWT (access 15min, refresh 7 dias)
- [ ] Implementar rate limiting de login (5 tentativas → bloqueio)
- [ ] Endpoint de recuperação de senha com template white label
- [ ] Decorador `require_role(*roles)` com testes

**API: Tema White Label**
- [ ] Escrever teste: GET /api/v1/theme/ retorna cores e logo do revendedor
- [ ] Escrever teste: resposta não contém "GT-Vision"
- [ ] Implementar endpoint /api/v1/theme/

**Frontend: Login**
- [ ] Tela de login consumindo /api/v1/theme/ para aplicar identidade
- [ ] Composable `useWhiteLabel` aplicando CSS variables e logo
- [ ] Formulário de login com tratamento de erros (401, 423)
- [ ] Redirect para /dashboard após login

### Critério de Aceite da Sprint 1
- Login funciona com identidade visual do revendedor
- TenantMiddleware isola tenants por host
- Nenhum endpoint retorna dados sem autenticação
- Cobertura de testes ≥ 85%

---

## SPRINT 2 — Câmeras (Semanas 3-4)

**Meta:** Admin consegue cadastrar câmeras e visualizá-las em lista com status online/offline.

### Backlog

**App: cameras**
- [ ] Escrever testes de CRUD de câmeras
- [ ] Escrever teste de limite de licença
- [ ] Criar model Camera com todos os campos
- [ ] Implementar validação de limite de licença no service
- [ ] CameraViewSet com filtragem automática por tenant
- [ ] Geração automática de stream_key para câmeras RTMP
- [ ] Lógica: ia_enabled=True → ia_status="ia_pending"
- [ ] Endpoint GET /api/v1/cameras/{id}/thumbnail/ (do Redis)

**Integração MediaMTX básica**
- [ ] Configurar `mediamtx.yml` com webhook de status (online/offline)
- [ ] Endpoint Django: POST /api/v1/internal/camera-status/
- [ ] Worker leve que escuta webhook MediaMTX e atualiza Camera.online

**Frontend: Gestão de Câmeras**
- [ ] Página /gestao/cameras — listagem com busca e filtros
- [ ] Formulário de cadastro: nome, endereço, lat/lng, protocolo, retenção
- [ ] Toggle IA com exibição de status
- [ ] Validação inline no formulário (campos obrigatórios, URL válida)
- [ ] Confirmação de exclusão de câmera

**Frontend: Listagem /cameras**
- [ ] Cards de câmeras com thumbnail, status badge, IA status
- [ ] Busca por nome e endereço
- [ ] Filtros por status e IA

### Critério de Aceite da Sprint 2
- Câmera RTSP e RTMP cadastradas com sucesso
- Limite de licença impede câmeras extras (403)
- Status online/offline atualizado via webhook do MediaMTX
- Thumbnails (placeholder inicialmente) visíveis nos cards

---

## SPRINT 3 — Pipeline de Vídeo (Semanas 5-6)

**Meta:** Live view WebRTC funcionando para câmeras online. Gravação contínua iniciada.

### Backlog

**App: recordings (Django)**
- [ ] Escrever testes de RecordingSegment e purge
- [ ] Criar model RecordingSegment
- [ ] Endpoint interno POST /api/v1/internal/segments/ (recebe metadados do worker)
- [ ] Job de purge (Celery Beat): deleta segmentos com expires_at passado
- [ ] Teste: clipes nunca são deletados

**Worker: Recorder (FastAPI)**
- [ ] Escrever testes do RecorderService (mock FFmpeg, mock storage)
- [ ] Implementar RecorderService:
  - Consume fila "recording.start"
  - Grava segmentos MP4 de 10 min via FFmpeg + MediaMTX HLS
  - Salva no storage (local ou S3)
  - Registra metadados via API interna Django
- [ ] Implementar reconexão com backoff exponencial
- [ ] Graceful shutdown ao SIGTERM
- [ ] Health check: GET /health

**Worker: Frame Grabber (FastAPI)**
- [ ] Implementar captura de frames (1/seg) para thumbnails
- [ ] Salvar thumbnail no Redis (TTL 60s)
- [ ] Publicar frames na fila "ai.frame" para câmeras com IA ativa

**Frontend: Player de Vídeo**
- [ ] Componente VideoPlayer.vue/tsx
- [ ] Modo live: WebRTC via protocolo WHEP (MediaMTX)
- [ ] Fallback automático para HLS se WebRTC falhar
- [ ] Indicador de latência
- [ ] Controles: play/pause, fullscreen, volume, snapshot

**Frontend: Timeline de Gravação**
- [ ] Barra de segmentos disponíveis abaixo do player
- [ ] Navegação temporal via clique/drag na timeline
- [ ] Exibição de lacunas (sem gravação) na timeline

### Critério de Aceite da Sprint 3
- Live view WebRTC funcionando com < 500ms de latência
- Recorder Worker gravando segmentos MP4 continuamente
- Thumbnails das câmeras atualizando a cada 60s
- Purge automático removendo segmentos expirados

---

## SPRINT 4 — IA: ROI e LPR (Semanas 7-8)

**Meta:** Câmeras com ROI configurado detectam placas veiculares e geram eventos em tempo real.

### Backlog

**App: cameras — ROI**
- [ ] Escrever testes de ROI (criar, deletar, validações)
- [ ] Criar model RegionOfInterest
- [ ] ROIViewSet com CRUD
- [ ] Lógica: criar ROI → ia_status="active"; deletar último ROI → ia_status="ia_pending"
- [ ] Publicar "roi.updated" no RabbitMQ ao salvar/deletar ROI
- [ ] Endpoint GET /api/v1/cameras/{id}/snapshot/ (frame atual via MediaMTX API)

**Worker: AI Worker — LPR (Dockerfile.ai — FROM ai-base:latest)**
- [ ] Escrever testes LPR com mock de YOLOv8 (não precisa de GPU para testar)
- [ ] Criar `Dockerfile.ai`: `FROM ai-base:latest` (PyTorch, OpenCV, Ultralytics já incluídos)
- [ ] Implementar LPRProcessor:
  - Carrega modelo local `/app/models/plate_detector.pt` via Ultralytics
  - Crop do frame no polígono ROI
  - Inferência YOLOv8 → confidence ≥ 0.7 → gera evento
  - Dedup via Redis TTL 30s: `dedup:{camera_id}:{plate}` (redis já na ai-base)
- [ ] Salvar snapshot no storage com cv2 (opencv já na ai-base)
- [ ] Publicar em "ai.events"

**App: detections (Django)**
- [ ] Escrever testes de AIEvent e endpoint /detections/
- [ ] Criar model AIEvent
- [ ] Consumer RabbitMQ: consume "ai.events" → persiste AIEvent
- [ ] DetectionViewSet com filtros e paginação
- [ ] Notificação WebSocket ao operador (Django Channels)
- [ ] Exportação CSV e PDF

**Frontend: ROI**
- [ ] Página /zona-de-interesse
- [ ] Canvas com Konva.js para desenho de polígono
- [ ] Carregamento do snapshot da câmera
- [ ] Salvar/editar/excluir ROIs
- [ ] Feedback visual: ROI ativo = overlay colorido

**Frontend: Detecções**
- [ ] Página /detections com lista de eventos LPR
- [ ] Cards: snapshot, placa, modelo, data, câmera
- [ ] Filtros e busca por placa
- [ ] Toast de notificação em tempo real via WebSocket

### Critério de Aceite da Sprint 4
- ROI desenhado ativa a câmera (ia_status="active")
- Evento LPR gerado, persistido e visível em /detections
- Operador recebe notificação em tempo real
- Isolamento de tenant nos eventos garantido

---

## SPRINT 5 — Frontend Completo (Semanas 9-10)

**Meta:** Interface completa e funcional para o operador: mapa, mosaico, player completo.

### Backlog

**Dashboard: Mapa Tático**
- [ ] Mapa Leaflet com ícones de câmeras por coordenada
- [ ] Popup com thumbnail e botão "Abrir Player"
- [ ] Atualização de status em tempo real via WebSocket
- [ ] Filtros na sidebar funcionando
- [ ] Contadores no topo atualizados

**Mosaico**
- [ ] Página /mosaico
- [ ] Seletor de câmeras para compor grade
- [ ] Grades 2×2, 3×3, 4×4
- [ ] Stream WebRTC por célula
- [ ] Clique em célula → fullscreen

**Player: Timeline e Clipes**
- [ ] Timeline com marcadores de eventos IA
- [ ] Seletor de início/fim para clipe
- [ ] Modal de confirmação de clipe
- [ ] POST /api/v1/clips/ + toast "Processando..."

**App: clips (Django)**
- [ ] Escrever testes de geração de clipe
- [ ] Criar model Clip
- [ ] Endpoint POST /api/v1/clips/ → publica na fila "clip.request"
- [ ] Worker Clip Builder: concatena segmentos MP4 com FFmpeg
- [ ] Notificação quando clipe fica pronto
- [ ] Página /clipes com download

**Gestão de Usuários**
- [ ] Página /gestao/usuarios
- [ ] CRUD de usuários do tenant
- [ ] Atribuição de roles

### Critério de Aceite da Sprint 5
- Mapa tático exibindo câmeras com status em tempo real
- Mosaico com streams ao vivo funcionando
- Clipes gerados e disponíveis para download
- CRUD de usuários funcionando

---

## SPRINT 6 — Finalização e Franquia (Semanas 11-12)

**Meta:** Sistema completo com painel de franquia, relatórios, testes E2E e pronto para produção.

### Backlog

**App: reports (Django)**
- [ ] Relatório de eventos por câmera e período
- [ ] Relatório de uso de storage
- [ ] Exportação PDF (WeasyPrint ou ReportLab)
- [ ] Exportação CSV
- [ ] Agendamento de relatório por email (Celery Beat)

**Painel Master de Franquia**
- [ ] CRUD de Resellers (super admin)
- [ ] CRUD de Tenants por Revendedor
- [ ] Gerenciamento de Licenças
- [ ] Dashboard de métricas globais
- [ ] Funcionalidade de impersonação com log de auditoria
- [ ] Testes: super admin exclusivo, reseller sem acesso

**Ajustes Finais de White Label**
- [ ] Email de boas-vindas com identidade do revendedor
- [ ] Email de recuperação de senha com identidade do revendedor
- [ ] Verificação: nenhuma referência a GT-Vision em nenhuma saída de usuário
- [ ] Tema escuro por revendedor funcionando

**Testes E2E (Cypress)**
- [ ] Fluxo completo de white label (login, logo, cores)
- [ ] Fluxo de cadastro de câmera → aparece no mapa
- [ ] Fluxo de ROI → ativa IA
- [ ] Fluxo de clipe → download disponível
- [ ] Teste de isolamento de tenant (usuário A não vê câmeras do tenant B)

**Hardening e Produção**
- [ ] Revisão de segurança: scan de dependências (safety, snyk)
- [ ] Rate limiting global (django-ratelimit)
- [ ] Headers de segurança (CSP, HSTS, X-Frame-Options)
- [ ] Configuração Nginx para produção (SSL, gzip, caching)
- [ ] Kubernetes manifests básicos para deploy
- [ ] Runbook de deploy e rollback
- [ ] Documentação de variáveis de ambiente (`.env.example`)

### Critério de Aceite da Sprint 6 (Definition of Done do Projeto)
- Testes E2E passando em todos os fluxos críticos
- Cobertura de testes ≥ 85% no backend
- Nenhuma credencial exposta no código
- Nenhuma referência a "GT-Vision" visível ao usuário final
- Sistema deployado em ambiente de staging
- Painel de franquia operacional para super admin
- Documentação atualizada

---

## Resumo de Entregáveis por Sprint

| Sprint | Semanas | Entregável Principal |
|---|---|---|
| 1 | 1-2 | Login white label funcionando com tenant isolado |
| 2 | 3-4 | Câmeras cadastradas, status online/offline no mapa |
| 3 | 5-6 | Live view WebRTC + gravação contínua |
| 4 | 7-8 | Detecção de placas em tempo real com ROI |
| 5 | 9-10 | Interface completa: mapa, mosaico, clipes |
| 6 | 11-12 | Franquia, relatórios, E2E, hardening |

---

## Métricas de Qualidade por Sprint

| Métrica | Sprint 1-2 | Sprint 3-4 | Sprint 5-6 |
|---|---|---|---|
| Cobertura unit tests | ≥ 80% | ≥ 85% | ≥ 90% |
| Cobertura integração | ≥ 70% | ≥ 75% | ≥ 80% |
| Endpoints sem teste | 0 | 0 | 0 |
| Vazamentos de tenant | 0 | 0 | 0 |
| Referências GT-Vision em UI | 0 | 0 | 0 |
