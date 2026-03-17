# Sprint 3 - Escalabilidade e Segundo Serviço

**Duração**: 2 semanas  
**Objetivo**: Adicionar segundo serviço e otimizar performance

## 🎯 Objetivos

1. Implementar serviço `people_counter`
2. Otimizar processamento de frames
3. Implementar métricas e observabilidade
4. Testes de carga e escalabilidade

## 📋 User Stories

### US-3.1: Serviço People Counter
**Como** cliente  
**Quero** contar pessoas em uma área  
**Para** análise de fluxo e ocupação

**Critérios de Aceite**:
- [ ] Implementa `AIServiceInterface`
- [ ] Conta pessoas por frame
- [ ] Configuração de threshold
- [ ] Dockerfile isolado
- [ ] Carregado automaticamente pelo Plugin Loader

**Arquivos**:
- `services/people_counter/__init__.py`
- `services/people_counter/Dockerfile`
- `services/people_counter/requirements.txt`

---

### US-3.2: Otimização de Performance
**Como** sistema  
**Quero** processar mais frames por segundo  
**Para** suportar mais câmeras simultaneamente

**Critérios de Aceite**:
- [ ] Batch processing de frames
- [ ] Pool de workers configurável
- [ ] Reuso de conexões RTSP
- [ ] Cache de modelos YOLO
- [ ] Redução de latência em 30%

**Arquivos**:
- `core/orchestrator.py` (otimizações)
- `config/settings.py` (novos parâmetros)

---

### US-3.3: Métricas e Observabilidade
**Como** operador  
**Quero** métricas detalhadas do sistema  
**Para** identificar gargalos e problemas

**Critérios de Aceite**:
- [ ] Métricas de latência por serviço
- [ ] Contadores de frames processados
- [ ] Tamanho de filas Redis
- [ ] Uso de CPU/memória por serviço
- [ ] Endpoint `/metrics` (Prometheus format)

**Arquivos**:
- `core/metrics.py`
- `main.py` (endpoint /metrics)

---

### US-3.4: Reload Dinâmico de Serviços
**Como** desenvolvedor  
**Quero** recarregar serviços sem reiniciar o sistema  
**Para** agilizar desenvolvimento e deploy

**Critérios de Aceite**:
- [ ] Endpoint `/reload-services`
- [ ] Shutdown graceful de serviços antigos
- [ ] Carregamento de novos serviços
- [ ] Zero downtime para outros serviços

**Arquivos**:
- `main.py` (endpoint)
- `core/plugin_loader.py` (reload)

---

## 🏗️ Tarefas Técnicas

### T-3.1: Batch Processing
- [ ] Agrupar frames por serviço
- [ ] Processar em lotes (batch inference)
- [ ] Otimizar serialização Redis

### T-3.2: Connection Pooling
- [ ] Pool de conexões RTSP
- [ ] Reuso de VideoCapture
- [ ] Gerenciamento de recursos

### T-3.3: Métricas
- [ ] Integração com Prometheus
- [ ] Histogramas de latência
- [ ] Contadores de eventos
- [ ] Gauges de estado

### T-3.4: Testes de Carga
- [ ] Simular 20 câmeras simultâneas
- [ ] Medir throughput
- [ ] Identificar bottlenecks
- [ ] Documentar limites

---

## 🧪 Testes

### Testes de Performance
- [ ] Latência <100ms com 10 câmeras
- [ ] Throughput >50 FPS total
- [ ] Uso de memória <4GB
- [ ] CPU <80% em carga máxima

### Testes de Escalabilidade
- [ ] Adicionar serviço em runtime
- [ ] Remover serviço sem impacto
- [ ] Múltiplos workers por serviço
- [ ] Balanceamento de carga

### Testes de Resiliência
- [ ] Falha de um serviço não afeta outros
- [ ] Reconexão automática Redis
- [ ] Reconexão automática MediaMTX
- [ ] Graceful degradation

---

## 📊 Definição de Pronto (DoD)

- [ ] Código implementado e revisado
- [ ] Testes de carga executados
- [ ] Documentação de performance
- [ ] Métricas implementadas
- [ ] Benchmarks documentados
- [ ] Guia de otimização criado

---

## 🚀 Entregáveis

1. **Código**:
   - Serviço people_counter
   - Otimizações de performance
   - Sistema de métricas
   - Reload dinâmico

2. **Documentação**:
   - Guia de performance tuning
   - Benchmarks e limites
   - Troubleshooting avançado

3. **Infraestrutura**:
   - Prometheus + Grafana (opcional)
   - Dashboards de monitoramento

---

## 📈 Métricas de Sucesso

- ✅ Processa 20 câmeras a 5 FPS cada
- ✅ Latência média <100ms
- ✅ Adicionar novo serviço em <1 minuto
- ✅ Zero downtime em reload
- ✅ Uso de memória linear com número de serviços

---

## 🎓 Aprendizados Esperados

- Otimização de sistemas em tempo real
- Observabilidade e métricas
- Batch processing
- Hot reload de módulos Python
- Performance profiling

---

## 🔄 Próxima Sprint

**Sprint 4**: Produção e deployment
