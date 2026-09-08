"""Structured adapter for cycle-driven lithium-cell SOH forecasting."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


ALLOWED_MODELS = {
    "sundial", "toto-2", "timer-s1", "chronos-2", "timesfm-2.5",
    "moirai-2.0", "tirex-1.1",
}
ALLOWED_THRESHOLDS = {95, 90, 85, 80, 75, 70}
ALLOWED_CAPACITY_BASELINES = {"自动识别", "额定容量", "初始稳定容量"}
ALLOWED_CAPACITY_UNITS = {"Ah", "mAh"}

DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出容量衰减预测曲线、目标SOH的预计首次到达圈数、剩余可用圈数、"
    "置信区间、衰减趋势解读和主要不确定性；未可靠覆盖的阈值不要强行外推。"
)


class CellSohForecastParams(BaseModel):
    model: str = "sundial"
    soh_threshold: int = 80
    capacity_baseline: str = "自动识别"
    nominal_capacity: Optional[float] = Field(default=None, gt=0)
    capacity_unit: str = "Ah"
    additional_requirements: str = Field(
        default=DEFAULT_ADDITIONAL_REQUIREMENTS,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.model not in ALLOWED_MODELS:
            raise ValueError("unsupported prediction model")
        if self.soh_threshold not in ALLOWED_THRESHOLDS:
            raise ValueError("unsupported SOH threshold")
        if self.capacity_baseline not in ALLOWED_CAPACITY_BASELINES:
            raise ValueError("unsupported capacity baseline")
        if self.capacity_unit not in ALLOWED_CAPACITY_UNITS:
            raise ValueError("unsupported capacity unit")
        if self.capacity_baseline == "额定容量" and self.nominal_capacity is None:
            raise ValueError("nominal capacity is required when using rated capacity")
        return self


def build_query(raw_params: Dict[str, Any]) -> str:
    params = CellSohForecastParams.model_validate(raw_params)
    baseline = params.capacity_baseline
    if baseline == "额定容量":
        baseline = f"额定容量（{params.nominal_capacity:g} {params.capacity_unit}）"
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS

    return "\n".join([
        "请执行锂电电芯SOH时间序列预测任务。",
        "预测目标：基于历史容量衰减序列，预测电芯达到设定SOH阈值所需的循环圈数。",
        f"指定预测模型：{params.model}；SOH计算基准：{baseline}。",
        f"目标SOH阈值：{params.soh_threshold}%。",
        "历史数据范围：默认使用上传文件中的全部有效历史容量衰减序列，不主动截取最近窗口。",
        "以循环序号或圈数作为时间轴，根据所选基准计算SOH；数据中已有SOH列时优先复用并校验其口径。",
        "请根据历史容量衰减速度、近期趋势和已完成循环数，自行估算覆盖目标SOH所需的预测输出步长，并留出合理裕量；不要要求用户预先提供时间粒度或预测周期。若单次预测无法覆盖目标阈值，请分段续推，直到达到阈值或确认无法可靠外推。",
        f"补充要求：{extra}",
    ])
