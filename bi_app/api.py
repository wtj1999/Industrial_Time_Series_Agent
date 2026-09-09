"""Standalone FastAPI service for the production BI application."""

import logging

from fastapi import FastAPI, HTTPException

from .client import BiRemoteClient, BiUpstreamError
from .config import get_settings
from .schemas import BiQueryRequest, RemoteBiResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Production BI Adapter",
    version="1.0.0",
    description="Independent adapter for the remote production BI application.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "production-bi"}


@app.post("/api/bi/query")
async def query_bi(request: BiQueryRequest) -> dict[str, object]:
    payload = request.model_dump(exclude_none=True)
    client = BiRemoteClient(get_settings())
    try:
        raw_response = await client.query(payload)
        return RemoteBiResponse.model_validate(raw_response).as_dict()
    except BiUpstreamError as exc:
        logger.warning("Production BI upstream request failed: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Production BI upstream schema validation failed: %s", exc)
        raise HTTPException(status_code=502, detail="生产 BI 服务响应缺少必要字段") from exc

