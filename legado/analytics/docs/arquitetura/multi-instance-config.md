# Configuração de Múltiplas Instâncias MediaMTX

## Visão Geral

O sistema suporta conexão com N instâncias MediaMTX simultaneamente, permitindo multi-tenancy e isolamento por cliente.

## Configuração via JSON

### 1. Copie o arquivo de exemplo

```bash
cp config/mediamtx_instances.json.example config/mediamtx_instances.json
cp config/services_config.json.example config/services_config.json
```

### 2. Configure suas instâncias

Edite `config/mediamtx_instances.json`:

```json
[
  {
    "id": "cliente_a",
    "api_url": "http://192.168.1.100:9997/v3/paths/list",
    "username": "user_a",
    "password": "pass_a",
    "enabled": true
  },
  {
    "id": "cliente_b",
    "api_url": "http://192.168.1.101:9997/v3/paths/list",
    "username": "user_b",
    "password": "pass_b",
    "enabled": true
  }
]
```

### 3. Configure os serviços de IA

Edite `config/services_config.json`:

```json
{
  "invasion_ai": {
    "model_path": "models/yolov8n.pt",
    "confidence_threshold": 0.5,
    "target_classes": ["person"]
  },
  "people_counter": {
    "model_path": "models/yolov8s.pt",
    "confidence_threshold": 0.6
  }
}
```

## Campos da Configuração MediaMTX

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id` | string | Sim | Identificador único da instância |
| `api_url` | string | Sim | URL da API MediaMTX v3 |
| `username` | string | Sim | Usuário para autenticação |
| `password` | string | Sim | Senha para autenticação |
| `enabled` | boolean | Não | Se false, instância é ignorada (padrão: true) |

## Variáveis de Ambiente

Você pode sobrescrever os caminhos dos arquivos:

```bash
export MEDIAMTX_CONFIG_FILE=/custom/path/mediamtx.json
export SERVICES_CONFIG_FILE=/custom/path/services.json
```

## Exemplo Multi-Tenant

### Cenário: 3 Clientes

**Cliente A** (10 câmeras):
- Serviços: invasion_ai

**Cliente B** (15 câmeras):
- Serviços: invasion_ai, people_counter

**Cliente C** (5 câmeras):
- Serviços: people_counter

### Configuração

```json
[
  {
    "id": "cliente_a_vms",
    "api_url": "http://10.0.1.100:9997/v3/paths/list",
    "username": "cliente_a",
    "password": "secure_pass_a"
  },
  {
    "id": "cliente_b_vms",
    "api_url": "http://10.0.2.100:9997/v3/paths/list",
    "username": "cliente_b",
    "password": "secure_pass_b"
  },
  {
    "id": "cliente_c_vms",
    "api_url": "http://10.0.3.100:9997/v3/paths/list",
    "username": "cliente_c",
    "password": "secure_pass_c"
  }
]
```

Todos os serviços processam frames de todas as instâncias automaticamente.

## Segurança

1. Nunca commite `mediamtx_instances.json` no Git
2. Use variáveis de ambiente em produção
3. Considere usar secrets management (AWS Secrets Manager, HashiCorp Vault)
4. Rotacione senhas regularmente

## Troubleshooting

### Instância não conecta

```bash
# Teste manualmente
curl -u username:password http://IP:9997/v3/paths/list
```

### Verificar instâncias carregadas

```bash
curl http://localhost:8000/streams
```

### Desabilitar instância temporariamente

Mude `"enabled": false` no JSON e reinicie:

```bash
docker-compose restart core
```
