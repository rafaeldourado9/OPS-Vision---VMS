# Testes Unitários - Camera CRUD (TDD)

## Status: RED ❌

Testes criados seguindo TDD. Implementação do serviço ainda não existe.

## Arquivos Criados

### Testes
- `core/apps/cameras/tests/test_services.py` - Testes unitários do serviço create_camera

### Stubs (interfaces)
- `core/apps/cameras/models.py` - Model Camera
- `core/apps/cameras/services.py` - Stub do serviço create_camera
- `core/shared/mediamtx_client.py` - Stub do MediaMTXClient
- `core/shared/event_bus.py` - Stub do event_bus
- `tests/factories.py` - Factories para testes

## Casos de Teste Implementados

### TestCreateCamera (7 testes)

1. **test_creates_camera_in_database**
   - Verifica que a câmera é criada no banco com todos os campos corretos
   - Valida valores padrão (is_online=False)

2. **test_registers_path_in_mediamtx**
   - Verifica que MediaMTXClient.add_path() é chamado
   - Valida formato do path: `tenant-{tenant_id}/cam-{camera_id}`
   - Valida que source é o rtsp_url correto

3. **test_publishes_camera_created_event**
   - Verifica que publish_event() é chamado com tipo "camera.created"
   - Valida payload do evento (camera_id, tenant_id, name, location)

4. **test_mediamtx_failure_raises_error**
   - Verifica que MediaMTXError é propagado quando MediaMTX falha
   - Valida mensagem de erro

5. **test_rollback_on_mediamtx_failure**
   - Verifica que a transação é revertida se MediaMTX falhar
   - Valida que câmera NÃO existe no banco após falha
   - Valida que evento NÃO é publicado após falha

6. **test_event_published_after_mediamtx_success**
   - Verifica ordem de execução: MediaMTX antes do evento
   - Garante que evento só é publicado após sucesso no MediaMTX

7. **test_creates_camera_with_default_values**
   - Verifica valores padrão quando campos opcionais não são fornecidos
   - Valida manufacturer="other" e retention_days=7

## Mocks Utilizados

- `@patch("apps.cameras.services.MediaMTXClient")` - Mock do client MediaMTX
- `@patch("apps.cameras.services.publish_event")` - Mock do event bus

## Próximos Passos

1. Rodar os testes (devem FALHAR - RED)
2. Implementar o serviço `create_camera` em `services.py`
3. Rodar os testes novamente (devem PASSAR - GREEN)
4. Refatorar se necessário (REFACTOR)

## Como Rodar

```bash
# Quando o ambiente Django estiver configurado:
pytest core/apps/cameras/tests/test_services.py -v
```

## Cobertura Esperada

- ✅ Criação no banco de dados
- ✅ Integração com MediaMTX
- ✅ Publicação de eventos
- ✅ Tratamento de erros
- ✅ Rollback de transações
- ✅ Ordem de execução
- ✅ Valores padrão
