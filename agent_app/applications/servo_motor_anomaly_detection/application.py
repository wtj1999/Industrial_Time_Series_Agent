"""Structured adapter for lithium-battery servo-motor anomaly detection."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator


ALLOWED_TARGETS = {
    "电机转速", "输出扭矩", "驱动电流", "母线电压",
    "电机温度", "振动幅值", "位置跟随误差", "编码器位置",
}
ALLOWED_MODELS = {
    "自动推荐", "SpectralResidual", "MatrixProfile", "SAND",
    "TimeSeriesOD + ECOD", "TimeSeriesOD + IForest",
    "LSTMAD", "AnomalyTransformer",
}
DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出异常时间点、连续异常区间、异常分数、判定阈值、Top异常样本、"
    "主要异常特征、异常方向、可能故障模式、设备影响和建议排查项；"
    "优先生成异常分数时序图，并区分瞬时异常与持续异常。"
)


class ServoMotorAnomalyParams(BaseModel):
    anomaly_targets: List[str] = Field(default_factory=lambda: ["驱动电流"])
    model: str = "自动推荐"
    contamination: float = Field(default=0.01, gt=0, le=0.5)
    window_size: int = Field(default=30, ge=2, le=5000)
    return_top_n: int = Field(default=20, ge=1, le=100)
    random_state: int = 42
    additional_requirements: str = Field(default=DEFAULT_ADDITIONAL_REQUIREMENTS, max_length=500)

    @model_validator(mode="after")
    def validate_configuration(self):
        if not self.anomaly_targets:
            raise ValueError("at least one anomaly target is required")
        if any(target not in ALLOWED_TARGETS for target in self.anomaly_targets):
            raise ValueError("unsupported anomaly target")
        if len(set(self.anomaly_targets)) != len(self.anomaly_targets):
            raise ValueError("duplicate anomaly target")
        if self.model not in ALLOWED_MODELS:
            raise ValueError("unsupported anomaly detector")
        return self


def build_query(raw_params: Dict[str, Any]) -> str:
    params = ServoMotorAnomalyParams.model_validate(raw_params)
    targets = "、".join(params.anomaly_targets)
    auto_model = "SpectralResidual" if len(params.anomaly_targets) == 1 else "TimeSeriesOD + ECOD"
    model = f"自动推荐（{auto_model}）" if params.model == "自动推荐" else params.model
    resolved_model = auto_model if params.model == "自动推荐" else params.model
    parameter_parts = [
        "按时序模式检测",
        f"预期异常比例={params.contamination * 100:.1f}%",
    ]
    if resolved_model != "SpectralResidual":
        parameter_parts.append(f"检测窗口={params.window_size} 个采样点")
    parameter_parts.extend([
        f"返回异常数量={params.return_top_n}",
        f"随机种子={params.random_state}",
    ])
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS

    return "\n".join([
        "请执行锂电伺服电机时序异常检测任务。",
        f"异常检测目标：{targets}。",
        "检测重点：识别目标特征的瞬时突变、持续偏移、周期形态异常及多特征协同异常。",
        f"异常检测模型：{model}。",
        f"检测参数：{'；'.join(parameter_parts)}。",
        f"补充要求：{extra}",
    ])
