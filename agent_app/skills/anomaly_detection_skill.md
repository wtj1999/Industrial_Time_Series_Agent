# Anomaly Detection Skill

> 工业数据**异常检测**:PyOD 60+ 检测器,覆盖表格 / 时序,支持训练保存、评估、对比、融合、解释。**不做预测、不做参数优化**。

`task_type=anomaly_detection`

## 何时命中

| 类型 | 关键词 |
|---|---|
| 异常检测 | 异常 / 离群 / outlier / anomaly |
| 故障样本 | 故障 / defect / 缺陷样本 / faulty |
| 时序异常时段 | 异常时段 / 异常区间 / 异常时间段 |
| 检测器选型 | IForest / LOF / ECOD / PyOD / 哪个检测器 |
| 标签评估 | 有 label / 算 ROC / precision / recall |
| 多算法共识 | 共识 / 融合 / ensemble / consensus |
| 模型持久化 | 训练并保存 / 加载模型 / 重新打分 |

**默认起点**:工业表格首选 `auto_detect_anomalies`;时序首选 `detect_ts_anomalies(detector_name="MatrixProfile")`;快速跑 `detect_anomalies(detector_name="IForest" / "ECOD")`。

## 何时不命中

| 用户意图 | 路由到 |
|---|---|
| 看趋势 / 分布 / 相关 | `analysis` |
| 预测未来 | `prediction` |
| 3σ / IQR / Z-score 找极端值(统计视角) | `analysis` |
| 解释为什么出问题(找因果,无检测语境) | `analysis` |
| 持续监控告警(部署态) | `monitoring` |

**模糊判据**:提"算法名 / PyOD / 训练保存 / 算 ROC / 共识" → 本 skill;只说"看看有没有不正常"→ `analysis` 兜底。

## 可用检测器(按耗时,选型必看)

| 耗时 | 代表 | 1k / 10k 行 |
|---|---|---|
| 秒级 | `ECOD` / `IForest` / `HBOS` / `COPOD` | <1s / 几秒 |
| 十秒级 | `LOF` / `KNN` / `OCSVM` / `ABOD` | 1-3s / 10-60s |
| 几十秒级(**时序首选**) | `MatrixProfile` / `SpectralResidual` / `KShape` | 1-5s / 10-30s |
| 分钟级 ⚠️ | `LSTMAD` / `AnomalyTransformer` / `AnoGAN` / `AutoEncoder` / `VAE` / `DevNet` / `SOOD` | 10-60s / 2-10 分钟 |

**行数 > 5000 禁默认选 DL 类**。

## 可用工具

| 工具 | 用途 |
|---|---|
| `auto_detect_anomalies` | ADEngine 一键全流程(默认稳妥) |
| `detect_anomalies` | 单检测器表格检测 |
| `detect_ts_anomalies` / `detect_ts_with_forecast` | 时序检测 / 预测残差异常 |
| `train_anomaly_detector` / `load_detector_and_predict` / `list_saved_detectors` / `delete_saved_detector` | 持久化 |
| `evaluate_detection` | 带 label 评估(ROC-AUC / P@n / F1) |
| `compare_detection_results` | 多算法对比(内部并行重训,**不要**先单跑再 compare) |
| `combine_detector_scores` / `train_ensemble_detector` | 分数融合 / ensemble(二选一) |
| `apply_threshold_method` | pythresh 高级阈值 |
| `explain_anomalies` / `compute_feature_importance` | 解释(用户追问时) |
| `list_pyod_detectors` / `explain_pyod_detector` / `recommend_detectors` | 知识查询 |

## 输入 / 输出

- **输入**:`target_columns`(fallback feature);非数值列跳过;`label_column`(仅评估);`time_column`(仅标注);`contamination`(默认 0.1);`save_name`(裸名称,不带路径)
- **输出**:`n_anomalies` / `anomaly_ratio` / `threshold` / `top_anomalies` / `anomaly_intervals`(时序) / `labels_` / `decision_scores_` + 图表

## 限制

- **不做**:预测 / 趋势分布分析 / 参数优化
- `MatrixProfile` 等 transductive 检测器不支持新样本 `predict`,`supports_out_of_sample=false` 必须告知
- 标签全 0 / 全 1 跳过评估,**不得编造指标**
- 不要传内部构造参数(`n_estimators` / `n_neighbors` 等),只暴露 `contamination` / `window_size` / `step` / `method` / `test_fraction` / `random_state`
- 不要自己拼模型路径(框架按 `(user_id, thread_id, file_path)` 拼接)
- 同一回合 ≤ 1 个检测类工具(除非明确要求对比 / 融合 / 解释)
