# 工业时序智能体 · 前端 (Frontend)

为 `agent_app/` 后端配套的 React + TypeScript + Vite + TailwindCSS 单页应用。
**第一步**已实现：

- **对话框（Chat）**：流式 Token 输出、Markdown / 代码高亮渲染、自动滚动、文件附带
- **断点人机交互页面（Human-in-the-Loop）**：完整覆盖后端三类 LangGraph 中断
  - `choose_tech_path` —— 技术方案选择
  - `upload_csv` —— CSV / Excel / Parquet 上传
  - `clarification` —— 业务语义 ↔ CSV 列字段映射确认

## 目录结构

```
frontend/
├── index.html
├── package.json
├── vite.config.ts          # 配置 /api → http://127.0.0.1:8000 代理
├── tailwind.config.js
├── tsconfig.json
├── public/
│   └── favicon.svg
└── src/
    ├── main.tsx            # 入口
    ├── App.tsx
    ├── index.css           # Tailwind 基础样式 + Markdown 样式
    ├── types/index.ts      # 与后端 schemas 对齐的类型
    ├── services/api.ts     # REST + NDJSON 流式客户端
    ├── context/SessionContext.tsx   # 全局会话 / 流式状态
    ├── utils/              # cn / format 工具
    └── components/
        ├── layout/         # AppLayout / Header / Sidebar
        ├── chat/           # ChatView / MessageBubble / ChatInput / Markdown
        ├── interrupt/      # InterruptCard (分发器) + 三种断点子组件
        └── ui/             # Button / Card / Badge / Spinner / IconButton
```

## 快速开始

```bash
# 1. 安装依赖（任选其一）
npm install        # 或 pnpm install / yarn

# 2. 启动后端（在 agent_app 目录）
cd ../agent_app
python api.py      # 默认监听 0.0.0.0:8000

# 3. 启动前端
cd ../frontend
npm run dev        # 默认 http://localhost:5173
```

开发模式下，Vite 会把所有 `/api/*` 与 `/health` 请求代理到 `http://127.0.0.1:8000`，
因此不需要在前端配置任何后端地址。

## 与后端的对接要点

| 主题 | 约定 |
| --- | --- |
| 主查询 | `POST /api/query`，`multipart/form-data`，必带 `session_id`，可选 `query` / `file` / `resume_value`（JSON 字符串） |
| 流式协议 | `text/event-stream`，但**实际上是 NDJSON**（每行一个 JSON 事件）。前端通过 `fetch` + `ReadableStream` 读取并按 `\n` 切分。 |
| 事件类型 | `token` / `update` / `interrupt` / `completed` |
| 三类中断 | `interrupt.data.type ∈ { choose_tech_path, upload_csv, clarification }` |
| 恢复执行 | 把构造好的对象以 `JSON.stringify()` 写入 `resume_value` 字段重新调用 `POST /api/query` |
| 文件上传 | 在 `upload_csv` 中断时把文件放进 `multipart` 的 `file` 字段，**后端会自动注入 `file_path`**（见 `agent_app/api.py`） |

## 三种断点交互的 UX 设计

1. **技术方案选择**
   - 卡片化展示 2–3 条方案：标题、`model_type` 徽章、`short_summary`、`steps` 列表、`target_objects`、`expected_effect`
   - 单选确认后，发送 `{ selected_path_id }` 作为 `resume_value`

2. **CSV 上传**
   - 大号拖拽 + 点击双区域上传
   - 文件类型与大小校验（`.csv / .xlsx / .parquet`，100MB 上限）
   - 提交时仅上传文件，后端落盘后自动生成 `file_path`

3. **字段映射确认**
   - 目标列 / 特征列分页签
   - 每一行：业务语义名 → 下拉选择 CSV 列 → 三态状态按钮（已确认 / 待确认 / 未映射）
   - 进度徽章显示 `confirmedCount / total`
   - 一键全部确认 + 提交时回传完整的 `target_columns` 与 `feature_columns`

## 生产部署

```bash
npm run build      # 输出到 dist/
```

构建产物为静态资源，可直接由 Nginx / Caddy / FastAPI `StaticFiles` 托管。
若前端与后端**不同源**，需要设置环境变量：

```bash
# .env.local
VITE_API_BASE_URL=http://10.2.131.172:8000
```

同时请记得在 `agent_app/api.py` 的 `CORSMiddleware` 中把该前端源加入白名单。

## 后续可扩展点

本仓库的第一阶段聚焦于对话与断点交互。后续可在此基础上继续构建：

- 会话列表 / 多会话切换（对接 `GET /api/session/{id}/history`）
- 分析结果可视化（图表、异常点、置信区间）
- 数据画像摘要侧栏（对接 `SessionState.csv_profile`）
- 任务执行进度时间轴（对接 `planned_workflow`）
- 暗色主题切换（TailwindCSS 已启用 `darkMode: 'class'`）
