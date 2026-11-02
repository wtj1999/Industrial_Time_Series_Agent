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
    vehicle_segments: List[str] = Field(default_factory=list, description="品牌销量入口填写具体车型型号；行业入口可填写车型类别与动力类型")
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


def build_query(raw_params: Dict[str, Any], *, brand: str | None = None) -> str:
    params = NewEnergyVehicleSalesParams.model_validate(raw_params)
    if brand and any(value in {"BEV", "PHEV", "EREV", "乘用车", "商用车"} for value in params.vehicle_segments):
        raise ValueError("品牌销量预测请选择具体车型型号，不使用车型类别或动力类型")
    period_unit = "月" if params.granularity == "月度" else "季度"
    segments = _join_or_default(params.vehicle_segments, "全部车型")
    external_variables = _join_or_default(
        params.external_variables,
        "不指定，由系统根据数据字段自动判断",
    )
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS

    target = f"{brand}销量" if brand else "新能源汽车销量"
    brand_scope = [
        f"品牌范围：仅分析{brand}销量；若数据包含多个品牌，须确认并筛选对应品牌，不能以全行业销量或其他品牌销量代替。"
        "无法确认品牌范围或缺少对应数据时，请用户提供该品牌的历史销量数据，不编造数据。"
    ] if brand else []
    return "\n".join([
        f"请执行{target}时间序列预测任务。",
        f"预测目标：{target}；指定预测模型：{params.model}；时间粒度：{params.granularity}。",
        *brand_scope,
        f"预测未来 {params.horizon} 个{period_unit}。",
        f"{'车型型号' if brand else '分析维度'}：{segments}。",
        f"可参考的外生变量：{external_variables}。",
        f"补充要求：{extra}。",
    ])
