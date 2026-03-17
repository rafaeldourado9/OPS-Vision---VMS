"""Classe base para plugins de analytics."""
from abc import ABC, abstractmethod
from typing import Any


class AnalyticsPlugin(ABC):
    """Classe base para plugins de analytics.

    Para criar um plugin:
    1. Crie uma pasta em /plugins/<nome>/
    2. Crie plugin.py com uma classe que herda AnalyticsPlugin
    3. Implemente process_frame()
    4. O Plugin Loader descobre automaticamente.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome único do plugin."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Versão semântica."""

    @abstractmethod
    async def process_frame(
        self,
        frame: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Processa um frame e retorna resultado.

        Args:
            frame: Bytes do frame (JPEG/PNG).
            metadata: Camera ID, timestamp, etc.

        Returns:
            Dict com resultado ou None se nada detectado.
        """

    def on_load(self) -> None:
        """Hook chamado quando o plugin é carregado."""

    def on_unload(self) -> None:
        """Hook chamado quando o plugin é descarregado."""
