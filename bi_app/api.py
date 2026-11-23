"""Standalone FastAPI service for the production BI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Response
from .analysis import attach_analysis, close_analyzer

from .client import BiRemoteClient, BiUpstreamError
from .config import get_settings
from .auth import BiAuthMiddleware, new_account_client
from .schemas import BiQueryRequest, RemoteBiResponse
from .ng.api import close_ng_service, router as ng_router
from .control_plan import router as control_plan_router
from .sessions import router as sessions_router, failed_operation
from .session_store import get_bi_sessions, scope

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_bi_sessions()
    async with new_account_client() as client:
        app.state.bi_account_client = client
        try:
            yield
        finally:
            app.state.bi_account_client = None
            close_ng_service()
            await close_analyzer()


app = FastAPI(
    title="Production BI Service",
    version="1.1.0",
    description="Remote production BI adapter and local NG analytics with resumable confirmation.",
    lifespan=lifespan,
)
app.include_router(ng_router)
app.include_router(control_plan_router)
app.include_router(sessions_router)
app.add_middleware(BiAuthMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "production-bi"}


@app.post("/api/bi/query")
async def query_bi(request: BiQueryRequest, response: Response, x_user_id: str = Header(default='', alias='X-User-Id')) -> dict[str, object]:
    history = get_bi_sessions()
    operation = history.begin(x_user_id, request.thread_id, scope(f'{request.domain or "manufacturing"}-bi-analysis', tenant_id=request.tenant_id),
                              query=request.query, selection=request.resume)
    response.headers['X-BI-Session-ID'] = operation['session_id']
    payload = request.model_dump(exclude_none=True, exclude={'domain', 'analysis_query'})
    payload['thread_id'] = 'bi-' + operation['session_id']
    client = BiRemoteClient(get_settings())
    try:
        raw_response = await client.query(payload)
        result = RemoteBiResponse.model_validate(raw_response).as_dict()
    except BiUpstreamError as exc:
        logger.warning("Production BI upstream request failed: %s", exc)
        error = HTTPException(status_code=exc.status_code, detail=str(exc))
        failed_operation(history, operation, error)
        raise error from exc
    except ValueError as exc:
        logger.warning("Production BI upstream schema validation failed: %s", exc)
        error = HTTPException(status_code=502, detail="生产 BI 服务响应缺少必要字段")
        failed_operation(history, operation, error)
        raise error from exc
    except Exception as exc:
        error = HTTPException(status_code=502, detail="生产 BI 服务暂时无法完成，请稍后重试")
        failed_operation(history, operation, error)
        raise error from exc
    result['thread_id'] = request.thread_id
    if isinstance(result.get('confirm'), dict) and 'thread_id' in result['confirm']:
        result['confirm']['thread_id'] = request.thread_id
    try:
        result = await attach_analysis(request, result, x_user_id)
        history.finish(operation, result)
    except Exception as exc:
        failed_operation(history, operation, exc)
        raise
    return result

