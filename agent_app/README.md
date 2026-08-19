# 工业时间序列多智能体系统

一个基于 LangChain 的工业时间序列数据分析多智能体系统，采用 "先理解数据，再理解用户，再调度能力，再持续对话" 的设计理念。

## 🎯 核心特性

### 🏗️ 五层架构设计

1. **输入层** - 接收用户查询、CSV文件和历史上下文
2. **理解层** - 文件解析、CSV画像、用户意图识别、参数抽取
3. **编排层** - 决定调用哪个能力、是否需要追问
4. **任务层** - 预测、异常诊断、分析解释、报告生成
5. **记忆与状态层** - 会话记忆、CSV画像记忆、参数记忆

### 🤖 专业智能体分工

- **会话管理智能体** - 维护会话状态、判断上下文延续性
- **CSV画像智能体** - 深度分析数据结构、类型、质量
- **意图识别智能体** - 理解自然语言、提取任务参数
- **任务调度智能体** - 协调各智能体、管理多轮对话
- **预测智能体** - 时间序列预测与置信区间
- **异常诊断智能体** - 多方法异常检测与根因分析
- **解释智能体** - 业务解读与风险识别
- **报告生成智能体** - 综合分析与决策建议

### 🔄 多轮对话支持

- **延续性识别** - 自动识别"继续"、"展开"等追问
- **参数继承** - 多轮对话自动继承已确认参数
- **上下文保持** - 统一状态对象避免信息丢失
- **参数修改** - 支持"改成"、"改为"等修改指令

## 📦 安装部署

### 环境要求

- Python 3.8+
- pip 或 conda

### 快速安装

```bash
# 克隆项目
git clone <repository-url>
cd agent_app

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env .env
# 编辑 .env 文件，设置 API密钥等配置
```

### 环境配置

编辑 `.env` 文件：

```bash
# OpenAI 兼容模型接口配置
MODEL_NAME=Qwen3-235B-A22B
BASE_URL=http://your-openai-compatible-api:8000/v1
API_KEY=your-api-key-here
TEMPERATURE=0.7
TIMEOUT=600

# 数据库配置（可选）
DB_BACKEND=sqlite
DB_CONNECTION_STRING=sqlite:///sessions.db

# 会话配置
MAX_CONVERSATION_HISTORY=50
SESSION_TIMEOUT_MINUTES=30
```

## 🚀 快速开始

### 命令行界面

```bash
# 启动交互式命令行界面
python main.py
```

### Python API

```python
from main import IndustrialTimeSeriesAgent

# 初始化系统
agent = IndustrialTimeSeriesAgent()

# 处理查询
result = agent.process_query(
    query="预测未来25步",
    file_path="data/sensor_data.csv"
)

# 查看结果
if result['success']:
    print(result['response'])
    session_id = result['session_id']
```

### 多轮对话

```python
# 继续会话
result = agent.continue_session(
    session_id=session_id,
    query="再详细解释一下异常点"
)
```

### REST API

```bash
# 启动 API 服务器
python api.py
```

API 基于 FastAPI 框架，提供以下功能：
- 📄 自动生成的 Swagger 文档 (`/docs`)
- 📚 ReDoc 文档 (`/redoc`)
- 🚀 高性能异步处理
- 🔒 自动数据验证
- 🌐 CORS 支持

主要 API 端点：

- `POST /api/query` - 处理查询
- `GET /api/session/{session_id}` - 获取会话信息
- `POST /api/session/{session_id}/continue` - 继续会话
- `DELETE /api/session/{session_id}/reset` - 重置任务
- `GET /api/session/{session_id}/tasks` - 获取可用任务
- `POST /api/session` - 创建新会话
- `GET /api/status` - 系统状态
- `POST /api/cleanup` - 清理过期会话
- `GET /health` - 健康检查

## 💡 使用示例

### 预测分析

```python
# 简单预测
agent.process_query(
    query="预测未来25步",
    file_path="data.csv"
)

# 指定参数预测
agent.process_query(
    query="用ARIMA模型预测目标列未来50步",
    file_path="data.csv"
)
```

### 异常检测

```python
# 异常检测
agent.process_query(
    query="检测传感器数据中的异常点",
    file_path="sensor_data.csv"
)

# 追问异常详情
agent.continue_session(
    session_id=session_id,
    query="这些异常的可能原因是什么？"
)
```

### 趋势分析

```python
# 趋势分析
agent.process_query(
    query="分析销售数据的趋势",
    file_path="sales_data.csv"
)

# 深度分析
agent.continue_session(
    session_id=session_id,
    query="做深度分析，包括季节性"
)
```

### 综合报告

```python
# 生成综合报告
agent.process_query(
    query="生成包含预测、异常检测和趋势分析的综合报告",
    file_path="industrial_data.csv"
)
```

## 🎨 系统架构

### 核心设计原则

1. **统一状态管理** - 避免各智能体各自维护记忆
2. **画像与任务分离** - 数据层记忆与业务层记忆分开存储
3. **追问即新意图** - 将追问视为基于上轮结果的 follow-up intent
4. **结构化状态存储** - 不仅存对话文本，更存结构化参数对象

### 数据流

```
用户输入 → 意图识别 → CSV画像 → 参数补全 → 任务路由 → 智能体执行 → 结果解释 → 状态回写
```

### 状态对象结构

```python
SessionState:
  - session_id: 会话唯一标识
  - csv_profile: 数据集画像（长期保留）
  - current_task: 当前任务类型
  - confirmed_spec: 已确认的任务参数
  - dialogue_history: 对话历史
  - analysis_artifacts: 分析结果存储
  - clarification_pending: 是否待澄清
```

## 🔧 扩展开发

### 添加新的分析类型

1. 在 `models/schemas.py` 中添加新的 TaskType
2. 创建专门的智能体类继承基础功能
3. 在 `OrchestratorAgent` 中注册新的任务类型
4. 更新 `ParserAgent` 的意图识别模式

### 添加新的工具函数

1. 在 `tools/` 目录下创建新的工具模块
2. 实现工具函数并添加类型提示
3. 在 `tools/__init__.py` 中导出
4. 在相关智能体中集成使用

### 自定义 LLM 模型

```python
# config/settings.py
class LLMConfig(BaseModel):
    provider: str = "custom"
    model_name: str = "your-model"
    # ... 其他配置
```

## 📊 支持的分析类型

- ✅ 时间序列预测（多种方法）
- ✅ 异常检测（多算法支持）
- ✅ 趋势分析
- ✅ 相关性分析
- ✅ 数据解释
- ✅ 报告生成
- ✅ 对比分析
- ✅ 季节性检测

## 🔒 安全性考虑

- 输入验证和清理
- 文件大小限制
- 会话超时管理
- 错误处理和日志记录
- API 访问控制（可扩展）

## 🚨 已知限制

1. 需要有效的 LLM API 密钥
2. 大文件处理可能需要较多内存
3. 复杂查询可能需要较长时间
4. 某些功能需要特定格式的数据

## 🛠️ 故障排除

### 常见问题

**Q: API 密钥无效**
```
A: 检查 .env 文件中的 API_KEY、BASE_URL 和 MODEL_NAME 配置
```

**Q: 文件加载失败**
```
A: 确保文件路径正确，文件格式为 CSV/Excel/Parquet
```

**Q: 会话丢失**
```
A: 检查会话超时设置，默认30分钟无活动后过期
```

**Q: 分析结果不准确**
```
A: 检查数据质量，确保时间列和目标列正确识别
```

## 📚 相关文档

- [API 文档](./docs/API.md) - REST API 详细说明
- [项目结构](./PROJECT_STRUCTURE.md) - 项目结构和模块说明
- [示例代码](./example_usage.py) - 详细使用示例
- [测试脚本](./test_system.py) - 系统测试脚本

## 🔧 API 文档

启动 API 服务器后，访问自动生成的文档：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

这些交互式文档提供：
- 完整的 API 端点列表
- 请求/响应模型
- 在线测试功能
- 数据验证规则
- 错误处理说明

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。

## 🙏 致谢

感谢 LangChain 团队提供的优秀框架，以及所有贡献者的支持。

---

**版本**: 1.0.0
**更新日期**: 2026-05-29
**联系方式**: 通过 GitHub Issues 提交问题和建议
