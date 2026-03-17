"""
Redis Bus - Transporta frames e resultados entre Core e Serviços.

Padrão: Producer-Consumer com filas separadas por serviço.
"""
import json
import pickle
import logging
from typing import Dict, Any, Optional
import redis.asyncio as redis
import numpy as np

logger = logging.getLogger(__name__)


class RedisBus:
    """Barramento de mensagens via Redis"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
    
    async def connect(self):
        """Conecta ao Redis"""
        self.client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=False  # Precisamos de bytes para frames
        )
        logger.info("Connected to Redis")
    
    async def disconnect(self):
        """Desconecta do Redis"""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")
    
    async def publish_frame(
        self, 
        service_name: str,
        frame: np.ndarray,
        metadata: Dict[str, Any]
    ):
        """
        Publica um frame para um serviço específico.
        
        Args:
            service_name: Nome do serviço destino
            frame: Frame de vídeo
            metadata: Metadados do frame
        """
        try:
            # Serializa frame e metadata
            payload = {
                'frame': pickle.dumps(frame),
                'metadata': json.dumps(metadata)
            }
            
            queue_name = f"frames:{service_name}"
            await self.client.lpush(queue_name, pickle.dumps(payload))
            
        except Exception as e:
            logger.error(f"Erro ao publicar frame para {service_name}: {e}")
    
    async def consume_frame(
        self, 
        service_name: str,
        timeout: int = None
    ) -> Optional[tuple[np.ndarray, Dict[str, Any]]]:
        """
        Consome um frame da fila de um serviço.
        
        Args:
            service_name: Nome do serviço
            timeout: Timeout em segundos (usa config se None)
        
        Returns:
            Tupla (frame, metadata) ou None
        """
        if timeout is None:
            from config.settings import settings
            timeout = settings.REDIS_TIMEOUT
        try:
            queue_name = f"frames:{service_name}"
            result = await self.client.brpop(queue_name, timeout=timeout)
            
            if not result:
                return None
            
            _, data = result
            payload = pickle.loads(data)
            
            frame = pickle.loads(payload['frame'])
            metadata = json.loads(payload['metadata'])
            
            return frame, metadata
            
        except Exception as e:
            logger.error(f"Erro ao consumir frame de {service_name}: {e}")
            return None
    
    async def publish_result(
        self,
        result: Dict[str, Any]
    ):
        """
        Publica resultado de processamento.
        
        Args:
            result: Resultado do serviço de IA
        """
        try:
            await self.client.lpush(
                "results:all",
                json.dumps(result)
            )
        except Exception as e:
            logger.error(f"Erro ao publicar resultado: {e}")
    
    async def get_queue_size(self, service_name: str) -> int:
        """Retorna tamanho da fila de um serviço"""
        try:
            queue_name = f"frames:{service_name}"
            return await self.client.llen(queue_name)
        except:
            return 0
