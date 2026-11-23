"""Authenticated BI history endpoints, independent of the agent conversation API."""
import logging
from fastapi import APIRouter, Header, Query, HTTPException
from .session_store import get_bi_sessions

router = APIRouter(prefix='/api/bi/sessions', tags=['BI历史对话'])
logger = logging.getLogger(__name__)


@router.get('')
def list_bi_sessions(x_user_id: str = Header(alias='X-User-Id'), limit: int = Query(default=100, ge=1, le=200)):
    items = get_bi_sessions().list(x_user_id, limit)
    return {'sessions': items, 'total': len(items)}


@router.get('/{session_id}')
def read_bi_session(session_id: str, x_user_id: str = Header(alias='X-User-Id')):
    return get_bi_sessions().get(x_user_id, session_id)


@router.delete('/{session_id}')
def delete_bi_session(session_id: str, x_user_id: str = Header(alias='X-User-Id')):
    metadata = get_bi_sessions().delete(x_user_id, session_id)
    if metadata['app_id'] == 'ng-defect-analysis':
        from .ng.api import get_ng_service
        try:
            workflow = get_ng_service(metadata['factory_id'])
            config = workflow._config(metadata['thread_id'], x_user_id)
            with workflow._thread_lock(config['configurable']['thread_id']):
                workflow.checkpointer.delete_thread(config['configurable']['thread_id'])
        except Exception as exc:
            # History deletion is final even if an older workflow checkpoint cannot be cleaned.
            logger.warning('BI history checkpoint cleanup failed (%s)', type(exc).__name__)
    return {'success': True, 'session_id': session_id}


def failed_operation(store, operation, exc, prefix='查询未完成'):
    detail = exc.detail if isinstance(exc, HTTPException) and isinstance(exc.detail, str) else '服务暂时无法完成，请稍后重试'
    store.fail(operation, f'{prefix}：{detail}')
    if isinstance(exc, HTTPException):
        exc.headers = {**(exc.headers or {}), 'X-BI-Session-ID': operation['session_id']}
