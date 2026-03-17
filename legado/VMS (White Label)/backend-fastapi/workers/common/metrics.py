"""Shared Prometheus metrics server for VMS workers.

Usage in any worker:
    from common.metrics import start_metrics_server, REGISTRY
    # At startup:
    await start_metrics_server(port=9100)

    # Or use the health-aware version:
    from common.metrics import MetricsServer
    server = MetricsServer(port=9100)
    server.register_health_check('rabbitmq', check_rabbitmq)
    server.register_health_check('redis', check_redis)
    await server.start()
"""

import asyncio
import time
from aiohttp import web
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, Histogram, Info,
    generate_latest, CONTENT_TYPE_LATEST,
)

REGISTRY = CollectorRegistry()

# ── Common metrics (used across workers) ──────────────────────
worker_info = Info('worker', 'Worker metadata', registry=REGISTRY)
worker_up = Gauge('worker_up', 'Worker is running', ['worker_name'], registry=REGISTRY)
worker_start_time = Gauge('worker_start_time_seconds', 'Worker start timestamp', registry=REGISTRY)

messages_consumed_total = Counter(
    'messages_consumed_total', 'Total messages consumed from RabbitMQ',
    ['worker', 'queue'], registry=REGISTRY,
)
messages_failed_total = Counter(
    'messages_failed_total', 'Total messages that failed processing',
    ['worker', 'queue'], registry=REGISTRY,
)
message_processing_seconds = Histogram(
    'message_processing_seconds', 'Message processing duration',
    ['worker'], registry=REGISTRY,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
events_published_total = Counter(
    'events_published_total', 'Total events published to RabbitMQ',
    ['worker', 'event_type'], registry=REGISTRY,
)


class MetricsServer:
    """Lightweight HTTP server for /metrics and /health endpoints."""

    def __init__(self, port: int = 9100, worker_name: str = ''):
        self.port = port
        self.worker_name = worker_name
        self._health_checks: dict[str, callable] = {}
        self._app = web.Application()
        self._app.router.add_get('/metrics', self._handle_metrics)
        self._app.router.add_get('/health', self._handle_health)
        worker_start_time.set(time.time())
        if worker_name:
            worker_info.info({'name': worker_name})
            worker_up.labels(worker_name=worker_name).set(1)

    def register_health_check(self, name: str, check_fn):
        """Register an async health check function. Should return True/False."""
        self._health_checks[name] = check_fn

    async def _handle_metrics(self, request):
        metrics = generate_latest(REGISTRY)
        # CONTENT_TYPE_LATEST contains "charset=utf-8" which aiohttp forbids in
        # content_type; pass it as a raw header instead.
        return web.Response(
            body=metrics,
            headers={'Content-Type': CONTENT_TYPE_LATEST},
        )

    async def _handle_health(self, request):
        checks = {}
        healthy = True
        for name, check_fn in self._health_checks.items():
            try:
                result = await check_fn() if asyncio.iscoroutinefunction(check_fn) else check_fn()
                checks[name] = 'ok' if result else 'fail'
                if not result:
                    healthy = False
            except Exception as e:
                checks[name] = f'error: {str(e)}'
                healthy = False

        status = 200 if healthy else 503
        import json
        return web.Response(
            body=json.dumps({'status': 'healthy' if healthy else 'unhealthy', 'checks': checks}),
            content_type='application/json',
            status=status,
        )

    async def start(self):
        runner = web.AppRunner(self._app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()
        print(f'[Metrics] Server listening on :{self.port} (/metrics, /health)', flush=True)


async def start_metrics_server(port: int = 9100, worker_name: str = '') -> MetricsServer:
    """Quick-start metrics server without health checks."""
    server = MetricsServer(port=port, worker_name=worker_name)
    await server.start()
    return server
