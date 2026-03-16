"""Plugin de detecção de intrusão."""
from typing import Any

from plugins.base import AnalyticsPlugin


class IntrusionDetectionPlugin(AnalyticsPlugin):
    """Detecta intrusão em zonas configuradas."""

    @property
    def name(self) -> str:
        return "intrusion_detection"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def process_frame(
        self,
        frame: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Detecta intrusão no frame.

        Returns:
            {"intrusions": list[dict]} ou None.
        """
        # TODO: implementar detecção de intrusão
        return None
