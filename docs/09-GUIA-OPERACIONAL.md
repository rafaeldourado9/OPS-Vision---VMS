# 09 — Guia Operacional
**GT-Vision VMS · Como iniciar, configurar e operar o sistema**

---

## 1. Pré-requisitos

- Docker Desktop instalado e rodando
- Modelo YOLO em `D:\VMS (White Label)\models\plate_detector.pt`
- Imagem `ai-base:latest` buildada localmente

```bash
# Buildar ai-base (apenas uma vez)
docker build -t ai-base:latest C:\docker-images\ai-base\
```

---

## 2. Subir o sistema

```bash
cd "D:\VMS (White Label)\infra"
docker-compose up --build
```

Na primeira vez o build demora ~5 min (download de dependências IA).

### Verificar se está tudo rodando

```bash
docker-compose ps
```

Todos os serviços devem estar `running`:
- `django`, `postgres`, `redis`, `rabbitmq`
- `mediamtx`, `frontend`
- `ai-worker`, `frame-grabber`, `recorder-worker`, `clip-builder`, `purge-worker`

---

## 3. Primeiro acesso — seed inicial

Na **primeira vez** que subir, é necessário criar os dados base via Django shell:

```bash
cd "D:\VMS (White Label)\infra"
docker-compose exec django python manage.py shell
```

Cole e execute:

```python
from datetime import date, timedelta
from apps.resellers.models import Reseller
from apps.franchise.models import License
from apps.tenants.models import Tenant
from apps.auth_app.models import User

# 1. Reseller (marca/revendedor)
r = Reseller.objects.create(
    name='Minha Empresa',
    slug='minha-empresa',
    primary_color='#3B82F6',
    secondary_color='#1E40AF',
    custom_domain='localhost',   # domínio que o nginx vai usar
    active=True,
)

# 2. Licença
lic = License.objects.create(
    reseller=r,
    max_cameras=50,              # limite de câmeras
    valid_until=date(2027, 12, 31),
    active=True,
)

# 3. Tenant (cliente/cidade)
t = Tenant.objects.create(
    reseller=r,
    license=lic,
    name='Cidade Demo',
    subdomain='demo',
    active=True,
)

# 4. Super Admin
u = User.objects.create_superuser(
    email='admin@empresa.com',
    password='SuaSenhaAqui123',
    role='super_admin',
    tenant=t,
)

print('Pronto!')
print(f'  Reseller : {r.name}')
print(f'  Tenant   : {t.name}')
print(f'  Login    : {u.email}')
```

Acesse **http://localhost** e faça login com as credenciais criadas.

---

## 4. Criar Resellers adicionais (White Label)

Cada revendedor tem sua própria identidade visual e domínio.

```bash
docker-compose exec django python manage.py shell
```

```python
from apps.resellers.models import Reseller

Reseller.objects.create(
    name='Empresa Parceira LTDA',
    slug='parceira',
    primary_color='#EF4444',        # cor principal
    secondary_color='#991B1B',
    logo_url='https://cdn.exemplo.com/logo.png',  # opcional
    favicon_url='https://cdn.exemplo.com/favicon.ico',
    custom_domain='parceira.exemplo.com',  # domínio público do revendedor
    active=True,
)
```

---

## 5. Criar Tenants (clientes/cidades)

Cada tenant é uma cidade ou cliente isolado dentro de um revendedor.

```python
from datetime import date
from apps.resellers.models import Reseller
from apps.franchise.models import License
from apps.tenants.models import Tenant

r = Reseller.objects.get(slug='parceira')

lic = License.objects.create(
    reseller=r,
    max_cameras=20,
    valid_until=date(2026, 12, 31),
    active=True,
)

Tenant.objects.create(
    reseller=r,
    license=lic,
    name='Prefeitura de São Paulo',
    subdomain='saopaulo',   # acessado via saopaulo.parceira.exemplo.com
    active=True,
)
```

---

## 6. Criar Usuários

### Via shell (qualquer role)

```python
from apps.auth_app.models import User
from apps.tenants.models import Tenant

t = Tenant.objects.get(subdomain='demo')

User.objects.create_user(
    email='operador@empresa.com',
    password='Senha123',
    role='operator',       # operator | supervisor | city_admin | reseller_admin | super_admin
    tenant=t,
)
```

### Via interface web

1. Acesse **http://localhost**
2. Faça login como `city_admin` ou superior
3. Vá em **Usuários** → **Novo Usuário**
4. Preencha nome, email, perfil e senha

### Hierarquia de roles

| Role | Pode criar até |
|------|---------------|
| `super_admin` | Todos |
| `reseller_admin` | city_admin, supervisor, operator |
| `city_admin` | supervisor, operator |
| `supervisor` | — |
| `operator` | — |

---

## 7. Gerenciar Licenças

### Ver licenças ativas

```python
from apps.franchise.models import License

for lic in License.objects.select_related('reseller').filter(active=True):
    cameras_usadas = lic.tenants.first().cameras.count() if lic.tenants.exists() else 0
    print(f'{lic.reseller.name}: {cameras_usadas}/{lic.max_cameras} câmeras | válida até {lic.valid_until}')
```

### Alterar limite de câmeras

```python
lic = License.objects.get(reseller__slug='minha-empresa')
lic.max_cameras = 100
lic.save()
```

### Renovar validade

```python
from datetime import date
lic.valid_until = date(2028, 12, 31)
lic.save()
```

### Desativar licença (bloqueia criação de novas câmeras)

```python
lic.active = False
lic.save()
```

---

## 8. Comandos úteis do dia a dia

```bash
# Subir tudo
docker-compose up -d

# Parar tudo
docker-compose down

# Ver logs em tempo real
docker-compose logs -f django
docker-compose logs -f ai-worker
docker-compose logs -f frontend

# Reiniciar um serviço específico
docker-compose restart django
docker-compose restart frontend

# Aplicar migrations após mudanças no modelo
docker-compose exec django python manage.py makemigrations
docker-compose exec django python manage.py migrate

# Abrir shell Django
docker-compose exec django python manage.py shell

# Abrir psql direto no banco
docker-compose exec postgres psql -U gtvision -d gtvision
```

---

## 9. Resetar tudo (banco limpo)

```bash
cd "D:\VMS (White Label)\infra"
docker-compose down -v        # remove containers E volumes
docker-compose up --build     # sobe do zero
# Depois repita o seed do item 3
```

---

## 10. Acessos rápidos

| Serviço | URL | Credenciais |
|---------|-----|-------------|
| Frontend | http://localhost | admin criado no seed |
| Django Admin | http://localhost/api/admin/ | mesmo login |
| RabbitMQ UI | http://localhost:15672 | guest / guest |
| HLS stream | http://localhost:8888/{stream_key}/index.m3u8 | — |
| MediaMTX API | http://localhost:9997 | — |

---

## 11. Configurar câmera (fluxo completo)

1. Acesse http://localhost → **Câmeras** → **+ Adicionar Câmera**
2. Escolha protocolo: **RTSP** (câmera IP) ou **RTMP** (push)
3. Informe IP/URL, usuário e senha da câmera
4. Dê um nome e localização (lat/lng para aparecer no mapa)
5. Escolha retenção (7, 15 ou 30 dias)
6. Ative IA se quiser analíticos

Após salvar, o `frame-grabber` começa a capturar thumbnails e o `recorder-worker` inicia a gravação contínua.

### Adicionar ROI (área de análise)

1. Clique na câmera → aba **ROI** → **Editar ROIs**
2. Clique em **Nova ROI**, escolha o tipo de analítico
3. Desenhe o polígono no canvas clicando nos pontos
4. Duplo clique para fechar → **Salvar**

O AI worker recebe a ROI em tempo real via RabbitMQ e começa a detectar eventos.

---

## 12. Troubleshooting

| Sintoma | Causa provável | Fix |
|---------|---------------|-----|
| Frontend retorna 404 | nginx com nome errado do upstream | Verificar `nginx.conf`: `proxy_pass http://django:8000` |
| Login retorna 404 | Tenant não existe para o host | Criar reseller com `custom_domain=localhost` |
| `/api/v1/internal/persons/` 500 | WhiteLabelMiddleware sem bypass | Verificar `middleware/tenant.py` BYPASS_PATHS |
| AI worker sem GPU | CUDA não disponível no container | Mudar `AI_DEVICE=cpu` no `.env` do ai-worker |
| Câmera sempre offline | MediaMTX não consegue conectar | Verificar URL RTSP e rede Docker |
| Heatmap não atualiza | Redis sem pontos | Normal se câmera sem movimento |
