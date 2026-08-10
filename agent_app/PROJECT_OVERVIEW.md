# 工业时间序列多智能体系统 — 项目思路、进展与后续工作

> 本文档基于 `agent_app/` 目录下的实际代码梳理而成，用于客观记录当前项目的设计思路、已实现的内容以及仍待完成的工作。

---

## 一、项目整体思路

### 1.1 设计理念

项目核心目标：构建一个面向工业时间序列数据的多智能体分析系统，遵循 **"先理解数据，再理解用户，再调度能力，再持续对话"** 的设计理念。

它不依赖一个大模型一次性完成所有事情，而是把整个流程拆成多个角色清晰的智能体，每个智能体各司其职，并通过一份**统一的会话状态对象**共享上下文，从而支持多轮、可中断、可补全参数的复杂对话。

### 1.2 五层架构

| 层级 | 职责 | 对应代码 |
|------|------|----------|
| 输入层 | 接收用户 query、CSV 文件、会话上下文 | `main.py` / `api.py` |
| 理解层 | 意图路由、CSV 画像、参数抽取 | `intent_router_agent.py` / `profile_agent.py` / `parser_agent.py` |
| 编排层 | 决定下一步走哪个节点、是否需要追问/上传文件 | `orchestrator_graph.py`（LangGraph） |
| 任务层 | 预测、异常检测、通用分析、监控、报告 | `prediction_agent.py` / `anomaly_agent.py` / `analysis_agent.py` / `report_agent.py` |
| 记忆与状态层 | 统一会话状态、对话历史、画像与参数记忆 | `state/session_state.py` / `SessionState`（Pydantic） |

### 1.3 核心智能体分工（当前实际代码）

- **IntentRouterAgent**：二分类路由，区分 `industrial`（进入工业分析工作流）与 `chat`（普通问答）。
- **ChatAgent**：处理闲聊、知识问答、文档类请求。
- **ProposalAgent**：两阶段生成技术方案 —— 先用 `proposal_text.md` 生成一段端到端方案长文，再用 `proposal_path.md` 把方案结构化为 `TechProposalEnvelope`（包含 2–3 条 `TechPath`）。
- **ProfileAgent**：基于 `get_basic_info` 与 `analyze_column` 工具链自主调用，输出 `CSVProfile`。
- **ParserAgent**：基于「历史优先 + 增量补全」的原则，输出 `TaskSpecEnvelope`，并通过 `need_clarification` 触发澄清流程。
- **AnalysisAgent**：通用分析执行器，提供 10 种分析模式（trend / correlation / comparison / distribution / quality / outlier / seasonality / change_point / stability / group_aggregation）。
- **PredictionAgent / AnomalyAgent**：面向特定任务的执行器。
- **ExplanationAgent / ReportAgent**：结果解释与综合报告（在新 graph 流程中尚未完整接入）。

### 1.4 关键设计点

1. **统一会话状态 `SessionState`**
   把 `csv_profile`、`confirmed_spec`、`tech_proposal`、`selected_path`、`clarification_pending`、`dialogue_history` 等全部放进一个 Pydantic 对象，避免各 agent 各自维护记忆导致信息丢失。

2. **LangGraph 状态图 + interrupt 人机交互**
   `orchestrator_graph.py` 用 `StateGraph` 把整个流程编排为一张图，并通过 `interrupt` 实现三种人机交互节点：
   - `choose_path`：让用户在多条技术路径中选择一条
   - `await_csv_upload`：尚未上传 CSV 时中断等待
   - `await_clarification`：参数不全时让用户确认字段映射

3. **业务语义与 CSV 字段分离（`ColumnMapping`）**
   每个 target/feature 字段都同时记录 `semantic_name`（业务语义）与 `csv_column`（实际列名），并带有三态 `status`：
   - `mapped`：已确认映射（只能由人机确认阶段写入）
   - `uncertain`：模型给出候选，但不确定
   - `unmapped`：无法映射或尚无 CSV

4. **结构化输出优先**
   所有关键节点（路由、画像、方案、参数抽取）都通过 Pydantic Schema 约束输出，避免「自由文本 → 解析失败」的脆弱链路。

5. **多轮对话规则（见 `prompts/parser.md`）**
   - 历史已确认字段默认保持不变
   - 当前轮只做增量补全 / 冲突修正
   - 不允许模型自行写 `status="mapped"`
   - 没有 CSV 时只输出语义字段，`csv_column=null`

### 1.5 主流程图（当前 graph）

```
START
  │
  ▼
intent_router ──chat──► chat ──► END
  │
  ▼ industrial
tech_proposal
  │
  ▼
choose_path (interrupt: 选路径)
  │
  ▼
parse_intent  ◄──────────────────────────────────────┐
  │                                                  │
  ▼                                                  │
route_before_execute                                 │
  ├─ upload_file ──► await_csv_upload ──► profiling ─┘
  ├─ profiling ────► profiling ─┘
  ├─ await_clarification ──► await_clarification (interrupt)
  │
  └─ execute_task ──► END
```

---

## 二、当前进展

### 2.1 已完成的骨架与能力

- **基础设施**
  - `BaseAgent` 封装了 LangChain `create_agent` + `InMemorySaver`，支持 `invoke_structured`（带重试）与 `invoke_chat` 两种调用方式。
  - `SessionManager` 提供会话创建、查询、更新、过期清理、画像/参数/分析结果写入等基础能力。
  - `config/settings.py` 统一管理模型、超时、最大预测步数、文件限制等配置。

- **理解层**
  - 意图路由、闲聊分支已可用。
  - CSV 画像通过工具自主调用（`get_basic_info` + `analyze_column`），生成结构化 `CSVProfile`。
  - 技术方案生成支持「长文方案 + 结构化路径」两段式输出。

- **编排层（LangGraph）**
  - `orchestrator_graph.py` 已实现完整的状态图，包含上述 9 个节点和条件路由。
  - 通过 `interrupt` + `Command(resume=...)` 机制支持多轮中断恢复。

- **任务执行层**
  - `AnalysisAgent` 已实现 10 种分析工具函数（趋势、相关性、对比、分布、质量、离群点、季节性、变点、稳定性、分组聚合），每种都返回 `summary / key_findings / metrics / recommendations` 结构化结果。
  - `PredictionAgent` 与 `AnomalyAgent` 已具备独立的执行逻辑、结果对象、报告模板与后续建议生成能力。

- **参数与状态对象**
  - `TaskSpecEnvelope` 通过 `model_validator` 强制 `task_type` 与 `spec` 类型一致。
  - `ColumnMapping`、`AnalysisTaskSpec`、`PredictionTaskSpec` 等结构完备，含丰富的 `description`，可直接作为结构化输出 schema。

- **入口与接口**
  - `main.py` 提供 CLI 入口（`IndustrialTimeSeriesAgent`）。
  - `api.py` 提供 FastAPI REST 接口（含会话管理、查询、清理、健康检查等）。

### 2.2 已观察到的不一致 / 待收口点

> 这些是基于代码静态阅读发现的问题，是后续工作的重点。

1. **新旧编排器并存**
   - `agents/orchestrator_agent.py`（旧版线性流程）与 `agents/orchestrator_graph.py`（新版 LangGraph）同时存在。
   - `main.py` 当前导入的是 `orchestrator_graph.OrchestratorAgent`，已迁移到新版。
   - 旧版 `orchestrator_agent.py` 内部仍保留大量被注释的 `_parse_intent` / `_execute_task` / `_explain_results` 代码块，且 `_execute_task` 中只保留了 `ANALYSIS` 分支，其它分支被注释。
   - `parser_agent_v0.py` 也是遗留文件。

2. **`process_query` 入参不一致**
   - `main.py` 的 `process_query` 仍声明 `file_path` 参数，但新版 graph 用 `interrupt` 等待用户上传，二者尚未完全对齐。
   - `main.py` 中 `continue_session` 调用的是同步 `self.orchestrator.continue_session(...)`，而 graph 版本是 `async`，需要核对调用方式。

3. **`_node_execute_task` 引用了未导入的 `self.monitoring_agent`**
   - `orchestrator_graph.py` 在 `TaskType.MONITORING` 分支里使用了 `self.monitoring_agent`，但 `__init__` 中没有实例化它，一旦走到该分支会抛 `AttributeError`。

4. **任务 Agent 与新 TaskSpec 的对接不完整**
   - `PredictionAgent.execute_prediction` / `AnomalyAgent.execute_anomaly_detection` 仍接收 `target_column` / `time_column` / `method` 等扁平参数，与新的 `ColumnMapping + TaskSpec` 模型不一致。
   - 新 graph 中调用 `execute_prediction(file_path, task_spec, thread_id)`，但 `PredictionAgent` 当前签名并不匹配，需要适配。

5. **解释与报告节点缺失**
   - 新 graph 没有独立的 `explain` / `report` 节点；`ExplanationAgent` 与 `ReportAgent` 在新流程中尚未接入。
   - 当前分析结果直接取 `last_ai_message` 作为返回，缺少统一的结果解释/报告生成阶段。

6. **状态持久化**
   - 全部使用 `InMemorySaver` 与内存字典，重启即丢失；`DatabaseConfig` 已定义但未实际使用。

---

## 三、未来还需要做的工作

按优先级与模块分类整理。

### 3.1 优先级 P0：让现有流程真正跑通

- [ ] **收口新旧编排器**
  - 删除或归档 `orchestrator_agent.py`（旧版）、`parser_agent_v0.py`、`parser_graph.py`（若已弃用）。
  - 清理 `orchestrator_agent.py` / `analysis_agent.py` 等文件中大段被注释的代码。

- [ ] **修复 `orchestrator_graph._node_execute_task`**
  - 实例化 `monitoring_agent`，或先在路由中禁用 `MONITORING` 分支并返回友好提示。

- [ ] **统一任务 Agent 的调用签名**
  - 让 `PredictionAgent` / `AnomalyAgent` 接受 `(file_path, task_spec, thread_id)`，从 `task_spec.spec.target_columns / time_column / ...` 中解析出实际 CSV 列名后再执行。
  - 与 `AnalysisAgent.execute_analysis` 保持一致的接口风格。

- [ ] **对齐 `main.py` / `api.py` 与 graph 的接口**
  - 移除或重新定义 `file_path` 流转方式，让 CLI/API 明确支持「先发 query → 中断 → resume 上传文件」的两阶段调用。
  - 校对所有同步/异步调用，避免在 async 入口里直接同步阻塞。

### 3.2 优先级 P1：补全系统能力

- [ ] **重新接入 ExplanationAgent / ReportAgent**
  - 在 graph 中增加 `explain` 节点（基于 `execution_results` + `csv_profile` 生成业务解读）。
  - 增加 `report` 路由分支，支持「生成综合报告」类请求。

- [ ] **完善澄清/字段映射闭环**
  - `await_clarification` 返回的结构需要前后端约定清楚；目前 `interrupt` 的 payload 形式已写明，但前端/CLI 侧的回传校验、错误恢复、二次追问尚未覆盖。
  - 增加「修改/撤销已映射字段」的支持（多轮修改链路）。

- [ ] **多轮对话能力回归测试**
  - 围绕「延续任务 / 修改参数 / 开启新任务」三种场景构造端到端测试，验证 `confirmed_spec` 的增量补全逻辑符合 `parser.md` 的规则。

### 3.3 优先级 P2：工程质量与可运维性

- [ ] **状态持久化**
  - 用数据库（PostgreSQL/Redis）或文件持久化替换 `InMemorySaver` 与 `SessionManager.sessions` 字典。
  - 与 `DatabaseConfig` 对齐，支持会话恢复、断点续跑。

- [ ] **可观测性**
  - 关键节点（路由、画像、参数抽取、任务执行）增加结构化日志与耗时统计。
  - 接入链路追踪（如 OpenTelemetry）便于排查多智能体调用链。

- [ ] **错误处理与降级**
  - LLM 调用超时/失败时提供降级（例如画像失败 → 用规则版画像兜底）。
  - 结构化输出校验失败时的重试与人工介入策略。

- [ ] **测试覆盖**
  - 单元测试覆盖 `ColumnMapping` 状态机、`TaskSpecEnvelope` 校验、各分析工具的数值正确性。
  - 端到端测试覆盖典型 query：预测、异常检测、对比分析、生成报告。

### 3.4 优先级 P3：能力扩展

- [ ] **更多数据源**：Excel/Parquet/数据库直连/时序库（InfluxDB/TDengine），目前 `profile_tools` 只支持 CSV。
- [ ] **可视化产出**：`visualization_tools.py` 已存在但未在新流程中调用；应让分析结果附带图表/可下载文件。
- [ ] **预测/异常模型升级**：现有 `predict_time_series` 等仍偏简单统计方法，可接入 ARIMA / Prophet / 季节性模型 / Isolation Forest / LSTM 等。
- [ ] **领域知识沉淀**：把工业制造、半导体、新能源等领域的画像规则、字段同义词、阈值经验固化到 `prompts/` 与 `utils/data_process.py`。
- [ ] **权限与多租户**：API 层增加鉴权、配额、租户隔离。
- [ ] **大文件与性能**：流式 CSV 读取、采样画像、缓存画像结果，避免每次重复计算。

### 3.5 文档与示例

- [ ] 更新 `README.md` 与 `PROJECT_STRUCTURE.md`，使其与新的 graph 流程一致（目前仍描述旧版线性流程）。
- [ ] 补充 `API_USAGE.md` 中关于 `interrupt` / `resume` 调用模式的示例。
- [ ] 提供端到端可运行的 demo 脚本（`example_usage.py` 需要适配新接口）。

---

## 四、一句话总结

> 项目已经搭出一个**结构清晰、设计理念成熟**的工业时间序列多智能体骨架（LangGraph 编排 + 统一状态 + 结构化输出 + interrupt 人机交互 + 业务语义/CSV 字段分离），但**新旧实现并存、部分任务 Agent 尚未与新 TaskSpec 对齐、解释/报告/持久化等环节未接入新流程**，当前最关键的工作是**完成新旧收口、让整条链路在 graph 版本上稳定跑通**，再逐步扩展能力与工程质量。
