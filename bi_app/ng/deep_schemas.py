"""The model and browser select catalog IDs, never SQL identifiers."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .config import DEFAULT_NG_FACTORY

Identifier = Annotated[str, StringConstraints(min_length=1, max_length=250)]


class DeepBaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    factory_id: str = Field(default=DEFAULT_NG_FACTORY, pattern=r"^[a-z0-9-]+$", max_length=80)
    thread_id: str = Field(min_length=1, max_length=200)


class DeepRecommendRequest(DeepBaseRequest):
    source_id: Identifier
    row_index: int = Field(ge=0, le=1000000)
    display_message: str | None = Field(default=None, max_length=10000)


class DeepAnalyzeRequest(DeepBaseRequest):
    plan_id: Identifier
    target_id: Identifier
    feature_ids: list[Identifier] = Field(min_length=1, max_length=100)


class ValidationListRequest(DeepBaseRequest):
    analysis_id: Identifier


class QualityAuditRequest(ValidationListRequest):
    field_id: Identifier
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class ValidationRecordRequest(ValidationListRequest):
    field_id: Identifier
    quality_view: Literal["automatic_cleaned", "include_suspects", "exclude_suspects"] = "automatic_cleaned"
    hypothesis: str = Field(min_length=1, max_length=1500)
    action: str = Field(min_length=1, max_length=1500)
    controls: str = Field(min_length=1, max_length=1500)
    decision: Literal["planned", "supported", "refuted", "inconclusive"] = "planned"
    before_total: int | None = Field(default=None, ge=1, le=1000000000)
    before_ng: int | None = Field(default=None, ge=0, le=1000000000)
    after_total: int | None = Field(default=None, ge=1, le=1000000000)
    after_ng: int | None = Field(default=None, ge=0, le=1000000000)
    replicated: bool = False
    notes: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def counts_are_consistent(self):
        if not all(getattr(self,name).strip() for name in ("hypothesis","action","controls")):
            raise ValueError("假设、验证动作与保持条件不能为空白")
        for prefix in ("before", "after"):
            total, ng = getattr(self,prefix+"_total"),getattr(self,prefix+"_ng")
            if (total is None) != (ng is None) or total is not None and ng > total:
                raise ValueError("NG数与总数须成对提供，且NG数不能大于总数")
        if self.decision != "planned" and (self.before_total is None or self.after_total is None or not self.notes.strip()):
            raise ValueError("验证结论需填写前后NG/总数及验证说明")
        return self


class FieldChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field_id: Identifier
    reason: str = Field(min_length=1, max_length=400)


class DeepFieldRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: FieldChoice
    features: list[FieldChoice] = Field(min_length=1, max_length=100)
