"""Interface base para todos os plugins analíticos."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class FrameMetadata:
    """Metadados associados a um frame capturado."""

    camera_id: int
    tenant_id: int
    timestamp: datetime
    stream_url: str


@dataclass
class ROIConfig:
    """Configuração de uma Region of Interest vinda do Django."""

    id: int
    name: str
    ia_type: str
    # Pontos [[x, y], ...] normalizados 0.0–1.0
    polygon_points: list[list[float]]
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalyticsResult:
    """Resultado produzido por um plugin para uma ROI/frame."""

    plugin: str        # "vehicle_dwell"
    camera_id: int
    tenant_id: int
    event_type: str    # "analytics.vehicle.dwell"
    payload: dict[str, Any]


class AnalyticsPlugin(ABC):
    """Contrato que todos os plugins em analytics/ devem implementar.

    Princípios:
    - Cada plugin é um Bounded Context isolado.
    - O Core não conhece a lógica interna.
    - Adicionar novo plugin = criar pasta + plugin.py. Zero mudança na plataforma.
    """

    #: Nome único do plugin em snake_case. Deve bater com o campo plugin no ingest.
    name: str
    #: Versão semântica do plugin.
    version: str
    #: ia_type de ROI que este plugin consome (filtra ROIs antes de process_frame).
    roi_type: str

    @abstractmethod
    async def initialize(self, config: dict[str, Any]) -> None:
        """Inicializa recursos (carrega modelo, configura tracker, etc.).

        Args:
            config: Configuração específica do plugin.
        """

    @abstractmethod
    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa um frame e retorna lista de resultados.

        Args:
            frame: Frame BGR em numpy array.
            metadata: Metadados do frame (câmera, tenant, timestamp).
            rois: ROIs ativas filtradas por roi_type para esta câmera.

        Returns:
            Lista de AnalyticsResult (vazia se sem detecções relevantes).
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Libera recursos antes de desligar."""
