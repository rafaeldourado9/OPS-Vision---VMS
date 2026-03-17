# 06 — GT-Vision · Regras para Agentes de IA
**Guia de Comportamento para Claude Code, Cursor e Copilot · v1.0**

---

## 1. Princípios Fundamentais

Todo agente que trabalhar neste projeto deve seguir estas regras sem exceção.
Se uma instrução do usuário conflitar com estas regras, as regras prevalecem e o agente deve informar o conflito.

---

## 2. Regras de Segurança

### 2.1 Multi-Tenant — REGRA ABSOLUTA
```
❌ PROIBIDO escrever qualquer query sem filtro de tenant_id
✅ CORRETO sempre filtrar pelo tenant do usuário autenticado

# Errado:
Camera.objects.all()
Camera.objects.filter(name="Centro")

# Correto:
Camera.objects.filter(tenant=request.tenant)
Camera.objects.filter(tenant=request.tenant, name="Centro")
```

**O agente deve:**
- Recusar-se a gerar código que consulte dados sem filtro de tenant
- Adicionar automaticamente `tenant=request.tenant` em toda QuerySet de models com tenant
- Criar um teste de isolamento para cada endpoint que acessa dados de tenant

### 2.2 White Label — REGRA DE IDENTIDADE
```
❌ PROIBIDO referenciar "GT-Vision" em qualquer template, email ou UI visível ao usuário final
✅ CORRETO usar sempre dados do request.reseller para textos, logos e cores

# Errado no template:
<title>GT-Vision — Sistema de Monitoramento</title>
<img src="/static/gt-vision-logo.png">

# Correto:
<title>{{ request.reseller.name }}</title>
<img src="{{ request.reseller.logo_url }}">
```

### 2.3 Autenticação
```
❌ PROIBIDO criar endpoints sem autenticação (exceto /api/v1/auth/login/ e /api/v1/theme/)
❌ PROIBIDO expor SECRET_KEY, senhas ou tokens em código
✅ CORRETO usar variáveis de ambiente para toda credencial

Endpoints internos (/api/v1/internal/*):
- Usar API key estática via header X-Internal-Key
- NUNCA acessíveis pela internet (apenas comunicação interna entre containers)
```

### 2.4 Permissões RBAC
```
Hierarquia de permissões (do mais restrito ao mais amplo):
operator < supervisor < city_admin < reseller_admin < super_admin

Regras:
- operator: apenas leitura (câmeras, detecções, dashboard)
- supervisor: leitura + ROI + clipes + relatórios
- city_admin: tudo do tenant (CRUD câmeras, usuários)
- reseller_admin: CRUD de tenants do seu revendedor
- super_admin: acesso total, incluindo /master/

O agente DEVE aplicar @require_role(...) em todo endpoint de escrita.
```

---

## 3. Regras de Código

### 3.1 Estilo Python/Django
```python
# Sempre usar type hints
def get_cameras(tenant_id: UUID) -> QuerySet[Camera]:
    ...

# Sempre usar serializers DRF — nunca retornar dict direto
# Sempre usar ViewSets com roteamento automático
# Sempre criar migration após alterar model
# Nunca usar raw SQL (usar ORM Django)
# Exceção ao ORM: queries complexas de relatório (usar .raw() com params)
```

### 3.2 Nomenclatura
```
Models: PascalCase (Camera, RecordingSegment, AIEvent)
Views/ViewSets: PascalCase + sufixo (CameraViewSet, ROIViewSet)
URLs: kebab-case (/zona-de-interesse/, /ai-events/)
Filas RabbitMQ: dot.notation (recording.start, ai.frame, clip.request)
Redis keys: colon:notation (wl:{host}, session:{id}, camera:thumb:{id})
Env vars: UPPER_SNAKE_CASE (DJANGO_SECRET_KEY, RABBITMQ_URL)
```

### 3.3 Estrutura de Arquivos
```
Nunca criar lógica de negócio em views.py
Criar services.py dentro de cada app para lógica de negócio:

apps/cameras/
├── models.py       → apenas modelo e relacionamentos
├── serializers.py  → validação e serialização
├── views.py        → apenas HTTP in/out, chama service
├── services.py     → lógica de negócio (criar câmera, ativar IA, etc.)
├── tasks.py        → tarefas Celery (se houver)
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   └── test_api.py
└── urls.py
```

### 3.4 Regras FastAPI Workers
```python
# Todo worker deve ter:
# 1. Reconexão automática com backoff exponencial
# 2. Health check endpoint: GET /health → {"status": "ok", "cameras_active": N}
# 3. Logging estruturado (JSON) com campos: timestamp, level, worker, camera_id, tenant_id
# 4. Graceful shutdown ao receber SIGTERM

async def start_with_retry(self, max_retries: int = -1):
    """max_retries=-1 significa retry infinito"""
    attempt = 0
    while max_retries == -1 or attempt < max_retries:
        try:
            await self.connect()
            return
        except Exception as e:
            wait = min(2 ** attempt, 30)  # backoff máximo de 30s
            logger.warning(f"Conexão falhou, tentando em {wait}s", extra={"error": str(e)})
            await asyncio.sleep(wait)
            attempt += 1
```

---

## 4. Regras de TDD

### 4.1 Ordem Obrigatória
```
1. Ler o requisito
2. Escrever o teste (falha esperada)
3. Escrever o mínimo de código para passar
4. Refatorar
5. Repetir

O agente NUNCA deve escrever implementação antes de ter um teste.
Se o usuário pedir apenas o código sem testes, o agente deve avisar e oferecer
escrever os testes junto.
```

### 4.2 Cobertura Mínima
```
Unit tests: 90% de cobertura por arquivo
Integration tests: todos os endpoints devem ter ao menos:
  - Teste de sucesso (happy path)
  - Teste de não autorizado (401/403)
  - Teste de isolamento de tenant (404 para recurso de outro tenant)
  - Teste de validação de entrada (400)
```

### 4.3 Nomenclatura de Testes
```python
# Padrão: test_{o_que_faz}_quando_{condição}_{resultado_esperado}

def test_create_camera_when_license_limit_reached_returns_403():
def test_login_when_wrong_password_returns_401():
def test_list_cameras_when_different_tenant_returns_empty():
def test_roi_when_less_than_3_points_returns_400():
```

---

## 5. Regras de Frontend

### 5.1 White Label no Frontend
```javascript
// SEMPRE usar o composable useWhiteLabel
// NUNCA hardcodar cores, logos ou nomes de produto

// Errado:
const primaryColor = '#005A9C'
<img src="/logo.png">
<h1>GT-Vision</h1>

// Correto:
const { theme } = useWhiteLabel()
<img :src="theme.logo_url">
// cor aplicada via CSS variable --color-primary injetada pelo composable
```

### 5.2 Performance
```
- Lazy loading obrigatório para rotas Vue/React
- Imagens: usar <img loading="lazy"> sempre
- Thumbnails: não carregar mais de 20 por vez (paginação)
- WebRTC: fechar conexão ao sair da página (cleanup em onUnmounted)
- Store Pinia: não guardar dados de vídeo binário (apenas URLs)
```

### 5.3 Tratamento de Erros
```javascript
// Todo fetch/axios deve ter try/catch com mensagem amigável
// Erro 401: redirecionar para /login automaticamente
// Erro 403: exibir "Sem permissão para esta ação"
// Erro 404: exibir "Recurso não encontrado"
// Erro 5xx: exibir "Erro interno. Tente novamente." + botão retry
// NUNCA exibir stack trace ou mensagem técnica para o usuário
```

---

## 6. Checklist por Funcionalidade

Antes de considerar uma funcionalidade como concluída, o agente deve verificar:

```
□ Model criado com tenant_id e migration gerada
□ Serializer com validação de campos obrigatórios
□ ViewSet com filtragem por tenant em todas as queries
□ Permissões RBAC aplicadas
□ Testes unitários (model e service)
□ Testes de integração (API)
□ Teste de isolamento de tenant
□ Teste de permissão (operador não pode escrever)
□ Factory criada em tests/factories.py
□ Endpoint documentado (docstring + tipo de retorno)
□ Nenhuma referência a "GT-Vision" em output visível ao usuário
□ Nenhuma credencial hardcoded
```

---

## 7. O Que o Agente NUNCA Deve Fazer

```
❌ Criar endpoint público sem autenticação (exceto /auth/login e /theme/)
❌ Fazer query sem filtro de tenant_id em models com tenant
❌ Hardcodar IPs, portas, senhas ou tokens
❌ Usar print() para debug (usar logging estruturado)
❌ Criar arquivo de migration manualmente (usar makemigrations)
❌ Retornar mais de 1.000 registros sem paginação
❌ Ignorar erros silenciosamente (exceto com log explícito)
❌ Usar eval() ou exec() em qualquer contexto
❌ Armazenar senha em plaintext (usar hashers do Django)
❌ Commitar com credenciais mesmo que de teste
❌ Criar funcionalidade sem teste correspondente
❌ Expor o nome "GT-Vision" em qualquer UI ou email do usuário final
❌ Chamar APIs externas de IA (AWS Rekognition, Google Vision, OpenALPR cloud, etc.)
❌ Instalar torch/opencv/ultralytics no Dockerfile.worker — essas libs só vão no Dockerfile.ai
❌ Usar FROM python:3.11-slim no Dockerfile do ai_worker — deve ser FROM ai-base:latest
```

---

## 8. Regras Docker — ai-base

```
Estrutura de imagens obrigatória:

Dockerfile.ai   (ai_worker)      → FROM ai-base:latest
Dockerfile.worker (demais)       → FROM python:3.11-slim

❌ PROIBIDO usar ai-base para workers que não fazem inferência de IA
   (recorder, frame_grabber, clip_builder, purge) — imagem desnecessariamente pesada

✅ CORRETO separar responsabilidades de imagem:
   - ai-base: PyTorch + OpenCV + ONNX + Ultralytics — apenas quem infere modelos
   - python:3.11-slim + ffmpeg: quem só processa vídeo/áudio

Ao gerar docker-compose.yml:
- ai-worker deve ter volume: ./models:/app/models:ro
- Todos os workers devem ter restart: unless-stopped
- Variáveis de ambiente NUNCA hardcoded no compose — usar env_file: .env

Diretório do projeto no host: D:\VMS (White Label)\
Imagem base local: C:\docker-images\ai-base\
Build da ai-base: docker build -t ai-base:latest C:\docker-images\ai-base\
Deve ser executado antes de qualquer docker-compose build
```

---

## 9. Comandos de Validação que o Agente Deve Rodar

```bash
# Após cada alteração em backend:
python manage.py check              # validações Django
pytest --cov=apps --cov-fail-under=80
flake8 apps/                        # linting
black apps/ --check                 # formatação

# Após alterar models:
python manage.py makemigrations --check  # verifica se migration foi gerada

# Verificar vazamento de tenant (grep por queries sem tenant):
grep -rn "\.objects\.all()" apps/ --include="*.py"
grep -rn "\.objects\.filter(" apps/ --include="*.py" | grep -v "tenant"
# → qualquer resultado do segundo grep é um bug potencial

# Verificar Dockerfiles incorretos no ai_worker:
grep -rn "FROM python" backend-fastapi/workers/ai_worker/
# → não deve retornar nada (deve ser FROM ai-base:latest)

# Verificar se libs de IA estão em workers errados:
grep -rn "torch\|ultralytics\|onnxruntime\|opencv" \
  backend-fastapi/workers/recorder/ \
  backend-fastapi/workers/frame_grabber/ \
  backend-fastapi/workers/clip_builder/ \
  backend-fastapi/workers/purge/
# → não deve retornar nada

# Frontend:
npm run type-check
npm run lint
npm run test:unit
```
