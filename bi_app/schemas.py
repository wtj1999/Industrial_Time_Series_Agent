"""Request and response boundary models for the remote BI service."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BiQueryRequest(BaseModel):
    query: str = Field(default="", max_length=10_000)
    thread_id: str = Field(min_length=1, max_length=200)
    resume: dict[str, list[str]] | None = None

    @model_validator(mode="after")
    def require_query_or_resume(self) -> "BiQueryRequest":
        self.query = self.query.strip()
        if not self.query and self.resume is None:
            raise ValueError("query 与 resume 至少需要提供一个")
        return self


class RemoteBiResponse(BaseModel):
    """Validate the stable envelope while preserving remote extensions."""

    model_config = ConfigDict(extra="allow")

    status: str
    type: str | None = None
    thread_id: str = Field(min_length=1)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

