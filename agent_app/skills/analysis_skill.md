# Analysis Skill

> 工业时序数据的**描述性与诊断性分析**:趋势 / 分布 / 关系 / 稳定性 / 变点 / SPC / 组间差异 / 模型化根因分析。**不预测未来、不做 ML 异常检测**。

`task_type=analysis`

## 何时命中

用户问数据**分析 / 分布 / 趋势 / 关系 / 周期 / 平稳性 / 变点 / 稳定性 / SPC / 组间差异 / 关键影响参数 / 根因分析 / 统计极值(3σ、IQR、Z-score)**,且不需要训练检测器或预测未来。

## 何时不命中

| 用户意图 | 路由到 |
|---|---|
| 用 IForest / LOF / PyOD 检测;训练并保存模型 | `anomaly_detection` |
| 找异常时段 / 时序异常区间 | `anomaly_detection` |
| 预测未来 / 后面会怎样 | `prediction` |
| 解释某次异常(已有检测语境) | `anomaly_detection` |

**模糊判据**:帮我分析一下数据→ `analysis`

## 可用工具(29 个,按问题类型,遵守 Agent 的调用预算)

| 类型 | 工具 |
|---|---|
| 数据质量 | `analyze_missing_values` / `analyze_duplicates` / `analyze_constant_or_low_variance_columns` |
| 描述统计 | `analyze_basic_statistics` / `analyze_distribution_shape` / `analyze_histogram` |
| 趋势 | `analyze_linear_trend` / `analyze_mann_kendall_trend` / `analyze_rolling_trend` |
| 关系 | `analyze_correlation_matrix` / `analyze_cross_correlation` / `analyze_mutual_information` |
| 时序分解 | `analyze_autocorrelation` / `analyze_seasonality` / `decompose_time_series` / `analyze_stationarity` |
| 变点 | `detect_mean_change_points` / `detect_variance_change` / `detect_cusum_change` |
| 统计极值 | `detect_univariate_outliers` / `detect_multivariate_outliers` / `analyze_extreme_values` |
| 稳定性 / SPC | `analyze_stability` / `analyze_process_capability`(需 USL/LSL) / `analyze_control_chart` |
| 分组对比 | `compare_group_statistics` / `compare_group_distributions` / `compare_two_groups`(需 group_column) |
| 模型化根因分析 | `analyze_root_causes_catboost`：用 feature_columns 分别预测每个 target_column，输出验证/测试指标、特征重要性与 TreeSHAP，并持久化模型；runtime 注入已训练模型时直接加载并预测当前数据 |

## 输入 / 输出

- **输入**:`target_columns` + `feature_columns`;`time_column` / `group_column` / `usl` / `lsl` 等由 LLM 从 schema 推断或用户给出
- **输出**:自然语言报告 + 结构化指标 + 图表(直方图、趋势线、控制图、热力图、SHAP 根因诊断等)

## 限制

- **不做**:未来预测(→ prediction)、ML 异常检测(→ anomaly_detection)、自动参数搜索
- CatBoost 根因分析揭示预测关联和贡献方向，不等同于已证明的物理因果关系
- USL / LSL、采样频率等无法从数据推断的参数必须由用户提供,否则对应工具跳过
- 工具未返回的指标一律不得编造
