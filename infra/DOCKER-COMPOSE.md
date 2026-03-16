# Docker Compose Modular

O projeto foi dividido em múltiplos docker-compose para facilitar o build e gerenciamento dos serviços.

## Estrutura

```
infra/
├── docker-compose.core.yml       # Postgres, Redis, RabbitMQ, MediaMTX
├── docker-compose.app.yml        # Django, Frontend, Nginx
├── docker-compose.ai.yml         # YOLO, Facial, LPR workers
├── docker-compose.analytics.yml  # Analytics workers
└── docker-compose.media.yml      # Recorder, Frame-grabber, Clip-builder, Purge
```

## Comandos Disponíveis

### Iniciar Serviços

```bash
# Inicia TODOS os serviços (recomendado para primeira vez)
make dev

# Inicia apenas serviços core (banco, cache, message broker)
make dev-core

# Inicia apenas aplicação (Django + Frontend + Nginx)
make dev-app

# Inicia apenas workers de IA (YOLO, Facial, LPR)
make dev-ai

# Inicia apenas workers de analytics
make dev-analytics

# Inicia apenas workers de mídia
make dev-media
```

### Build Seletivo

```bash
# Rebuild apenas workers de IA (útil quando há erro de rede)
make build-ai

# Rebuild apenas workers de analytics
make build-analytics

# Rebuild apenas workers de mídia
make build-media
```

### Logs

```bash
# Ver logs dos serviços core
make logs-core

# Ver logs da aplicação
make logs-app

# Ver logs dos workers de IA
make logs-ai

# Ver logs dos workers de analytics
make logs-analytics

# Ver logs dos workers de mídia
make logs-media
```

### Parar Serviços

```bash
# Para todos os serviços
make stop-all

# Para apenas serviços core
make stop-core

# Para apenas aplicação
make stop-app

# Para apenas workers de IA
make stop-ai

# Para apenas workers de analytics
make stop-analytics

# Para apenas workers de mídia
make stop-media
```

### Limpar Tudo

```bash
# Remove todos os containers e volumes
make clean
```

## Fluxo de Trabalho Recomendado

### Primeira Vez

```bash
# 1. Inicia serviços core
make dev-core

# 2. Aguarda ~10s e inicia aplicação
make dev-app

# 3. Inicia workers de mídia
make dev-media

# 4. Inicia workers de analytics
make dev-analytics

# 5. Por último, inicia workers de IA (mais pesados)
make dev-ai
```

Ou simplesmente:

```bash
make dev
```

### Desenvolvimento

```bash
# Se alterou código do Django/Frontend
make stop-app
make dev-app

# Se alterou código dos workers de IA
make stop-ai
make build-ai
make dev-ai

# Se há erro de rede no build dos workers de IA
make build-ai  # Tenta novamente com timeout maior
```

### Troubleshooting

Se um worker de IA falhar no build por erro de rede:

```bash
# Para o serviço
make stop-ai

# Rebuild apenas esse stack
make build-ai

# Inicia novamente
make dev-ai
```

## Vantagens

1. **Build mais rápido**: Builda apenas o que mudou
2. **Menos memória**: Inicia apenas os serviços necessários
3. **Melhor debugging**: Logs separados por stack
4. **Recuperação de erros**: Se um worker falhar, rebuilda apenas ele
5. **Desenvolvimento**: Trabalha em uma parte sem afetar outras

## Dependências

- **core** → Não depende de nada
- **app** → Depende de **core**
- **ai** → Depende de **core**
- **analytics** → Depende de **core**
- **media** → Depende de **core**

Todos os serviços compartilham a mesma rede Docker: `gtvision`
