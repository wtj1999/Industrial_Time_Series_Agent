"""Authenticated adapter for the remote Control Plan conversation protocol."""
import hashlib
import os
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .config import get_settings
from .control_plan_analysis import attach_control_plan_analysis

router = APIRouter(prefix='/api/bi/control-plan', tags=['control-plan'])


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    option_id: str | None = Field(default=None, min_length=1, max_length=500)
    option_ids: list[str] | None = Field(default=None, max_length=10000)

    @model_validator(mode='after')
    def one_form(self):
        if (self.option_id is None) == (self.option_ids is None):
            raise ValueError('需要提供 option_id 或 option_ids 其中一个')
        if self.option_ids is not None and any(not value or len(value) > 500 for value in self.option_ids):
            raise ValueError('无效的选项 ID')
        return self


class ControlPlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session_id: str = Field(min_length=1, max_length=200)
    query: str | None = Field(default=None, max_length=10000)
    analysis_query: str | None = Field(default=None, max_length=10000)
    confirm: Selection | None = None

    @model_validator(mode='after')
    def question_or_confirmation(self):
        self.query = self.query.strip() if self.query else None
        if bool(self.query) == (self.confirm is not None):
            raise ValueError('请提供问题或确认选项其中一个')
        return self


class Option(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(min_length=1, max_length=500)
    label: str
    detail: str = ''
    selected: bool = False


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='allow')
    selection_mode: Literal['single', 'multiple', 'multi'] = 'multiple'
    options: list[Option]
    preselect: list[str] = Field(default_factory=list)
    shown_count: int | None = Field(default=None, ge=0)
    page_size: int = Field(default=10, ge=1, le=100)
    total_count: int | None = Field(default=None, ge=0)


class ControlPlanResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    status: Literal['need_confirm', 'success', 'error']
    content_type: Literal['options', 'table', 'text'] | None = None
    empty: bool = False
    message: str = ''
    type: str = ''
    confirm: Confirmation | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    columns: dict[str, str] = Field(default_factory=dict)
    row_count: int | None = Field(default=None, ge=0)
    total_count: int | None = Field(default=None, ge=0)
    page_size: int = Field(default=10, ge=1, le=100)

    @model_validator(mode='after')
    def confirmation_required(self):
        if self.status == 'need_confirm' and self.confirm is None:
            raise ValueError('缺少确认选项')
        expected = {'need_confirm': 'options', 'success': 'table', 'error': 'text'}[self.status]
        if self.content_type is not None and self.content_type != expected:
            raise ValueError('响应内容类型与状态不匹配')
        self.content_type = expected
        if self.status == 'success':
            if self.empty and self.data:
                raise ValueError('空结果不应包含数据行')
            self.empty = not self.data
        return self


async def query_remote(payload: dict) -> dict:
    settings = get_settings()
    url = os.getenv('CONTROL_PLAN_QUERY_URL', 'http://10.2.96.249:8767/api/query')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.request_timeout_seconds, connect=settings.connect_timeout_seconds), trust_env=False) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise HTTPException(504, 'Control Plan 服务响应超时，请稍后重试') from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f'Control Plan 服务返回异常状态（{exc.response.status_code}）') from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, '暂时无法连接 Control Plan 服务') from exc
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(502, 'Control Plan 服务响应格式不正确') from exc


@router.post('/query')
async def query_control_plan(request: ControlPlanRequest, x_user_id: str = Header(alias='X-User-Id')):
    # The same client session cannot address another account's remote conversation.
    remote_id = 'cp-' + hashlib.sha256(f'{x_user_id}:{request.session_id}'.encode()).hexdigest()
    payload = request.model_dump(exclude_none=True, exclude={'analysis_query'})
    payload['session_id'] = remote_id
    if request.confirm is not None:
        # Accept the previous browser's single-choice form during rollout, but
        # always speak the new option_ids-only protocol to the remote service.
        payload['confirm'] = {'option_ids': request.confirm.option_ids if request.confirm.option_ids is not None else [request.confirm.option_id]}
    raw = await query_remote(payload)
    try:
        result = ControlPlanResponse.model_validate(raw).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise HTTPException(502, 'Control Plan 服务响应缺少必要字段或格式不正确') from exc
    result['session_id'] = result['thread_id'] = request.session_id
    if 'tenant_id' in raw:
        result['tenant_id'] = raw['tenant_id']
    if result.get('confirm'):
        confirmation = result['confirm']
        confirmation['session_id'] = confirmation['thread_id'] = request.session_id
        ids = {option['id'] for option in confirmation['options']}
        reply = confirmation.get('reply_with')
        fallback = reply.get('payload', {}).get('option_ids', []) if isinstance(reply, dict) and isinstance(reply.get('payload', {}), dict) else []
        if not isinstance(fallback, list):
            fallback = []
        initial = confirmation['preselect'] or [option['id'] for option in confirmation['options'] if option.get('selected')] or fallback
        confirmation['preselect'] = list(dict.fromkeys(value for value in initial if isinstance(value, str) and value in ids))
        confirmation['selection_mode'] = 'multiple'
        confirmation['shown_count'] = len(confirmation['options'])
        # Only the documented confirm payload is used; remote URLs/extra fields
        # never decide where the browser sends authenticated requests.
        confirmation.pop('reply_with', None)
    return await attach_control_plan_analysis(result, x_user_id, request.analysis_query or request.query or '')
