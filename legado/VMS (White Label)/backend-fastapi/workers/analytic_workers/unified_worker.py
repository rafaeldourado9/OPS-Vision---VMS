"""Unified analytic worker — runs all 10 analytic queues in a single process.

Instead of 10 separate containers each with their own AMQP connection and event
loop, this module starts one connection, declares all 10 queues, and routes each
message to the appropriate worker instance.  One MetricsServer serves metrics for
all workers on port 9100.
"""
import asyncio
import json
import os
import time as _time

import aio_pika
from common.metrics import (
    MetricsServer,
    messages_consumed_total,
    messages_failed_total,
    events_published_total,
)
from analytic_workers.base import BaseAnalyticWorker, analytic_events_processed, analytic_processing_seconds

from analytic_workers.crowd import CrowdWorker
from analytic_workers.intrusion import IntrusionWorker
from analytic_workers.object_detection import ObjectDetectionWorker
from analytic_workers.loitering import LoiteringWorker
from analytic_workers.abandoned_object import AbandonedObjectWorker
from analytic_workers.queue_analytic import QueueWorker
from analytic_workers.heatmap import HeatmapWorker
from analytic_workers.traffic import LineCrossingWorker, HumanTrafficWorker, VehicleTrafficWorker

RABBITMQ_URL = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@rabbitmq:5672/')


def _make_on_message(worker: BaseAnalyticWorker):
    """Return an aio_pika message handler bound to *worker*."""
    worker_name = worker.__class__.__name__
    queue_name = worker.queue_name

    async def on_message(message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                payload = json.loads(message.body)
                messages_consumed_total.labels(worker=worker_name, queue=queue_name).inc()
                t0 = _time.monotonic()
                await worker.process(payload)
                analytic_events_processed.labels(worker=worker_name).inc()
                analytic_processing_seconds.labels(worker=worker_name).observe(_time.monotonic() - t0)
            except Exception as e:
                messages_failed_total.labels(worker=worker_name, queue=queue_name).inc()
                import traceback
                print(f'[{worker_name}] Erro: {e}', flush=True)
                traceback.print_exc()

    return on_message


async def main():
    workers: list[BaseAnalyticWorker] = [
        CrowdWorker(),
        IntrusionWorker(),
        ObjectDetectionWorker(),
        LoiteringWorker(),
        AbandonedObjectWorker(),
        QueueWorker(),
        HeatmapWorker(),
        LineCrossingWorker(),
        HumanTrafficWorker(),
        VehicleTrafficWorker(),
    ]

    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=8)

    # Declare all queues and register consumers on the shared channel
    for worker in workers:
        queue = await channel.declare_queue(worker.queue_name, durable=True)
        await queue.consume(_make_on_message(worker))
        print(f'[UnifiedWorker] Consuming {worker.queue_name} ({worker.__class__.__name__})', flush=True)

    print('[UnifiedWorker] All 10 analytic queues active.', flush=True)

    server = MetricsServer(port=9100, worker_name='unified')
    await server.start()

    await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
