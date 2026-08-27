"""Structured adapter for lithium-battery factory energy forecasting."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator


DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出点预测、置信区间、能耗趋势解读、环比变化、单位产量能耗以及主要能耗风险提示。"
)


class FactoryEnergyForecastParams(BaseModel):
    model: str = "sundial"
    granularity: str = "月度"
    horizon: int = Field(default=6, ge=1, le=90)
    energy_segments: List[str] = Field(default_factory=list)
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
        if value not in {"日度", "周度", "月度"}:
            raise ValueError("granularity must be 日度、周度 or 月度")
        return value


def _join_or_default(values: List[str], default: str) -> str:
    return "、".join(values) if values else default


def build_query(raw_params: Dict[str, Any]) -> str:
    params = FactoryEnergyForecastParams.model_validate(raw_params)
    period_unit = {"日度": "天", "周度": "周", "月度": "月"}[params.granularity]
    segments = _join_or_default(params.energy_segments, "总计(千度)")
    external_variables = _join_or_default(
        params.external_variables,
        "不指定，由系统根据数据字段自动判断",
    )
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS

    return "\n".join([
        "请执行锂电工厂能耗时间序列预测任务。",
        f"预测目标：锂电工厂能耗；指定预测模型：{params.model}；时间粒度：{params.granularity}。",
        f"预测未来 {params.horizon} 个{period_unit}。",
        f"分析维度：{segments}。",
        f"可参考的外生变量：{external_variables}。",
        f"补充要求：{extra}。",
    ])
