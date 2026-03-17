"""Rotas de controle de streams e verificação de tokens."""
import os
from urllib.parse import parse_qs

import jwt
from fastapi import APIRouter, Response
from pydantic import BaseModel

from services.stream_manager import list_active_streams

router = APIRouter(tags=["streaming"])


class MediaMTXAuthPayload(BaseModel):
    """Payload enviado pelo MediaMTX para verificação de autenticação.

    MediaMTX envia null (não string vazia) para campos ausentes,
    por isso todos os campos opcionais aceitam None.
    """

    action: str
    path: str = ""
    query: str | None = None
    protocol: str = ""
    user: str | None = None
    password: str | None = None
    ip: str = ""
    id: str = ""


@router.get("/streams/")
async def get_streams() -> dict[str, list]:
    """Lista todos os streams ativos no MediaMTX."""
    streams = await list_active_streams()
    return {"streams": streams}


@router.post("/streaming/token/verify/")
async def verify_stream_token(payload: MediaMTXAuthPayload, response: Response) -> dict:
    """Endpoint de verificação de autenticação chamado pelo MediaMTX.

    MediaMTX chama este endpoint antes de servir qualquer stream.
    Retorna 200 para permitir ou seta status 403 para negar.

    Regras:
    - action == "publish": câmeras IP publicam livremente (sem token).
    - action == "read"/"playback": exige token JWT válido no query param.
    - Token deve corresponder ao path (tenant-{id}/cam-{id}).
    """
    # Câmeras publicam livremente (não precisam de token)
    if payload.action == "publish":
        return {"status": "allowed"}

    # Extrai token da query string (ex: "token=abc123&other=val")
    token = _extract_token(payload.query)
    if not token:
        response.status_code = 403
        return {"status": "denied", "reason": "missing token"}

    secret_key = os.environ.get("DJANGO_SECRET_KEY", "INSECURE-change-me")

    try:
        claims = jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        response.status_code = 403
        return {"status": "denied", "reason": "token expired"}
    except jwt.InvalidTokenError:
        response.status_code = 403
        return {"status": "denied", "reason": "invalid token"}

    if claims.get("type") != "stream":
        response.status_code = 403
        return {"status": "denied", "reason": "invalid token type"}

    # Verifica que o path do request bate com o token
    expected_path = f"tenant-{claims['tenant_id']}/cam-{claims['camera_id']}"
    if payload.path != expected_path:
        response.status_code = 403
        return {"status": "denied", "reason": "path mismatch"}

    return {"status": "allowed"}


def _extract_token(query: str) -> str | None:
    """Extrai o valor do param 'token' da query string.

    Args:
        query: Query string (ex: "token=abc&foo=bar").

    Returns:
        Valor do token ou None se ausente.
    """
    if not query:
        return None
    params = parse_qs(query)
    values = params.get("token", [])
    return values[0] if values else None
