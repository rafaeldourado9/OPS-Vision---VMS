"""
VMS Edge Worker - PC 2 (Worker Node)

Aplicação principal que orquestra MediaMTX e Serviços de IA.
"""
import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.plugin_loader import PluginLoader
from core.mediamtx_connector import MediaMTXConnector, MediaMTXInstance
from core.redis_bus import RedisBus
from core.orchestrator import Orchestrator
from config.settings import settings

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Estado global da aplicação
app_state = {
    'orchestrator': None,
    'plugin_loader': None,
    'redis_bus': None
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""
    logger.info("Starting VMS Edge Worker")
    
    # 1. Carrega plugins dinamicamente
    plugin_loader = PluginLoader()
    services = await plugin_loader.load_all_services(settings.SERVICES_CONFIG)
    
    if not services:
        logger.warning("No AI services loaded")
    
    # 2. Conecta ao Redis
    redis_bus = RedisBus(settings.REDIS_URL)
    await redis_bus.connect()
    
    # 3. Configura conexões MediaMTX
    mediamtx_instances = [
        MediaMTXInstance(
            instance_id=inst['id'],
            api_url=inst['api_url'],
            username=inst['username'],
            password=inst['password']
        )
        for inst in settings.MEDIAMTX_INSTANCES
    ]
    mediamtx_connector = MediaMTXConnector(mediamtx_instances)
    
    # 4. Inicia orquestrador
    orchestrator = Orchestrator(
        mediamtx_connector=mediamtx_connector,
        redis_bus=redis_bus,
        services=services,
        fps=settings.FPS,
        workers_per_service=settings.WORKERS_PER_SERVICE
    )
    await orchestrator.start()
    
    # Salva no estado global
    app_state['orchestrator'] = orchestrator
    app_state['plugin_loader'] = plugin_loader
    app_state['redis_bus'] = redis_bus
    
    logger.info("VMS Edge Worker started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down VMS Edge Worker")
    await orchestrator.stop()
    await plugin_loader.shutdown_all()
    await redis_bus.disconnect()


app = FastAPI(
    title="VMS Edge Worker",
    description="Worker Node para processamento de IA em streams de vídeo",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "service": "VMS Edge Worker",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check da aplicação"""
    orchestrator = app_state.get('orchestrator')
    
    if not orchestrator:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "reason": "orchestrator not initialized"}
        )
    
    status = await orchestrator.get_status()
    
    return {
        "status": "healthy" if status['running'] else "unhealthy",
        "orchestrator": status
    }


@app.get("/services")
async def list_services():
    """Lista serviços de IA carregados"""
    plugin_loader = app_state.get('plugin_loader')
    
    if not plugin_loader:
        return {"services": []}
    
    services_info = []
    for name, service in plugin_loader.loaded_services.items():
        health = await service.health_check()
        services_info.append({
            "name": name,
            "version": service.version,
            "health": health
        })
    
    return {"services": services_info}


@app.get("/streams")
async def list_streams():
    """Lista streams ativos"""
    orchestrator = app_state.get('orchestrator')
    
    if not orchestrator:
        return {"streams": []}
    
    streams = []
    for camera_id, stream in orchestrator.mediamtx.active_streams.items():
        streams.append({
            "camera_id": camera_id,
            "name": stream.name,
            "instance_id": stream.instance_id,
            "rtsp_url": stream.rtsp_url,
            "ready": stream.ready
        })
    
    return {"streams": streams, "total": len(streams)}


@app.post("/reload-services")
async def reload_services():
    """Recarrega serviços dinamicamente"""
    plugin_loader = app_state.get('plugin_loader')
    
    if not plugin_loader:
        return JSONResponse(
            status_code=503,
            content={"error": "plugin_loader not initialized"}
        )
    
    # Desliga serviços atuais
    await plugin_loader.shutdown_all()
    
    # Recarrega
    services = await plugin_loader.load_all_services(settings.SERVICES_CONFIG)
    
    return {
        "message": "Services reloaded",
        "services": list(services.keys())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
