"""Gerenciador de subprocessos ffmpeg para streaming de câmeras."""
from __future__ import annotations

import logging
import signal
import subprocess
from datetime import datetime, timedelta
from typing import Any

from .models import CameraConfig, StreamProcess

logger = logging.getLogger(__name__)

# Backoff exponencial: min(5 * 2^restart_count, MAX_BACKOFF)
_INITIAL_BACKOFF_SECONDS = 5
_MAX_BACKOFF_SECONDS = 300
_STABLE_THRESHOLD_SECONDS = 60  # Reset backoff após 60s estável
_SIGTERM_TIMEOUT_SECONDS = 5


class StreamManager:
    """Gerencia subprocessos ffmpeg — um por câmera.

    Responsável por iniciar, parar e sincronizar streams ffmpeg
    com a configuração desejada recebida do backend.
    """

    def __init__(self) -> None:
        self._streams: dict[int, StreamProcess] = {}

    @property
    def active_streams(self) -> dict[int, StreamProcess]:
        """Streams atualmente gerenciados (pode ou não estar rodando)."""
        return dict(self._streams)

    def sync(self, desired: list[CameraConfig]) -> None:
        """Sincroniza streams com a configuração desejada.

        - Inicia câmeras novas
        - Para câmeras removidas da config
        - Reinicia câmeras cuja config mudou (rtsp_url ou rtmp_push_url)
        - Não toca em câmeras iguais e rodando

        Args:
            desired: Lista de configurações de câmeras desejadas.
        """
        desired_map = {cam.id: cam for cam in desired if cam.enabled}
        current_ids = set(self._streams.keys())
        desired_ids = set(desired_map.keys())

        # Câmeras removidas → parar
        for cam_id in current_ids - desired_ids:
            logger.info("Câmera %d removida da config, parando stream", cam_id)
            self.stop_stream(cam_id)

        # Câmeras novas → iniciar
        for cam_id in desired_ids - current_ids:
            cam = desired_map[cam_id]
            logger.info(
                "Nova câmera %d (%s), iniciando stream",
                cam.id,
                cam.name,
            )
            self.start_stream(cam)

        # Câmeras existentes → verificar se config mudou
        for cam_id in current_ids & desired_ids:
            current = self._streams[cam_id]
            new_config = desired_map[cam_id]
            if self._config_changed(current.camera_config, new_config):
                logger.info(
                    "Config da câmera %d mudou, reiniciando stream",
                    cam_id,
                )
                self.stop_stream(cam_id)
                self.start_stream(new_config)

    def start_stream(self, camera: CameraConfig) -> None:
        """Inicia um subprocesso ffmpeg para a câmera.

        Comando: ffmpeg -nostdin -rtsp_transport tcp -i {rtsp} -c copy -f flv {rtmp}

        Args:
            camera: Configuração da câmera.
        """
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-rtsp_transport", "tcp",
            "-i", camera.rtsp_url,
            "-c", "copy",
            "-f", "flv",
            camera.rtmp_push_url,
        ]

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )

            stream = StreamProcess(
                camera_id=camera.id,
                camera_config=camera,
                process=process,
                started_at=datetime.now(),
            )
            self._streams[camera.id] = stream

            logger.info(
                "Stream iniciado: câmera %d (%s) pid=%d | %s → %s",
                camera.id,
                camera.name,
                process.pid,
                camera.rtsp_url,
                camera.rtmp_push_url,
            )

        except FileNotFoundError:
            logger.error(
                "ffmpeg não encontrado. Instale ffmpeg no container."
            )
        except Exception:
            logger.exception(
                "Erro ao iniciar stream para câmera %d", camera.id
            )

    def stop_stream(self, camera_id: int) -> None:
        """Para o subprocesso ffmpeg de uma câmera.

        Envia SIGTERM, espera 5s, e faz SIGKILL se não terminou.

        Args:
            camera_id: ID da câmera.
        """
        stream = self._streams.pop(camera_id, None)
        if stream is None or stream.process is None:
            return

        if not stream.is_running:
            return

        pid = stream.process.pid
        logger.info("Parando stream câmera %d (pid=%d)", camera_id, pid)

        try:
            stream.process.terminate()  # SIGTERM
            try:
                stream.process.wait(timeout=_SIGTERM_TIMEOUT_SECONDS)
                logger.debug("Stream câmera %d terminou com SIGTERM", camera_id)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "Stream câmera %d não respondeu SIGTERM, enviando SIGKILL",
                    camera_id,
                )
                stream.process.kill()  # SIGKILL
                stream.process.wait(timeout=2)
        except Exception:
            logger.exception(
                "Erro ao parar stream câmera %d (pid=%d)",
                camera_id,
                pid,
            )

    def stop_all(self) -> None:
        """Para todos os streams. Usado no graceful shutdown."""
        camera_ids = list(self._streams.keys())
        for cam_id in camera_ids:
            self.stop_stream(cam_id)
        logger.info("Todos os streams parados (%d)", len(camera_ids))

    def check_and_restart(self) -> None:
        """Verifica streams mortos e reinicia com backoff exponencial.

        - Se o ffmpeg crashou e já passou o backoff, reinicia.
        - Se o stream está estável há 60+ segundos, reseta o backoff.
        """
        now = datetime.now()

        for cam_id, stream in list(self._streams.items()):
            if stream.is_running:
                # Stream estável — reset backoff se > 60s
                if (
                    stream.uptime_seconds > _STABLE_THRESHOLD_SECONDS
                    and stream.restart_count > 0
                ):
                    logger.info(
                        "Câmera %d estável há %.0fs, resetando backoff",
                        cam_id,
                        stream.uptime_seconds,
                    )
                    stream.restart_count = 0
                continue

            # Stream morta — verificar backoff
            if stream.backoff_until and now < stream.backoff_until:
                continue  # Ainda em backoff

            # Capturar último erro do stderr
            if stream.process is not None:
                try:
                    stderr = stream.process.stderr
                    if stderr:
                        err = stderr.read()
                        if err:
                            stream.last_error = err.decode(
                                "utf-8", errors="replace"
                            )[-500:]
                except Exception:
                    pass

            # Calcular backoff exponencial
            stream.restart_count += 1
            backoff = min(
                _INITIAL_BACKOFF_SECONDS * (2 ** (stream.restart_count - 1)),
                _MAX_BACKOFF_SECONDS,
            )

            logger.warning(
                "Câmera %d stream morreu (tentativa #%d). "
                "Reiniciando em %ds. Último erro: %s",
                cam_id,
                stream.restart_count,
                backoff,
                (stream.last_error or "desconhecido")[:200],
            )

            stream.backoff_until = now + timedelta(seconds=backoff)

            # Reiniciar
            config = stream.camera_config
            restart_count = stream.restart_count
            backoff_until = stream.backoff_until

            self.start_stream(config)

            # Preservar contadores de restart no novo stream
            if config.id in self._streams:
                self._streams[config.id].restart_count = restart_count
                self._streams[config.id].backoff_until = backoff_until

    def get_health(self) -> dict[str, Any]:
        """Retorna status de todos os streams.

        Returns:
            Dict com info de cada câmera para o heartbeat.
        """
        result: dict[str, Any] = {}
        for cam_id, stream in self._streams.items():
            result[str(cam_id)] = {
                "running": stream.is_running,
                "pid": stream.process.pid if stream.process else None,
                "uptime_seconds": int(stream.uptime_seconds),
                "restart_count": stream.restart_count,
                "last_error": stream.last_error,
            }
        return result

    @staticmethod
    def _config_changed(
        current: CameraConfig,
        new: CameraConfig,
    ) -> bool:
        """Verifica se a config da câmera mudou (precisa reiniciar)."""
        return (
            current.rtsp_url != new.rtsp_url
            or current.rtmp_push_url != new.rtmp_push_url
        )
