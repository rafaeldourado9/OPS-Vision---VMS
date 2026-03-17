"""
Orchestrator - Coordena o fluxo de frames entre MediaMTX e Serviços de IA.

Responsabilidades:
- Captura frames dos streams MediaMTX
- Distribui frames para serviços via Redis
- Gerencia workers de processamento
"""
import asyncio
import logging
from typing import Dict, List
from datetime import datetime

from core.mediamtx_connector import MediaMTXConnector, StreamInfo
from core.redis_bus import RedisBus
from services import AIServiceInterface

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orquestra o fluxo de dados entre MediaMTX e Serviços de IA"""
    
    def __init__(
        self,
        mediamtx_connector: MediaMTXConnector,
        redis_bus: RedisBus,
        services: Dict[str, AIServiceInterface],
        fps: int = 2,  # 2 FPS por câmera para 20 câmeras = 40 frames/s total
        workers_per_service: int = 3  # Workers paralelos por serviço
    ):
        self.mediamtx = mediamtx_connector
        self.redis = redis_bus
        self.services = services
        self.fps = fps
        self.workers_per_service = workers_per_service
        self.running = False
        self._tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Inicia o orquestrador"""
        logger.info("Starting Orchestrator")
        
        # Descobre streams disponíveis
        await self.mediamtx.discover_all_streams()
        
        if not self.mediamtx.active_streams:
            logger.warning("No active streams found")
        
        self.running = True
        
        # Task de redescoberta periódica de streams
        rediscovery_task = asyncio.create_task(self._stream_discovery_loop())
        self._tasks.append(rediscovery_task)
        
        # Inicia captura de frames
        for stream in self.mediamtx.active_streams.values():
            task = asyncio.create_task(self._capture_loop(stream))
            self._tasks.append(task)
        
        # Inicia workers de processamento para cada serviço (múltiplos workers)
        for service_name in self.services.keys():
            for worker_id in range(self.workers_per_service):
                task = asyncio.create_task(
                    self._processing_worker(service_name, worker_id)
                )
                self._tasks.append(task)
        
        logger.info(f"Orchestrator running with {len(self._tasks)} tasks")
    
    async def stop(self):
        """Para o orquestrador"""
        logger.info("Stopping Orchestrator")
        self.running = False
        
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
    
    async def _stream_discovery_loop(self):
        """Loop de redescoberta periódica de streams"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Verifica a cada 30 segundos
                
                old_streams = set(self.mediamtx.active_streams.keys())
                await self.mediamtx.discover_all_streams()
                new_streams = set(self.mediamtx.active_streams.keys())
                
                # Detecta novos streams
                added = new_streams - old_streams
                removed = old_streams - new_streams
                
                if added:
                    logger.info(f"New streams detected: {added}")
                    for camera_id in added:
                        stream = self.mediamtx.active_streams[camera_id]
                        task = asyncio.create_task(self._capture_loop(stream))
                        self._tasks.append(task)
                
                if removed:
                    logger.info(f"Streams removed: {removed}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in stream discovery: {e}")
    
    async def _capture_loop(self, stream: StreamInfo):
        """
        Loop de captura de frames de um stream.
        
        Args:
            stream: Informações do stream
        """
        interval = 1.0 / self.fps
        
        while self.running:
            try:
                # Captura frame (operação síncrona, roda em executor)
                loop = asyncio.get_event_loop()
                frame = await loop.run_in_executor(
                    None,
                    self.mediamtx.capture_frame,
                    stream.rtsp_url
                )
                
                if frame is None:
                    await asyncio.sleep(interval)
                    continue
                
                # Cria metadata
                metadata = await self.mediamtx.get_frame_metadata(stream)
                
                # Distribui para todos os serviços
                for service_name in self.services.keys():
                    await self.redis.publish_frame(
                        service_name,
                        frame,
                        metadata
                    )
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no capture loop de {stream.camera_id}: {e}")
                await asyncio.sleep(interval)
    
    async def _processing_worker(self, service_name: str, worker_id: int = 0):
        """
        Worker que processa frames para um serviço específico.
        
        Args:
            service_name: Nome do serviço
            worker_id: ID do worker (para logs)
        """
        service = self.services[service_name]
        logger.info(f"Worker {service_name}#{worker_id} started")
        
        while self.running:
            try:
                # Consome frame da fila
                result = await self.redis.consume_frame(service_name, timeout=1)
                
                if result is None:
                    continue
                
                frame, metadata = result
                
                # Processa frame
                detection_result = await service.process_frame(frame, metadata)
                
                # Publica resultado se houver detecção
                if detection_result:
                    await self.redis.publish_result(detection_result)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no worker {service_name}#{worker_id}: {e}")
                await asyncio.sleep(0.1)
    
    async def get_status(self) -> Dict:
        """Retorna status do orquestrador"""
        queue_sizes = {}
        for service_name in self.services.keys():
            size = await self.redis.get_queue_size(service_name)
            queue_sizes[service_name] = size
        
        return {
            'running': self.running,
            'active_streams': len(self.mediamtx.active_streams),
            'active_services': len(self.services),
            'queue_sizes': queue_sizes,
            'tasks': len(self._tasks)
        }
