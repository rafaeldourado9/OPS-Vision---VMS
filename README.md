# GT-Vision - VMS Urbano com IA

Sistema de gerenciamento de vídeo urbano com IA, white label e multi-tenant.

## Stack

- Django 4.2 + Django REST Framework
- PostgreSQL 15
- Redis 7
- Django Channels (WebSocket)
- MediaMTX (streaming)
- RabbitMQ (message queue)
- FastAPI Workers (AI processing)

## Setup Inicial

1. Clone o repositório
2. Copie o arquivo de ambiente:
```bash
cp backend-django/.env.example backend-django/.env
```

3. Edite o `.env` com suas credenciais

4. Inicie os serviços:
```bash
make dev
```

5. Execute as migrations:
```bash
make migrate
```

## Comandos Disponíveis

- `make dev` - Inicia todos os serviços com hot reload
- `make build-ai` - Rebuild da imagem ai-base e ai-worker
- `make test` - Executa testes
- `make migrate` - Executa migrations
- `make shell` - Abre Django shell
- `make logs-ai` - Visualiza logs do AI worker
- `make stop` - Para todos os serviços
- `make clean` - Para e remove volumes

## Estrutura do Projeto

```
.
├── backend-django/          # Django API
│   ├── gtvision/           # Configurações principais
│   └── apps/               # Apps Django
├── backend-fastapi/        # Workers FastAPI
│   └── workers/
│       ├── ai_worker/      # Processamento de IA
│       ├── recorder/       # Gravação de vídeo
│       ├── frame_grabber/  # Captura de frames
│       ├── clip_builder/   # Geração de clipes
│       └── purge/          # Limpeza de arquivos
├── infra/                  # Docker compose e configs
└── docs/                   # Documentação
```

## Portas

- 80: Nginx (proxy reverso)
- 8000: Django
- 5432: PostgreSQL
- 6379: Redis
- 5672: RabbitMQ
- 15672: RabbitMQ Management
- 8554: MediaMTX RTSP
- 1935: MediaMTX RTMP
- 8888: MediaMTX HLS
- 8889: MediaMTX WebRTC
