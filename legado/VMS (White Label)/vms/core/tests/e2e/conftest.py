"""Configuração para testes E2E."""
import time

import httpx
import pika
import pytest


@pytest.fixture(scope="session")
def docker_services():
    """Verifica que serviços Docker estão rodando."""
    services = {
        "postgres": ("postgres", 5432),
        "redis": ("redis", 6379),
        "rabbitmq": ("rabbitmq", 5672),
        "mediamtx": ("mediamtx", 9997),
    }

    # Aguarda serviços ficarem prontos
    max_retries = 30
    for service_name, (host, port) in services.items():
        for i in range(max_retries):
            try:
                if service_name == "mediamtx":
                    response = httpx.get(
                        f"http://{host}:{port}/v3/paths/list",
                        timeout=2.0,
                        auth=("mediamtx_api_user", "GtV!sionMed1aMTX$2025"),
                    )
                    if response.status_code == 200:
                        break
                elif service_name == "rabbitmq":
                    connection = pika.BlockingConnection(
                        pika.ConnectionParameters(
                            host=host,
                            port=port,
                            credentials=pika.PlainCredentials("vms", "change-me"),
                        )
                    )
                    connection.close()
                    break
                else:
                    # Para postgres e redis, apenas aguarda
                    time.sleep(1)
                    break
            except Exception:
                if i == max_retries - 1:
                    pytest.skip(f"Service {service_name} not ready — skipping E2E tests")
                time.sleep(1)

    yield services


@pytest.fixture(autouse=True)
def cleanup_mediamtx_paths():
    """Limpa paths do MediaMTX antes de cada teste E2E."""
    from shared.mediamtx_client import MediaMTXClient
    client = MediaMTXClient()
    try:
        paths = client.list_paths()
        for p in paths:
            try:
                client.remove_path(p.name)
            except Exception:
                pass
    except Exception:
        pass
    yield


@pytest.fixture(scope="session")
def mediamtx_client(docker_services):
    """Client HTTP para MediaMTX."""
    return httpx.Client(
        base_url="http://mediamtx:9997",
        timeout=5.0,
        auth=("mediamtx_api_user", "GtV!sionMed1aMTX$2025"),
    )


@pytest.fixture(scope="session")
def rabbitmq_connection(docker_services):
    """Conexão com RabbitMQ."""
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host="rabbitmq",
            port=5672,
            credentials=pika.PlainCredentials("vms", "change-me"),
        )
    )
    yield connection
    connection.close()


@pytest.fixture
def rabbitmq_channel(rabbitmq_connection):
    """Canal RabbitMQ para testes."""
    channel = rabbitmq_connection.channel()

    # Declara exchange
    channel.exchange_declare(
        exchange="vms_events",
        exchange_type="topic",
        durable=True,
    )

    yield channel

    # Cleanup
    try:
        channel.close()
    except:
        pass


@pytest.fixture
def event_consumer(rabbitmq_channel):
    """Consumer de eventos para testes."""
    events = []

    # Cria fila temporária
    result = rabbitmq_channel.queue_declare(queue="", exclusive=True)
    queue_name = result.method.queue

    # Bind para todos os eventos
    rabbitmq_channel.queue_bind(
        exchange="vms_events",
        queue=queue_name,
        routing_key="camera.*",
    )

    def callback(ch, method, properties, body):
        import json
        events.append({
            "type": method.routing_key,
            "payload": json.loads(body),
        })
        ch.basic_ack(delivery_tag=method.delivery_tag)

    rabbitmq_channel.basic_consume(
        queue=queue_name,
        on_message_callback=callback,
    )

    return {
        "channel": rabbitmq_channel,
        "events": events,
        "queue": queue_name,
    }


@pytest.fixture(autouse=True)
def setup_test_settings(settings):
    """Configura settings para testes E2E."""
    settings.MEDIAMTX_API_URL = "http://mediamtx:9997"
    settings.MEDIAMTX_STREAM_BASE_URL = "http://mediamtx:8889"
    settings.MEDIAMTX_API_USER = "mediamtx_api_user"
    settings.MEDIAMTX_API_PASSWORD = "GtV!sionMed1aMTX$2025"
    settings.RABBITMQ_HOST = "rabbitmq"
    settings.RABBITMQ_PORT = 5672
    settings.RABBITMQ_USER = "vms"
    settings.RABBITMQ_PASSWORD = "change-me"
