# VMS — Plano de Correção Completa

## Diagnóstico: Causas-Raiz de Todos os Problemas

### Bug 1 — Capa da câmera não exibe (thumbnail)
**Causa:** O `frame_grabber` salva o thumbnail no Redis com a chave `:1:thumbnail:{camera_id}`, mas o [views.py](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/roi/views.py) lê via Django `cache.get(f'thumbnail:{camera_id}')`. O prefixo `:1:` é adicionado automaticamente pelo framework de cache do Django (KEY_PREFIX:VERSION:key). **O grabber escreve diretamente no Redis sem o prefixo do Django**, então o Django nunca encontra o cache → cai no fallback FFmpeg → falha porque o stream HLS pode não estar disponível imediatamente.

**Solução:** Fazer o `frame_grabber` usar a chave sem prefixo manual, ou ainda mais simples: mover a escrita do thumbnail para usar a API de cache do Django (via endpoint HTTP interno) ou corrigir a chave para que coincida.

### Bug 2 — Foto da placa não exibe nos eventos
**Causa:** O `snapshot_path` é salvo como string relativa (ex: `snapshots/tenant_id/lpr/202503`), mas o serializer monta `/media/snapshots/...`. Em ambiente Docker, o volume `../storage:/app/storage` mapeia `storage/media` → `/app/storage/media`. O Nginx precisa ter o alias `/media/ → /app/storage/`. **Verificar se o Django tem `MEDIA_ROOT=/app/storage` e se o Nginx roteia `/media/` corretamente para o path do storage.**

### Bug 3 — Placas repetidas / duplicadas
**Causa:** O OCR (EasyOCR/Tesseract) lê a mesma placa com variações: `HI01557`, `HIO1557`, `HIQ1557`, `HTQZ557` etc. O dedup usa a string exata como chave. Com TTL de 30s, entre cada leitura OCR variante muda, gerando novos eventos.

**Solução:** Implementar normalização de placa + similaridade Levenshtein antes de gerar o dedup key. Aumentar o TTL para 120s. Usar formato de placa BR (AAA-0000 ou AAA-0A00 Mercosul) para validação por regex antes de salvar.

### Bug 4 — Gravação não está salvando
**Causa:** O `recorder_worker.consume_queue()` usa `async with start_queue.iterator() as queue_iter: async for message...` em modo bloqueante e **nunca chega à segunda fila `recording.stop`** — é dead code. Além disso, o [start_recordings.py](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/management/commands/start_recordings.py) só publica a mensagem se a câmera foi criada **com [stream_url](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/views.py#152-169) não vazio**, mas o [signals.py](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/signals.py) só dispara `recording.start` em [post_save](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/signals.py#76-86) de câmera nova — **câmera já existente na base não tem gravação iniciada**. O `mediamtx-sync` container executa o `start_recordings` no startup, mas o recorder-worker precisa estar pronto.

### Bug 5 — Analytics não funcionam (detecções)
**Causa identificada na análise:**
- O frame_grabber só manda frames para a fila quando há ROIs cadastrados (`general_rois` e `lpr_rois`). **Se não houver ROI configurado, nenhum frame é enviado.**
- O ai-worker consome a fila `ai.frame` mas o [service.py](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/recorder/worker/service.py) linha 215 tem `pass` para [lpr](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#108-118) no handler geral (correto, LPR vai para `ai.frame.lpr`), mas o [_handle_lpr()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#556-572) existe mas nunca é chamado na fila geral — OK.
- O maior problema: **para analytics funcionarem, é obrigatório ter ROIs configurados na câmera via frontend (ROI Editor)**. Sem ROI, zero frames são processados.
- O LPR worker (lpr_service.py) existe separado do ai_worker — ambos precisam estar rodando.

---

## Proposed Changes

### Componente 1 — Frame Grabber: Thumbnail (Redis key fix)

#### [MODIFY] [service.py](file:///d:/VMS%20(White%20Label)/backend-fastapi/workers/frame_grabber/worker/service.py)

- **Linha 115**: Mudar a chave do Redis de `:1:thumbnail:{camera_id}` para `thumbnail:{camera_id}` (remover o prefixo `:1:` que é interno do Django).
- Alternativamente: enviar thumbnail via HTTP internal endpoint no Django `PATCH /api/v1/internal/cameras/{id}/thumbnail/` para o Django salvar via `cache.set(f'thumbnail:{camera_id}', ...)`.

> A abordagem mais simples: corrigir a chave para `thumbnail:{camera_id}` sem o prefixo `:1:`. 

---

### Componente 2 — LPR: Dedup robusto + normalização de placa

#### [MODIFY] [lpr_service.py](file:///d:/VMS%20(White%20Label)/backend-fastapi/workers/ai_worker/worker/lpr_service.py)

- Adicionar função `normalize_plate(text)` que: remove espaços, converte para maiúsculas, remove caracteres não alfanuméricos.
- Adicionar função `is_valid_br_plate(text)` com regex para placas antigas `[A-Z]{3}[0-9]{4}` e Mercosul `[A-Z]{3}[0-9][A-Z][0-9]{2}`.
- Adicionar dedup difuso: salvar no Redis as últimas N placas por câmera e comparar distância Levenshtein (via `rapidfuzz` já disponível ou `difflib.SequenceMatcher`). Se similaridade > 80%, considerar duplicata.
- Aumentar `DEDUP_TTL_SECONDS` de 30 para **120 segundos**.
- Salvar a placa normalizada (somente válidas por regex); descartar leituras inválidas.

#### [MODIFY] [analyzers/lpr.py](file:///d:/VMS%20(White%20Label)/backend-fastapi/workers/ai_worker/worker/analyzers/lpr.py)

- Mesma normalização e validação de placa BR aplicada aqui também.

---

### Componente 3 — Gravação: Corrigir recorder_worker

#### [MODIFY] [recorder/worker/service.py](file:///d:/VMS%20(White%20Label)/backend-fastapi/workers/recorder/worker/service.py)

- Corrigir [consume_queue()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/recorder/worker/service.py#114-140) para processar **ambas as filas concorrentemente** em vez de sequencialmente. Implementar loop com duas tasks asyncio separadas.
- Adicionar startup: ao iniciar, consumir `recording.start` para câmeras que já existam (publicar um evento de sincronia ao subir).

#### [MODIFY] [cameras/signals.py](file:///d:/VMS%20(White%20Label)/backend-django/apps/cameras/signals.py)

- Disparar `recording.start` tanto em `created=True` quanto em câmera já existente quando `ia_enabled` muda para True ou quando [stream_url](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/views.py#152-169) é atualizada.
- Adicionar `recording.start` trigger no [post_save](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/signals.py#76-86) para câmeras já existentes (não só `created`).

---

### Componente 4 — Snapshots: Servir imagens de eventos no frontend

#### [MODIFY] [detections/serializers.py](file:///d:/VMS%20(White%20Label)/backend-django/apps/detections/serializers.py)

- Verificar e corrigir [get_thumbnail_url()](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/serializers.py#52-57): O `snapshot_path` é salvo pelo worker com separadores do OS (possível `\` no Windows). Normalizar para `/media/{path normalizado com forward slashes}`.

#### [MODIFY] [infra/nginx.conf](file:///d:/VMS%20(White%20Label)/infra/nginx.conf)

- Verificar/adicionar rota `/media/` → `/app/storage/` para servir os snapshots das detecções.

---

### Componente 5 — Analytics: Garantir que todos os 12 funcionem

> [!IMPORTANT]
> Todos os analytics já têm implementação backend completa em [service.py](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/recorder/worker/service.py). O pré-requisito é que a câmera tenha **ROIs configurados no frontend** via Analíticos → Nova Área de Análise. Sem ROI, nenhum frame é processado.

**Mapeamento Frontend → Backend (todos já implementados):**

| Frontend | `ia_type` no ROI | Handler no [service.py](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/recorder/worker/service.py) |
|---|---|---|
| Tráfego Humano | `human_traffic` | [_handle_line()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#321-358) |
| Tráfego Veicular | `vehicle_traffic` | [_handle_line()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#321-358) |
| Detecção de Multidão | [crowd](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#263-286) | [_handle_crowd()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#263-286) |
| Intrusão | [intrusion](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#287-320) | [_handle_intrusion()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#287-320) |
| Objeto Detectado | `object_detection` | [_handle_objects()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#229-262) |
| Perambulação | [loitering](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#359-393) | [_handle_loitering()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#359-393) |
| Objeto Abandonado | `abandoned_object` | [_handle_abandoned()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#394-434) |
| Detecção de Fila | [queue](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/recorder/worker/service.py#114-140) | [_handle_queue()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#435-482) |
| Reconhecimento de Placa | [lpr](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#108-118) | LPR Worker dedicado |
| Reconhecimento Facial | [facial](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#98-105) | [_handle_facial()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#537-555) |
| Cruzamento de Linha | `line_crossing` | [_handle_line()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#321-358) |
| Mapa de Calor | [heatmap](file:///d:/VMS%20%28White%20Label%29/backend-django/apps/cameras/views.py#183-200) | [_handle_heatmap()](file:///d:/VMS%20%28White%20Label%29/backend-fastapi/workers/ai_worker/worker/service.py#483-502) |

**Adicionar ao frame_grabber:** Modo de captura contínuo mesmo sem ROIs (para câmeras com `ia_enabled=True`), enviando frames para análise geral mínima (ao menos para heatmap e traffic sempre ativo).

---

## Verificação

### Testes Automatizados

```bash
# Verificar se containers estão rodando
cd infra && docker compose ps

# Verificar logs do frame-grabber (deve mostrar frames sendo capturados)
docker compose logs -f frame-grabber

# Verificar logs do ai-worker (deve mostrar frames sendo processados)
docker compose logs -f ai-worker

# Verificar logs do recorder-worker
docker compose logs -f recorder-worker

# Testar Redis thumbnail key
docker compose exec redis redis-cli keys "thumbnail:*"

# Testar se snapshot files estão sendo criados
docker compose exec django ls /app/storage/snapshots/
```

### Verificação Manual

1. **Thumbnail câmera**: Acessar Câmeras no frontend → câmera deve mostrar imagem ao vivo (não tela preta).
2. **Eventos com foto**: Acessar Detecções → clicar em evento LPR → campo "Thumbnail" deve mostrar imagem real, não texto `Thumbnail`.
3. **LPR sem duplicatas**: Observar lista de eventos por 2 minutos — mesma placa física não deve aparecer mais de 1×/120s.
4. **Gravações**: Acessar Gravações → selecionar câmera e data → timeline deve mostrar segmentos verdes com vídeo disponível.
5. **Analytics**: Criar ROI do tipo Tráfego Veicular na câmera → aguardar 30s → eventos de `vehicle_traffic` devem aparecer na aba Detecções.
6. **Mapa de Calor**: Criar ROI tipo Mapa de Calor → aguardar ~5 min → acessar `GET /api/v1/cameras/{id}/heatmap/` deve retornar imagem JPEG colorida.
