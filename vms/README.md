# VMS White-Label

VMS (Video Management System) white-label self-hosted para integradores de segurança. Multi-tenant, streaming via MediaMTX, eventos via webhooks, analytics via plugins modulares.

## Status do Projeto

**Fases 1–6 completas · 356 testes · 94% cobertura**

| Fase | Descrição | Status |
|------|-----------|--------|
| 1 | Event Normalizers (Hikvision, Intelbras, genérico) | ✅ |
| 2 | ALPR Deduplicação (Redis SET + TTL) | ✅ |
| 3 | Security Hardening (rate limit, HSTS, HMAC) | ✅ |
| 4 | BDD completo (32 cenários), cobertura 94% | ✅ |
| 5 | Health check, logging JSON, backup script | ✅ |
| 6 | Documentação completa | ✅ |
| 7 | Analytics Plugins (6 plugins) | 🔄 stubs prontos |
| 8 | Frontend | ⬜ |

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| API REST | Django 5.x + DRF |
| API Async | FastAPI + Uvicorn |
| Banco | PostgreSQL 16 |
| Cache / PubSub | Redis 7 |
| Message broker | RabbitMQ 3 |
| Task queue | Celery 5.4+ |
| Streaming | MediaMTX |
| Reverse proxy | Nginx |
| Python | 3.12 |

---

## Quick Start

**Pré-requisitos:** Docker + Docker Compose + Make

```bash
# 1. Subir todos os serviços
make up

# 2. Rodar migrations
make migrate

# 3. Criar superusuário
docker compose exec django python manage.py createsuperuser

# 4. Verificar saúde
curl http://localhost/api/v1/health/
```

---

## Serviços e Portas

| Serviço | Porta | Uso |
|---------|-------|-----|
| Nginx (API) | 80 | Ponto de entrada |
| Django | 8000 | API REST |
| FastAPI | 8001 | Webhooks / SSE |
| MediaMTX RTSP | 8554 | Ingestão de câmeras |
| MediaMTX RTMP | 1935 | Push dos agents |
| MediaMTX HLS | 8888 | Playback HLS |
| MediaMTX WebRTC | 8889 | Playback WebRTC |
| MediaMTX API | 9997 | Gestão de paths |
| PostgreSQL | 5432 | Banco de dados |
| Redis | 6379 | Cache / PubSub |
| RabbitMQ | 5672 | Event bus |
| RabbitMQ UI | 15672 | Management console |

---

## Comandos Principais

```bash
# Desenvolvimento
make up          # Sobe todos os serviços
make down        # Para tudo
make logs        # Logs (make logs s=django para um serviço)
make shell       # Django shell
make migrate     # Roda migrations
make seed        # Popula banco com dados de teste

# Qualidade
make test        # Testes unitários
make test-all    # Todos os testes (exceto E2E)
make test-bdd    # Testes BDD
make test-e2e    # Testes E2E (requer stack completa)
make test-cov    # Cobertura de código
make lint        # ruff + mypy
make ci          # lint + test-all (pipeline local)

# Manutenção
make clean       # Remove __pycache__ e .pyc
```

---

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [CLAUDE.md](CLAUDE.md) | Spec viva — leia antes de qualquer implementação |
| [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) | Referência completa da API REST com exemplos curl |
| [docs/deploy.md](docs/deploy.md) | Guia completo de deploy em produção |
| [docs/plugins.md](docs/plugins.md) | Como criar plugins de analytics |

---

## Convenções

- Lógica de negócio em `services.py` — nunca em views ou models
- Type hints em tudo
- Funções < 20 linhas
- Filtro por `tenant` obrigatório em todo QuerySet
- Tasks Celery em `core/apps/*/tasks.py` (worker monta `./core:/app`)
- Testes obrigatórios para toda feature e todo bugfix
