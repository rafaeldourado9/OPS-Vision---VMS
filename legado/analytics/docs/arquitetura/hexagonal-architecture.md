# Arquitetura Hexagonal - VMS Edge Worker

## Visão Geral

O VMS Edge Worker implementa uma **Arquitetura Hexagonal** (Ports & Adapters) com foco em:

1. **Desacoplamento Total**: Core não conhece implementações de IA
2. **Plugin-Based**: Adicione serviços sem alterar código existente
3. **Bounded Contexts**: Cada serviço é um contexto isolado
4. **Portabilidade**: Serviços podem ser movidos entre projetos

## Camadas da Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                    EXTERNAL WORLD                        │
│  (MediaMTX Instances, Redis, FastAPI Clients)           │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────┼─────────────────────────────┐
│                    ADAPTERS (Infrastructure)           │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ MediaMTX     │  │  Redis Bus   │  │  FastAPI    │ │
│  │ Connector    │  │              │  │  Routes     │ │
│  └──────────────┘  └──────────────┘  └─────────────┘ │
└────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────┼─────────────────────────────┐
│                    CORE (Domain)                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │         Orchestrator (Application Service)       │ │
│  │  - Coordena fluxo de dados                       │ │
│  │  - Agnóstico sobre implementações                │ │
│  └──────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────┐ │
│  │         Plugin Loader (Discovery)                │ │
│  │  - Descobre serviços dinamicamente               │ │
│  │  - Carrega implementações em runtime             │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────┼─────────────────────────────┐
│                    PORTS (Interfaces)                  │
│  ┌──────────────────────────────────────────────────┐ │
│  │         AIServiceInterface (Protocol)            │ │
│  │  - process_frame()                               │ │
│  │  - initialize()                                  │ │
│  │  - health_check()                                │ │
│  │  - shutdown()                                    │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
                          ▲
                          │
┌─────────────────────────┼─────────────────────────────┐
│              SERVICES (Bounded Contexts)               │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │ invasion_ai │  │   people    │  │   future     │  │
│  │             │  │   counter   │  │   service    │  │
│  │ - YOLO      │  │ - Counting  │  │ - ???        │  │
│  │ - Zones     │  │ - Tracking  │  │              │  │
│  └─────────────┘  └─────────────┘  └──────────────┘  │
└────────────────────────────────────────────────────────┘
```

## Princípios Aplicados

### 1. Dependency Inversion Principle (DIP)
- Core depende de abstrações (AIServiceInterface)
- Serviços implementam a interface
- Inversão de controle via Plugin Loader

### 2. Open/Closed Principle (OCP)
- Sistema aberto para extensão (novos serviços)
- Fechado para modificação (Core não muda)

### 3. Single Responsibility Principle (SRP)
- **MediaMTX Connector**: Apenas conexão com streams
- **Redis Bus**: Apenas transporte de mensagens
- **Orchestrator**: Apenas coordenação
- **Services**: Apenas lógica de IA

### 4. Interface Segregation Principle (ISP)
- Interface mínima e coesa
- Serviços implementam apenas o necessário

## Fluxo de Dados

```
1. MediaMTX Connector captura frames
         ↓
2. Orchestrator distribui via Redis
         ↓
3. Redis Bus enfileira por serviço
         ↓
4. Workers consomem e processam
         ↓
5. Resultados publicados no Redis
         ↓
6. Sistema externo consome resultados
```

## Vantagens da Arquitetura

### ✅ Modularidade
- Adicione serviços sem tocar no Core
- Remova serviços sem quebrar o sistema

### ✅ Testabilidade
- Cada camada pode ser testada isoladamente
- Mocks fáceis via interfaces

### ✅ Escalabilidade
- Escale serviços independentemente
- Múltiplos workers por serviço

### ✅ Manutenibilidade
- Mudanças localizadas
- Código limpo e organizado

### ✅ Portabilidade
- Serviços são autocontidos
- Reutilize em outros projetos

## Como Adicionar um Novo Serviço

1. Crie pasta em `/services/novo_servico/`
2. Implemente `AIServiceInterface` no `__init__.py`
3. Adicione `Dockerfile` e `requirements.txt`
4. **Pronto!** O sistema detecta automaticamente

Nenhuma linha de código fora da pasta precisa ser alterada.

## Tecnologias e Padrões

- **Python 3.11+**: Linguagem base
- **FastAPI**: API REST para controle
- **Redis**: Message broker
- **OpenCV**: Captura de vídeo
- **Ultralytics**: YOLO para detecção
- **Docker**: Isolamento de serviços
- **Async/Await**: Processamento concorrente

## Referências

- [Hexagonal Architecture (Alistair Cockburn)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Domain-Driven Design (Eric Evans)](https://www.domainlanguage.com/ddd/)
- [Clean Architecture (Robert C. Martin)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
