"""Standalone FastAPI service for the production BI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header
from .analysis import attach_analysis, close_analyzer

from .client import BiRemoteClient, BiUpstreamError
from .config import get_settings
from .auth import BiAuthMiddleware
from .schemas import BiQueryRequest, RemoteBiResponse
from .ng.api import close_ng_service, router as ng_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_ng_service()
    await close_analyzer()


app = FastAPI(
    title="Production BI Service",
    version="1.1.0",
    description="Remote production BI adapter and local NG analytics with resumable confirmation.",
    lifespan=lifespan,
)
app.include_router(ng_router)
app.add_middleware(BiAuthMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "production-bi"}


@app.post("/api/bi/query")
async def query_bi(request: BiQueryRequest, x_user_id: str = Header(default='', alias='X-User-Id')) -> dict[str, object]:
    payload = request.model_dump(exclude_none=True, exclude={'domain', 'analysis_query'})
    client = BiRemoteClient(get_settings())
    try:
        raw_response = await client.query(payload)
        result = RemoteBiResponse.model_validate(raw_response).as_dict()
    except BiUpstreamError as exc:
        logger.warning("Production BI upstream request failed: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Production BI upstream schema validation failed: %s", exc)
        raise HTTPException(status_code=502, detail="生产 BI 服务响应缺少必要字段") from exc
    return await attach_analysis(request, result, x_user_id)

