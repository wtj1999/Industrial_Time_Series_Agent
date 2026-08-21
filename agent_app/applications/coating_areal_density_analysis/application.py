"""Structured adapter for lithium coating areal-density analysis."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


ANALYSIS_INTENTS = {
    "SPC控制状态分析": "使用 analyze_control_chart 识别控制限及 Western Electric 规则违例，并生成控制图。",
    "均值变点定位": "使用 detect_mean_change_points 定位均值显著改变的位置，并生成分段均值图。",
    "分区相关性分析": "使用 analyze_correlation_matrix 分析横向分区的相关关系，并生成相关性热力图。",
    "面密度分布分析": "使用 analyze_histogram 分析集中区间、偏态、双峰或截断，并生成直方图。",
    "自相关与周期结构分析": "使用 analyze_autocorrelation 分析滞后依赖和周期结构，并生成 ACF/PACF 图。",
    "趋势与周期分解": "使用 decompose_time_series 按指定周期拆分趋势、周期和残差，并生成分解图。",
    "过程稳定性评估": "使用 analyze_stability 评估变异系数、滚动均值漂移和滚动波动。",
    "过程能力分析": "使用 analyze_process_capability 计算 Cp/Cpk、Pp/Ppk 和潜在缺陷风险。",
    "长期趋势与持续漂移": "分析长期升降趋势或微小持续偏移，优先选择线性趋势或 CUSUM 中最匹配的一个。",
    "波动突变分析": "使用 detect_variance_change 定位波动幅度突变和工况失稳位置。",
    "综合质量诊断": "最多选择三个互补分析，覆盖基线、稳定性和最高价值的异常证据，并优先保留可视化结果。",
}

DEFAULT_ADDITIONAL_REQUIREMENTS = (
    "输出核心结论、关键指标、异常或失稳位置、可能原因、业务影响和可执行建议。"
)


class CoatingArealDensityParams(BaseModel):
    analysis_mode: str = "SPC控制状态分析"
    coating_scopes: List[str] = Field(default_factory=lambda: ["A面分区", "A+B双面分区"])
    window: int = Field(default=30, ge=2, le=5000)
    subgroup_size: int = Field(default=1, ge=1, le=1000)
    sigma_width: float = Field(default=3.0, gt=0, le=6)
    max_change_points: int = Field(default=5, ge=1, le=20)
    min_segment_length: int = Field(default=10, ge=2, le=10000)
    correlation_method: str = "pearson"
    min_abs_correlation: float = Field(default=0.3, ge=0, le=1)
    histogram_bins: int = Field(default=20, ge=5, le=100)
    bin_strategy: str = "equal_width"
    max_lag: int = Field(default=40, ge=1, le=500)
    ci_level: float = Field(default=0.95, gt=0, lt=1)
    period_steps: Optional[int] = Field(default=None, ge=2, le=1500)
    decomposition_model: str = "additive"
    decomposition_method: str = "stl"
    drift_threshold: float = Field(default=0.1, gt=0, le=1)
    trend_method: str = "稳健线性趋势"
    cusum_threshold: float = Field(default=5.0, gt=0, le=100)
    cusum_drift: float = Field(default=0.5, ge=0, le=10)
    variance_ratio_threshold: float = Field(default=1.5, ge=1, le=20)
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
        if self.correlation_method not in {"pearson", "spearman", "kendall"}:
            raise ValueError("unsupported correlation method")
        if self.bin_strategy not in {"equal_width", "quantile"}:
            raise ValueError("unsupported histogram bin strategy")
        if self.decomposition_model not in {"additive", "multiplicative"}:
            raise ValueError("unsupported decomposition model")
        if self.decomposition_method not in {"stl", "classical"}:
            raise ValueError("unsupported decomposition method")
        if self.trend_method not in {"稳健线性趋势", "CUSUM持续漂移"}:
            raise ValueError("unsupported trend method")
        allowed_scopes = {"A面分区", "A+B双面分区", "全部面密度分区"}
        if any(scope not in allowed_scopes for scope in self.coating_scopes):
            raise ValueError("unsupported coating scope")
        if self.analysis_mode == "过程能力分析" and self.lsl is None and self.usl is None:
            raise ValueError("过程能力分析必须提供至少一个规格限")
        if self.analysis_mode == "趋势与周期分解" and self.period_steps is None:
            raise ValueError("趋势与周期分解必须提供周期采样点数")
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
    ]
    if params.analysis_mode == "SPC控制状态分析":
        lines.append(
            f"分析参数：控制限宽度={params.sigma_width:g}σ；"
            f"控制图子组大小={params.subgroup_size}；应用标准 Western Electric 规则。"
        )
    elif params.analysis_mode == "均值变点定位":
        lines.append(
            f"分析参数：最大变点数={params.max_change_points}；"
            f"最小分段长度={params.min_segment_length} 个采样点。"
        )
    elif params.analysis_mode == "分区相关性分析":
        lines.append(
            f"分析参数：相关方法={params.correlation_method}；"
            f"最小绝对相关系数={params.min_abs_correlation:g}。"
        )
    elif params.analysis_mode == "面密度分布分析":
        lines.append(
            f"分析参数：分箱数量={params.histogram_bins}；"
            f"分箱策略={params.bin_strategy}。"
        )
    elif params.analysis_mode == "自相关与周期结构分析":
        lines.append(
            f"分析参数：最大滞后阶数={params.max_lag}；"
            f"置信水平={params.ci_level:g}。"
        )
    elif params.analysis_mode == "趋势与周期分解":
        lines.append(
            f"分析参数：周期采样点数={params.period_steps}；"
            f"分解模型={params.decomposition_model}；"
            f"分解方法={params.decomposition_method}；稳健分解=true。"
        )
    elif params.analysis_mode == "过程稳定性评估":
        lines.append(
            f"分析参数：滚动窗口={params.window} 个采样点；"
            f"漂移阈值={params.drift_threshold:g}。"
        )
    elif params.analysis_mode == "过程能力分析":
        lines.append(
            "规格参数："
            f"LSL={_format_number(params.lsl)}；"
            f"目标值={_format_number(params.target)}；"
            f"USL={_format_number(params.usl)}。"
        )
    elif params.analysis_mode == "长期趋势与持续漂移":
        if params.trend_method == "CUSUM持续漂移":
            lines.append(
                f"分析参数：趋势方法=CUSUM持续漂移；"
                f"触发阈值={params.cusum_threshold:g}；"
                f"容忍漂移={params.cusum_drift:g}；"
                f"最小分段长度={params.min_segment_length}。"
            )
        else:
            lines.append("分析参数：趋势方法=稳健线性趋势；robust=true。")
    elif params.analysis_mode == "波动突变分析":
        lines.append(
            f"分析参数：滚动窗口={params.window} 个采样点；"
            f"最大变点数={params.max_change_points}；"
            f"波动比阈值={params.variance_ratio_threshold:g}。"
        )
    else:
        lines.append(f"分析参数：综合诊断参考窗口={params.window} 个采样点。")
    lines.append(f"补充要求：{extra}。")
    return "\n".join(lines)
