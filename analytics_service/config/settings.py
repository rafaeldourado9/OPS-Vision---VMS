"""Configurações do analytics_service via variáveis de ambiente."""
import os


class Settings:
    # URL da API interna do MediaMTX (ex: http://mediamtx:9997)
    MEDIAMTX_URL: str = os.environ.get("MEDIAMTX_URL", "http://mediamtx:9997")
    MEDIAMTX_API_USER: str = os.environ.get("MEDIAMTX_API_USER", "")
    MEDIAMTX_API_PASSWORD: str = os.environ.get("MEDIAMTX_API_PASSWORD", "")

    # URL RTSP base do MediaMTX (ex: rtsp://mediamtx:8554)
    MEDIAMTX_RTSP_BASE_URL: str = os.environ.get(
        "MEDIAMTX_RTSP_BASE_URL", "rtsp://mediamtx:8554"
    )

    # URL interna do Django (ex: http://django:8000)
    DJANGO_INTERNAL_URL: str = os.environ.get(
        "DJANGO_INTERNAL_URL", "http://django:8000"
    )

    # API key interna (deve bater com ANALYTICS_SERVICE_API_KEY do Django)
    ANALYTICS_SERVICE_API_KEY: str = os.environ.get("ANALYTICS_SERVICE_API_KEY", "")

    # URL do Redis
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")

    # Frames por segundo capturados de cada câmera
    # 10 FPS = bom equilíbrio entre real-time e carga de CPU sem GPU
    # Para 15+ FPS recomenda-se GPU (CUDA/ROCm)
    FPS: int = int(os.environ.get("FPS", "10"))

    # Workers paralelos por plugin
    WORKERS_PER_PLUGIN: int = int(os.environ.get("WORKERS_PER_PLUGIN", "5"))

    # Threads do ThreadPoolExecutor para inferência CPU-bound
    # Recomendado: >= número de câmeras para evitar starving
    FRAME_EXECUTOR_WORKERS: int = int(os.environ.get("FRAME_EXECUTOR_WORKERS", "20"))

    # Profundidade máxima de fila por plugin antes de descartar frames (backpressure)
    # 20 câmeras × 2 FPS = 40 frames/s → manter ~1s de backlog
    MAX_QUEUE_DEPTH: int = int(os.environ.get("MAX_QUEUE_DEPTH", "40"))

    # TTL do cache de ROIs em segundos
    ROI_CACHE_TTL: int = int(os.environ.get("ROI_CACHE_TTL", "30"))

    # Caminho onde snapshots de frames são gravados
    SNAPSHOTS_PATH: str = os.environ.get("SNAPSHOTS_PATH", "/recordings/snapshots")


settings = Settings()
