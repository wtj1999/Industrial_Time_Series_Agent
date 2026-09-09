"""HTTP client for the remote production BI API."""

import httpx

from .config import BiSettings


class BiUpstreamError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class BiRemoteClient:
    def __init__(self, settings: BiSettings) -> None:
        self._url = settings.remote_query_url
        self._timeout = httpx.Timeout(
            timeout=settings.request_timeout_seconds,
            connect=settings.connect_timeout_seconds,
        )

    async def query(self, payload: dict[str, object]) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise BiUpstreamError("生产 BI 服务响应超时，请稍后重试", 504) from exc
        except httpx.HTTPStatusError as exc:
            raise BiUpstreamError(
                f"生产 BI 服务返回异常状态 ({exc.response.status_code})"
            ) from exc
        except httpx.RequestError as exc:
            raise BiUpstreamError("暂时无法连接生产 BI 服务") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise BiUpstreamError("生产 BI 服务返回了无法解析的响应") from exc
        if not isinstance(body, dict):
            raise BiUpstreamError("生产 BI 服务响应格式不正确")
        return body

