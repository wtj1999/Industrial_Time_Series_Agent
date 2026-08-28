"""Structured adapter for the lithium-battery raw-material price forecast application."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出点预测、置信区间、价格趋势解读、周期涨跌幅、供需驱动因素以及主要价格风险提示。"
)

ALLOWED_MODELS = {
    "sundial", "toto-2", "timer-s1", "chronos-2", "timesfm-2.5",
    "moirai-2.0", "tirex-1.1",
}


class RawMaterialPriceForecastParams(BaseModel):
    model: str = "sundial"
    granularity: str = "月度"
    horizon: int = Field(default=6, ge=1, le=90)
    material_categories: List[str] = Field(default_factory=list)
    external_variables: List[str] = Field(default_factory=list)
    additional_requirements: str = Field(
        default=DEFAULT_ADDITIONAL_REQUIREMENTS,
        max_length=500,
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if value not in ALLOWED_MODELS:
            raise ValueError("unsupported prediction model")
        return value

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, value: str) -> str:
        if value not in {"日度", "周度", "月度"}:
            raise ValueError("granularity must be 日度, 周度 or 月度")
        return value


def _join_or_default(values: List[str], default: str) -> str:
    return "、".join(values) if values else default


def build_query(raw_params: Dict[str, Any]) -> str:
    params = RawMaterialPriceForecastParams.model_validate(raw_params)
    period_unit = {"日度": "天", "周度": "周", "月度": "个月"}[params.granularity]
    categories = _join_or_default(params.material_categories, "全部原材料")
    external_variables = _join_or_default(
        params.external_variables,
        "不指定，由系统根据数据字段自动判断",
    )
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS

    return "\n".join([
        "请执行锂电原材料价格时间序列预测任务。",
        f"预测目标：锂电原材料价格；指定预测模型：{params.model}；时间粒度：{params.granularity}。",
        f"预测未来 {params.horizon} {period_unit}。",
        f"原材料品类：{categories}。",
        f"可参考的外生变量：{external_variables}。",
        f"补充要求：{extra}。",
    ])
