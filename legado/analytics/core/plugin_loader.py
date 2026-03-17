"""
Plugin Loader - Carrega dinamicamente todos os serviços de IA.

Princípio: Zero configuração manual.
Adicione uma pasta em /services e ela será descoberta automaticamente.
"""
import importlib
import pkgutil
import inspect
from pathlib import Path
from typing import Dict, List, Type
import logging

from services import AIServiceInterface

logger = logging.getLogger(__name__)


class PluginLoader:
    """Descobre e carrega serviços de IA dinamicamente"""
    
    def __init__(self, services_path: str = None):
        if services_path is None:
            from config.settings import settings
            services_path = settings.SERVICES_PATH
        self.services_path = Path(services_path)
        self.loaded_services: Dict[str, AIServiceInterface] = {}
    
    def discover_services(self) -> List[Type[AIServiceInterface]]:
        """
        Varre a pasta /services e encontra todas as implementações.
        
        Returns:
            Lista de classes que implementam AIServiceInterface
        """
        discovered = []
        
        if not self.services_path.exists():
            logger.warning(f"Services path não encontrado: {self.services_path}")
            return discovered
        
        # Itera sobre todas as subpastas em /services
        for item in self.services_path.iterdir():
            if not item.is_dir() or item.name.startswith('_'):
                continue
            
            service_name = item.name
            logger.info(f"Discovering service: {service_name}")
            
            try:
                # Importa o módulo dinamicamente
                module = importlib.import_module(f"services.{service_name}")
                
                # Procura por classes que implementam AIServiceInterface
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, AIServiceInterface) and 
                        obj is not AIServiceInterface and
                        not inspect.isabstract(obj)):
                        
                        logger.info(f"Service found: {name} in {service_name}")
                        discovered.append(obj)
                        
            except Exception as e:
                logger.error(f"Error loading {service_name}: {e}")
        
        return discovered
    
    async def load_all_services(self, config: Dict[str, Dict]) -> Dict[str, AIServiceInterface]:
        """
        Carrega e inicializa todos os serviços descobertos.
        
        Args:
            config: Configurações por serviço
                {
                    'invasion_ai': {'model': 'yolov8n.pt', ...},
                    'people_counter': {...}
                }
        
        Returns:
            Dicionário de serviços carregados {service_name: instance}
        """
        service_classes = self.discover_services()
        
        for ServiceClass in service_classes:
            try:
                instance = ServiceClass()
                service_name = instance.service_name
                
                # Inicializa com config específica ou vazia
                service_config = config.get(service_name, {})
                await instance.initialize(service_config)
                
                self.loaded_services[service_name] = instance
                logger.info(f"Service '{service_name}' v{instance.version} loaded")
                
            except Exception as e:
                logger.error(f"Failed to initialize {ServiceClass.__name__}: {e}")
        
        return self.loaded_services
    
    async def shutdown_all(self):
        """Desliga todos os serviços carregados"""
        for name, service in self.loaded_services.items():
            try:
                await service.shutdown()
                logger.info(f"Service '{name}' shutdown")
            except Exception as e:
                logger.error(f"Erro ao desligar {name}: {e}")
