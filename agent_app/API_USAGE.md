# API 使用说明

## 重要说明

**session_id 现在是必传参数！**

所有 API 请求都必须提供 `session_id` 查询参数。如果 `session_id` 不存在，系统会自动创建该会话。

## 文件上传功能

### 使用文件上传进行分析

API 现在支持直接上传 CSV 文件进行分析，无需预先上传文件。

### 请求格式

```bash
# session_id 是必传参数
curl -X POST "http://localhost:8000/api/query?session_id=user123" \
  -F "query=预测未来25步" \
  -F "file=@/path/to/your/data.csv"
```

### 使用 Python requests

```python
import requests

# API 端点
url = "http://localhost:8000/api/query"

# session_id 是必传参数（查询参数）
params = {
    "session_id": "user123"  # 必传
}

data = {
    "query": "预测未来25步"
}

# 上传文件
files = {
    "file": open("data.csv", "rb")
}

# 发送请求
response = requests.post(url, params=params, data=data, files=files)
result = response.json()

print(result)
```

### 使用 JavaScript/TypeScript

```javascript
const formData = new FormData();

// 添加查询文本
formData.append('query', '预测未来25步');

// 添加文件
formData.append('file', fileInput.files[0]);

// session_id 作为必传查询参数
const sessionId = 'user123';  // 必须提供

// 发送请求
fetch(`http://localhost:8000/api/query?session_id=${sessionId}`, {
    method: 'POST',
    body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

### 支持的文件格式

- `.csv` - CSV 文件
- `.xlsx` - Excel 文件
- `.parquet` - Parquet 文件

### 文件大小限制

- 默认最大文件大小：100MB
- 可在 `.env` 文件中配置 `MAX_FILE_SIZE_MB`

### 文件存储

- 上传的文件保存在 `uploads/` 目录
- 文件名保持原始名称
- 如果文件已存在，将被覆盖

### 完整示例

```python
import requests
import json

class TimeSeriesAgentAPI:
    """工业时间序列多智能体系统 API 客户端"""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def analyze_with_file(self, query: str, file_path: str, session_id: str):
        """
        使用文件上传进行分析

        Args:
            query: 分析查询
            file_path: 文件路径
            session_id: 会话ID（必传）

        Returns:
            分析结果
        """
        url = f"{self.base_url}/api/query"

        # session_id 作为必传查询参数
        params = {"session_id": session_id}

        # 准备表单数据
        data = {"query": query}

        # 准备文件
        with open(file_path, "rb") as f:
            files = {"file": f}

            # 发送请求
            response = requests.post(url, params=params, data=data, files=files)

        return response.json()

    def continue_analysis(self, session_id: str, query: str):
        """
        继续分析（不需要重新上传文件）

        Args:
            session_id: 会话ID（必传）
            query: 后续查询

        Returns:
            分析结果
        """
        url = f"{self.base_url}/api/query"

        # session_id 作为必传查询参数
        params = {"session_id": session_id}
        data = {"query": query}

        # 继续分析时不需要文件
        response = requests.post(url, params=params, data=data)

        return response.json()

# 使用示例
if __name__ == "__main__":
    api = TimeSeriesAgentAPI()

    # 使用固定的 session_id
    session_id = "user123"

    # 第一次分析（上传文件）
    result = api.analyze_with_file(
        query="预测未来25步",
        file_path="data/sensor_data.csv",
        session_id=session_id
    )

    print("分析结果:", json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("success"):
        # 继续分析（不需要重新上传文件）
        followup = api.continue_analysis(
            session_id=session_id,
            query="详细解释一下异常点"
        )

        print("追问结果:", json.dumps(followup, indent=2, ensure_ascii=False))
```

### 错误处理

```python
import requests

try:
    url = "http://localhost:8000/api/query"

    # session_id 是必传参数
    params = {"session_id": "user123"}  # 必须提供

    data = {"query": "预测未来25步"}
    files = {"file": open("data.csv", "rb")}

    response = requests.post(url, params=params, data=data, files=files)

    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            print("分析成功:", result["response"])
        else:
            print("分析失败:", result.get("error"))
    else:
        print(f"HTTP 错误: {response.status_code}")
        print(response.json())

except FileNotFoundError:
    print("文件不存在")
except Exception as e:
    print(f"请求失败: {str(e)}")
```

### Swagger UI 测试

启动 API 服务器后，访问 `http://localhost:8000/docs`：

1. 找到 `POST /api/query` 端点
2. 点击 "Try it out"
3. **session_id 参数**: 在查询参数部分填写（**必传**）
4. **query**: 填写查询文本
5. **file**: 点击 "Choose File" 上传文件
6. 点击 "Execute" 执行请求

### 新的 API 设计

#### 参数传递方式
- **session_id**: 查询参数 `?session_id=xxx`（**必传**）
- **query**: 请求体 JSON 字段
- **file**: 表单文件上传

#### session_id 行为
- 如果 session_id 存在：继续现有会话
- 如果 session_id 不存在：自动创建新会话
- **不会自动生成新的 session_id**

#### 示例请求
```http
POST /api/query?session_id=user123 HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="query"

预测未来25步
------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="data.csv"
Content-Type: text/csv

[csv file content]
------WebKitFormBoundary--
```

### 注意事项

1. **session_id 必传**:
   - 所有请求必须提供 session_id
   - 不会自动生成新的 session_id
   - 客户端需要管理 session_id

2. **参数位置**:
   - `session_id` 是查询参数（必传）
   - `query` 在请求体中
   - `file` 作为表单文件上传

3. **文件格式**: 确保上传的文件格式正确
4. **文件大小**: 默认限制 100MB，可在配置中修改
5. **文件清理**: 定期清理 `uploads/` 目录中的旧文件
6. **并发限制**: 大文件上传可能影响性能
7. **安全性**: 生产环境应添加文件内容检查

### 高级用法

#### 批量文件处理

```python
import requests
import os

def batch_analyze(files, queries, session_id):
    """使用同一 session_id 批量分析多个文件"""
    results = []

    url = "http://localhost:8000/api/query"
    params = {"session_id": session_id}

    for file_path, query in zip(files, queries):
        with open(file_path, "rb") as f:
            response = requests.post(
                url,
                params=params,  # 使用同一 session_id
                data={"query": query},
                files={"file": f}
            )
            results.append(response.json())

    return results

# 使用
session_id = "user123"
files = ["data1.csv", "data2.csv", "data3.csv"]
queries = ["分析第一个文件", "分析第二个文件", "分析第三个文件"]
results = batch_analyze(files, queries, session_id)
```

#### 多轮对话

```python
import requests

class MultiTurnConversation:
    def __init__(self, session_id: str, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session_id = session_id

    def first_query(self, query, file_path):
        """第一次查询（上传文件）"""
        url = f"{self.base_url}/api/query"

        params = {"session_id": self.session_id}

        with open(file_path, "rb") as f:
            response = requests.post(
                url,
                params=params,
                data={"query": query},
                files={"file": f}
            )

        return response.json()

    def follow_up_query(self, query):
        """后续查询（不需要文件）"""
        url = f"{self.base_url}/api/query"

        params = {"session_id": self.session_id}
        data = {"query": query}

        response = requests.post(url, params=params, data=data)
        return response.json()

# 使用
conversation = MultiTurnConversation(session_id="user123")

# 第一轮（上传文件）
result1 = conversation.first_query(
    query="分析这个数据集",
    file_path="data.csv"
)

# 第二轮（不需要文件）
result2 = conversation.follow_up_query("详细解释异常点")

# 第三轮
result3 = conversation.follow_up_query("生成预测报告")
```

### session_id 管理建议

1. **客户端生成**: 在客户端应用中生成唯一的 session_id
2. **用户关联**: 可以将 session_id 与用户账户关联
3. **持久化**: 在客户端保存 session_id 以便后续使用
4. **安全性**: 不要在 URL 或日志中暴露 session_id

```python
import uuid

# 生成唯一 session_id
session_id = f"user_{uuid.uuid4().hex[:8]}"  # "user_abc12345"
# 或
session_id = str(uuid.uuid4())  # 标准UUID格式
```

通过将 `session_id` 作为必传参数，API 设计更加清晰和可控！
