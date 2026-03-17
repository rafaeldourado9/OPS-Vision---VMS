.PHONY: help up down build logs shell dbshell migrate makemigrations seed \
       test test-all test-bdd test-e2e test-cov lint ci \
       beat-logs frontend-dev frontend-build clean

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker ──────────────────────────────────────────
up: ## Sobe todos os serviços
	docker compose up -d

down: ## Para todos os serviços
	docker compose down

build: ## Reconstrói imagens
	docker compose build

logs: ## Mostra logs (use: make logs s=django)
	docker compose logs -f $(s)

beat-logs: ## Mostra logs do Celery Beat
	docker compose logs -f beat

# ── Desenvolvimento ─────────────────────────────────
shell: ## Shell Django
	docker compose exec django python manage.py shell

dbshell: ## Shell PostgreSQL
	docker compose exec postgres psql -U vms -d vms

migrate: ## Roda migrations
	docker compose exec django python manage.py migrate

makemigrations: ## Cria migrations
	docker compose exec django python manage.py makemigrations

seed: ## Popula banco com dados de teste
	docker compose exec django python manage.py seed --cameras=10

# ── Qualidade ───────────────────────────────────────
test: ## Roda testes unitários
	docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test django pytest -m "unit" --tb=short -q

test-all: ## Roda TODOS os testes (exceto E2E)
	docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test django pytest --tb=short --ignore=tests/e2e

test-bdd: ## Roda testes BDD
	docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test django pytest -m "bdd" -v

test-e2e: ## Roda testes E2E
	docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test django pytest -m "e2e" -v

test-cov: ## Testes com cobertura
	docker compose exec -e DJANGO_SETTINGS_MODULE=config.settings.test django pytest --cov=apps --cov-report=html --cov-report=term

lint: ## Roda linters
	docker compose exec django ruff check .
	docker compose exec django ruff format --check .
	docker compose exec django mypy apps/

ci: ## Pipeline CI completa (lint + test + type-check)
	@echo "══ LINT ═══════════════════════"
	$(MAKE) lint
	@echo "══ TESTS ═════════════════════"
	$(MAKE) test-all
	@echo "══ CI PASSED ═════════════════"

# ── Frontend ────────────────────────────────────────
frontend-dev: ## Sobe frontend via Docker (acessível em http://localhost via nginx)
	docker compose up -d frontend nginx

frontend-build: ## Build de produção do frontend
	docker compose build frontend

frontend-logs: ## Mostra logs do frontend
	docker compose logs -f frontend

# ── Limpeza ─────────────────────────────────────────
clean: ## Remove arquivos temporários
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov .coverage
