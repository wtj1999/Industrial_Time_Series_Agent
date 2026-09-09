"""Configuration for the standalone production BI proxy service."""

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class BiSettings(BaseModel):
    """Small env-backed configuration with no dependency on ``agent_app``."""

    remote_query_url: str = Field(default="http://10.11.88.106:19052/api/query")
    connect_timeout_seconds: float = Field(default=10.0, gt=0)
    request_timeout_seconds: float = Field(default=180.0, gt=0)


@lru_cache
def get_settings() -> BiSettings:
    return BiSettings(
        remote_query_url=os.getenv(
            "BI_REMOTE_QUERY_URL", "http://10.11.88.106:19052/api/query"
        ),
        connect_timeout_seconds=float(os.getenv("BI_CONNECT_TIMEOUT_SECONDS", "10")),
        request_timeout_seconds=float(os.getenv("BI_REQUEST_TIMEOUT_SECONDS", "180")),
    )
