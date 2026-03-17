# VMS Analytics Plugins

> Como criar, configurar e testar plugins de analytics no VMS.
> Atualizado: 2026-03-16 — arquitetura analytics_service com inversão de dependência.

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura — Inversão de Dependência](#2-arquitetura--inversão-de-dependência)
3. [Interface do Plugin](#3-interface-do-plugin)
4. [Criando um Novo Plugin](#4-criando-um-novo-plugin)
5. [Exemplo Completo — people_count](#5-exemplo-completo--people_count)
6. [Como o Django Recebe os Resultados](#6-como-o-django-recebe-os-resultados)
7. [Configurando ROIs](#7-configurando-rois)
8. [Testando um Plugin](#8-testando-um-plugin)
9. [Executando o Serviço](#9-executando-o-serviço)
10. [Plugins Disponíveis](#10-plugins-disponíveis)

---

## 1. Visão Geral

O `analytics_service` é um serviço FastAPI independente que converte câmeras bullet comuns em câmeras inteligentes, processando frames RTSP no servidor. É o **Fluxo B** da arquitetura:

```
Câmera (RTSP) → MediaMTX → analytics_service captura frame
    → plugin.process_frame(frame, metadata, rois)
    → POST /api/v1/analytics/ingest/ (Django)
    → DwellEvent no banco
    → SSE para o frontend
```

**Princípio central:** o VMS Platform (Django) **não sabe** como os plugins funcionam internamente. Ele apenas expõe ROIs via REST e recebe resultados via endpoint de ingest genérico. Adicionar um novo analítico não requer modificar o VMS.

---

## 2. Arquitetura — Inversão de Dependência

```
analytics_service/ (independente)
        │
        ├── GET  /api/v1/analytics/internal/rois/?camera={id}  ← lê ROIs
        └── POST /api/v1/analytics/ingest/                      ← escreve resultados

VMS Platform (Django) — NÃO conhece a implementação interna
        │
        ├── Expõe ROIs via REST (autenticado por API key interna)
        └── Recebe eventos via ingest → cria DwellEvent, IntrusionEvent, etc.
```

### 2.1 Pipeline completo

```
1. Startup: analytics_service inicia
   → plugin_loader.py escaneia analytics/ → instancia e inicializa cada plugin
   → mediamtx_connector.py conecta em http://mediamtx:9997/v3/paths/list
   → descobre streams no padrão tenant-{x}/cam-{y} → extrai camera_id + tenant_id
   → lança asyncio task de captura por stream

2. Por câmera (a cada 1/FPS segundos):
   → captura frame via cv2.VideoCapture(rtsp_url) em thread executor
   → redis_bus.publish_frame(plugin.name, frame, metadata) para cada plugin ativo

3. Workers (WORKERS_PER_PLUGIN por plugin):
   → redis_bus.consume_frame(plugin.name) → bloqueia até ter frame
   → django_client.get_rois(camera_id) → busca ROIs (cache 30s)
   → plugin.process_frame(frame, metadata, rois) → retorna AnalyticsResult[]
   → para cada resultado: django_client.post_ingest(result)

4. Django recebe ingest:
   → valida API key
   → handlers.dispatch_ingest(plugin, camera_id, tenant_id, payload)
   → handler específico cria/atualiza evento no banco
   → publica Redis pubsub vms:realtime → SSE para o frontend
```

### 2.2 Estrutura de arquivos

```
analytics_service/
├── Dockerfile
├── pyproject.toml
├── main.py                     ← FastAPI + lifespan (start/stop orchestrator)
├── config/
│   └── settings.py             ← env vars: MEDIAMTX_URL, REDIS_URL, FPS, ...
├── core/
│   ├── mediamtx_connector.py   ← descobre streams /v3/paths/list
│   ├── orchestrator.py         ← asyncio tasks de captura + workers
│   ├── redis_bus.py            ← listas Redis "analytics:frames:{plugin}"
│   ├── plugin_loader.py        ← autodiscovery em analytics/*/plugin.py
│   └── django_client.py        ← GET rois (cache 30s) + POST ingest
└── analytics/
    ├── base.py                 ← AnalyticsPlugin ABC (interface)
    └── vehicle_dwell/
        └── plugin.py           ← VehicleDwellPlugin (YOLOv8 + ByteTrack)
```

---

## 3. Interface do Plugin

Todos os plugins herdam `AnalyticsPlugin` de `analytics/base.py`:

```python
from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig

class MeuPlugin(AnalyticsPlugin):
    name = "meu_plugin"      # único, snake_case — bate com field "plugin" no ingest
    version = "1.0.0"
    roi_type = "meu_plugin"  # filtra quais ROIs este plugin recebe

    async def initialize(self, config: dict) -> None:
        """Carrega modelo, configura recursos. Chamado uma vez no startup."""
        ...

    async def process_frame(
        self,
        frame: np.ndarray,         # BGR, shape (H, W, 3)
        metadata: FrameMetadata,   # camera_id, tenant_id, timestamp, stream_url
        rois: list[ROIConfig],     # ROIs já filtradas por roi_type
    ) -> list[AnalyticsResult]:
        """Processa frame e retorna resultados. Nunca lança exceção."""
        ...

    async def shutdown(self) -> None:
        """Libera recursos. Chamado no shutdown do serviço."""
        ...
```

### 3.1 Tipos de dados

```python
@dataclass
class FrameMetadata:
    camera_id: int
    tenant_id: int
    timestamp: datetime
    stream_url: str

@dataclass
class ROIConfig:
    id: int
    name: str
    ia_type: str
    polygon_points: list[list[float]]   # [[x, y], ...] normalizados 0.0–1.0
    config: dict                        # parâmetros específicos da ROI

@dataclass
class AnalyticsResult:
    plugin: str          # "meu_plugin" — deve bater com name
    camera_id: int
    tenant_id: int
    event_type: str      # "analytics.meu_plugin.evento"
    payload: dict        # campos específicos do plugin
```

### 3.2 Regras do contrato

1. `name` deve ser único entre todos os plugins — use `snake_case`
2. `roi_type` define qual ia_type de ROI o plugin consome. O orchestrator filtra automaticamente.
3. `process_frame` **nunca** lança exceção — capture internamente, logue e retorne `[]`
4. Carregue modelos pesados em `initialize()`, nunca dentro de `process_frame` (lento demais)
5. O plugin recebe apenas ROIs do `roi_type` que declarou — não precisa filtrar novamente
6. `AnalyticsResult.plugin` deve ser idêntico ao `name` do plugin

---

## 4. Criando um Novo Plugin

### Passo 1 — Criar o arquivo do plugin

```
analytics_service/analytics/
  meu_plugin/
    __init__.py   ← vazio
    plugin.py     ← implementação (obrigatório)
```

O `plugin_loader.py` descobre automaticamente qualquer subpasta com `plugin.py` contendo uma classe concreta que herda `AnalyticsPlugin`.

### Passo 2 — Implementar o plugin

```python
# analytics_service/analytics/meu_plugin/plugin.py
import logging
from typing import Any
import numpy as np
from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig

logger = logging.getLogger(__name__)

class MeuPlugin(AnalyticsPlugin):
    name = "meu_plugin"
    version = "1.0.0"
    roi_type = "meu_plugin"

    async def initialize(self, config: dict[str, Any]) -> None:
        # Carrega modelo, conecta recursos externos, etc.
        logger.info("MeuPlugin inicializado")

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        if not rois:
            return []
        try:
            return self._processar(frame, metadata, rois)
        except Exception:
            logger.exception("MeuPlugin: erro inesperado")
            return []

    def _processar(self, frame, metadata, rois) -> list[AnalyticsResult]:
        # Lógica de detecção ...
        return [
            AnalyticsResult(
                plugin=self.name,
                camera_id=metadata.camera_id,
                tenant_id=metadata.tenant_id,
                event_type="analytics.meu_plugin.detectado",
                payload={"campo": "valor"},
            )
        ]

    async def shutdown(self) -> None:
        pass
```

### Passo 3 — Adicionar handler no Django

Edite `core/apps/analytics/handlers.py`:

```python
def handle_meu_plugin(payload: dict, camera_id: int, tenant_id: int) -> None:
    """Persiste resultado do meu_plugin no banco."""
    # Criar o model necessário, publicar SSE, etc.
    from shared.pubsub import publish
    publish("vms:realtime", {
        "type": "meu_plugin_evento",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        **payload,
    })

# Registrar no mapa de handlers
PLUGIN_HANDLERS: dict = {
    "vehicle_dwell": handle_vehicle_dwell,
    "meu_plugin": handle_meu_plugin,   # ← adicionar aqui
}
```

### Passo 4 — (Opcional) Criar Model Django

Se o plugin precisar persistir dados:

```bash
# Criar migration
docker compose exec django python manage.py makemigrations analytics
docker compose exec django python manage.py migrate
```

### Passo 5 — Reiniciar o serviço

```bash
# O volume mount faz hot-swap de plugins sem rebuild da imagem
docker compose restart analytics_service
```

Confirme que o plugin foi carregado nos logs:

```
analytics_service  | Plugin descoberto: MeuPlugin
analytics_service  | Plugin 'meu_plugin' v1.0.0 carregado com sucesso
```

---

## 5. Exemplo Completo — people_count

Plugin que conta pessoas em ROIs usando YOLOv8n. Não requer tracking (contagem instantânea).

```python
# analytics_service/analytics/people_count/plugin.py
import asyncio
import logging
from typing import Any

import numpy as np

from analytics.base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig

logger = logging.getLogger(__name__)

_PERSON_CLASS_ID = 0


class PeopleCountPlugin(AnalyticsPlugin):
    name = "people_count"
    version = "1.0.0"
    roi_type = "human_traffic"  # ia_type correspondente no modelo RegionOfInterest

    def __init__(self) -> None:
        self._model = None

    async def initialize(self, config: dict[str, Any]) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model, config)

    def _load_model(self, config: dict[str, Any]) -> None:
        from ultralytics import YOLO
        self._model = YOLO(config.get("model", "yolov8n.pt"))
        logger.info("PeopleCountPlugin: modelo carregado")

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        if not rois:
            return []
        try:
            loop = asyncio.get_event_loop()
            counts = await loop.run_in_executor(None, self._count, frame, rois)
            return [
                AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="analytics.people.count",
                    payload={
                        "roi_id": roi_id,
                        "count": count,
                        "timestamp": metadata.timestamp.isoformat(),
                    },
                )
                for roi_id, count in counts.items()
                if count > 0
            ]
        except Exception:
            logger.exception("PeopleCountPlugin: erro")
            return []

    def _count(self, frame: np.ndarray, rois: list[ROIConfig]) -> dict[int, int]:
        import cv2

        h, w = frame.shape[:2]
        results = self._model(frame, verbose=False)[0]

        # Centroides de todas as pessoas detectadas
        centroids = []
        for box in results.boxes:
            if int(box.cls) != _PERSON_CLASS_ID:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            centroids.append(((x1 + x2) / 2 / w, (y1 + y2) / 2 / h))

        # Conta por ROI
        counts: dict[int, int] = {}
        for roi in rois:
            if len(roi.polygon_points) < 3:
                continue
            poly = np.array(
                [[p[0] * w, p[1] * h] for p in roi.polygon_points], dtype=np.float32
            )
            counts[roi.id] = sum(
                1 for cx, cy in centroids
                if cv2.pointPolygonTest(poly, (cx * w, cy * h), False) >= 0
            )
        return counts

    async def shutdown(self) -> None:
        logger.info("PeopleCountPlugin encerrado")
```

**Handler no Django** (`handlers.py`):

```python
def handle_people_count(payload: dict, camera_id: int, tenant_id: int) -> None:
    from shared.pubsub import publish
    publish("vms:realtime", {
        "type": "people_count",
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "roi_id": payload.get("roi_id"),
        "count": payload.get("count"),
        "timestamp": payload.get("timestamp"),
    })
```

---

## 6. Como o Django Recebe os Resultados

O analytics_service chama `POST /api/v1/analytics/ingest/` com autenticação por API key interna.

### 6.1 Body do ingest

```json
{
  "plugin":     "vehicle_dwell",
  "camera_id":  5,
  "tenant_id":  1,
  "event_type": "analytics.vehicle.dwell",
  "payload": {
    "track_id":      42,
    "roi_id":         3,
    "entered_at":    "2026-03-16T10:00:00+00:00",
    "exited_at":     "2026-03-16T10:02:30+00:00",
    "dwell_seconds": 150,
    "frame_path":    "/recordings/snapshots/cam5_track42.jpg",
    "is_valid":      true
  }
}
```

### 6.2 Fluxo interno do Django

```
POST /api/v1/analytics/ingest/
        │
        ▼
_require_analytics_key (valida Authorization: Analytics <key>)
        │
        ▼
dispatch_ingest(plugin, camera_id, tenant_id, payload)
        │
        ├── "vehicle_dwell" → handle_vehicle_dwell() → cria/atualiza DwellEvent
        ├── "people_count"  → handle_people_count()  → publica SSE
        └── plugin desconhecido → 422
```

### 6.3 Adicionar suporte a novo plugin no Django

1. Criar função `handle_<plugin_name>` em `handlers.py`
2. Registrar no dict `PLUGIN_HANDLERS`
3. (Opcional) criar model + migration se precisar persistir dados

**Zero mudança nas views, urls ou settings.**

---

## 7. Configurando ROIs

ROIs são desenhadas pelo operador no frontend e armazenadas no Django. O analytics_service as consome via `GET /api/v1/analytics/internal/rois/?camera={id}`.

### 7.1 Criar ROI via API

```bash
curl -s -X POST http://localhost/api/v1/analytics/rois/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "camera": 5,
    "name": "Vaga VIP",
    "ia_type": "vehicle_dwell",
    "polygon_points": [
      [0.1, 0.2],
      [0.4, 0.2],
      [0.4, 0.8],
      [0.1, 0.8]
    ],
    "config": {
      "min_dwell_seconds": 60,
      "max_dwell_seconds": 240
    }
  }' | jq .
```

### 7.2 Mapa ia_type → plugin

| ia_type (ROI) | Plugin que consome | Evento gerado |
|--------------|-------------------|---------------|
| `vehicle_dwell` | `vehicle_dwell` | `analytics.vehicle.dwell` |
| `intrusion` | `intrusion_detection` | `analytics.intrusion.detected` |
| `human_traffic` | `people_count` | `analytics.people.count` |
| `vehicle_traffic` | `vehicle_count` | `analytics.vehicle.count` |
| `lpr` | `lpr_parking` | `analytics.lpr.detection` |
| `facial` | `face_recognition` | `analytics.face.recognized` |

O campo `roi_type` do plugin define qual `ia_type` ele consome. O orchestrator filtra automaticamente antes de chamar `process_frame`.

---

## 8. Testando um Plugin

### 8.1 Teste unitário (sem Docker, sem câmera)

```python
# analytics_service/analytics/vehicle_dwell/tests/test_plugin.py
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from analytics.base import FrameMetadata, ROIConfig
from analytics.vehicle_dwell.plugin import VehicleDwellPlugin, _point_in_polygon


@pytest.fixture
def plugin():
    p = VehicleDwellPlugin()
    p._model = MagicMock()
    return p


@pytest.fixture
def metadata():
    return FrameMetadata(
        camera_id=1,
        tenant_id=1,
        timestamp=datetime.now(tz=timezone.utc),
        stream_url="rtsp://localhost:8554/tenant-1/cam-1",
    )


@pytest.fixture
def roi():
    return ROIConfig(
        id=1,
        name="Vaga 1",
        ia_type="vehicle_dwell",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    )


def test_sem_roi_retorna_vazio(plugin, metadata):
    result = asyncio.run(plugin.process_frame(np.zeros((100, 100, 3), dtype=np.uint8), metadata, []))
    assert result == []


def test_point_in_polygon_dentro():
    poly = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    assert _point_in_polygon(0.5, 0.5, poly, 640, 480) is True


def test_point_in_polygon_fora():
    poly = [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]]
    assert _point_in_polygon(0.8, 0.8, poly, 640, 480) is False


def test_excecao_nao_propaga(plugin, metadata, roi):
    plugin._model = MagicMock(side_effect=RuntimeError("GPU OOM"))
    result = asyncio.run(
        plugin.process_frame(np.zeros((100, 100, 3), dtype=np.uint8), metadata, [roi])
    )
    assert result == []
```

### 8.2 Rodar testes

```bash
# Dentro do container ou com deps instaladas
cd analytics_service
pytest analytics/vehicle_dwell/tests/ -v

# Todos os plugins
pytest analytics/ -v --ignore=analytics/__init__.py
```

### 8.3 Teste de integração (requer stack rodando)

```bash
# 1. Criar ROI para uma câmera
TOKEN=$(curl -s -X POST http://localhost/api/v1/auth/token/ \
  -d '{"username":"admin","password":"senha"}' | jq -r .access)

curl -s -X POST http://localhost/api/v1/analytics/rois/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "camera": 1,
    "name": "Teste",
    "ia_type": "vehicle_dwell",
    "polygon_points": [[0,0],[1,0],[1,1],[0,1]]
  }'

# 2. Verificar health do serviço
curl -s http://localhost:8002/health | jq .

# 3. Aguardar evento (câmera com veículo estacionado ~60s)
curl -s "http://localhost/api/v1/analytics/dwell-events/?is_valid=true" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

## 9. Executando o Serviço

### 9.1 Variáveis de ambiente obrigatórias

| Variável | Exemplo | Descrição |
|----------|---------|-----------|
| `MEDIAMTX_URL` | `http://mediamtx:9997` | API interna do MediaMTX |
| `MEDIAMTX_RTSP_BASE_URL` | `rtsp://mediamtx:8554` | Base dos streams RTSP |
| `DJANGO_INTERNAL_URL` | `http://django:8000` | URL interna do Django |
| `ANALYTICS_SERVICE_API_KEY` | `sua-chave-secreta` | Deve bater com o Django |
| `REDIS_URL` | `redis://redis:6379/0` | Barramento de frames |
| `FPS` | `2` | Frames por segundo por câmera |
| `WORKERS_PER_PLUGIN` | `2` | Workers paralelos por plugin |
| `SNAPSHOTS_PATH` | `/recordings/snapshots` | Onde salvar snapshots |

### 9.2 Subir apenas o serviço

```bash
docker compose up analytics_service --build
```

### 9.3 Ver logs

```bash
docker compose logs analytics_service -f
```

Saída esperada na inicialização:

```
INFO  core.plugin_loader: Plugin descoberto: VehicleDwellPlugin
INFO  core.plugin_loader: Plugin 'vehicle_dwell' v1.0.0 carregado com sucesso
INFO  core.mediamtx_connector: 3 streams ativos encontrados no MediaMTX
INFO  core.orchestrator: Orchestrator em execução: 3 streams, 1 plugins, 8 tasks
INFO  main: analytics_service pronto: 1 plugin(s) carregado(s)
```

### 9.4 Health check

```bash
curl -s http://localhost:8002/health | jq .
```

```json
{
  "status": "ok",
  "running": true,
  "active_streams": 3,
  "plugins": ["vehicle_dwell"],
  "queue_sizes": {"vehicle_dwell": 0}
}
```

### 9.5 Hot-swap de plugins (sem rebuild)

O volume `./analytics_service/analytics:/app/analytics` permite adicionar plugins em runtime:

```bash
# Criar novo plugin em disco
mkdir -p analytics_service/analytics/people_count
# ... criar plugin.py ...

# Reiniciar o serviço (não precisa rebuild da imagem)
docker compose restart analytics_service
```

---

## 10. Plugins Disponíveis

| Plugin | Status | ia_type ROI | Modelo | Evento |
|--------|--------|------------|--------|--------|
| `vehicle_dwell` | ✅ implementado | `vehicle_dwell` | YOLOv8n + ByteTrack | `analytics.vehicle.dwell` |
| `intrusion_detection` | stub | `intrusion` | YOLOv8n + polígono | `analytics.intrusion.detected` |
| `people_count` | stub | `human_traffic` | YOLOv8n (classe: person) | `analytics.people.count` |
| `vehicle_count` | stub | `vehicle_traffic` | YOLOv8n (car, truck, motorcycle) | `analytics.vehicle.count` |
| `lpr_parking` | stub | `lpr` | YOLOv8 + PaddleOCR | `analytics.lpr.detection` |
| `weapon_detection` | stub ⚠️ | `object_detected` | YOLOv8 fine-tuned | `analytics.weapon.detected` |
| `face_recognition` | stub ⚠️ | `facial` | InsightFace / ONNX | `analytics.face.recognized` |

> **⚠️ weapon_detection:** Requer fine-tuning com dataset específico. Deploy em beta com disclaimer explícito. Alta taxa de falso positivo sem dataset de qualidade.
>
> **⚠️ face_recognition:** Armazena biometria (LGPD). Requer campo `facial_recognition_enabled = True` por tenant com aceite de termo. Nunca habilitado por default. Embeddings deletáveis por `DELETE /api/v1/faces/{id}/`.
