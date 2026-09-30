# Chronos-2 / TimesFM 2.5 微调集成规范

- 状态：Approved（依据 `agent_app/tools/finetuning_README.md` 与用户本轮授权）
- 日期：2026-08-14
- 范围：预测工具、Agent/编排流、模型索引 API、前端模型选择与训练进度

## Context

实际模型权重由远程微调服务保存，本应用只负责提交训练数据、转发 SSE 进度、保存可查询的轻量模型索引，并在预测时把索引中的远程 `modelPath` 传给预测服务。

## Functional Requirements

- FR-1：系统 MUST 提供 `finetune_prediction_model` 工具，且只允许 `chronos-2`、`timesfm-2.5`。
- FR-2：工具 MUST 以 POST SSE 调用远程 `/time/seriesFinetune/stream`，解析 `status/progress/completed/failed`。
- FR-3：工具 MUST 将进度转发为 `prediction_finetuning_progress` 自定义流事件。
- FR-4：完成后 MUST 在本地写入 JSON 索引；权重 MUST 继续保存在远程 `modelPath`。
- FR-5：`GET /api/models` MUST 同时返回当前用户的异常模型与预测微调模型，并带分类字段。
- FR-6：预测任务上传数据时 MUST 允许只选择预测类微调模型；异常任务只能选择异常类模型。
- FR-7：选中的预测模型 MUST 将 `model` 与远程 `modelPath` 透传给预测工具；基础模型预测不得携带 `modelPath`。
- FR-8：Chronos MUST 支持 full/lora；TimesFM MUST 仅支持 lora。
- FR-9：微调工具 MUST 从每条序列末尾预留同一段 holdout，微调请求 MUST NOT 使用该段数据，避免评估泄漏。
- FR-10：远程微调完成后，工具 MUST 使用相同训练上下文分别调用基础模型预测接口和带 `modelPath` 的微调预测接口。
- FR-11：工具 MUST 对两个预测结果计算同口径 MAE、RMSE、MAPE、sMAPE、MASE，并返回可供双模型 Backtest 卡片消费的结构。
- FR-12：前端 MUST 在同一张回测图上展示基础模型、微调模型和真实 holdout，并展示两个模型的指标。

## Non-Functional Requirements

- NFR-1：模型列表与模型选择 MUST 保持用户隔离。
- NFR-2：SSE 解析 MUST 支持分块边界、注释 keep-alive 和失败事件。
- NFR-3：已有异常检测与基础模型预测行为 MUST 保持向后兼容。

## Acceptance Criteria

- AC-1（FR-1/FR-8）：Given TimesFM full 模式，When 调用工具，Then 在发起 HTTP 前报参数错误。
- AC-2（FR-2/FR-3）：Given 分块 SSE，When 收到 progress，Then 前端流收到对应百分比、步数和指标。
- AC-3（FR-4/FR-5）：Given completed 事件，When 工具结束，Then JSON 索引可由 `/api/models` 查询。
- AC-4（FR-6/FR-7）：Given 用户选择预测模型，When 执行预测，Then请求包含同一 `modelPath`；未选择时不包含。
- AC-5（NFR-2）：Given keep-alive 或 failed，When 解析流，Then忽略注释或抛出明确错误。
- AC-6（FR-9）：Given 长度 N 的序列和 H 步 holdout，When 提交微调，Then `dataList` 长度为 N-H。
- AC-7（FR-10/FR-11）：Given 微调 completed 事件，When 后评估完成，Then基础接口与微调接口各调用一次，且实际值完全相同。
- AC-8（FR-12）：Given 双模型回测结果，When 图表提取，Then产生包含两个模型、真实值和各自指标的 `backtest` 图表。

## Edge Cases

- EC-1：目标列无可用数值序列时拒绝训练。
- EC-2：远程返回非 2xx、无响应体或 malformed JSON 时返回明确失败。
- EC-3：重复模型名通过唯一索引文件名共存。
- EC-4：前端传入的预测 `modelPath` 仅来自当前用户模型列表记录。
- EC-5：任一序列不足以同时满足训练上下文与 holdout 时，必须在发起微调前拒绝。
- EC-6：训练成功但任一后评估接口失败时，模型索引仍 MUST 保存，结果 MUST 明确标记评估失败且不得伪造指标。

## API Contracts

```ts
interface FinetuneRequest {
  model: "chronos-2" | "timesfm-2.5";
  dataList: number[][];
  outputDir: string;
  predictionLength: number;
  contextLength?: number;
  numSteps?: number;
  learningRate?: number;
  batchSize?: number;
  finetuneMode?: "full" | "lora";
  loggingSteps?: number;
}

interface PredictionModelIndex {
  category: "time_series_prediction";
  task_type: "prediction";
  model_type: "chronos-2" | "timesfm-2.5";
  save_name: string;
  model_path: string;
  output_dir: string;
}
```

## Data Models

| 字段 | 类型 | 约束 |
|---|---|---|
| model_path | string | 远程服务 completed 事件原样返回 |
| save_name | string | 当前用户范围内用于显示与索引 |
| user_id/thread_id/source_file | string | 本地索引作用域 |
| trained_at | ISO datetime | UTC |

## Out of Scope

- 不下载、复制或删除远程权重。
- 不新增远程微调服务端实现。
- 不预加载频繁变化的微调模型。
