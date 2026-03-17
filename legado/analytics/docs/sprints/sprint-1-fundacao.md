# Sprint 1 - Fundação da Arquitetura

**Duração**: 2 semanas  
**Objetivo**: Estabelecer a base da arquitetura hexagonal e plugin system

## 🎯 Objetivos

1. Criar estrutura de pastas do projeto
2. Implementar interface base (AIServiceInterface)
3. Desenvolver Plugin Loader dinâmico
4. Configurar infraestrutura básica (Redis, FastAPI)

## 📋 User Stories

### US-1.1: Interface Base para Serviços
**Como** desenvolvedor  
**Quero** uma interface abstrata que todos os serviços devem implementar  
**Para** garantir consistência e desacoplamento

**Critérios de Aceite**:
- [ ] Classe abstrata `AIServiceInterface` criada
- [ ] Métodos obrigatórios: `process_frame()`, `initialize()`, `health_check()`, `shutdown()`
- [ ] Propriedades: `service_name`, `version`
- [ ] Documentação clara dos contratos

**Arquivos**:
- `services/__init__.py`

---

### US-1.2: Plugin Loader Dinâmico
**Como** sistema  
**Quero** descobrir e carregar serviços automaticamente  
**Para** não precisar configurar manualmente cada novo serviço

**Critérios de Aceite**:
- [ ] Varre pasta `/services` dinamicamente
- [ ] Identifica classes que implementam `AIServiceInterface`
- [ ] Carrega e inicializa serviços em runtime
- [ ] Logs claros de descoberta e carregamento
- [ ] Tratamento de erros robusto

**Arquivos**:
- `core/plugin_loader.py`

---

### US-1.3: Infraestrutura Redis
**Como** sistema  
**Quero** um barramento de mensagens via Redis  
**Para** comunicar frames entre Core e Serviços

**Critérios de Aceite**:
- [ ] Conexão assíncrona com Redis
- [ ] Métodos: `publish_frame()`, `consume_frame()`, `publish_result()`
- [ ] Serialização de frames (pickle) e metadata (JSON)
- [ ] Filas separadas por serviço
- [ ] Tratamento de reconexão

**Arquivos**:
- `core/redis_bus.py`

---

### US-1.4: FastAPI Base
**Como** operador  
**Quero** endpoints REST para monitorar o sistema  
**Para** verificar saúde e status dos serviços

**Critérios de Aceite**:
- [ ] Endpoint `/health` - Status geral
- [ ] Endpoint `/services` - Lista serviços carregados
- [ ] Endpoint `/` - Informações básicas
- [ ] Lifecycle management (startup/shutdown)

**Arquivos**:
- `main.py`

---

## 🏗️ Tarefas Técnicas

### T-1.1: Estrutura de Pastas
```
/vms-edge-worker
├── core/
├── services/
├── config/
├── docs/
│   ├── sprints/
│   ├── arquitetura/
│   └── artigos_cientificos/
├── main.py
├── requirements.txt
└── docker-compose.yml
```

### T-1.2: Configuração de Ambiente
- [ ] Criar `requirements.txt`
- [ ] Criar `.env.example`
- [ ] Configurar logging
- [ ] Criar `config/settings.py`

### T-1.3: Docker Setup
- [ ] Dockerfile principal
- [ ] docker-compose.yml com Redis
- [ ] Configuração de rede

---

## 🧪 Testes

### Testes Unitários
- [ ] `test_plugin_loader.py` - Descoberta de serviços
- [ ] `test_redis_bus.py` - Publicação/consumo
- [ ] `test_ai_service_interface.py` - Validação de contrato

### Testes de Integração
- [ ] Plugin Loader + Serviço Mock
- [ ] Redis Bus + Serialização de frames
- [ ] FastAPI + Plugin Loader

---

## 📊 Definição de Pronto (DoD)

- [ ] Código implementado e revisado
- [ ] Testes unitários passando (>80% cobertura)
- [ ] Documentação atualizada
- [ ] Docker build funcionando
- [ ] Logs estruturados implementados
- [ ] Code review aprovado

---

## 🚀 Entregáveis

1. **Código**:
   - Interface base funcional
   - Plugin Loader operacional
   - Redis Bus implementado
   - FastAPI com endpoints básicos

2. **Documentação**:
   - README.md com instruções de setup
   - Documentação da arquitetura
   - Diagramas de fluxo

3. **Infraestrutura**:
   - Docker Compose funcional
   - Configurações de ambiente

---

## 🎓 Aprendizados Esperados

- Arquitetura Hexagonal na prática
- Plugin systems em Python
- Async/await com FastAPI
- Redis como message broker
- Dependency Injection

---

## 📈 Métricas de Sucesso

- ✅ Plugin Loader descobre serviços em <100ms
- ✅ Redis Bus processa >100 frames/segundo
- ✅ FastAPI responde health check em <50ms
- ✅ Zero configuração manual para novos serviços

---

## 🔄 Próxima Sprint

**Sprint 2**: Integração com MediaMTX e primeiro serviço de IA
