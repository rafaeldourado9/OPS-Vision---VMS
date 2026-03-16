"""SSE — Server-Sent Events para atualizações em tempo real."""
import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sse"])

_DJANGO_INTERNAL_URL = os.environ.get("DJANGO_INTERNAL_URL", "http://django:8000")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_REALTIME_CHANNEL = "vms:realtime"


async def validate_token(token: str) -> dict[str, Any]:
    """Valida JWT chamando o endpoint /api/v1/auth/me/ do Django.

    Args:
        token: JWT enviado pelo cliente via query param.

    Returns:
        Dict com informações do usuário (id, tenant_id).

    Raises:
        HTTPException 401: Token inválido ou expirado.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{_DJANGO_INTERNAL_URL}/api/v1/auth/me/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0,
            )
        except httpx.RequestError as exc:
            logger.error("Erro ao contatar Django para validação de token: %s", exc)
            raise HTTPException(status_code=401, detail="Serviço de autenticação indisponível.")

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

    data = resp.json()
    return {"id": data.get("id"), "tenant_id": data.get("tenant", {}).get("id")}


async def subscribe_to_channel(
    channel: str,
    tenant_id: int,
) -> AsyncGenerator[str, None]:
    """Inscreve-se no canal Redis e filtra mensagens pelo tenant.

    Args:
        channel: Canal Redis a ouvir.
        tenant_id: Apenas mensagens deste tenant são repassadas.

    Yields:
        Strings JSON das mensagens filtradas.
    """
    redis_client = aioredis.from_url(_REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue

            if data.get("tenant_id") != tenant_id:
                continue

            yield json.dumps(data)
    finally:
        await pubsub.unsubscribe(channel)
        await redis_client.aclose()


def _format_sse(data: str) -> str:
    """Formata string no protocolo SSE."""
    return f"data: {data}\n\n"


@router.get("/sse/")
async def sse_stream(token: str = Query(default="")) -> StreamingResponse:
    """Stream de eventos em tempo real via Server-Sent Events.

    Clientes devem passar o JWT como query param ``?token=<jwt>`` pois
    o EventSource API do browser não suporta headers customizados.

    Returns:
        StreamingResponse com content-type ``text/event-stream``.

    Raises:
        HTTPException 401: Token ausente ou inválido.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Token obrigatório.")

    user = await validate_token(token)
    tenant_id: int = user["tenant_id"]

    async def event_generator() -> AsyncGenerator[str, None]:
        # Mensagem de conexão confirmada
        yield _format_sse(json.dumps({"type": "connected", "tenant_id": tenant_id}))

        async for message in subscribe_to_channel(_REALTIME_CHANNEL, tenant_id):
            yield _format_sse(message)
            await asyncio.sleep(0)  # cede o loop para outras coroutines

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # desativa buffering no nginx
        },
    )
