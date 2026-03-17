"""Endpoint de autenticação do MediaMTX.

MediaMTX chama POST /streaming/auth/ para cada tentativa de conexão.
- read / playback: sempre permitido (controle feito pelo frontend via JWT)
- publish: valida HMAC-SHA256(path, MEDIAMTX_PUBLISH_SECRET)
- api / metrics: sempre permitido (chamadas internas do Docker)
"""
import hashlib
import hmac
import logging
import os
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["streaming-auth"])

_SECRET = os.environ.get("MEDIAMTX_PUBLISH_SECRET", "")


class AuthRequest(BaseModel):
    """Payload enviado pelo MediaMTX para validar cada conexão."""

    user: str = ""
    password: str = ""
    ip: str = ""
    action: Literal["read", "publish", "playback", "api", "metrics", "pprof"] = "read"
    path: str = ""
    protocol: str = ""
    id: str = ""
    query: str = ""


def _expected_token(path: str) -> str:
    """Gera token HMAC-SHA256 para um path específico."""
    return hmac.new(_SECRET.encode(), path.encode(), hashlib.sha256).hexdigest()[:24]


@router.post("/streaming/auth/")
async def streaming_auth(req: AuthRequest) -> Response:
    """Valida cada tentativa de conexão ao MediaMTX.

    Retorna 200 para permitir ou 401 para negar.
    """
    # Leitura e controle são sempre permitidos
    if req.action in ("read", "playback", "api", "metrics", "pprof"):
        return Response(status_code=200)

    # Publish: valida token
    if req.action == "publish":
        if not _SECRET:
            logger.warning(
                "MEDIAMTX_PUBLISH_SECRET não configurado — publish negado para path '%s'",
                req.path,
            )
            return Response(status_code=401)

        expected = _expected_token(req.path)
        if hmac.compare_digest(req.password, expected):
            logger.info("Publish autorizado: path='%s' ip=%s", req.path, req.ip)
            return Response(status_code=200)

        logger.warning(
            "Publish negado: path='%s' ip=%s token_inválido",
            req.path,
            req.ip,
        )
        return Response(status_code=401)

    return Response(status_code=401)
