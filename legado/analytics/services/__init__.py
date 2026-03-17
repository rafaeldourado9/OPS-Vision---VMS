"""
Interface Base para todos os Serviços de IA.
Garante que todos os plugins sigam o mesmo contrato.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np


class AIServiceInterface(ABC):
    """
    Contrato que todos os serviços em /services devem implementar.
    
    Princípios:
    - Cada serviço é um Bounded Context isolado
    - O Core não conhece a lógica interna
    - Comunicação via protocolo padronizado
    """
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Nome único do serviço (ex: 'invasion_ai')"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Versão do serviço (ex: '1.0.0')"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        Inicializa o serviço com configurações específicas.
        
        Args:
            config: Configurações do serviço (modelos, thresholds, etc)
        """
        pass
    
    @abstractmethod
    async def process_frame(
        self, 
        frame: np.ndarray, 
        metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Processa um frame e retorna resultados.
        
        Args:
            frame: Frame de vídeo (numpy array BGR)
            metadata: {
                'camera_id': str,
                'timestamp': float,
                'stream_url': str,
                'instance_id': str  # ID da instância MediaMTX
            }
        
        Returns:
            Resultado do processamento ou None se não houver detecção:
            {
                'service': str,
                'detections': List[Dict],
                'timestamp': float,
                'camera_id': str
            }
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica saúde do serviço.
        
        Returns:
            {
                'status': 'healthy' | 'degraded' | 'unhealthy',
                'details': Dict[str, Any]
            }
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Libera recursos antes de desligar"""
        pass
