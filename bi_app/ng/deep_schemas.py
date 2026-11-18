"""The model and browser select catalog IDs, never SQL identifiers."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .config import DEFAULT_NG_FACTORY

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=250)]


class DeepBaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    factory_id: str = Field(default=DEFAULT_NG_FACTORY, pattern=r"^[a-z0-9-]+$", max_length=80)
    thread_id: str = Field(min_length=1, max_length=200)


class DeepRecommendRequest(DeepBaseRequest):
    source_id: Identifier
    row_index: int = Field(ge=0, le=1000000)


class DeepAnalyzeRequest(DeepBaseRequest):
    plan_id: Identifier
    target_id: Identifier
    feature_ids: list[Identifier] = Field(min_length=1, max_length=100)


class FieldChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: Identifier
    reason: str = Field(min_length=1, max_length=400)


class DeepFieldRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: FieldChoice
    features: list[FieldChoice] = Field(min_length=1, max_length=100)
