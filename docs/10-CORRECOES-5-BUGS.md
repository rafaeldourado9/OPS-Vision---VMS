# 10 - Correcoes dos 5 Bugs Criticos (VMS)

**Data:** 2026-03-10  
**Escopo:** Thumbnail de camera, snapshots de deteccoes, deduplicacao LPR, recorder worker e pipeline de analytics.

---

## Resumo Executivo

Este documento registra as correcoes aplicadas no pacote "Plano de Correcao Completa (5 Bugs)", com foco em estabilidade de producao e consistencia entre Django, workers e infraestrutura.

Status final:

- Bug 1 (thumbnail): corrigido
- Bug 2 (foto da placa em eventos): corrigido e validado
- Bug 3 (placas duplicadas): corrigido
- Bug 4 (gravacao): corrigido
- Bug 5 (analytics/ingestao sem ROI): corrigido

---

## Bug 1 - Thumbnail da camera nao exibia

### Causa-raiz

O frame grabber escrevia base64 raw no Redis, mas a leitura em Django via `cache.get()` podia falhar por serializacao/deserializacao do backend de cache.

### Correcao aplicada

- Django passou a ler/escrever thumbnail direto no Redis (sem usar `django.core.cache` para esse caso).
- Frame grabber passou a gravar apenas na chave canonica `thumbnail:{camera_id}`.

### Arquivos alterados

- `backend-django/apps/cameras/views.py`
- `backend-fastapi/workers/frame_grabber/worker/service.py`

### Resultado esperado

- Endpoint `GET /api/v1/cameras/{id}/thumbnail/` retorna JPEG do cache de forma consistente.
- Menor dependencia do fallback FFmpeg no primeiro acesso.

---

## Bug 2 - Foto da placa nao exibia nos eventos

### Causa-raiz

Inconsistencia historica entre `snapshot_path`, separador de path e exposicao do volume no Nginx.

### Estado final

Este item ja estava corrigido e foi mantido:

- Serializer normaliza `snapshot_path` para URL com `/`.
- Nginx serve `/media/` usando `alias /app/storage/`.
- Frontend/nginx monta `../storage:/app/storage:ro`.

### Arquivos relevantes (ja corrigidos no ciclo anterior)

- `backend-django/apps/detections/serializers.py`
- `infra/nginx.conf`
- `infra/docker-compose.yml`

### Resultado esperado

- Campo `thumbnail_url` das deteccoes resolve para imagem valida em `/media/snapshots/...`.

---

## Bug 3 - Placas repetidas/duplicadas

### Causa-raiz

Dedup por igualdade exata era sensivel a variacoes de OCR (ex.: `HI01557` vs `HIO1557`).

### Correcao aplicada

- Criado modulo compartilhado de placa com:
  - normalizacao de texto
  - validacao de placa BR (antiga e Mercosul)
  - dedup difuso por similaridade
- Alinhado comportamento entre `lpr_service.py`, `service.py` (AI worker geral) e `analyzers/lpr.py`.
- TTL efetivo de dedup LPR alinhado para 120s no fluxo LPR do AI worker.

### Arquivos alterados

- `backend-fastapi/workers/ai_worker/worker/utils/plate.py` (novo)
- `backend-fastapi/workers/ai_worker/worker/utils/__init__.py` (novo)
- `backend-fastapi/workers/ai_worker/worker/lpr_service.py`
- `backend-fastapi/workers/ai_worker/worker/service.py`
- `backend-fastapi/workers/ai_worker/worker/analyzers/lpr.py`

### Resultado esperado

- Menos eventos duplicados da mesma placa fisica.
- Menos falsos positivos com texto OCR invalido.

---

## Bug 4 - Gravacao nao estava salvando de forma confiavel

### Causa-raiz

Embora o consumo das filas estivesse nao bloqueante, faltavam protecoes operacionais no recorder:

- sem guard de start duplicado
- sem observabilidade de erro FFmpeg
- sem autorecovery quando FFmpeg encerrava inesperadamente

### Correcao aplicada

- Guard para evitar processos FFmpeg duplicados por camera.
- Leitura e log de `stderr` do FFmpeg (linhas de erro).
- Adicionado `-rtsp_transport tcp` para maior estabilidade RTSP.
- Watchdog para reiniciar gravacao apos queda inesperada.
- Stop com timeout e kill de fallback.

### Arquivo alterado

- `backend-fastapi/workers/recorder/worker/service.py`

### Resultado esperado

- Gravacao continua mais estavel, com autorestart e logs diagnosticos uteis.

---

## Bug 5 - Analytics nao processavam sem ROI inicial

### Causa-raiz

Frame grabber dependia exclusivamente de `roi.updated` para iniciar captura; cameras sem ROI nao entravam no loop de captura.

### Correcao aplicada

- Frame grabber passou a consumir duas filas:
  - `roi.updated` (atualiza ROIs)
  - `camera.activated` (inicia captura mesmo sem ROI)
- Cenario sem ROI:
  - captura continua para manter thumbnails
  - publicacao em `ai.frame`/`ai.frame.lpr` ocorre apenas quando houver ROI
- Django passou a publicar `camera.activated` no `post_save` de camera RTSP.
- Comando de bootstrap `start_recordings` tambem publica `camera.activated` para sincronizar restart.

### Arquivos alterados

- `backend-fastapi/workers/frame_grabber/worker/service.py`
- `backend-django/apps/cameras/signals.py`
- `backend-django/apps/cameras/management/commands/start_recordings.py`

### Resultado esperado

- Camera recem-criada recebe thumbnail mesmo antes de ROI.
- Ao adicionar ROI depois, analytics passam a processar sem reinicio manual.

---

## Checklist de Validacao Pos-Deploy

Executar em `infra/`:

```bash
docker compose ps
docker compose logs -f frame-grabber
docker compose logs -f ai-worker
docker compose logs -f recorder-worker
docker compose exec redis redis-cli keys "thumbnail:*"
docker compose exec django ls /app/storage/snapshots/
```

Validacoes funcionais:

1. `Cameras` mostra thumbnail sem tela preta.
2. `Deteccoes` mostra imagem real no campo thumbnail.
3. Mesma placa nao repete continuamente em janela curta (dedup ativo).
4. `Gravacoes` mostra segmentos disponiveis na timeline.
5. Camera sem ROI ainda recebe thumbnail; ao criar ROI, eventos passam a aparecer.

---

## Observacoes Operacionais

- O modulo de utilitarios de placa centraliza a regra de normalizacao/validacao para evitar divergencias futuras.
- O canal `camera.activated` tornou o bootstrap de captura independente do ciclo de edicao de ROI.
- O recorder agora tem comportamento mais resiliente para operacao 24/7.
