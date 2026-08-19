"""
Pydantic schemas for Industrial Time Series Agent System.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union, TypedDict
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod


class IntentType(str, Enum):
    INDUSTRIAL = "industrial"
    CHAT = "chat"
    SWITCH_TOOL = "switch_tool"
    NEW_FILE = "new_file"
    CHANGE_TASK = "change_task"
    CHANGE_MAPPING = "change_mapping"


class ColumnType(str, Enum):
    """Column type enumeration."""
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEMPORAL = "temporal"
    TEXT = "text"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class TaskStage(str, Enum):
    """Task stage enumeration."""
    Router = "intent_router"
    CHAT = "chat"
    Parse = "parse_intent"
    PROFILING = "profiling"
    Proposal = "tech_proposal"
    CLARIFICATION = "clarification"
    EXECUTION = "execution"


class TaskType(str, Enum):
    """Task type enumeration."""
    PREDICTION = "prediction"
    ANOMALY_DETECTION = "anomaly_detection"
    ANALYSIS = "analysis"
    # MONITORING = 'monitoring'


class IntentRouterResult(BaseModel):
    intent: Literal[
        "industrial", "chat",
        "switch_tool", "new_file",
        "change_task", "change_mapping",
    ]
    skip_proposal: bool = Field(
        default=False,
        description=(
            "True 表示用户已经在本轮 query 中明确指出了要执行的任务类型与对象，"
            "仅 intent=industrial 时有效；其他 intent 必须保持 False。"
        ),
    )
    task_type_hint: Optional[TaskType] = Field(
        default=None,
        description=(
            "建议的任务类型。"
            "intent=industrial 且 skip_proposal=True 时必填，作为 parser 的参考输入；"
            "intent=change_task_type 时建议填写新的任务类型，供 tech_proposal 参考；"
            "其他场景必须为 None。"
        ),
    )


class ColumnInfo(BaseModel):
    """Information about a single column."""
    name: str = Field(description="列名")
    type: ColumnType = Field(description="列的数据类型分类，必须是 ColumnType 枚举之一")
    missing_rate: float = Field(ge=0, le=1, description="缺失值比例，取值范围 [0, 1]")
    unique_count: int = Field(description="该列中唯一值（去重后）的数量")
    distribution_stats: Optional[Dict[str, float]] = Field(
        default=None,
        description="数值列的分布统计信息，包含 mean/std/min/max/median/q25/q75 等键；非数值列应为 None"
    )


class CSVProfile(BaseModel):
    """Comprehensive profile of a CSV dataset."""
    total_rows: int = Field(description="数据集总行数")
    total_columns: int = Field(description="数据集总列数")
    columns: Dict[str, ColumnInfo] = Field(
        description="按列名索引的列信息字典，键为列名，值为对应的 ColumnInfo 对象"
    )
    time_column_candidates: List[str] = Field(
        default_factory=list,
        description="疑似时间列的列名列表，通常包含日期/时间戳格式的列"
    )
    target_column_candidates: List[str] = Field(
        default_factory=list,
        description="疑似目标列（业务关心的预测/监测对象）的列名列表，通常是数值型的关键指标"
    )
    grouping_columns: List[str] = Field(
        default_factory=list,
        description="疑似分组/分类列的列名列表，用于按维度切分数据（如设备ID、工厂、产品类型等）"
    )
    numeric_columns: List[str] = Field(
        default_factory=list,
        description="所有数值型列的列名列表"
    )
    categorical_columns: List[str] = Field(
        default_factory=list,
        description="所有类别型列的列名列表，低基数的离散值字段"
    )
    text_columns: List[str] = Field(
        default_factory=list,
        description="所有文本型列的列名列表，高基数的字符串字段"
    )

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Message(BaseModel):
    """Conversation message."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = Field(default=None)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TechPathStep(BaseModel):
    step_title: str
    content: str


class TechPath(BaseModel):
    path_id: str = Field(description="路径编号，如 技术路径_1")
    title: str = Field(description="路径标题")
    short_summary: str = Field(description="一句话概括")
    model_type: TaskType = Field(default=None)
    target_objects: List[str] = Field(default_factory=list)
    steps: List[TechPathStep] = Field(default_factory=list)
    expected_effect: Optional[str] = None


class TechProposalEnvelope(BaseModel):
    paths: List[TechPath] = Field(description="根据提供的材料提取出对应的技术路径")

class ColumnMapping(BaseModel):
    semantic_name: str = Field(
        description="业务语义字段名，中文描述。"
    )
    csv_column: Optional[str] = Field(
        default=None,
        description="与业务语义字段对应用户上传的 CSV 实际列名；如果无法明确映射，则置为 None。"
    )
    status: Literal["mapped", "unmapped", "uncertain"] = Field(
        default="unmapped",
        description="映射状态：mapped 表示已成功映射；unmapped 表示尚未映射；uncertain 表示候选列存在但映射不确定。"
    )

# class ToolArgMapping(BaseModel):
#     arg_name: str = Field(
#         description=(
#             "需要进行业务语义映射的 Tool 参数名称。"
#             "例如 target_columns、feature_columns、time_column、label_column 等。"
#         )
#     )
#
#     mappings: List[ColumnMapping] = Field(
#         default_factory=list,
#         description=(
#             "该 Tool 参数对应的业务语义字段与 CSV 字段映射关系。"
#             "Planner 应优先填写 semantic_name，并尝试根据 CSV 画像匹配 csv_column。"
#             "如果无法确认映射，则 csv_column=None，status='unmapped'；"
#             "如果存在候选字段，则 status='uncertain'；"
#             "只有用户确认后才能变为 'mapped'。"
#         )
#     )
#
# class ToolArgValue(BaseModel):
#     """
#     一个参数中的一个值对应的业务语义
#     """
#
#     semantic_name: str = Field(
#         default=None,
#         description="业务语义字段名，中文描述。"
#     )
#
#     csv_column: Optional[str] = Field(
#         description="真正传递给 Tool 的参数值,与业务语义字段对应用户上传的 CSV 实际列名；如果无法明确映射，则置为 None。"
#     )
#
#     status: Literal[
#         "mapped",
#         "unmapped",
#         "uncertain",
#     ] = Field(
#         default="uncertain",
#         description=(
#             "该 Tool 参数对应的业务语义字段与 CSV 字段映射关系。"
#             "Planner 应优先填写 semantic_name，并尝试根据 CSV 画像匹配 csv_column。"
#             "如果无法确认映射，则 csv_column=None，status='unmapped'；"
#             "如果存在候选字段，则 status='uncertain'；"
#             "只有用户确认后才能变为 'mapped'。"
#         )
#     )
#
#
# class ToolArg(BaseModel):
#     """
#     Tool 的一个参数
#     """
#
#     arg_name: str = Field(
#         description=(
#             "需要进行业务语义映射的 Tool 参数名称。"
#             "例如 target_columns、feature_columns、time_column、label_column 等。"
#         )
#     )
#
#     arg_values: List[ToolArgValue] = Field(
#         default_factory=list
#     )
#
# class ToolCall(BaseModel):
#
#     tool: str = Field(
#         description="需要调用的 Tool 名称。"
#     )
#
#     args: dict[str, Any] = Field(
#         default_factory=dict,
#         description=(
#             "Tool 的普通参数。"
#             "这里只填写无需业务字段映射的参数，例如 contamination、window_size、"
#             "detector_name、save_name、return_top_n 等。"
#         )
#     )
#
#     arg_maps: List[ToolArg] = Field(
#         default_factory=list,
#         description=(
#             "Tool 中所有涉及业务字段映射的参数。"
#             "例如 target_columns、feature_columns、time_column 等。"
#             "Planner 不应直接把 CSV 列名写入 args，而应统一放入 arg_maps 中等待用户确认。"
#         )
#     )

# class ToolArgItem(BaseModel):
#     """
#     一个参数中的一个元素（一个业务对象）
#     """
#
#     semantic_name: str = Field(
#         description="业务语义字段名，中文描述"
#     )
#
#     csv_column: Optional[str] = Field(
#         default=None,
#         description=(
#             "CSV中的候选字段。"
#             "没有CSV或无法确定时为None。"
#         )
#     )
#
#     status: Literal[
#         "mapped",
#         "uncertain",
#         "unmapped",
#     ] = Field(
#         default="uncertain",
#         description=(
#             "映射状态。"
#             "mapped=已确认；"
#             "uncertain=模型猜测；"
#             "unmapped=没有候选。"
#         )
#     )
#
# class ToolArg(BaseModel):
#     """
#     Tool的一个参数
#     """
#
#     name: str = Field(
#         description="Tool参数名，例如feature_columns、target_columns、time_column。"
#     )
#
#     values: List[ToolArgItem] = Field(
#         default_factory=list,
#         description="该参数对应的多个业务对象。"
#     )
#
# class ToolCall(BaseModel):
#
#     tool: str = Field(
#         description="Tool名称"
#     )
#
#     args: dict[str, Any] = Field(
#         default_factory=dict,
#         description=(
#             "普通参数，不涉及CSV映射。"
#         )
#     )
#
#     arg_maps: List[ToolArg] = Field(
#         default_factory=list,
#         description=(
#             "所有需要CSV字段映射的参数。"
#         )
#     )
#
# class ToolPlan(BaseModel):
#     reasoning: str = Field(
#         description=(
#             "任务规划过程中的简要推理说明。"
#             "用于解释为什么选择该任务类型以及为什么调用这些Tool。"
#             "不需要输出详细思维链，仅输出可解释的规划依据。"
#         )
#     )
#
#     tool_calls: list[ToolCall] = Field(
#         default_factory=list,
#         description=(
#             "需要执行的Tool调用列表。"
#             "每个ToolCall描述一个具体工具以及对应参数。"
#             "当一个任务需要多个步骤时，可以包含多个Tool调用，"
#             "执行顺序按照列表顺序排列。"
#         )
#     )
#
#     need_confirmation: bool = Field(
#         default=True,
#         description=(
#             "是否需要用户确认后再执行Tool。"
#             "当参数存在不确定字段映射、可能影响结果的关键选择、"
#             "或执行成本较高时，应设置为True。"
#             "当所有参数明确且风险较低时，可以设置为False直接执行。"
#         )
#     )


class BaseTaskSpec(BaseModel, ABC):

    @abstractmethod
    def apply_mapping(self, updated_spec: dict) -> "BaseTaskSpec":
        """根据用户确认结果更新当前 Spec"""
        raise NotImplementedError


class TaskSpec(BaseTaskSpec):

    target_columns: List[ColumnMapping] = Field(
        default_factory=list,
        description="目标变量字段列表及其对应的CSV映射。"
    )

    feature_columns: List[ColumnMapping] = Field(
        default_factory=list,
        description="输入变量字段列表及其对应的CSV映射。"
    )

    def apply_mapping(self, updated_spec: dict):

        feature_columns = [
            ColumnMapping(
                semantic_name=item["semantic_name"],
                csv_column=item["csv_column"],
                status="mapped",
            )
            for item in updated_spec.get("feature_columns", [])
        ]

        target_columns = [
            ColumnMapping(
                semantic_name=item["semantic_name"],
                csv_column=item["csv_column"],
                status="mapped",
            )
            for item in updated_spec.get("target_columns", [])
        ]

        return self.model_copy(
            update={
                "feature_columns": feature_columns,
                "target_columns": target_columns,
            }
        )



# class PredictionTaskSpec(BaseModel):
#     task_type: Literal["prediction"] = Field(
#         default="prediction",
#         description="任务类型，固定为 prediction。"
#     )
#
#     target_points: List[str] = Field(
#         default_factory=list,
#         description="要预测的目标点位名称列表，例如温度、厚度、压力、良率、产量等。"
#     )
#
#     input_points: List[str] = Field(
#         default_factory=list,
#         description="用于预测的输入点位名称列表，例如相关工艺参数、设备状态、环境变量等。"
#     )
#
#     time_column: Optional[str] = Field(
#         default=None,
#         description="时间字段名称，用于构建时间序列预测。"
#     )
#
#     group_columns: List[str] = Field(
#         default_factory=list,
#         description="分组字段名称列表，例如产线、设备、工位、批次等，用于分组建模或分组预测。"
#     )
#
#     history_window: Optional[int] = Field(
#         default=None,
#         description="历史窗口长度，用于指定模型回看多少个时间步或时间段。"
#     )
#
#     forecast_window: Optional[int] = Field(
#         default=None,
#         description="预测窗口长度，用于指定未来需要预测多少个时间步或时间段。"
#     )
#
#     evaluation_metrics: List[str] = Field(
#         default_factory=lambda: ["MAE", "RMSE", "MAPE"],
#         description="预测结果的评估指标列表，默认包含 MAE、RMSE、MAPE。"
#     )
#
#
# class MonitoringTaskSpec(BaseModel):
#     task_type: Literal["monitoring"] = "monitoring"
#
#
#
#
#
# class AnomalyDetectionTaskSpec(BaseTaskSpec):
#     task_type: Literal["anomaly_detection"] = Field(
#         default="anomaly_detection",
#         description="任务类型，固定为 anomaly_detection。"
#     )
#
#     # ---- 数据描述 ----
#     data_type: Literal["tabular", "text", "time_series"] = Field(
#         default="tabular",
#         description=(
#             "待检测数据的类型。"
#             "'tabular' 表示表格数据（二维结构化数据，如 CSV、Excel、DataFrame 等，每行表示一个样本，每列表示一个特征）；"
#             "'text' 表示文本数据（如评论、日志、文档等）；"
#             "'time_series' 表示时间序列数据（按时间顺序排列的数据，通常包含时间戳和一个或多个随时间变化的数值特征）。"
#         ),
#     )
#
#     target_columns: List[ColumnMapping] = Field(
#         default_factory=list,
#         description="核心异常检测对象字段列表，表示本次异常检测最重要的业务语义字段及其对应的 CSV 映射。"
#     )
#
#     # ---- 检测模式：决定 agent 调用哪个工具 ----
#     detection_mode: Literal[
#         "auto", "detect", "train_save", "load_predict", "evaluate", "compare"
#     ] = Field(
#         default="auto",
#         description=(
#             "检测模式，与工具的对应关系："
#             "'auto' → outlier_detection (ADEngine 全自动兜底)；"
#             "'detect' → detect_with_pyod（tabular/text）或 detect_time_series_anomalies（time_series）；"
#             "'train_save' → train_pyod_detector（训练并保存模型）；"
#             "'load_predict' → load_pyod_detector_and_predict（加载已保存模型打分）；"
#             "'evaluate' → evaluate_pyod_detection（带真实标签评估）；"
#             "'compare' → compare_pyod_detection_results（多检测器对比）。"
#             "Parser 根据 user_query 推断 mode；歧义时 fallback 到 'auto'。"
#         ),
#     )
#
#     # ---- 检测器选择 ----
#     detector_names: List[str] = Field(
#         default_factory=list,
#         description=(
#             "指定检测器类名（大小写敏感），例如 ['IForest']、['LOF','HBOS','IForest']。"
#             "mode='detect'/'train_save'/'load_predict'/'evaluate' 取列表第一个；"
#             "mode='compare' 时全部参与对比；"
#             "为空时由执行 agent 按 mode 自动选择默认检测器。"
#         ),
#     )
#
#     # ---- 通用参数 ----
#     contamination: float = Field(
#         default=0.1,
#         ge=0,
#         le=0.5,
#         description="期望异常比例，范围 (0, 0.5]。直接影响 threshold_ 与 labels_。",
#     )
#     params: Dict[str, Any] = Field(
#         default_factory=dict,
#         description=(
#             "检测器构造参数 dict（合并到 __init__）。"
#             "例如 IForest 用 {'n_estimators': 200}；LOF 用 {'n_neighbors': 30}。"
#             "由 Parser 按 detector_names 填对应参数；未提供时使用 PyOD 默认值。"
#         ),
#     )
#     return_top_n: int = Field(
#         default=10,
#         ge=0,
#         description="返回分数最高的前 N 行 / 时间点。设为 0 表示不返回 Top-N。",
#     )
#     random_state: Optional[int] = Field(
#         default=None,
#         description="随机种子，复现实验时使用。",
#     )
#
#     # ---- 持久化（mode='train_save' / 'load_predict'）----
#     save_name: Optional[str] = Field(
#         default=None,
#         description="mode='train_save' 时的保存文件名（不带 .joblib 后缀）。未提供时自动生成 {detector}_{timestamp}。",
#     )
#     model_name_or_path: Optional[str] = Field(
#         default=None,
#         description="mode='load_predict' 时指定要加载的模型名称（如 'iforest_v1'）或绝对路径。",
#     )
#
#     # ---- 评估（mode='evaluate'）----
#     label_column: Optional[ColumnMapping] = Field(
#         default=None,
#         description="mode='evaluate' 时使用的 0/1 ground-truth 标签列（任何非零值视为异常）。",
#     )
#
#     # ---- 时序（mode='detect' + data_type='time_series'）----
#     time_column: Optional[ColumnMapping] = Field(
#         default=None,
#         description="时序检测时的时间轴列（仅用于结果标注异常发生时间，不参与建模）。",
#     )
#     window_size: Optional[int] = Field(
#         default=None,
#         description="时序检测器的滑窗 / 子序列长度。未提供时使用检测器默认值。",
#     )
#
#     # ---- 意图透传 ----
#     user_query: Optional[str] = Field(
#         default=None,
#         description="用户原始问题的简短复述，让执行 agent 拿到原始措辞以便做边界判断。",
#     )
#     notes: List[str] = Field(
#         default_factory=list,
#         description="Parser / 用户确认阶段留下的提示，供执行 agent 参考。",
#     )
#
#     def apply_mapping(self, updated_spec: dict):
#         """根据用户确认结果更新当前 Spec。
#
#         支持两类更新：
#         1. 列映射（target_columns / label_column / time_column）：用户在前端
#            选择 CSV 列后回传，将 status 置为 'mapped'。
#         2. 标量参数（detection_mode / detector_names / contamination 等）：
#            用户在 clarification 阶段可编辑默认值。
#         未出现在 updated_spec 中的字段保持当前值不变（增量更新）。
#         """
#         update: Dict[str, Any] = {}
#
#         # 1. target_columns 列表
#         if "target_columns" in updated_spec:
#             update["target_columns"] = [
#                 ColumnMapping(
#                     semantic_name=item["semantic_name"],
#                     csv_column=item["csv_column"],
#                     status="mapped" if item.get("csv_column") else "unmapped",
#                 )
#                 for item in (updated_spec.get("target_columns") or [])
#             ]
#
#         # 2. label_column / time_column（单个 ColumnMapping 或 dict）
#         for col_field in ("label_column", "time_column"):
#             if col_field in updated_spec:
#                 val = updated_spec.get(col_field)
#                 if val is None:
#                     update[col_field] = None
#                 elif isinstance(val, ColumnMapping):
#                     update[col_field] = val
#                 elif isinstance(val, dict):
#                     csv_col = val.get("csv_column")
#                     update[col_field] = ColumnMapping(
#                         semantic_name=val.get("semantic_name", col_field),
#                         csv_column=csv_col,
#                         status="mapped" if csv_col else "unmapped",
#                     )
#
#         # 3. 标量字段
#         for field in (
#             "detection_mode", "contamination", "return_top_n",
#             "random_state", "save_name", "model_name_or_path",
#             "window_size", "user_query",
#         ):
#             if field in updated_spec:
#                 update[field] = updated_spec[field]
#
#         # 4. list / dict 字段
#         if "detector_names" in updated_spec:
#             update["detector_names"] = list(updated_spec.get("detector_names") or [])
#         if "params" in updated_spec:
#             update["params"] = dict(updated_spec.get("params") or {})
#         if "notes" in updated_spec:
#             update["notes"] = list(updated_spec.get("notes") or [])
#
#         return self.model_copy(update=update)
#
#
# class AnalysisTaskSpec(BaseTaskSpec):
#     task_type: Literal["analysis"] = Field(
#         default="analysis",
#         description="任务类型，固定为 analysis。"
#     )
#
#     analysis_modes: List[
#         Literal[
#             "trend",
#             "correlation",
#             "comparison",
#             "distribution",
#             "quality",
#             "outlier",
#             "seasonality",
#             "change_point",
#             "stability",
#             "group_aggregation"
#         ]
#     ] = Field(
#         default_factory=list,
#         description=(
#                 "分析方式偏好，仅作为模型构建阶段的软指引。模型应优先根据这些模式选择分析视角、分析方法和输出结构；若与 analysis_goal 冲突，以 analysis_goal 为准。"
#                 "trend - 适用于分析指标随时间的变化趋势；关注增长、下降、波动、漂移等现象；输出趋势方向、斜率、滚动均值等指标。"
#                 "correlation - 适用于分析变量之间的相关关系；输出相关系数矩阵及强相关变量组合；支持 pearson、spearman、kendall 方法。"
#                 "comparison - 适用于不同组之间的差异对比；基于 group_columns 对 target_columns 进行聚合统计比较；支持 mean、median、sum、count 等指标。"
#                 "distribution - 适用于分析数据分布特征；输出均值、标准差、分位数、偏度、峰度等统计信息；用于识别分布形态及离散程度。"
#                 "quality - 适用于分析数据质量情况；检查缺失值、重复值及字段缺失率；用于评估数据可用性和可靠性。"
#                 "outlier - 适用于识别异常点和异常区间；基于 IQR（四分位距）规则检测离群数据；输出异常数量及异常占比。"
#                 "seasonality - 适用于分析周期性或重复性波动特征；基于滚动窗口统计周期波动情况；用于识别班次、日周期或生产节拍规律。"
#                 "change_point - 适用于识别统计特征发生明显变化的位置；通过比较前后阶段均值差异检测潜在变点；用于发现工艺切换、设备调整或异常发生时刻。"
#                 "stability - 适用于评估过程稳定性；输出均值、标准差、变异系数（CV）、滚动均值波动等指标；用于判断工艺运行是否稳定。"
#                 "group_aggregation - 适用于按设备、工位、批次、班次等维度进行聚合统计；输出分组汇总结果；用于发现不同分组之间的表现差异。"
#         )
#     )
#
#     target_columns: List[ColumnMapping] = Field(
#         default_factory=list,
#         description="核心分析对象字段列表，表示本次分析最重要的业务语义字段及其对应的 CSV 映射。"
#     )
#
#     feature_columns: List[ColumnMapping] = Field(
#         default_factory=list,
#         description="辅助分析字段列表，表示用于解释、关联、对比或建模的辅助变量及其 CSV 映射。"
#     )
#
#     time_column: Optional[ColumnMapping] = Field(
#         default=None,
#         description="时间字段映射，用于趋势、周期性、变点、稳定性等时序分析；通常对应日期、时间戳、采样时刻、班次时间等字段。"
#     )
#
#     group_column: Optional[ColumnMapping] = Field(
#         default=None,
#         description="分组字段映射列表，用于按设备、产线、工位、批次、班次等维度进行分组比较、聚合统计或差异分析。"
#     )
#
#     dimensions: List[str] = Field(
#         default_factory=list,
#         description="分析维度字段，通常用于多维统计、切片、钻取、交叉分析。"
#     )
#
#     compare_groups: List[str] = Field(
#         default_factory=list,
#         description="对比分析时的分组对象，例如 A线 vs B线、白班 vs 夜班、不同批次之间对比。"
#     )
#
#     start_time: Optional[str] = Field(
#         default=None,
#         description="分析起始时间，用于限定分析区间。"
#     )
#
#     end_time: Optional[str] = Field(
#         default=None,
#         description="分析结束时间，与 start_time 配合限定分析区间。"
#     )
#
#     granularity: Optional[str] = Field(
#         default=None,
#         description="时间粒度，例如 1min、5min、15min、1h、1d。"
#     )
#
#     rolling_window: int = Field(
#         default=24,
#         description="滑动窗口长度，用于趋势、稳定性、周期性等分析。"
#     )
#
#     top_k: int = Field(
#         default=10,
#         description="返回前 K 个结果，例如 Top K 相关字段、Top K 异常点、Top K 分组结果。"
#     )
#
#     bins: int = Field(
#         default=10,
#         description="分布分析的分箱数，例如直方图分箱数量。"
#     )
#
#     confidence_level: float = Field(
#         default=0.95,
#         description="置信水平，常用于统计分析、区间估计、异常判断阈值辅助说明。"
#     )
#
#     correlation_method: Literal["pearson", "spearman", "kendall"] = Field(
#         default="pearson",
#         description="相关性分析方法。pearson 表示线性相关，spearman 和 kendall 适合秩相关。"
#     )
#
#     comparison_metric: Literal["mean", "median", "sum", "count", "rate"] = Field(
#         default="mean",
#         description="对比分析时使用的统计指标，默认 mean。"
#     )
#
#     distribution_method: Literal["histogram", "boxplot", "quantile"] = Field(
#         default="histogram",
#         description="分布分析方法，支持 histogram、boxplot、quantile。"
#     )
#
#     quality_rules: List[str] = Field(
#         default_factory=list,
#         description="质量分析规则或关注点，例如缺失率过高、重复值、越界值、零值异常、突变异常等。"
#     )
#
#     hypothesis: Optional[str] = Field(
#         default=None,
#         description="用户提出的分析假设，例如夜班良率低于白班、厚度波动与压力相关、某工位存在周期性偏移。"
#     )
#
#     output_format: Literal["json", "text", "table", "report"] = Field(
#         default="json",
#         description="输出格式偏好，支持 json、text、table、report。"
#     )
#
#     extra_params: Dict[str, Any] = Field(
#         default_factory=dict,
#         description="扩展参数，用于后续新增字段或临时实验参数，避免频繁修改 schema。"
#     )
#
#     def apply_mapping(self, updated_spec: dict):
#
#         feature_columns = [
#             ColumnMapping(
#                 semantic_name=item["semantic_name"],
#                 csv_column=item["csv_column"],
#                 status="mapped",
#             )
#             for item in updated_spec.get("feature_columns", [])
#         ]
#
#         target_columns = [
#             ColumnMapping(
#                 semantic_name=item["semantic_name"],
#                 csv_column=item["csv_column"],
#                 status="mapped",
#             )
#             for item in updated_spec.get("target_columns", [])
#         ]
#
#         return self.model_copy(
#             update={
#                 "feature_columns": feature_columns,
#                 "target_columns": target_columns,
#             }
#         )
#
#
# class TaskSpecEnvelope(BaseModel):
#     task_type: TaskType = Field(
#         description="任务类型枚举，用于标识当前任务属于 prediction、anomaly_detection、monitoring 或 analysis 中的哪一类。"
#     )
#     spec: Union[
#         PredictionTaskSpec,
#         AnomalyDetectionTaskSpec,
#         MonitoringTaskSpec,
#         AnalysisTaskSpec
#     ] = Field(
#         description="与 task_type 对应的任务专属参数对象，只能填充与当前任务类型一致的 Spec。"
#     )
#     question: Optional[str] = Field(
#         default=None,
#         description="当前最需要用户补充的一个问题，用于参数补全；如果无需追问则为 None。"
#     )
#
#     need_clarification: bool = Field(
#         default=False,
#         description="是否需要继续追问用户补充信息；当关键参数缺失或任务目标不明确时应为 True。"
#     )
#
#     reasoning: Optional[str] = Field(
#         default=None,
#         description="简要说明为什么根据用户问题、DDL 和 CSV 画像生成了当前任务判断与技术方案。"
#     )
#
#     @model_validator(mode="after")
#     def check_consistency(self):
#         mapping = {
#             TaskType.PREDICTION: PredictionTaskSpec,
#             TaskType.ANOMALY_DETECTION: AnomalyDetectionTaskSpec,
#             TaskType.MONITORING: MonitoringTaskSpec,
#             TaskType.ANALYSIS: AnalysisTaskSpec,
#         }
#         expected_cls = mapping.get(self.task_type)
#         if expected_cls and not isinstance(self.spec, expected_cls):
#             raise ValueError(f"task_type={self.task_type} but spec is {type(self.spec).__name__}")
#         return self
#
#     def apply_mapping(self, updated_spec: dict):
#         return self.model_copy(
#             update={
#                 "spec": self.spec.apply_mapping(updated_spec),
#                 "need_clarification": False,
#                 "question": None,
#             }
#         )


class ModelRef(BaseModel):
    """A user-selected reference to a previously trained anomaly detector.

    Populated in ``SessionState.selected_model_ref`` when the user picks an
    existing model from the CSV-upload breakpoint's model picker. The
    orchestrator forwards this to ``execute_anomaly_detection``, which in
    turn seeds ``AnomalyDetectionContext`` so ``detect_with_model``'s
    load branch can locate the model even when it was trained in a
    different ``(thread_id, file_path)`` scope.

    ``user_id`` is intentionally NOT carried here — the runtime always
    rebinds the path to the *current* user so the picker cannot be used to
    cross user boundaries.
    """
    save_name: str = Field(description="训练时给定的裸 save_name（不带 .joblib 后缀）")
    thread_id: Optional[str] = Field(
        default=None,
        description="模型所属的会话 id。None 时回退到当前会话作用域。",
    )
    source_file: Optional[str] = Field(
        default=None,
        description="模型训练时所基于的数据集文件名（file_stem）。None 时回退到当前文件作用域。",
    )
    detector_name: Optional[str] = Field(
        default=None,
        description="模型对应的检测器名称，仅用于 UI 提示与 prompt hint，不参与路径解析。",
    )
    category: Optional[str] = Field(default=None)
    model_type: Optional[str] = Field(default=None)
    model_path: Optional[str] = Field(default=None)


class SessionState(BaseModel):
    """Unified session state for multi-turn conversations."""
    session_id: str
    user_id: Optional[str] = Field(
        default=None,
        description=(
            "Owner of this session. Used to namespace uploaded files and "
            "trained-model artifacts so different users never see each "
            "other's data. Set once at session creation from the "
            "``X-User-Id`` request header."
        ),
    )
    current_stage: TaskStage = Field(default=TaskStage.Router)
    intent_type: Optional[IntentType] = None
    task_type: Optional[TaskType] = Field(default=None)
    chat_response: Optional[str] = Field(default=None)
    file_path: Optional[str] = Field(default=None)
    proposal_text: Optional[str] = Field(default=None)
    proposal_paths: Optional[list] = Field(default=None)
    selected_path: Optional[TechPath] = Field(default=None)
    confirmed_spec: Optional[TaskSpec] = Field(default=None)
    selected_model_ref: Optional[ModelRef] = Field(
        default=None,
        description=(
            "用户在 CSV 上传断点显式选择复用的已训练模型引用。"
            "在异常检测或预测任务下可能非空；为 None 时由 LLM 自由决策"
            "（训练新模型或复用当前作用域内的模型）。"
            "跨会话复用时 thread_id / source_file 指向模型原始作用域，"
            "user_id 始终绑定当前用户，前端无法伪造。"
        ),
    )
    csv_profile: Optional[CSVProfile] = Field(default=None)
    csv_preview: Optional[Dict[str, Any]] = Field(default=None)
    last_user_query: Optional[str] = Field(default=None)

    planned_workflow: List[str] = Field(default_factory=list)

    dialogue_history: List[Message] = Field(default_factory=list)

    event_log: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Chronological log of every displayable event emitted during "
            "this session — user messages, assistant responses, csv_preview "
            "and chart artifacts — in the order they originally appeared. "
            "Each entry: {kind, role?, content?, data?, ts?}. Used by the "
            "frontend to replay a past conversation with the SAME card "
            "positions the user saw during live chat, instead of the lossy "
            "'all messages then all artifacts' fallback. NOTE: dialogue_history "
            "(text only) is kept separately for LLM context; event_log is the "
            "source of truth for UI replay."
        ),
    )

    execution_results: Optional[str] = Field(default=None)
    anomaly_chart: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Structured payload for the anomaly-detection chart, emitted "
            "alongside ``execution_results`` when the sub-agent ran "
            "detect_with_model (tabular or time-series) or "
            "evaluate_detection. Mirrored on the "
            "frontend as a StreamEvent of type 'anomaly_chart'."
        ),
    )
    analysis_chart: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Structured payload for the analysis chart (correlation / "
            "histogram / decomposition / control / changepoint / acf), "
            "emitted when an analysis sub-agent ran a Tier-1 visualisable "
            "tool. Mirrored on the frontend as 'analysis_chart'."
        ),
    )
    prediction_chart: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Structured payload for the forecast chart (quantile bands "
            "+ history), emitted when the prediction sub-agent ran "
            "forecast_time_series / forecast_multi_models. Mirrored on "
            "the frontend as 'prediction_chart'."
        ),
    )

    tool_calls: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "子 Agent 执行过程中模型调用过的 tool_call 记录。"
            "目前仅记录 AnalysisAgent 与 AnomalyDetectionAgent 触发的调用。"
            "每条记录通常包含 tool 名称、参数、调用结果摘要等字段。"
        ),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    def update_timestamp(self):
        """Update the timestamp."""
        self.updated_at = datetime.utcnow()

    def add_message(self, role: Literal["user", "assistant", "system"], content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a message to dialogue history."""
        message = Message(role=role, content=content, metadata=metadata)
        self.dialogue_history.append(message)
        self.update_timestamp()

    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """Get recent messages from dialogue history."""
        return self.dialogue_history[-n:]


class QueryResponse(BaseModel):
    success: bool
    session_id: str
    status: str = Field(
        description="completed / interrupted / failed"
    )

    response: Optional[str] = None
    need_clarification: bool = False
    interrupt: Optional[Dict[str, Any]] = None
    graph_state: Optional[SessionState] = None
    error: Optional[str] = None





class AnalysisResult(BaseModel):
    """Base class for analysis results."""
    task_type: TaskType
    success: bool
    result_summary: str
    detailed_results: Optional[Dict[str, Any]] = Field(default=None)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    warnings: Optional[List[str]] = Field(default_factory=list)
    execution_time_seconds: Optional[float] = Field(default=None)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PredictionResult(AnalysisResult):
    """Prediction task result."""
    predictions: List[float]
    prediction_intervals: Optional[List[tuple]] = Field(default=None)
    trend_summary: str
    uncertainty_explanation: str
    phase_analysis: Optional[List[str]] = Field(default_factory=list)
    business_interpretation: str


class AnomalyResult(AnalysisResult):
    """Anomaly detection result."""
    anomaly_points: List[Dict[str, Any]]
    anomaly_intervals: List[Dict[str, Any]]
    anomaly_types: List[str]
    possible_causes: List[str]
    severity_levels: List[str]
    recommendations: List[str]


class ExplanationResult(AnalysisResult):
    """Explanation result."""
    trend_explanation: str
    risk_indicators: List[str]
    business_implications: List[str]
    suggested_actions: List[str]
    confidence_level: str
    additional_insights: Optional[List[str]] = Field(default_factory=list)


class ReportResult(AnalysisResult):
    """Report generation result."""
    report_title: str
    report_sections: List[Dict[str, str]]
    executive_summary: str
    key_findings: List[str]
    recommendations: List[str]
    charts: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    tables: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    appendix: Optional[Dict[str, Any]] = Field(default=None)
