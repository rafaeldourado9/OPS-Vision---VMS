"""Abstração do RabbitMQ para event bus."""
import json
from typing import Any

import pika
from django.conf import settings


def publish_event(event_type: str, payload: dict[str, Any]) -> None:
    """Publica evento no RabbitMQ.

    Args:
        event_type: Tipo do evento (ex: "camera.created").
        payload: Dados do evento.
    """
    try:
        connection = _get_connection()
        channel = connection.channel()

        # Declara exchange
        channel.exchange_declare(
            exchange="vms_events",
            exchange_type="topic",
            durable=True,
        )

        # Publica mensagem
        channel.basic_publish(
            exchange="vms_events",
            routing_key=event_type,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistente
                content_type="application/json",
            ),
        )

        connection.close()
    except Exception as e:
        # Log error but don't fail the operation
        print(f"Failed to publish event {event_type}: {e}")


def subscribe(
    event_type: str,
    callback,
    queue_name: str | None = None,
) -> None:
    """Inscreve-se para receber eventos do RabbitMQ.

    Bloqueia a thread atual consumindo mensagens indefinidamente.
    Destina-se a ser executado em um processo/thread dedicado.

    Args:
        event_type: Padrão de routing key (ex: "camera.*").
        callback: Função chamada a cada mensagem recebida.
        queue_name: Nome da fila (auto-gerado se None).
    """
    connection = _get_connection()
    channel = connection.channel()

    channel.exchange_declare(
        exchange="vms_events",
        exchange_type="topic",
        durable=True,
    )

    result = channel.queue_declare(
        queue=queue_name or "",
        durable=bool(queue_name),
        exclusive=not bool(queue_name),
    )
    channel.queue_bind(
        exchange="vms_events",
        queue=result.method.queue,
        routing_key=event_type,
    )

    def _on_message(ch, method, properties, body):
        payload = json.loads(body)
        callback(payload)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(
        queue=result.method.queue,
        on_message_callback=_on_message,
    )
    channel.start_consuming()


def _get_connection() -> pika.BlockingConnection:
    """Cria conexão com RabbitMQ.
    
    Returns:
        Conexão ativa com RabbitMQ.
    """
    host = getattr(settings, "RABBITMQ_HOST", "localhost")
    port = getattr(settings, "RABBITMQ_PORT", 5672)
    user = getattr(settings, "RABBITMQ_USER", "guest")
    password = getattr(settings, "RABBITMQ_PASSWORD", "guest")

    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=pika.PlainCredentials(user, password),
        )
    )
