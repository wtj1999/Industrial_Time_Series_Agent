"""Structured adapter for lithium coating areal-density analysis."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


ANALYSIS_INTENTS = {
    "稳定性评估": "评估面密度的过程稳定性、变异系数、滚动均值漂移和滚动波动。",
    "SPC控制图": "使用 SPC 控制图识别超控制限点及 Western Electric 规则违例。",
    "过程能力": "依据规格限分析 Cp/Cpk、Pp/Ppk 和潜在缺陷风险。",
    "趋势漂移": "分析面密度随时间的上升、下降或持续漂移趋势。",
    "均值变点": "检测面密度均值发生显著改变的时间位置和前后差异。",
    "波动变点": "检测面密度波动幅度突变和工况失稳的时间位置。",
    "异常点分析": "识别面密度中的单变量异常点、异常程度和集中区段。",
    "分区关联分析": "分析各横向分区面密度之间的相关关系和不同步分区。",
    "综合诊断": "进行综合诊断；最多选择三个互补分析，覆盖基线、稳定性及最高价值的异常证据。",
}

DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出核心结论、关键指标、异常或失稳位置、可能原因、业务影响和可执行建议。"
)


class CoatingArealDensityParams(BaseModel):
    analysis_mode: str = "稳定性评估"
    coating_scopes: List[str] = Field(default_factory=lambda: ["A面分区", "A+B双面分区"])
    window: int = Field(default=30, ge=2, le=5000)
    subgroup_size: int = Field(default=1, ge=1, le=1000)
    lsl: Optional[float] = None
    target: Optional[float] = None
    usl: Optional[float] = None
    additional_requirements: str = Field(
        default=DEFAULT_ADDITIONAL_REQUIREMENTS,
        max_length=500,
    )

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.analysis_mode not in ANALYSIS_INTENTS:
            raise ValueError("unsupported analysis mode")
        allowed_scopes = {"A面分区", "A+B双面分区", "全部面密度分区"}
        if any(scope not in allowed_scopes for scope in self.coating_scopes):
            raise ValueError("unsupported coating scope")
        if self.analysis_mode == "过程能力" and self.lsl is None and self.usl is None:
            raise ValueError("过程能力分析必须提供至少一个规格限")
        if self.lsl is not None and self.usl is not None and self.lsl >= self.usl:
            raise ValueError("规格下限必须小于规格上限")
        return self


def _format_number(value: Optional[float]) -> str:
    return "未设置" if value is None else f"{value:g}"


def build_query(raw_params: Dict[str, Any]) -> str:
    params = CoatingArealDensityParams.model_validate(raw_params)
    scopes = "、".join(params.coating_scopes) if params.coating_scopes else "全部面密度分区"
    extra = params.additional_requirements.strip() or DEFAULT_ADDITIONAL_REQUIREMENTS

    lines = [
        "请执行锂电涂布面密度时序分析任务。",
        f"主分析目标：{params.analysis_mode}；{ANALYSIS_INTENTS[params.analysis_mode]}",
        f"分析范围：{scopes}。",
        f"滚动窗口：{params.window} 个采样点；控制图子组大小：{params.subgroup_size}。",
    ]
    if params.analysis_mode == "过程能力" or any(
        value is not None for value in (params.lsl, params.target, params.usl)
    ):
        lines.append(
            "规格参数："
            f"LSL={_format_number(params.lsl)}；"
            f"目标值={_format_number(params.target)}；"
            f"USL={_format_number(params.usl)}。"
        )
    lines.append(f"补充要求：{extra}。")
    return "\n".join(lines)
