# 工业时间序列多智能体系统 - 项目结构

```
agent_app/
├── README.md                           # 项目说明文档
├── requirements.txt                    # Python依赖包
├── .env.example                        # 环境变量模板
├── .gitignore                          # Git忽略文件
├── start.bat                           # Windows启动脚本
├── agent.md                            # 智能体设计文档
│
├── main.py                             # 主程序入口（CLI界面）
├── api.py                              # REST API服务器（FastAPI）
├── example_usage.py                    # 使用示例代码
├── generate_test_data.py              # 测试数据生成脚本
├── test_system.py                      # 系统测试脚本
│
├── config/                             # 配置模块
│   ├── __init__.py
│   └── settings.py                     # 系统设置和配置
│
├── models/                             # 数据模型
│   ├── __init__.py
│   └── schemas.py                      # Pydantic数据模型定义
│
├── state/                              # 状态管理
│   ├── __init__.py
│   ├── session_state.py               # 会话状态管理
│   └── conversation_memory.py         # 对话记忆管理
│
├── tools/                              # 工具函数
│   ├── __init__.py
│   ├── data_tools.py                  # 数据处理工具
│   ├── analysis_tools.py              # 分析工具
│   └── visualization_tools.py         # 可视化工具
│
├── utils/                              # 工具函数
│   ├── __init__.py
│   └── helpers.py                     # 辅助函数
│
├── agents/                             # 智能体模块
│   ├── __init__.py
│   ├── profile_agent.py               # CSV画像智能体
│   ├── parser_agent.py                # 意图识别智能体
│   ├── orchestrator_agent.py          # 任务调度智能体
│   ├── prediction_agent.py            # 预测智能体
│   ├── anomaly_agent.py               # 异常检测智能体
│   ├── explanation_agent.py           # 解释智能体
│   └── report_agent.py                # 报告生成智能体
│
└── data/                               # 数据目录
    └── .gitkeep                       # 目录占位文件
```

## 模块说明

### 核心模块

#### `main.py`
- 系统的主入口点
- 提供命令行界面（CLI）
- 实现 `IndustrialTimeSeriesAgent` 主类
- 处理用户交互和系统初始化

#### `api.py`
- REST API 服务器（基于 FastAPI）
- 提供 HTTP 接口访问系统功能
- 支持会话管理、查询处理等操作
- 自动生成 Swagger/ReDoc 文档
- 异步处理和自动数据验证

### 配置模块 (`config/`)

#### `settings.py`
- 使用 Pydantic 进行配置管理
- 支持环境变量加载
- 包含 LLM、数据库、分析参数等配置

### 数据模型 (`models/`)

#### `schemas.py`
- 定义所有数据结构的 Pydantic 模型
- 包含：
  - `CSVProfile`: CSV数据画像
  - `TaskSpecification`: 任务规格说明
  - `SessionState`: 会话状态
  - `AnalysisResult`: 分析结果基类
  - `PredictionResult`: 预测结果
  - `AnomalyResult`: 异常检测结果
  - 索引...

### 状态管理 (`state/`)

#### `session_state.py`
- 会话状态管理器
- 支持会话创建、更新、查询、删除
- 自动清理过期会话
- 会话导入导出功能

#### `conversation_memory.py`
- 对话记忆管理
- 集成 LangChain 记忆系统
- 支持上下文总结
- 多轮对话追踪

### 工具模块 (`tools/`)

#### `data_tools.py`
- 数据加载和处理
- CSV 文件解析
- 列类型检测
- 相关性计算
- 数据验证

#### `analysis_tools.py`
- 时间序列预测
- 异常检测（多种算法）
- 趋势分析
- 统计计算
- 季节性检测

#### `visualization_tools.py`
- 时间序列图表
- 相关性热力图
- 异常点可视化
- 趋势分析图
- 分布图
- 对比图

### 智能体模块 (`agents/`)

#### `profile_agent.py`
- CSV 数据画像生成
- 列信息分析
- 数据质量评估
- 业务领域推断
- 分析任务建议

#### `parser_agent.py`
- 用户意图识别
- 参数提取和验证
- 多轮对话解析
- 追问检测
- 任务规格创建

#### `orchestrator_agent.py`
- 系统核心协调器
- 任务流程编排
- 智能体调度
- 结果综合
- 会话管理集成

#### `prediction_agent.py`
- 时间序列预测执行
- 多种预测方法
- 置信区间计算
- 趋势阶段分析
- 业务解读生成

#### `anomaly_agent.py`
- 异常检测执行
- 多算法支持
- 异常类型分类
- 严重程度评估
- 处理建议生成

#### `explanation_agent.py`
- 结果解释和翻译
- 业务洞察生成
- 风险指标识别
- 可操作建议提供
- 领域特定解读

#### `report_agent.py`
- 综合报告生成
- 执行摘要创建
- 关键发现提取
- 建议优先级排序
- 多格式输出支持

### 辅助模块 (`utils/`)

#### `helpers.py`
- 响应格式化
- 文件路径验证
- 错误处理装饰器
- 执行时间记录
- 输入清理

## 数据流

### 查询处理流程
```
用户输入 → main.py/api.py
    → OrchestratorAgent.process_query()
        → ProfileAgent (数据画像)
        → ParserAgent (意图解析)
        → 任务执行智能体 (分析执行)
        → ExplanationAgent (结果解释)
        → SessionManager (状态更新)
    → 返回结果
```

### 状态管理流程
```
SessionManager.create_session()
    → 初始化 SessionState
    → 添加到会话存储
    → 返回 session_id

SessionManager.get_session()
    → 查询会话存储
    → 检查超时
    → 返回会话状态

SessionManager.update_session()
    → 更新会话字段
    → 更新时间戳
    → 返回更新后的状态
```

## API 架构（FastAPI）

### 主要特性
- **异步处理**: 使用 async/await 提供高性能
- **自动文档**: Swagger UI 和 ReDoc 自动生成
- **数据验证**: 基于 Pydantic 的自动请求/响应验证
- **错误处理**: 统一的异常处理机制
- **CORS 支持**: 跨域资源共享配置
- **类型提示**: 完整的类型注解支持

### 端点结构
```
GET  /                          # API 信息
GET  /health                    # 健康检查
POST /api/query                 # 处理查询
GET  /api/session/{id}          # 获取会话信息
GET  /api/session/{id}/history  # 获取对话历史
POST /api/session/{id}/continue # 继续会话
DELETE /api/session/{id}/reset  # 重置任务
GET  /api/session/{id}/tasks    # 获取可用任务
POST /api/session               # 创建新会话
GET  /api/status                # 系统状态
POST /api/cleanup               # 清理会话
```

## 扩展指南

### 添加新的智能体

1. 在 `agents/` 目录创建新的智能体文件
2. 继承基础功能模式
3. 实现核心分析方法
4. 在 `OrchestratorAgent` 中注册
5. 更新 `ParserAgent` 意图识别

### 添加新的工具函数

1. 在 `tools/` 目录相应模块中添加函数
2. 包含完整的类型提示和文档字符串
3. 在 `tools/__init__.py` 中导出
4. 在相关智能体中集成使用

### 添加新的数据模型

1. 在 `models/schemas.py` 中定义 Pydantic 模型
2. 添加必要的验证逻辑
3. 在 `models/__init__.py` 中导出
4. 更新相关模块引用

### 添加新的 API 端点

1. 在 `api.py` 中定义 Pydantic 请求/响应模型
2. 使用 `@app.get()`, `@app.post()` 等装饰器
3. 实现异步处理函数
4. 添加错误处理和文档字符串

## 依赖关系

```
main.py / api.py
    ↓
agents.orchestrator_agent
    ↓
agents.{profile,prediction,anomaly,explanation,report}_agent
    ↓
tools.{data,analysis,visualization}_tools
    ↓
models.schemas
    ↓
config.settings
```

## 配置文件

### `.env` 文件
```bash
# LLM 配置
LLM_PROVIDER=openai
LLM_MODEL_NAME=gpt-4
LLM_API_KEY=your-key

# 数据库配置
DB_BACKEND=sqlite
DB_CONNECTION_STRING=sqlite:///sessions.db

# API 配置
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# 分析配置
DEFAULT_PREDICTION_STEPS=25
MAX_PREDICTION_STEPS=100
```

### `requirements.txt`
- fastapi: Web 框架
- uvicorn: ASGI 服务器
- langchain*: LangChain 框架
- pandas, numpy: 数据处理
- scikit-learn: 机器学习
- matplotlib: 可视化
- pydantic: 数据验证

## 使用说明

### 开发环境设置
1. 克隆项目到本地
2. 创建虚拟环境：`python -m venv venv`
3. 激活虚拟环境：`venv\Scripts\activate` (Windows) 或 `source venv/bin/activate` (Linux/Mac)
4. 安装依赖：`pip install -r requirements.txt`
5. 配置环境：复制 `.env.example` 到 `.env` 并配置

### 运行系统

#### 命令行界面
```bash
python main.py
```

#### REST API (FastAPI)
```bash
python api.py
# 访问 http://localhost:8000/docs 查看API文档
```

#### 生成测试数据
```bash
python generate_test_data.py
```

#### 运行测试
```bash
python test_system.py
```

### 开发指南

1. **代码风格**: 遵循 PEP 8，使用 Black 格式化
2. **类型提示**: 所有函数使用类型提示
3. **文档字符串**: 所有公共函数和类包含文档字符串
4. **测试**: 编写单元测试验证功能
5. **日志**: 使用 logging 模块记录重要操作

## 性能优化

1. **异步处理**: FastAPI 提供异步请求处理
2. **并发**: 支持多工作进程处理请求
3. **缓存**: 启用 LLM 响应缓存
4. **数据库**: 可选择 Redis/PostgreSQL 提升性能
5. **监控**: 集成 Prometheus 监控系统状态

## 安全考虑

1. **输入验证**: 所有用户输入通过 Pydantic 验证
2. **文件限制**: 限制上传文件大小和类型
3. **会话管理**: 自动清理过期会话
4. **错误处理**: 优雅处理错误，不暴露敏感信息
5. **API 安全**: 可集成身份验证和授权
6. **CORS 配置**: 生产环境需配置允许的源

## FastAPI vs Flask 变更

### 主要变更
1. **框架**: Flask → FastAPI
2. **服务器**: Flask development server → Uvicorn
3. **异步**: 同步处理 → 异步处理（async/await）
4. **文档**: 手动编写 → 自动生成（Swagger/ReDoc）
5. **验证**: 手动验证 → Pydantic 自动验证
6. **类型提示**: 可选 → 必需（FastAPI 依赖）
7. **CORS**: flask-cors → FastAPI 中间件

### 优势
- 🚀 更高的性能（异步支持）
- 📄 自动生成的 API 文档
- 🔒 更强的类型安全
- 🛠️ 更好的开发体验
- 📊 内置数据验证
- 🌐 更简单的 CORS 配置

这个项目结构设计支持快速开发和功能扩展，同时保持代码的可维护性和可测试性。FastAPI 的引入使得 API 开发更加高效和现代化。
