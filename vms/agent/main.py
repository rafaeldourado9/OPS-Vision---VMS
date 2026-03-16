"""Loop principal do VMS Agent."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time

from .cloud_client import AuthenticationError, CloudClient
from .config import AgentConfig
from .stream_manager import StreamManager

logger = logging.getLogger(__name__)

# Flag global de shutdown
_shutdown_event = asyncio.Event()


def _setup_logging(level: str) -> None:
    """Configura logging formatado para o agent."""
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _setup_signal_handlers(manager: StreamManager) -> None:
    """Configura handlers para graceful shutdown.

    SIGTERM e SIGINT param todos os streams e finalizam o agent.
    """

    def handle_shutdown(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Recebido %s, iniciando graceful shutdown...", sig_name)
        manager.stop_all()
        _shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)


async def run(config: AgentConfig) -> None:
    """Loop principal do agent.

    1. Poll config do backend a cada ``poll_interval`` segundos
    2. Sincroniza streams ffmpeg com a config desejada
    3. Verifica e reinicia streams mortos (com backoff)
    4. Envia heartbeat a cada ``heartbeat_interval`` segundos

    Args:
        config: Configuração do agent.
    """
    client = CloudClient(config)
    manager = StreamManager()

    _setup_signal_handlers(manager)

    start_time = time.monotonic()
    last_heartbeat = 0.0

    logger.info(
        "VMS Agent iniciado | api=%s poll=%ds heartbeat=%ds",
        config.api_url,
        config.poll_interval,
        config.heartbeat_interval,
    )

    while not _shutdown_event.is_set():
        try:
            # 1. Poll config
            cameras = await client.get_config()

            if cameras:
                # 2. Sync streams com a config desejada
                manager.sync(cameras)

            # 3. Verificar e reiniciar streams mortos
            manager.check_and_restart()

            # 4. Heartbeat periódico
            now = time.monotonic()
            if now - last_heartbeat >= config.heartbeat_interval:
                uptime = int(now - start_time)
                health = manager.get_health()
                await client.send_heartbeat(uptime, health)
                last_heartbeat = now

        except AuthenticationError:
            logger.critical(
                "Autenticação falhou. Verifique VMS_API_KEY. "
                "Tentando novamente em %ds...",
                config.poll_interval * 2,
            )
            try:
                await asyncio.wait_for(
                    _shutdown_event.wait(),
                    timeout=config.poll_interval * 2,
                )
            except asyncio.TimeoutError:
                pass
            continue
        except Exception:
            logger.exception("Erro no loop principal")

        # Espera até próximo poll (interruptível por shutdown)
        try:
            await asyncio.wait_for(
                _shutdown_event.wait(),
                timeout=config.poll_interval,
            )
        except asyncio.TimeoutError:
            pass  # Timeout normal — próximo ciclo

    logger.info("VMS Agent encerrado.")


def main() -> None:
    """Entry point do agent."""
    try:
        config = AgentConfig.from_env()
    except ValueError as exc:
        print(f"ERRO DE CONFIGURAÇÃO: {exc}", file=sys.stderr)
        sys.exit(1)

    _setup_logging(config.log_level)
    asyncio.run(run(config))


if __name__ == "__main__":
    main()
