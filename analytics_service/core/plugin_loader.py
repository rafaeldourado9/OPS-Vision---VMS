"""Plugin Loader — descobre e inicializa plugins em analytics/."""
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any

from analytics.base import AnalyticsPlugin

logger = logging.getLogger(__name__)

# Caminho padrão relativo ao diretório do serviço
_ANALYTICS_PATH = Path(__file__).resolve().parent.parent / "analytics"


class PluginLoader:
    """Varre analytics/ e carrega todas as implementações de AnalyticsPlugin."""

    def __init__(self, analytics_path: Path | None = None) -> None:
        self._path = analytics_path or _ANALYTICS_PATH
        self.plugins: dict[str, AnalyticsPlugin] = {}

    def _discover_classes(self) -> list[type[AnalyticsPlugin]]:
        """Varre subpastas de analytics/ e retorna classes concretas encontradas."""
        found: list[type[AnalyticsPlugin]] = []

        if not self._path.exists():
            logger.warning("Pasta de plugins não encontrada: %s", self._path)
            return found

        for item in sorted(self._path.iterdir()):
            if not item.is_dir() or item.name.startswith("_"):
                continue

            module_name = f"analytics.{item.name}.plugin"
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError:
                # Plugin pode não ter plugin.py — ignora silenciosamente
                continue
            except Exception as exc:
                logger.error("Erro ao importar %s: %s", module_name, exc)
                continue

            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, AnalyticsPlugin)
                    and obj is not AnalyticsPlugin
                    and not inspect.isabstract(obj)
                ):
                    found.append(obj)
                    logger.info("Plugin descoberto: %s", obj.__name__)

        return found

    async def load_all(self, config: dict[str, Any] | None = None) -> dict[str, AnalyticsPlugin]:
        """Instancia e inicializa todos os plugins descobertos.

        Args:
            config: Mapa {plugin_name: dict_config}. None usa config vazia para todos.

        Returns:
            Mapa {plugin.name: instância inicializada}.
        """
        config = config or {}
        classes = self._discover_classes()

        for PluginClass in classes:
            try:
                instance: AnalyticsPlugin = PluginClass()
                plugin_config = config.get(instance.name, {})
                await instance.initialize(plugin_config)
                self.plugins[instance.name] = instance
                logger.info(
                    "Plugin '%s' v%s carregado com sucesso",
                    instance.name,
                    instance.version,
                )
            except Exception as exc:
                logger.error(
                    "Falha ao inicializar plugin %s: %s", PluginClass.__name__, exc
                )

        return self.plugins

    async def shutdown_all(self) -> None:
        """Chama shutdown() em todos os plugins carregados."""
        for name, plugin in self.plugins.items():
            try:
                await plugin.shutdown()
                logger.info("Plugin '%s' encerrado", name)
            except Exception as exc:
                logger.error("Erro ao encerrar plugin '%s': %s", name, exc)
