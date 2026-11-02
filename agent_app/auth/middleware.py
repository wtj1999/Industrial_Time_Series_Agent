"""Protect API routes and derive namespace headers from server-side sessions."""
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from .routes import bearer
from .service import session_user

PUBLIC = {'/api/auth/login', '/api/auth/register', '/api/auth/send-code', '/api/auth/reset-password', '/api/auth/logout'}


class SessionAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '').rstrip('/')
        if scope['type'] != 'http' or not path.startswith('/api/') or path in PUBLIC or scope['method'] == 'OPTIONS':
            return await self.app(scope, receive, send)
        try:
            user = await run_in_threadpool(session_user, bearer(Request(scope)))
        except Exception:
            response = JSONResponse({'success': False, 'error': '账户服务暂时不可用'}, status_code=503)
            return await response(scope, receive, send)
        if not user:
            response = JSONResponse({'success': False, 'error': '会话已失效，请重新登录'}, status_code=401, headers={'Cache-Control': 'no-store'})
            return await response(scope, receive, send)
        # Discard any client-supplied identity, including duplicate headers.
        scope['headers'] = [(k, v) for k, v in scope['headers'] if k.lower() != b'x-user-id'] + [(b'x-user-id', user['user_id'].encode())]
        return await self.app(scope, receive, send)
