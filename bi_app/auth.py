"""Validate BI sessions against the account service before accepting a namespace."""
import os
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def auth_service_url() -> str:
    """Older containers may not have the new Compose environment injected.

    Loopback is correct for local Python processes; in Docker the account
    service is a different container, reachable by its Compose service name.
    An explicit URL still takes precedence (including host-network setups).
    """
    configured = os.getenv('AUTH_SERVICE_URL', '').strip()
    base = configured or ('http://backend:8000' if Path('/.dockerenv').is_file() else 'http://127.0.0.1:8000')
    if any(ord(char) < 32 or ord(char) == 127 for char in base):
        raise ValueError('AUTH_SERVICE_URL contains control characters')
    parts = urlsplit(base)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('AUTH_SERVICE_URL must be an HTTP(S) service URL without credentials, query or fragment')
    if parts.port is not None and not 1 <= parts.port <= 65535:
        raise ValueError('AUTH_SERVICE_URL contains an invalid port')
    return base.rstrip('/')


def auth_me_url() -> str:
    base = auth_service_url()
    return base if base.endswith('/api/auth/me') else base + '/api/auth/me'


async def verify_bi_token(authorization: str) -> dict | None:
    scheme, _, token = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not token.strip() or len(authorization) > 263:
        return None
    endpoint = auth_me_url()
    async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
        response = await client.get(endpoint, headers={'Authorization': authorization})
    if response.status_code == 401:
        return None
    response.raise_for_status()
    user = response.json()
    if not isinstance(user, dict) or user.get('success') is not True or not isinstance(user.get('user_id'), str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', user['user_id']):
        raise ValueError('Invalid account service response')
    return user


class BiAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope.get('path', '').startswith('/api/bi/') or scope['method'] == 'OPTIONS':
            return await self.app(scope, receive, send)
        try:
            user = await verify_bi_token(Request(scope).headers.get('authorization', ''))
        except (httpx.HTTPError, ValueError) as exc:
            # Never log request headers, tokens, or an exception's raw body.
            try:
                endpoint = auth_me_url()
            except ValueError:
                endpoint = '<invalid AUTH_SERVICE_URL>'
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            logger.error('BI account validation failed: endpoint=%s exception_type=%s status=%s; check AUTH_SERVICE_URL, backend health and Docker network', endpoint, type(exc).__name__, status)
            message = '账户服务暂时不可用，请稍后重试'
            code = 'AUTH_SERVICE_UNAVAILABLE'
            if isinstance(exc, httpx.RequestError):
                message = '账户验证服务连接失败，请联系管理员检查服务连接'
                code = 'AUTH_SERVICE_UNREACHABLE'
            elif isinstance(exc, ValueError) or status == 404:
                message = '账户验证服务配置或响应异常，请联系管理员'
                code = 'AUTH_SERVICE_INVALID_RESPONSE'
            response = JSONResponse({'error': message, 'code': code}, status_code=503, headers={'Cache-Control': 'no-store'})
            return await response(scope, receive, send)
        if not user:
            response = JSONResponse({'error': '会话已失效，请重新登录'}, status_code=401)
            return await response(scope, receive, send)
        scope['headers'] = [(k, v) for k, v in scope['headers'] if k.lower() != b'x-user-id'] + [(b'x-user-id', user['user_id'].encode())]
        return await self.app(scope, receive, send)
