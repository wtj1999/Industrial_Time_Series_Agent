"""Structured adapter for the new-energy-vehicle sales application."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出点预测、置信区间、趋势解读、同比或环比变化以及主要风险提示。"
)


class NewEnergyVehicleSalesParams(BaseModel):
    model: str = "sundial"
    granularity: str = "月度"
    horizon: int = Field(default=6, ge=1, le=36)
    vehicle_segments: List[str] = Field(default_factory=list)
    external_variables: List[str] = Field(default_factory=list)
    additional_requirements: str = Field(
        default=DEFAULT_ADDITIONAL_REQUIREMENTS,
        max_length=500,
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        if value not in {
            "sundial", "toto-2", "timer-s1", "chronos-2", "timesfm-2.5",
            "moirai-2.0", "tirex-1.1",
        }:
            raise ValueError("unsupported prediction model")
        return value

    @field_validator("granularity")
    @classmethod
    def validate_granularity(cls, value: str) -> str:
        if value not in {"月度", "季度"}:
            raise ValueError("granularity must be 月度 or 季度")
        return value


def _join_or_default(values: List[str], default: str) -> str:
    return "、".join(values) if values else default


def build_query(raw_params: Dict[str, Any]) -> str:
    params = NewEnergyVehicleSalesParams.model_validate(raw_params)
    period_unit = "月" if params.granularity == "月度" else "季度"
    segments = _join_or_default(params.vehicle_segments, "全部车型")
    external_variables = _join_or_default(
        params.external_variables,
        "不指定，由系统根据数据字段自动判断",
    )
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS

    return "\n".join([
        "请执行新能源汽车销量时间序列预测任务。",
        f"预测目标：新能源汽车销量；指定预测模型：{params.model}；时间粒度：{params.granularity}。",
        f"预测未来 {params.horizon} 个{period_unit}。",
        f"分析维度：{segments}。",
        f"可参考的外生变量：{external_variables}。",
        f"补充要求：{extra}。",
    ])
