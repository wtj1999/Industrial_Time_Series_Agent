# Prediction Skill

## Chronos-2 / TimesFM 2.5 微调

- 命中词：微调、finetune、LoRA、继续训练、训练 Chronos/TimesFM。
- 工具：`finetune_prediction_model`；权重保存在远程服务器，本地保存 JSON 索引。
- 支持范围：Chronos-2=`full|lora`，TimesFM 2.5=`lora`。
- 训练流：`status -> progress* -> completed`，失败为 `failed`；前端动态展示步数、百分比、loss、学习率等。
- 预测复用：前端选中微调模型后，`forecast_time_series` 自动把远程 `modelPath` 交给预测服务；模型缓存由远端按 `model + modelPath` 隔离。
- 微调后评估：训练前从历史末尾预留 `holdout_steps`（默认等于 `prediction_length`），训练完成后分别用基础权重和微调权重预测同一 holdout，返回双模型曲线及 MAE/RMSE/MAPE/sMAPE/MASE 对比。

> 工业时序**预测**:7 个时序基础模型,对未来 N 步给点预测 + 9 个分位区间。**不做异常检测、不做因果归因**。

`task_type=prediction`

## 何时命中

| 类型 | 关键词 |
|---|---|
| 未来值预测 | 预测 / 未来 N 步 / 后面会怎样 / forecast / predict |
| 寿命 / SOH | RUL / SOH / 退化 / degradation |
| 产量 / 能耗 | 产量 / 良率 / 能耗 / 需求 |
| 模型对比 / 选型 | 用哪个模型 / backtest / 回测 |
| 多模型融合 | 融合 / 集成 / ensemble / 共识 |

**默认起点**:工业时序首选 `sundial`;多变量 `toto-2`;短序列(< 64 步)`chronos-2` / `moirai-2.0-R-small`。

## 何时不命中

| 用户意图 | 路由到 |
|---|---|
| 找异常点 / 离群 / 故障 | `anomaly_detection` |
| 解释某次异常 | `anomaly_detection`(explain_anomalies) |
| 看趋势 / 分布 / 相关 | `analysis` |
| 监控告警(部署态) | `monitoring` / `anomaly_detection` |

**模糊判据**:"未来 / 后面 / 下一步" + 数值型时序 → 本 skill;"会不会出故障" → `anomaly_detection`。

## 可用模型(7 个,远端 HTTP 推理)

`sundial`(工业首选) / `toto-2`(多变量) / `chronos-2`(短序列) / `timer-s1`(长序列) / `timesfm-2.5` / `moirai-2.0-R-small` / `tirex-1.1-gifteval`。大小写不敏感。

## 可用工具

| 工具 | 用途 |
|---|---|
| `forecast_time_series` | 单模型单次预测 |
| `forecast_multi_models` | 多模型并排(不融合) |
| `forecast_ensemble` | 多模型加权融合(`weighting` / `holdout_steps`) |
| `backtest_forecast` | 单模型回测(`test_steps`) |
| `compare_forecast_models_backtest` | 多模型对比 + 排名(`rank_by`) |
| `recommend_prediction_model` / `list_prediction_models` / `explain_prediction_model` | 知识查询 |

## 输入 / 输出

- **输入**:`target_columns`(必须,工具不回退 feature);非数值列跳过;`prediction_length` ≤ 历史长度 1/3;长序列(> 512 步)必须传 `history_tail`
- **输出**:`point_forecast` + 9 分位(p10-p90);回测给 MAE / RMSE / MAPE / sMAPE / MASE;含图表

## 限制

- **不做**:异常检测 / 因果归因 / 实时流式
- `target_columns` 必须显式配置,空则工具直接报错
- HTTP 失败以 `{"error":...}` 出现在 per_column / per_model,**不得编造**
- 列数 > 10 或模型数 > 3 必须先与用户确认
