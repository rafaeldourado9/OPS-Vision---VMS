"""
Configurações centralizadas da aplicação.

Usa variáveis de ambiente com fallback para valores padrão.
"""
import os
import json
from typing import List, Dict, Any
from pathlib import Path


class Settings:
    """Configurações da aplicação"""
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # FPS de processamento (por câmera)
    FPS: int = int(os.getenv("FPS", "2"))  # 2 FPS x 20 câmeras = 40 frames/s
    
    # Workers paralelos por serviço
    WORKERS_PER_SERVICE: int = int(os.getenv("WORKERS_PER_SERVICE", "3"))
    
    # Timeout para operações
    REDIS_TIMEOUT: int = int(os.getenv("REDIS_TIMEOUT", "1"))
    MEDIAMTX_REQUEST_TIMEOUT: int = int(os.getenv("MEDIAMTX_REQUEST_TIMEOUT", "10"))
    
    # Paths
    SERVICES_PATH: str = os.getenv("SERVICES_PATH", "services")
    MEDIAMTX_CONFIG_FILE: str = os.getenv("MEDIAMTX_CONFIG_FILE", "config/mediamtx_instances.json")
    SERVICES_CONFIG_FILE: str = os.getenv("SERVICES_CONFIG_FILE", "config/services_config.json")
    
    # Instâncias MediaMTX
    @property
    def MEDIAMTX_INSTANCES(self) -> List[Dict[str, str]]:
        config_file = Path(self.MEDIAMTX_CONFIG_FILE)
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        return []
    
    # Configurações dos serviços de IA
    @property
    def SERVICES_CONFIG(self) -> Dict[str, Dict[str, Any]]:
        config_file = Path(self.SERVICES_CONFIG_FILE)
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        return {}


settings = Settings()
