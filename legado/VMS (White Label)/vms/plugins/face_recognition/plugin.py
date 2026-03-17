"""Plugin de reconhecimento facial."""
from typing import Any

from plugins.base import AnalyticsPlugin


class FaceRecognitionPlugin(AnalyticsPlugin):
    """Detecta e reconhece faces em frames."""

    @property
    def name(self) -> str:
        return "face_recognition"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def process_frame(
        self,
        frame: bytes,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Detecta faces no frame.

        Returns:
            {"faces": list[dict]} ou None.
        """
        # TODO: implementar detecção facial
        return None
