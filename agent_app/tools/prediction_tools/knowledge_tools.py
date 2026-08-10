"""Knowledge / discovery tools for the prediction tool family.

Three read-only tools that surface model metadata to the LLM:

- :func:`list_prediction_models` — enumerate all seven foundation models
  with their endpoint, output shape and characteristics.
- :func:`explain_prediction_model` — full descriptor for one model
  (resolved case-insensitively).
- :func:`recommend_prediction_model` — lightweight rule-based picker that
  scores each model against the user's constraints (multivariate,
  probabilistic preference, short-series handling).

None of these tools touch the network; they read exclusively from
:data:`MODEL_REGISTRY`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain.tools import ToolRuntime, tool

from agent_app.tools._tool_guard import tool_guard
from agent_app.tools.prediction_tools._common import (
    AVAILABLE_MODELS,
    MODEL_REGISTRY,
    QUANTILE_LEVELS,
    make_envelope,
    resolve_model,
)


# ----------------------------------------------------------------------
# Tools
# ----------------------------------------------------------------------

@tool("list_prediction_models")
@tool_guard("list_prediction_models")
def list_prediction_models(runtime: ToolRuntime) -> Dict[str, Any]:
    """列出所有可用的时序预测基础模型及其元信息。

    返回每个模型的：API 端点、输出张量形状、是否支持多变量、标签与简介。
    **只读，不调用远端服务。**

    所有模型共享统一接口协议：输入 ``dataList`` 维度
    ``[变量数, 输入历史长度]``，返回 ``predict_data_result`` 维度
    ``[变量数, 预测长度, 9]``（9 个分位数 p10..p90）。

    Returns
    -------
    Dict[str, Any]
        ``metrics.models`` 为模型列表；``metrics.quantile_levels`` 为
        9 个标准分位水平。
    """
    models: List[Dict[str, Any]] = []
    for name in AVAILABLE_MODELS:
        entry = MODEL_REGISTRY[name]
        models.append({
            "name": name,
            "endpoint": entry["preferred_endpoint"],
            "endpoints": list(entry["endpoints"]),
            "output_shape": entry["output_shape"],
            "output_type": entry["output_type"],
            "multivariate": entry["multivariate"],
            "tags": list(entry.get("tags", [])),
            "description": entry["description"],
        })

    return make_envelope(
        tool_name="list_prediction_models",
        summary="共 %d 个可用预测模型（统一分位数输出协议）。" % len(models),
        key_findings=[
            "统一输出：所有模型返回 [变量数, 预测长度, 9] 分位数张量。",
            "多变量支持：%s。" % ", ".join(
                m["name"] for m in models if m["multivariate"]),
        ],
        metrics={
            "models": models,
            "quantile_levels": list(QUANTILE_LEVELS),
            "endpoints": {
                "endpoint_1": MODEL_REGISTRY["sundial"]["endpoints"][0],
                "endpoint_2": MODEL_REGISTRY["chronos-2"]["endpoints"][0],
            },
        },
        recommendations=[
            "通用稳健首选 sundial；多变量任务用 toto-2。",
            "短序列（<64 步）优先 chronos-2 / moirai-2.0-R-small。",
        ],
    )


@tool("explain_prediction_model")
@tool_guard("explain_prediction_model")
def explain_prediction_model(
    model_name: str,
    runtime: ToolRuntime,
) -> Dict[str, Any]:
    """返回单个预测模型的详细说明（端点、输出形状、用法）。

    Parameters
    ----------
    model_name : str
        模型名（大小写不敏感），例如 ``"sundial"``、``"toto-2"``、
        ``"chronos-2"``、``"timer-s1"``、``"timesfm-2.5"``、
        ``"moirai-2.0-R-small"``、``"tirex-1.1-gifteval"``。
    """
    canonical, entry = resolve_model(model_name)

    return make_envelope(
        tool_name="explain_prediction_model",
        summary="模型 %s 详情。" % canonical,
        key_findings=[
            "%s → %s" % (canonical, entry["description"]),
            "统一输出形状：%s（9 个分位数 p10..p90）" % entry["output_shape"],
            "多变量支持：%s" % ("是" if entry["multivariate"] else "否"),
        ],
        metrics={
            "model": canonical,
            "endpoint": entry["preferred_endpoint"],
            "endpoints": list(entry["endpoints"]),
            "output_shape": entry["output_shape"],
            "output_type": entry["output_type"],
            "multivariate": entry["multivariate"],
            "tags": list(entry.get("tags", [])),
            "quantile_levels": list(QUANTILE_LEVELS),
            "description": entry["description"],
        },
        recommendations=[
            "所有模型均返回 [变量数, 预测长度, 9] 的统一分位数张量。",
            "forecast_time_series 会自动把返回值归一化为 p10..p90 分位带。",
        ],
        notes=[
            "调用 forecast_time_series(model_name=%r) 即可使用。" % canonical,
        ],
    )


@tool("recommend_prediction_model")
@tool_guard("recommend_prediction_model")
def recommend_prediction_model(
    runtime: ToolRuntime,
    multivariate: bool = False,
    prefer_probabilistic: bool = True,
    short_series: bool = False,
    need_speed: bool = False,
) -> Dict[str, Any]:
    """根据数据特征与场景约束推荐合适的预测模型。

    打分启发式，仅作为参考——最终选择仍由 LLM/用户决定。

    Parameters
    ----------
    multivariate : bool, default False
        是否需要多变量联合建模。
    prefer_probabilistic : bool, default True
        是否偏好带分位带/样本路径的密度预测（当前所有模型均为 True）。
    short_series : bool, default False
        历史序列是否较短（建议 < 64 步）。
    need_speed : bool, default False
        是否优先选择轻量级模型（小模型优先）。
    """
    rankings: List[Dict[str, Any]] = []
    for name in AVAILABLE_MODELS:
        entry = MODEL_REGISTRY[name]
        score = 0
        reasons: List[str] = []

        if multivariate:
            if entry["multivariate"]:
                score += 5
                reasons.append("原生多变量")
            else:
                score -= 2
                reasons.append("仅单变量")
        else:
            if not entry["multivariate"]:
                score += 1
                reasons.append("单变量，匹配场景")

        if prefer_probabilistic:
            # 当前所有模型均输出概率分布
            score += 1
            reasons.append("概率输出")

        if short_series and not entry["multivariate"]:
            score += 1
            reasons.append("适合短序列")

        if need_speed:
            # 轻量级小模型
            if name in ("moirai-2.0-R-small", "chronos-2"):
                score += 2
                reasons.append("轻量级")

        rankings.append({
            "name": name,
            "score": int(score),
            "output_type": entry["output_type"],
            "multivariate": entry["multivariate"],
            "endpoint": entry["preferred_endpoint"],
            "reasons": reasons,
        })

    rankings.sort(key=lambda r: r["score"], reverse=True)
    preferred = rankings[0]

    return make_envelope(
        tool_name="recommend_prediction_model",
        summary="推荐模型：%s（得分 %d）。"
                % (preferred["name"], preferred["score"]),
        key_findings=[
            "首选 %s。" % preferred["name"],
            "入选理由：%s。" % "；".join(preferred["reasons"]),
        ],
        metrics={
            "preferred": preferred["name"],
            "preferred_endpoint": preferred["endpoint"],
            "ranked": rankings,
            "criteria": {
                "multivariate": bool(multivariate),
                "prefer_probabilistic": bool(prefer_probabilistic),
                "short_series": bool(short_series),
                "need_speed": bool(need_speed),
            },
        },
        recommendations=[
            "调用 forecast_time_series(model=%r) 直接使用首选模型。"
            % preferred["name"],
            "如需多模型横向对比，改用 forecast_multi_models 或 "
            "compare_forecast_models_backtest。",
        ],
    )


TOOLS = [
    list_prediction_models,
    explain_prediction_model,
    recommend_prediction_model,
]
