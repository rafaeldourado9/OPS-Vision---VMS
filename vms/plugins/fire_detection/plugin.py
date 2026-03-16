"""Plugin de detecção de incêndio."""
from typing import Any

from plugins.base import AnalyticsPlugin


class FireDetectionPlugin(AnalyticsPlugin):
    """Detecta focos de incêndio em frames."""

    @property
    def name(self) -> str:
        return "fire_detection"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def process_frame(
        self,
        frame: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Detecta incêndio no frame.

        Returns:
            {"fire_detected": bool, "confidence": float} ou None.
        """
        # TODO: implementar detecção de incêndio
        return None
