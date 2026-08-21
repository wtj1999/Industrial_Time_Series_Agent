"""Structured adapter for lithium coating areal-density anomaly detection."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator


DETECTION_INTENTS = {
    "瞬时突变检测": "重点识别突然升高、突然降低、尖峰和跌落。",
    "局部形态异常检测": "重点识别一段时间内偏离正常生产模式的局部波形。",
    "多分区协同异常检测": "联合多个横向分区识别同步异常、局部失衡和组合模式异常。",
    "连续异常区间检测": "聚合连续异常点，定位异常开始、结束和持续时间。",
    "分区异常贡献分析": "在检测异常样本后，分析主要驱动分区及其偏高或偏低方向。",
    "综合异常诊断": "最多选择三个互补步骤，完成时序检测、异常区间定位和分区贡献诊断。",
}

AUTO_MODELS = {
    "瞬时突变检测": "SpectralResidual",
    "局部形态异常检测": "MatrixProfile",
    "多分区协同异常检测": "TimeSeriesOD + ECOD",
    "连续异常区间检测": "SAND",
    "分区异常贡献分析": "TimeSeriesOD + ECOD",
    "综合异常诊断": "SAND",
}

ALLOWED_MODELS = {
    "自动推荐", "SpectralResidual", "MatrixProfile", "SAND",
    "TimeSeriesOD + ECOD", "TimeSeriesOD + IForest",
    "LSTMAD", "AnomalyTransformer",
}
ALLOWED_SCOPES = {"A面分区", "A+B双面分区", "全部面密度分区"}

DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出异常时间点、连续异常区间、异常分数、判定阈值、Top异常样本、"
    "主要异常分区、异常方向、可能原因、生产影响和建议排查项；"
    "优先生成异常分数时序图，并区分瞬时异常与持续异常。"
)


class CoatingArealDensityAnomalyParams(BaseModel):
    detection_task: str = "瞬时突变检测"
    coating_scopes: List[str] = Field(default_factory=lambda: ["A+B双面分区"])
    model: str = "自动推荐"
    contamination: float = Field(default=0.01, gt=0, le=0.5)
    window_size: int = Field(default=30, ge=2, le=5000)
    return_top_n: int = Field(default=20, ge=1, le=100)
    random_state: int = 42
    additional_requirements: str = Field(
        default=DEFAULT_ADDITIONAL_REQUIREMENTS,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.detection_task not in DETECTION_INTENTS:
            raise ValueError("unsupported detection task")
        if self.model not in ALLOWED_MODELS:
            raise ValueError("unsupported anomaly detector")
        if not self.coating_scopes:
            raise ValueError("at least one coating scope is required")
        if any(scope not in ALLOWED_SCOPES for scope in self.coating_scopes):
            raise ValueError("unsupported coating scope")
        return self


def build_query(raw_params: Dict[str, Any]) -> str:
    params = CoatingArealDensityAnomalyParams.model_validate(raw_params)
    scopes = "、".join(params.coating_scopes)
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS
    model = (
        f"自动推荐（{AUTO_MODELS[params.detection_task]}）"
        if params.model == "自动推荐"
        else params.model
    )
    resolved_model = AUTO_MODELS[params.detection_task] if params.model == "自动推荐" else params.model
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
    return "\n".join([
        "请执行锂电涂布面密度时序异常检测任务。",
        f"主检测任务：{params.detection_task}；{DETECTION_INTENTS[params.detection_task]}",
        f"检测范围：{scopes}。",
        f"异常检测模型：{model}。",
        f"检测参数：{'；'.join(parameter_parts)}。",
        f"补充要求：{extra}",
    ])
