"""Authentication API, usable independently of the agent/LLM runtime."""
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import service
from .mailer import MailDeliveryError, smtp_config

router = APIRouter(prefix='/api/auth', tags=['auth'])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class CodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    purpose: Literal['register', 'reset_password', 'bind_email']


class RegisterRequest(LoginRequest):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=1, max_length=6)


class ResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=1, max_length=6)
    password: str = Field(min_length=1, max_length=128)


def bearer(request: Request) -> str:
    scheme, _, value = request.headers.get('authorization', '').partition(' ')
    return value if scheme.lower() == 'bearer' else ''


def invoke(operation):
    try:
        result = operation()
        return JSONResponse(result or {'success': True}, headers={'Cache-Control': 'no-store'})
    except service.AuthError as exc:
        headers = {'Cache-Control': 'no-store'}
        if exc.retry_after:
            headers['Retry-After'] = str(exc.retry_after)
        return JSONResponse({'success': False, 'error': str(exc), 'retry_after': exc.retry_after}, status_code=exc.status, headers=headers)
    except MailDeliveryError as exc:
        return JSONResponse({'success': False, 'error': str(exc)}, status_code=503, headers={'Cache-Control': 'no-store'})
    except Exception:
        logging.getLogger(__name__).error('Authentication storage unavailable', exc_info=True)
        return JSONResponse({'success': False, 'error': '账户服务暂时不可用，请稍后重试'}, status_code=503, headers={'Cache-Control': 'no-store'})


def ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


@router.post('/send-code')
def send_code(body: CodeRequest, request: Request, background: BackgroundTasks):
    def operation():
        smtp_config()  # Fail visibly if SMTP has not been configured.
        owner = ''
        if body.purpose == 'bind_email':
            user = service.session_user(bearer(request))
            if not user:
                raise service.AuthError('请先登录', 401)
            owner = user['user_id']
        challenge = service.request_code(body.email, body.purpose, ip(request), owner)
        background.add_task(service.deliver_code, challenge)
        return {'success': True, 'message': '请求已提交；若邮箱符合条件，您将收到验证码，请检查收件箱及垃圾邮件。', 'retry_after': service.RESEND_SECONDS, 'expires_in': service.CODE_TTL}
    return invoke(operation)


@router.post('/register')
def register(body: RegisterRequest, request: Request):
    return invoke(lambda: service.register(body.username, body.password, body.email, body.code, ip(request)))


@router.post('/login')
def login(body: LoginRequest, request: Request):
    return invoke(lambda: service.login(body.username, body.password, ip(request)))


@router.post('/reset-password')
def reset_password(body: ResetRequest, request: Request):
    return invoke(lambda: service.reset_password(body.email, body.code, body.password, ip(request)))


@router.get('/me')
def me(request: Request):
    def operation():
        user = service.session_user(bearer(request))
        if not user:
            raise service.AuthError('会话已失效，请重新登录', 401)
        return dict(success=True, **user)
    return invoke(operation)


@router.post('/logout')
def logout(request: Request):
    return invoke(lambda: service.logout(bearer(request)))


@router.post('/bind-email')
def bind_email(body: ResetRequest, request: Request):
    def operation():
        user = service.session_user(bearer(request))
        if not user:
            raise service.AuthError('会话已失效，请重新登录', 401)
        return service.bind_email(user['user_id'], body.email, body.code, body.password, ip(request))
    return invoke(operation)
