.PHONY: dev dev-core dev-app dev-ai dev-analytics dev-media build-ai build-analytics build-media test migrate shell logs stop stop-all clean

# Inicia todos os serviços
dev:
	@echo Iniciando todos os servicos...
	@docker network create gtvision 2>nul || echo.
	@cd infra && docker compose -f docker-compose.core.yml up -d
	@echo Aguardando servicos core ficarem prontos...
	@timeout /t 15 /nobreak >nul 2>nul || echo.
	@cd infra && docker compose -f docker-compose.app.yml up --build -d
	@cd infra && docker compose -f docker-compose.media.yml up --build -d
	@cd infra && docker compose -f docker-compose.analytics.yml up --build -d
	@cd infra && docker compose -f docker-compose.ai.yml up --build -d
	@echo Todos os servicos iniciados!

# Inicia apenas serviços core (postgres, redis, rabbitmq, mediamtx)
dev-core:
	@docker network create gtvision 2>nul || echo.
	@cd infra && docker compose -f docker-compose.core.yml up -d

# Inicia apenas aplicação (django, frontend, nginx)
dev-app:
	@docker network create gtvision 2>nul || echo.
	@cd infra && docker compose -f docker-compose.app.yml up --build -d

# Inicia apenas workers de IA (yolo, facial, lpr)
dev-ai:
	@docker network create gtvision 2>nul || echo.
	@cd infra && docker compose -f docker-compose.ai.yml up --build -d

# Inicia apenas workers de analytics
dev-analytics:
	@docker network create gtvision 2>nul || echo.
	@cd infra && docker compose -f docker-compose.analytics.yml up --build -d

# Inicia apenas workers de mídia
dev-media:
	@docker network create gtvision 2>nul || echo.
	@cd infra && docker compose -f docker-compose.media.yml up --build -d

# Build apenas workers de IA
build-ai:
	@cd infra && docker compose -f docker-compose.ai.yml build --no-cache

# Build apenas workers de analytics
build-analytics:
	@cd infra && docker compose -f docker-compose.analytics.yml build --no-cache

# Build apenas workers de mídia
build-media:
	@cd infra && docker compose -f docker-compose.media.yml build --no-cache

test:
	@cd infra && docker compose -f docker-compose.app.yml exec django pytest

migrate:
	@cd infra && docker compose -f docker-compose.app.yml exec django python manage.py migrate

shell:
	@cd infra && docker compose -f docker-compose.app.yml exec django python manage.py shell

# Logs de serviços específicos
logs:
	@echo Use: make logs-core, logs-app, logs-ai, logs-analytics, logs-media

logs-core:
	@cd infra && docker compose -f docker-compose.core.yml logs -f

logs-app:
	@cd infra && docker compose -f docker-compose.app.yml logs -f

logs-ai:
	@cd infra && docker compose -f docker-compose.ai.yml logs -f

logs-analytics:
	@cd infra && docker compose -f docker-compose.analytics.yml logs -f

logs-media:
	@cd infra && docker compose -f docker-compose.media.yml logs -f

# Para serviços específicos
stop:
	@echo Use: make stop-core, stop-app, stop-ai, stop-analytics, stop-media, stop-all

stop-core:
	@cd infra && docker compose -f docker-compose.core.yml down

stop-app:
	@cd infra && docker compose -f docker-compose.app.yml down

stop-ai:
	@cd infra && docker compose -f docker-compose.ai.yml down

stop-analytics:
	@cd infra && docker compose -f docker-compose.analytics.yml down

stop-media:
	@cd infra && docker compose -f docker-compose.media.yml down

stop-all:
	@cd infra && docker compose -f docker-compose.core.yml down
	@cd infra && docker compose -f docker-compose.app.yml down
	@cd infra && docker compose -f docker-compose.ai.yml down
	@cd infra && docker compose -f docker-compose.analytics.yml down
	@cd infra && docker compose -f docker-compose.media.yml down

clean:
	@cd infra && docker compose -f docker-compose.core.yml down -v
	@cd infra && docker compose -f docker-compose.app.yml down -v
	@cd infra && docker compose -f docker-compose.ai.yml down -v
	@cd infra && docker compose -f docker-compose.analytics.yml down -v
	@cd infra && docker compose -f docker-compose.media.yml down -v
	@docker network rm gtvision 2>nul || echo.
