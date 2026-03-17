"""
MediaMTX Connection Manager - Gerencia N instâncias de MediaMTX.

Responsabilidades:
- Conectar em múltiplas instâncias MediaMTX
- Obter lista de streams disponíveis
- Capturar frames via RTSP
- Agnóstico sobre o que acontece com os frames
"""
import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import aiohttp
import cv2
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MediaMTXInstance:
    """Representa uma instância de MediaMTX"""
    instance_id: str
    api_url: str
    username: str
    password: str
    enabled: bool = True


@dataclass
class StreamInfo:
    """Informações de um stream"""
    camera_id: str
    rtsp_url: str
    instance_id: str
    name: str
    ready: bool


class MediaMTXConnector:
    """Gerencia conexões com múltiplas instâncias MediaMTX"""
    
    def __init__(self, instances: List[MediaMTXInstance]):
        self.instances = {inst.instance_id: inst for inst in instances}
        self.active_streams: Dict[str, StreamInfo] = {}
        self._capture_tasks: Dict[str, asyncio.Task] = {}
    
    async def fetch_streams_from_instance(
        self, 
        instance: MediaMTXInstance
    ) -> List[StreamInfo]:
        """
        Obtém lista de streams de uma instância MediaMTX.
        
        Args:
            instance: Instância MediaMTX
        
        Returns:
            Lista de streams disponíveis
        """
        try:
            auth = aiohttp.BasicAuth(instance.username, instance.password)
            
            async with aiohttp.ClientSession(auth=auth) as session:
                async with session.get(instance.api_url) as response:
                    if response.status != 200:
                        logger.error(
                            f"Erro ao buscar streams de {instance.instance_id}: "
                            f"Status {response.status}"
                        )
                        return []
                    
                    data = await response.json()
                    streams = []
                    
                    # Parse da resposta da API MediaMTX v3
                    items = data.get('items', [])
                    
                    for item in items:
                        if not item.get('online', False):
                            continue
                        
                        path_name = item.get('name', '')
                        if not path_name:
                            continue
                        
                        # Extrai URL RTSP base da instância
                        base_url = instance.api_url.replace('/v3/paths/list', '')
                        rtsp_url = f"rtsp://{base_url.split('//')[1].split(':')[0]}:8554/{path_name}"
                        
                        stream = StreamInfo(
                            camera_id=f"{instance.instance_id}_{path_name}",
                            rtsp_url=rtsp_url,
                            instance_id=instance.instance_id,
                            name=path_name,
                            ready=item.get('ready', False)
                        )
                        streams.append(stream)
                    
                    logger.info(
                        f"{len(streams)} streams found in {instance.instance_id}"
                    )
                    return streams
                    
        except Exception as e:
            logger.error(f"Error connecting to {instance.instance_id}: {e}")
            return []
    
    async def discover_all_streams(self) -> Dict[str, StreamInfo]:
        """
        Descobre streams de todas as instâncias MediaMTX.
        
        Returns:
            Dicionário {camera_id: StreamInfo}
        """
        tasks = [
            self.fetch_streams_from_instance(inst)
            for inst in self.instances.values()
            if inst.enabled
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_streams = {}
        for streams in results:
            if isinstance(streams, list):
                for stream in streams:
                    all_streams[stream.camera_id] = stream
        
        self.active_streams = all_streams
        logger.info(f"Total of {len(all_streams)} active streams")
        return all_streams
    
    def capture_frame(self, rtsp_url: str) -> Optional[np.ndarray]:
        """
        Captura um frame de um stream RTSP (síncrono).
        
        Args:
            rtsp_url: URL RTSP do stream
        
        Returns:
            Frame como numpy array ou None
        """
        try:
            cap = cv2.VideoCapture(rtsp_url)
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return frame
            return None
            
        except Exception as e:
            logger.error(f"Erro ao capturar frame de {rtsp_url}: {e}")
            return None
    
    async def get_frame_metadata(self, stream: StreamInfo) -> Dict:
        """Cria metadata para um frame"""
        return {
            'camera_id': stream.camera_id,
            'timestamp': datetime.now().timestamp(),
            'stream_url': stream.rtsp_url,
            'instance_id': stream.instance_id,
            'camera_name': stream.name
        }
