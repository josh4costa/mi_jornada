"""app/core/limiter.py  —  NUEVO

El Limiter vivia dentro de auth.py y nunca se registraba en app.state, por lo que
al superarse el limite el handler de slowapi truena con 500 en vez de responder 429.

Ademas get_remote_address() ve la IP del proxy: detras de Traefik TODOS los usuarios
comparten el mismo cubo de 5 intentos / 15 min (un solo atacante bloquea el login de
toda la empresa). Aqui se resuelve la IP real contando saltos de proxy confiables.
"""
from slowapi import Limiter
from starlette.requests import Request

from app.core.config import settings


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            # El ultimo elemento lo agrega el proxy mas cercano al backend.
            # Con N saltos confiables, la IP real esta N posiciones antes del final.
            idx = max(len(parts) - max(settings.TRUSTED_PROXY_HOPS, 1), 0)
            return parts[idx]
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip, headers_enabled=True)
