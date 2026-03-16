# VMS Analytics Plugins

> Como criar, configurar e testar plugins de analytics no VMS.

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Classe Base](#2-classe-base)
3. [Criando um Plugin](#3-criando-um-plugin)
4. [Exemplo Completo — people_count](#4-exemplo-completo--people_count)
5. [Publicando Eventos no Bus](#5-publicando-eventos-no-bus)
6. [Worker Analytics](#6-worker-analytics)
7. [Testando um Plugin](#7-testando-um-plugin)
8. [Plugins Disponíveis](#8-plugins-disponíveis)

---

## 1. Visão Geral

O sistema de analytics converte câmeras bullet comuns em câmeras inteligentes processando frames no servidor. É o **Fluxo B** da arquitetura (câmeras burras → stream RTSP → captura de frame → plugin → evento).

```
Camera (RTSP) → MediaMTX → captura frame → Celery task → Plugin → Event Bus
```

**Características:**
- Cada plugin é um módulo Python em `plugins/<nome>/plugin.py`
- Descoberta automática por convenção de estrutura de pastas
- Todos os plugins são `async` — a task Celery usa `asyncio.run()` como bridge
- Plugins rodam no worker `analytics` (separado do worker padrão)
- Resultados são publicados no RabbitMQ exchange `vms_events`

---

## 2. Classe Base

Todos os plugins herdam de `AnalyticsPlugin` (`plugins/base.py`):

```python
class AnalyticsPlugin(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome único do plugin. Usado como chave no loader e roteamento de eventos."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Versão semântica, ex: "1.0.0"."""

    @abstractmethod
    async def process_frame(
        self,
        frame: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Processa um frame e retorna resultado.

        Args:
            frame:    Bytes do frame JPEG ou PNG.
            metadata: {
                "camera_id": int,
                "tenant_id": int,
                "timestamp": str (ISO 8601),
                "stream_path": str,
            }

        Returns:
            Dict com resultado da detecção, ou None se nada detectado.
        """

    def on_load(self) -> None:
        """Chamado uma vez ao carregar o plugin. Use para inicializar modelos."""

    def on_unload(self) -> None:
        """Chamado ao descarregar. Use para liberar recursos."""
```

### Convenções de retorno

`process_frame` deve retornar `None` quando não há detecção (sem ruído no event bus) ou um dict com os dados detectados. Estrutura recomendada:

```python
return {
    "plugin": self.name,
    "version": self.version,
    "camera_id": metadata["camera_id"],
    "tenant_id": metadata["tenant_id"],
    "timestamp": metadata["timestamp"],
    # campos específicos do plugin:
    "count": 3,
    "detections": [...],
}
```

---

## 3. Criando um Plugin

### 3.1 Estrutura de pastas

```
plugins/
  meu_plugin/
    __init__.py      ← arquivo vazio
    plugin.py        ← lógica do plugin (obrigatório)
    tests/
      __init__.py
      test_plugin.py
```

O loader (`plugins/__init__.py`) descobre automaticamente qualquer subpasta que contenha um `plugin.py` com uma classe que herda `AnalyticsPlugin`.

### 3.2 Regras

1. `name` deve ser único entre todos os plugins — use `snake_case`
2. `process_frame` **nunca** lança exceção — capture internamente e retorne `None`
3. Carregue modelos de IA em `on_load()`, não dentro de `process_frame` (lento)
4. Plugin de IA pesada? Declare as dependências extras no Dockerfile do worker analytics
5. Adicione o routing key do evento novo em `CLAUDE.md` seção 5

### 3.3 Loader automático

```python
from plugins import discover_plugins

plugins = discover_plugins()
# {"people_count": <PeopleCountPlugin>, "intrusion_detection": <IntrusionDetectionPlugin>, ...}
plugin = plugins["people_count"]
result = await plugin.process_frame(frame_bytes, metadata)
```

---

## 4. Exemplo Completo — people_count

Implementação completa do plugin de contagem de pessoas usando YOLOv8n.

### 4.1 `plugins/people_count/__init__.py`

```python
# arquivo vazio
```

### 4.2 `plugins/people_count/plugin.py`

```python
"""Plugin de contagem de pessoas via YOLOv8."""
from __future__ import annotations

import io
import logging
from typing import Any

import numpy as np
from PIL import Image

from plugins.base import AnalyticsPlugin

logger = logging.getLogger(__name__)

# YOLOv8 class index for "person"
PERSON_CLASS_ID = 0


class PeopleCountPlugin(AnalyticsPlugin):
    """Conta pessoas em um frame usando YOLOv8n."""

    _model = None  # carregado em on_load()

    @property
    def name(self) -> str:
        return "people_count"

    @property
    def version(self) -> str:
        return "1.0.0"

    def on_load(self) -> None:
        """Carrega o modelo YOLOv8n uma única vez."""
        from ultralytics import YOLO

        self._model = YOLO("yolov8n.pt")
        logger.info("PeopleCountPlugin: modelo carregado")

    async def process_frame(
        self,
        frame: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Conta pessoas no frame.

        Returns:
            {"count": int, "detections": list[dict]} ou None se 0 pessoas.
        """
        try:
            return self._detect(frame, metadata)
        except Exception:
            logger.exception("PeopleCountPlugin: erro ao processar frame")
            return None

    def _detect(
        self,
        frame: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        image = Image.open(io.BytesIO(frame)).convert("RGB")
        img_array = np.array(image)

        results = self._model(img_array, verbose=False)[0]

        detections = []
        for box in results.boxes:
            if int(box.cls) != PERSON_CLASS_ID:
                continue
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append({
                "bbox": [round(x1), round(y1), round(x2), round(y2)],
                "confidence": round(float(box.conf), 3),
            })

        if not detections:
            return None

        return {
            "plugin": self.name,
            "version": self.version,
            "camera_id": metadata["camera_id"],
            "tenant_id": metadata["tenant_id"],
            "timestamp": metadata["timestamp"],
            "count": len(detections),
            "detections": detections,
        }
```

### 4.3 Como funciona

1. `on_load()` é chamado pelo loader e carrega `yolov8n.pt` na memória (baixa automaticamente na primeira execução)
2. `process_frame()` recebe o frame JPEG como `bytes`, converte para array numpy via PIL
3. YOLOv8n executa inferência e filtra apenas detecções da classe `person`
4. Retorna `None` se nenhuma pessoa for encontrada (sem evento publicado)
5. Retorna contagem + bounding boxes se detectar pessoas

---

## 5. Publicando Eventos no Bus

O resultado de `process_frame` é recebido pela task Celery e publicado no RabbitMQ.

**Routing key:** `analytics.{plugin_name}`

Exemplos por plugin:

| Plugin | Routing key |
|--------|-------------|
| `people_count` | `analytics.people.count` |
| `vehicle_count` | `analytics.vehicle.count` |
| `intrusion_detection` | `analytics.intrusion.detected` |
| `lpr_parking` | `analytics.lpr.detection` |
| `weapon_detection` | `analytics.weapon.detected` |
| `face_recognition` | `analytics.face.recognized` |

Para criar uma notificação que dispara quando pessoas são detectadas:

```bash
curl -s -X POST http://localhost/api/v1/notifications/rules/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alerta pessoas detectadas",
    "event_type_pattern": "analytics.people.count",
    "channel": "webhook",
    "destination": "https://central.exemplo.com/pessoas"
  }'
```

---

## 6. Worker Analytics

Plugins de IA têm dependências pesadas (ultralytics ~500 MB, paddleocr, insightface). Para não contaminar o worker padrão, use um serviço separado no docker-compose.

### 6.1 Serviço `worker-analytics` (adicionar ao `docker-compose.yml`)

```yaml
worker-analytics:
  build:
    context: ./core
    dockerfile: Dockerfile.analytics   # Dockerfile com dependências de IA
  command: celery -A config.celery worker -l info -Q analytics -c 2
  environment:
    - DJANGO_SETTINGS_MODULE=config.settings.prod
  volumes:
    - ./core:/app
    - ./plugins:/plugins               # monta plugins dentro do container
  depends_on:
    - postgres
    - redis
    - rabbitmq
  restart: unless-stopped
```

### 6.2 `core/Dockerfile.analytics`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Dependências do OS necessárias para cv2 e paddleocr
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxrender1 libxext6 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[prod]"

# Dependências de analytics (separadas do worker padrão)
RUN pip install --no-cache-dir \
    ultralytics \
    paddleocr \
    onnxruntime \
    pillow \
    numpy

COPY . .
```

### 6.3 Bridge async/sync

Celery tasks são síncronas. O bridge usa `asyncio.run()`:

```python
# core/apps/analytics/tasks.py
import asyncio
from celery import shared_task
from plugins import discover_plugins

_plugins = None

@shared_task(name="analytics.process_frame")
def process_frame_task(
    plugin_name: str,
    frame_data: bytes,
    camera_id: int,
    tenant_id: int,
    timestamp: str,
) -> dict | None:
    global _plugins
    if _plugins is None:
        _plugins = discover_plugins()

    plugin = _plugins.get(plugin_name)
    if plugin is None:
        return None

    metadata = {
        "camera_id": camera_id,
        "tenant_id": tenant_id,
        "timestamp": timestamp,
    }
    return asyncio.run(plugin.process_frame(frame_data, metadata))
```

> **Nota:** `_plugins` é inicializado uma vez por worker process para evitar recarregar modelos a cada task.

---

## 7. Testando um Plugin

### 7.1 Estrutura do teste

```python
# plugins/people_count/tests/test_plugin.py
import asyncio
import pytest
from unittest.mock import MagicMock, patch

from plugins.people_count.plugin import PeopleCountPlugin


@pytest.fixture
def plugin():
    p = PeopleCountPlugin()
    # Não chamar on_load() real em testes unitários — mockamos o modelo
    return p


@pytest.fixture
def metadata():
    return {
        "camera_id": 1,
        "tenant_id": 1,
        "timestamp": "2026-03-15T10:00:00Z",
    }


def test_name_and_version(plugin):
    assert plugin.name == "people_count"
    assert plugin.version == "1.0.0"


def test_no_detection_returns_none(plugin, metadata):
    """Quando nenhuma pessoa é detectada, retorna None."""
    mock_result = MagicMock()
    mock_result.boxes = []

    plugin._model = MagicMock(return_value=[mock_result])

    result = asyncio.run(plugin.process_frame(b"fake_frame", metadata))
    assert result is None


def test_detection_returns_count(plugin, metadata):
    """Quando pessoas são detectadas, retorna contagem e bboxes."""
    mock_box = MagicMock()
    mock_box.cls = MagicMock()
    mock_box.cls.__int__ = lambda self: 0          # classe person
    mock_box.conf = MagicMock()
    mock_box.conf.__float__ = lambda self: 0.92
    mock_box.xyxy = [MagicMock()]
    mock_box.xyxy[0].tolist.return_value = [10.0, 20.0, 100.0, 200.0]

    mock_result = MagicMock()
    mock_result.boxes = [mock_box]

    plugin._model = MagicMock(return_value=[mock_result])

    with patch("plugins.people_count.plugin.Image") as mock_img, \
         patch("plugins.people_count.plugin.np") as mock_np:
        mock_img.open.return_value.__enter__ = lambda s: s
        mock_img.open.return_value.convert.return_value = MagicMock()
        mock_np.array.return_value = MagicMock()

        result = asyncio.run(plugin.process_frame(b"fake_frame", metadata))

    assert result is not None
    assert result["count"] == 1
    assert result["plugin"] == "people_count"
    assert result["camera_id"] == 1
    assert len(result["detections"]) == 1


def test_exception_returns_none(plugin, metadata):
    """Exceção interna não propaga — retorna None."""
    plugin._model = MagicMock(side_effect=RuntimeError("GPU OOM"))

    result = asyncio.run(plugin.process_frame(b"fake_frame", metadata))
    assert result is None
```

### 7.2 Rodar testes do plugin

```bash
# Apenas o plugin people_count
pytest plugins/people_count/tests/ -v

# Todos os plugins
pytest plugins/ -v

# Com cobertura
pytest plugins/ --cov=plugins --cov-report=term-missing
```

---

## 8. Plugins Disponíveis

| Plugin | Status | Modelo | Evento |
|--------|--------|--------|--------|
| `intrusion_detection` | stub | YOLOv8n + polígono virtual | `analytics.intrusion.detected` |
| `people_count` | stub | YOLOv8n (classe: person) | `analytics.people.count` |
| `vehicle_count` | stub | YOLOv8n (car, truck, motorcycle) | `analytics.vehicle.count` |
| `lpr_parking` | stub | YOLOv8 + PaddleOCR | `analytics.lpr.detection` |
| `weapon_detection` | stub | YOLOv8 fine-tuned ⚠️ | `analytics.weapon.detected` |
| `face_recognition` | stub | InsightFace / ONNX ⚠️ | `analytics.face.recognized` |

> **⚠️ weapon_detection:** Requer fine-tuning com dataset específico. Deploy em beta com disclaimer explícito para o operador. Alta chance de falso positivo sem dataset adequado.
>
> **⚠️ face_recognition:** Armazena biometria (LGPD). Deve ser habilitado explicitamente por tenant via campo `facial_recognition_enabled`. Nunca habilitado por default.
