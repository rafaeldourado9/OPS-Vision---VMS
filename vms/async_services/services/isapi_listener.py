"""ISAPI Event Listener para câmeras Hikvision/Intelbras.

Conecta ao endpoint alertStream de cada câmera e consome eventos
em tempo real (motion, videoloss, line crossing, etc).
Despacha eventos para processamento via Celery.
"""
import asyncio
import logging
import re
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

# Namespace Hikvision ISAPI XML
HIK_NS = "http://www.hikvision.com/ver20/XMLSchema"

# Mapeamento de event types ISAPI → tipos internos do VMS
ISAPI_EVENT_MAP: dict[str, str] = {
    "VMD": "motion.detected",
    "videoloss": "video.loss",
    "shelteralarm": "tampering.detected",
    "linedetection": "line_crossing.detected",
    "fielddetection": "intrusion.detected",
    "facedetection": "face.detected",
    "PIR": "motion.detected",
}

# Eventos com alta frequência que precisam de debounce
DEBOUNCE_EVENTS: set[str] = {"VMD", "PIR", "videoloss"}

# Segundos mínimos entre eventos do mesmo tipo para a mesma câmera
DEBOUNCE_SECONDS: float = 5.0

# Máximo de falhas consecutivas antes de desistir
MAX_CONSECUTIVE_FAILURES: int = 10

# Regex para extrair blocos XML de EventNotificationAlert
_XML_BLOCK_RE = re.compile(
    r"(<EventNotificationAlert[^>]*>.*?</EventNotificationAlert>)",
    re.DOTALL,
)


def parse_isapi_credentials(rtsp_url: str) -> tuple[str, str, str]:
    """Extrai host, username e password de uma URL RTSP.

    Args:
        rtsp_url: URL como rtsp://user:pass@host:port/path.

    Returns:
        Tupla (host, username, password).
    """
    parsed = urlparse(rtsp_url)
    return (
        parsed.hostname or "",
        parsed.username or "",
        parsed.password or "",
    )


def parse_alert_xml(xml_str: str) -> dict[str, str] | None:
    """Parseia XML de EventNotificationAlert ISAPI.

    Args:
        xml_str: String XML completa do alert.

    Returns:
        Dict com dados do evento ou None se parsing falhar.
    """
    try:
        root = ET.fromstring(xml_str)
        ns = {"hik": HIK_NS}

        def _text(tag: str) -> str:
            el = root.find(f"hik:{tag}", ns)
            if el is None:
                el = root.find(tag)
            return el.text if el is not None and el.text else ""

        event_type = _text("eventType")
        if not event_type:
            return None

        return {
            "ip_address": _text("ipAddress"),
            "channel_id": _text("channelID"),
            "date_time": _text("dateTime"),
            "event_type": event_type,
            "event_state": _text("eventState"),
            "event_description": _text("eventDescription"),
        }
    except ET.ParseError:
        logger.warning("Falha ao parsear XML ISAPI")
        return None


class ISAPIManager:
    """Gerencia listeners ISAPI para múltiplas câmeras.

    Cada câmera online recebe um asyncio.Task que consome
    o alertStream ISAPI e despacha eventos para processamento.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, asyncio.Task] = {}
        self._last_state: dict[str, dict[str, tuple[str, float]]] = {}

    @property
    def active_listeners(self) -> list[str]:
        """Retorna lista de paths com listeners ativos."""
        return list(self._listeners.keys())

    async def start_listener(self, path: str, rtsp_url: str) -> None:
        """Inicia listener ISAPI para uma câmera.

        Args:
            path: Path do MediaMTX (ex: tenant-1/cam-3).
            rtsp_url: URL RTSP da câmera (contém credenciais).
        """
        if path in self._listeners:
            logger.info("ISAPI listener já ativo para %s", path)
            return

        host, username, password = parse_isapi_credentials(rtsp_url)
        if not host or not username:
            logger.warning(
                "ISAPI listener não iniciado para %s: credenciais ausentes",
                path,
            )
            return

        task = asyncio.create_task(
            self._listen(path, host, username, password),
            name=f"isapi-{path}",
        )
        self._listeners[path] = task
        logger.info("ISAPI listener iniciado para %s (%s)", path, host)

    async def stop_listener(self, path: str) -> None:
        """Para o listener ISAPI de uma câmera.

        Args:
            path: Path do MediaMTX.
        """
        task = self._listeners.pop(path, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("ISAPI listener parado para %s", path)
        self._last_state.pop(path, None)

    async def stop_all(self) -> None:
        """Para todos os listeners ativos."""
        paths = list(self._listeners.keys())
        for path in paths:
            await self.stop_listener(path)

    def _should_forward(
        self, path: str, event_type: str, event_state: str,
    ) -> bool:
        """Verifica se evento deve ser encaminhado (debounce).

        Para eventos de alta frequência (VMD, PIR), só encaminha:
        - Transições de estado (active→inactive, inactive→active)
        - Eventos active com intervalo >= DEBOUNCE_SECONDS

        Args:
            path: Path da câmera.
            event_type: Tipo ISAPI do evento.
            event_state: Estado (active/inactive).

        Returns:
            True se o evento deve ser encaminhado.
        """
        if event_type not in DEBOUNCE_EVENTS:
            return True

        now = asyncio.get_event_loop().time()
        path_state = self._last_state.setdefault(path, {})
        last = path_state.get(event_type)

        if last is None:
            path_state[event_type] = (event_state, now)
            return event_state == "active"

        last_state, last_time = last
        path_state[event_type] = (event_state, now)

        if event_state != last_state:
            return True

        if event_state == "active" and (now - last_time) >= DEBOUNCE_SECONDS:
            return True

        return False

    async def _listen(
        self, path: str, host: str, username: str, password: str,
    ) -> None:
        """Coroutine de longa duração que consome o alertStream ISAPI.

        Reconecta automaticamente com backoff exponencial em caso de erro.

        Args:
            path: Path do MediaMTX (ex: tenant-1/cam-3).
            host: IP/hostname da câmera.
            username: Usuário ISAPI.
            password: Senha ISAPI.
        """
        url = f"http://{host}/ISAPI/Event/notification/alertStream"
        auth = httpx.DigestAuth(username, password)
        retry_delay = 5
        consecutive_failures = 0

        while True:
            try:
                async with httpx.AsyncClient(auth=auth, timeout=None) as client:
                    logger.info(
                        "Conectando ao ISAPI alertStream: %s", url,
                    )
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()
                        retry_delay = 5
                        consecutive_failures = 0
                        buffer = ""

                        async for chunk in response.aiter_text():
                            buffer += chunk
                            while True:
                                match = _XML_BLOCK_RE.search(buffer)
                                if not match:
                                    break
                                xml_str = match.group(1)
                                buffer = buffer[match.end():]
                                await self._handle_event(path, xml_str)

            except asyncio.CancelledError:
                logger.info("ISAPI listener cancelado para %s", path)
                raise

            except Exception:
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(
                        "ISAPI listener desistindo para %s após %d falhas",
                        path, consecutive_failures,
                    )
                    self._listeners.pop(path, None)
                    return

                logger.exception(
                    "ISAPI listener erro para %s, retry em %ds (%d/%d)",
                    path, retry_delay, consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _handle_event(self, path: str, xml_str: str) -> None:
        """Parseia e encaminha um evento ISAPI.

        Args:
            path: Path da câmera no MediaMTX.
            xml_str: XML do EventNotificationAlert.
        """
        event = parse_alert_xml(xml_str)
        if not event:
            return

        isapi_type = event["event_type"]
        internal_type = ISAPI_EVENT_MAP.get(isapi_type)
        if not internal_type:
            logger.debug("Tipo ISAPI desconhecido ignorado: %s", isapi_type)
            return

        if not self._should_forward(path, isapi_type, event["event_state"]):
            return

        from services.webhook_processor import process_isapi_event

        process_isapi_event(path, internal_type, event)


# Instância singleton
isapi_manager = ISAPIManager()
