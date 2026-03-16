"""Plugin loader — descobre plugins automaticamente em subpastas."""
import importlib
import logging
from pathlib import Path
from typing import Any

from .base import AnalyticsPlugin

logger = logging.getLogger(__name__)


def discover_plugins() -> dict[str, AnalyticsPlugin]:
    """Descobre e carrega todos os plugins disponíveis.

    Busca em cada subpasta de /plugins por um módulo plugin.py
    que contenha uma classe que herda AnalyticsPlugin.

    Returns:
        Dicionário {nome_do_plugin: instância}.
    """
    plugins: dict[str, AnalyticsPlugin] = {}
    plugins_dir = Path(__file__).parent

    for path in plugins_dir.iterdir():
        if not path.is_dir() or path.name.startswith("_"):
            continue
        plugin = _try_load_plugin(path.name)
        if plugin:
            plugins[plugin.name] = plugin

    logger.info("Loaded %d plugins: %s", len(plugins), list(plugins.keys()))
    return plugins


def _try_load_plugin(folder_name: str) -> AnalyticsPlugin | None:
    """Tenta carregar um plugin de uma pasta.

    Args:
        folder_name: Nome da pasta do plugin.

    Returns:
        Instância do plugin ou None se falhar.
    """
    try:
        module = importlib.import_module(f"plugins.{folder_name}.plugin")
        for attr in dir(module):
            obj = getattr(module, attr)
            if _is_plugin_class(obj):
                instance = obj()
                instance.on_load()
                return instance
    except Exception:
        logger.exception("Failed to load plugin: %s", folder_name)
    return None


def _is_plugin_class(obj: Any) -> bool:
    """Verifica se obj é uma subclasse concreta de AnalyticsPlugin."""
    return (
        isinstance(obj, type)
        and issubclass(obj, AnalyticsPlugin)
        and obj is not AnalyticsPlugin
    )
