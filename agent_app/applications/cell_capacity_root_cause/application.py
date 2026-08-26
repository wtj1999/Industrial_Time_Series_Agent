"""Structured adapter for lithium-cell low-capacity root-cause analysis."""

import math
from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator


FEATURE_SCOPES = {
    "分容关键工步参数",
    "化成关键工步参数",
    "注液工艺参数",
    "高温浸润工艺参数",
    "全部可用工艺参数",
}

DEFAULT_REQUIREMENTS = (
    "输出容量偏低的关键影响参数排序、TreeSHAP贡献方向、模型评估指标、"
    "重点排查对象和可执行的工艺验证建议。"
)


class CellCapacityRootCauseParams(BaseModel):
    feature_scopes: List[str] = Field(default_factory=lambda: ["全部可用工艺参数"])
    train_ratio: float = Field(default=0.7, gt=0, lt=1)
    validation_ratio: float = Field(default=0.1, gt=0, lt=1)
    test_ratio: float = Field(default=0.2, gt=0, lt=1)
    split_strategy: str = "chronological"
    iterations: int = Field(default=500, ge=10, le=5000)
    learning_rate: float = Field(default=0.05, gt=0, le=1)
    depth: int = Field(default=6, ge=2, le=16)
    early_stopping_rounds: int = Field(default=50, ge=1, le=1000)
    top_n_features: int = Field(default=15, ge=1, le=100)
    shap_sample_size: int = Field(default=300, ge=1, le=300)
    additional_requirements: str = Field(default=DEFAULT_REQUIREMENTS, max_length=500)

    @model_validator(mode="after")
    def validate_configuration(self):
        if not self.feature_scopes or any(scope not in FEATURE_SCOPES for scope in self.feature_scopes):
            raise ValueError("unsupported feature scope")
        if self.split_strategy not in {"chronological", "random"}:
            raise ValueError("unsupported split strategy")
        if not math.isclose(
            self.train_ratio + self.validation_ratio + self.test_ratio,
            1.0,
            abs_tol=1e-8,
        ):
            raise ValueError("训练集、验证集和测试集比例之和必须为 1")
        return self


def build_query(raw_params: Dict[str, Any]) -> str:
    params = CellCapacityRootCauseParams.model_validate(raw_params)
    scopes = "、".join(params.feature_scopes)
    extra = params.additional_requirements.strip() or DEFAULT_REQUIREMENTS
    return "\n".join([
        "请执行锂电分容容量偏低根因分析任务。",
        "分析目标：分容容量。将分容容量列设置为 target_columns。",
        f"候选特征范围：{scopes}；将匹配的数据列设置为 feature_columns，排除时间列、ID列、分容容量本身及明显泄漏字段。",
        "分析方法：调用 analyze_root_causes_catboost，分别训练目标列模型，输出模型评估、特征重要性和 TreeSHAP。",
        f"数据切分：方式={params.split_strategy}；训练集={params.train_ratio:g}；验证集={params.validation_ratio:g}；测试集={params.test_ratio:g}。",
        f"模型参数：iterations={params.iterations}；learning_rate={params.learning_rate:g}；depth={params.depth}。",
        f"补充要求：{extra}。",
    ])
