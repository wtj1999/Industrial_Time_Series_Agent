from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from ..schemas import BiQueryRequest

FILTER_LABELS = {
    "tenant_id": "租户",
    "technics_line_name": "产线",
    "shift": "班次",
    "produce_order_code": "生产工单",
    "technics_process_name": "工序",
    "device_name": "设备",
}
GROUP_LABELS = {"shift_date": "日期", **FILTER_LABELS}
GroupName = Literal["ng_type", "shift_date", "tenant_id", "technics_line_name", "shift", "produce_order_code", "technics_process_name", "device_name"]
FilterName = Literal["tenant_id", "technics_line_name", "shift", "produce_order_code", "technics_process_name", "device_name"]
FilterValues = Annotated[list[Annotated[str, StringConstraints(min_length=1, max_length=500)]], Field(max_length=500)]


class NgFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: FilterValues = Field(default_factory=list)
    technics_line_name: FilterValues = Field(default_factory=list)
    shift: FilterValues = Field(default_factory=list)
    produce_order_code: FilterValues = Field(default_factory=list)
    technics_process_name: FilterValues = Field(default_factory=list)
    device_name: FilterValues = Field(default_factory=list)

    @field_validator("*")
    @classmethod
    def clean_values(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("筛选值不能为空")
        return list(dict.fromkeys(value.strip() for value in values))

    def nonempty(self) -> dict[str, list[str]]:
        return {key: values for key, values in self.model_dump().items() if values}


class NgParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date = Field(description="shift_date 起始日期，YYYY-MM-DD，包含当天")
    end_date: date = Field(description="shift_date 结束日期，YYYY-MM-DD，包含当天")
    filters: NgFilters = Field(default_factory=NgFilters)
    group_by: list[GroupName] = Field(default_factory=list, max_length=8,
        description="在固定ng_type分组之外增加的分组维度；每天用shift_date，每台设备用device_name，每道工序用technics_process_name；不指定则空数组")

    @field_validator("group_by")
    @classmethod
    def normalize_groups(cls, values: list[str]) -> list[str]:
        # ng_type is always present in the fixed template, including legacy requests.
        return list(dict.fromkeys(value for value in values if value != "ng_type"))

    @model_validator(mode="after")
    def ordered_dates(self) -> "NgParameters":
        if self.start_date > self.end_date:
            raise ValueError("起始日期不能晚于结束日期")
        return self


class ParsedNgIntent(NgParameters):
    filters: NgFilters = Field(default_factory=NgFilters, description="用户提到的筛选原话，尚未匹配数据库，不能直接用于统计查询")
    supported: bool = Field(default=True, description="是否为支持的NG数量查询，可按日期、设备、工序等白名单维度和NG类型组合分组")
    reason: str = Field(default="", max_length=500, description="不支持时说明需要用户补充什么")


class NgMatchDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_id: int = Field(ge=0)
    status: Literal["matched", "ambiguous", "unmatched"]
    candidate_ids: list[Annotated[int, Field(ge=0)]] = Field(default_factory=list, max_length=200)


class NgMatchingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decisions: list[NgMatchDecision] = Field(default_factory=list, max_length=100)


class NgQueryRequest(BiQueryRequest):
    model_config = ConfigDict(extra="forbid")
    confirmation_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_ng_request(self) -> "NgQueryRequest":
        if self.resume is not None:
            if self.query:
                raise ValueError("确认请求不能同时提供新问题")
            if not self.confirmation_id:
                raise ValueError("确认请求缺少 confirmation_id")
            self.resume = NgFilters.model_validate(self.resume).nonempty()
        elif self.confirmation_id:
            raise ValueError("新问题不能携带 confirmation_id")
        return self


class NgOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: str = Field(min_length=1, max_length=200)
    confirmation_id: str = Field(min_length=1, max_length=100)
    field: FilterName
    search: str = Field(default="", max_length=200)
    offset: int = Field(default=0, ge=0, le=1_000_000)
