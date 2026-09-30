# Chronos-2 / TimesFM 2.5 微调服务

本项目提供统一的时间序列微调接口，目前支持：

- `chronos-2`：调用 `Chronos2Pipeline.fit()`，支持 `full` 和 `lora`。
- `timesfm-2.5`：使用 Transformers 模型和 PEFT，当前只支持 `lora`。

服务提供两种调用方式：

- 同步 JSON：训练结束后一次性返回结果和训练日志。
- POST SSE：提交请求后，在同一个 HTTP 响应中持续返回训练进度和最终结果。

- URL:http://10.2.128.43:19155/time/seriesFinetune/stream

## 6. 统一请求格式

两个模型共用以下请求结构：

```json
{
  "model": "chronos-2",
  "dataList": [
    [10.1, 10.5, 11.0, 11.8, 12.1, 12.5],
    [20.0, 20.8, 21.2, 21.9, 22.4, 23.0]
  ],
  "outputDir": "/data/huggingface/finetuned/chronos-factory-a",
  "baseModelPath": "/data/huggingface/chronos-2",
  "device": "cuda:2",
  "predictionLength": 2,
  "contextLength": 4,
  "numSteps": 1000,
  "learningRate": 0.000001,
  "batchSize": 32,
  "finetuneMode": "full",
  "loggingSteps": 100
}
```

### 公共参数

| 参数 | 必填 | 默认值 | 说明                                                                                          |
| --- | :---: | --- |---------------------------------------------------------------------------------------------|
| `model` | 是 | 无 | `chronos-2` 或 `timesfm-2.5`                                                                 |
| `dataList` | 是 | 无 | 一维或二维数值数组；二维时每个子数组是一条序列                                                                     |
| `outputDir` | 是 | 无 | 容器内的微调输出目录，必须位于可写挂载中                                                                        |
| `baseModelPath` | 否 | 见下文 | 容器内基础模型目录，/data/huggingface/chronos-2, /data/huggingface/timesfm-2.5-200m-transformers 只有这两个 |
| `device` | 否 | 模型相关 | 例如 `cuda`、`cuda:0`、`cuda:2`                                                         |
| `predictionLength` | 是 | 无 | 训练预测窗口长度，必须大于 0                                                                             |
| `contextLength` | 否 | 模型相关 | 输入上下文窗口长度；TimesFM 默认 64                                                                     |
| `numSteps` | 否 | 1000 | 优化器更新总次数，每个 batch 完成一次反向传播和参数更新即算一步                                                         |
| `learningRate` | 否 | `1e-5` | 学习率                                                                                         |
| `batchSize` | 否 | 32 | 每一步使用的训练样本窗口数量                                                                              |
| `finetuneMode` | 否 | `lora` | Chronos 支持 `full`/`lora`；TimesFM 只支持 `lora`                                                 |
| `loggingSteps` | 否 | 100 | 每隔多少训练步产生一次进度日志；TimesFM 设为 0 可关闭周期日志                                                        |


## 7. Chronos-2 微调

Chronos 调用官方接口，核心逻辑等价于：

```python
pipeline = Chronos2Pipeline.from_pretrained(base_model, device_map=device)
finetuned_pipeline = pipeline.fit(
    inputs=train_inputs,
    prediction_length=prediction_length,
    context_length=context_length,
    finetune_mode=finetune_mode,
    learning_rate=learning_rate,
    num_steps=num_steps,
    batch_size=batch_size,
    logging_steps=logging_steps,
    output_dir=output_dir,
)
```

完整请求示例：

```json
{
  "model": "chronos-2",
  "dataList": [
    [10.1, 10.5, 11.0, 11.8, 12.1, 12.5, 12.9, 13.4],
    [20.0, 20.8, 21.2, 21.9, 22.4, 23.0, 23.6, 24.1]
  ],
  "outputDir": "/data/huggingface/finetuned/chronos-factory-a",
  "baseModelPath": "/data/huggingface/chronos-2",
  "device": "cuda:2",
  "predictionLength": 2,
  "contextLength": 4,
  "numSteps": 1000,
  "learningRate": 0.000001,
  "batchSize": 32,
  "finetuneMode": "full",
  "loggingSteps": 100
}
```

默认可加载检查点为：

```text
<outputDir>/finetuned-ckpt
```

可通过额外参数 `finetuned_ckpt_name` 修改子目录名。API 返回的 `modelPath` 是最终检查点目录，不需要前端自行拼接。

## 8. TimesFM 2.5 微调

TimesFM 使用 `TimesFm2_5ModelForPrediction` 加载基础模型，再通过 PEFT 添加 LoRA 层。训练数据会按照 `contextLength + predictionLength` 切成滑动窗口。

完整请求示例：

```json
{
  "model": "timesfm-2.5",
  "dataList": [
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
  ],
  "outputDir": "/data/huggingface/finetuned/timesfm-factory-a",
  "baseModelPath": "/data/huggingface/timesfm-2.5-200m-transformers",
  "device": "cuda:0",
  "predictionLength": 2,
  "contextLength": 8,
  "numSteps": 1000,
  "learningRate": 0.00001,
  "batchSize": 32,
  "finetuneMode": "lora",
  "loggingSteps": 100,
  "loraR": 4,
  "loraAlpha": 8,
  "loraDropout": 0.05
}
```

TimesFM 特有参数：

| 参数 | 默认值 | 说明 |
| --- | ---: | --- |
| `loraR` | 4 | LoRA 低秩维度 |
| `loraAlpha` | 8 | LoRA 缩放系数 |
| `loraDropout` | 0.05 | LoRA dropout |

每条 TimesFM 序列必须满足：

```text
序列长度 >= contextLength + predictionLength
```

否则接口返回：

```text
Each series must be at least contextLength + predictionLength long
```

TimesFM 保存的是 PEFT adapter，因此 `outputDir` 本身就是最终 `modelPath`。其中的 `adapter_config.json` 会记录基础模型位置，预测时应将该适配器目录作为 `modelPath`。

## 9. 同步 JSON 接口

### 请求

```http
POST /time/seriesFinetune
Content-Type: application/json
```

命令行示例：

```bash
curl -X POST http://localhost:19155/time/seriesFinetune \
  -H 'Content-Type: application/json' \
  -d @request.json
```

该请求会一直等待训练完成，适合短任务、调试或不需要实时进度的调用方。

### 成功响应

```json
{
  "code": "success",
  "model": "chronos-2",
  "outputDir": "/data/huggingface/finetuned/chronos-factory-a",
  "modelPath": "/data/huggingface/finetuned/chronos-factory-a/finetuned-ckpt",
  "baseModelPath": "/data/huggingface/chronos-2",
  "trainingLogs": [
    {
      "step": 100,
      "totalSteps": 1000,
      "progress": 10.0,
      "loss": 7.676,
      "grad_norm": 27.7009,
      "learning_rate": 9.01e-7,
      "epoch": 0.1
    }
  ]
}
```

`trainingLogs` 只在训练完成后随响应一起返回。Chronos 的具体指标名来自 Transformers Trainer；TimesFM 周期日志使用 `loss` 和 `learningRate`。

### 参数错误响应

参数校验或训练初始化失败时返回 HTTP 400：

```json
{
  "detail": "predictionLength is required"
}
```

## 10. POST SSE 实时日志接口

### 请求

```http
POST /time/seriesFinetune/stream
Content-Type: application/json
Accept: text/event-stream
```

请求体与同步接口完全相同：

```bash
curl -N -X POST http://localhost:19155/time/seriesFinetune/stream \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  -d @request.json
```

`-N` 用于关闭 curl 输出缓冲，否则终端可能不能及时看到事件。

### 事件顺序

正常情况下：

```text
status -> progress（0 到多次）-> completed
```

异常情况下：

```text
status -> progress（可能有）-> failed
```

连接空闲超过约 15 秒时，服务会发送 SSE 注释作为 keep-alive：

```text
: keep-alive
```

### 事件示例

训练开始：

```text
event: status
data: {"status":"running","message":"Training started"}
```

训练进度：

```text
event: progress
data: {"step":100,"totalSteps":1000,"progress":10.0,"loss":7.676,"learning_rate":9.01e-7,"epoch":0.1}
```

训练完成：

```text
event: completed
data: {"status":"completed","model":"chronos-2","outputDir":"/data/huggingface/finetuned/chronos-factory-a","modelPath":"/data/huggingface/finetuned/chronos-factory-a/finetuned-ckpt","baseModelPath":"/data/huggingface/chronos-2"}
```

训练失败：

```text
event: failed
data: {"status":"failed","message":"错误信息"}
```

注意：SSE 接口在成功建立响应后，训练过程中的错误以 `failed` 事件返回，而不是再切换成普通 HTTP JSON 错误。

### 浏览器调用示例

浏览器原生 `EventSource` 只能发 GET 请求，不能用于这个 POST 接口。应使用 `fetch()` 读取响应流：

```javascript
const response = await fetch(
  "http://localhost:19155/time/seriesFinetune/stream",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(requestBody),
  },
);

if (!response.ok) {
  throw new Error(await response.text());
}

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { value, done } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const messages = buffer.split("\n\n");
  buffer = messages.pop() ?? "";

  for (const message of messages) {
    if (!message || message.startsWith(":")) continue;

    let event = "message";
    let data = "";
    for (const line of message.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }

    const payload = JSON.parse(data);
    console.log(event, payload);

    if (event === "completed") {
      console.log("模型保存位置：", payload.modelPath);
    }
    if (event === "failed") {
      throw new Error(payload.message);
    }
  }
}
```

如果经过 Nginx 等反向代理，需要关闭该接口的响应缓冲。服务已返回 `X-Accel-Buffering: no`，代理层仍应确认没有覆盖该配置，并适当增加读取超时时间。

## 11. 微调权重如何用于预测

微调响应中的 `modelPath` 是后续加载权重时应使用的路径：

```json
{
  "model": "chronos-2",
  "modelPath": "/data/huggingface/finetuned/chronos-factory-a/finetuned-ckpt",
  "dataList": [[10.1, 10.5, 11.0, 11.8]],
  "predictionLength": 12
}
```

TimesFM 则传适配器目录：

```json
{
  "model": "timesfm-2.5",
  "modelPath": "/data/huggingface/finetuned/timesfm-factory-a",
  "dataList": [[1, 2, 3, 4, 5, 6, 7, 8]],
  "predictionLength": 12
}
```

模型缓存键由“模型名 + 模型路径”组成，因此基础权重和多个微调权重可以同时存在，不会因为模型名相同而错误复用旧权重。

当前 Compose 只启动微调服务，`server_finetune.py` 本身不提供预测接口；以上请求体适用于单独启动预测服务后的模型加载约定。

## 12. 是否需要预加载模型

微调服务不需要预加载预测模型。预加载只是在预测服务启动时提前占用时间和显存，换取第一次预测请求更低的延迟，不影响功能正确性。

项目的预测模型加载采用懒加载和缓存：

- 默认在第一次使用某个 `model + modelPath` 时加载。
- 后续相同组合复用缓存。
- 不同微调目录对应不同缓存实例。
- `PRELOAD_MODELS=true` 仅适合基础模型固定、显存充足、且非常关注首请求延迟的部署。

对微调权重频繁新增或切换的场景，保持懒加载更合适。

## 13. 故障排查

### `TimesFm2_5ModelForPrediction` 无法导入

典型错误：

```text
cannot import name 'TimesFm2_5ModelForPrediction' from 'transformers'
```

确认容器中的实际版本：

```bash
docker compose exec finetuning python -c "import transformers; print(transformers.__version__)"
```

项目要求 `transformers==5.3.0`。修改依赖后必须重建镜像，单纯重启不会重新安装包：

```bash
docker compose build --no-cache finetuning
docker compose up -d finetuning
```

### Hugging Face Hub 依赖冲突

`transformers==5.3.0` 要求较新的 `huggingface-hub`。不要继续固定旧的 `huggingface_hub==0.36.x`；当前项目使用兼容版本 `1.3.5`。

在容器内检查依赖一致性：

```bash
docker compose exec finetuning pip check
```

### `finetune_mode` 被传给 `TrainingArguments`

`finetuneMode` 是 `Chronos2Pipeline.fit()` 的参数，不应直接传入 Transformers `TrainingArguments`。项目代码已经把该参数传给官方 `pipeline.fit()`。如果仍出现：

```text
TrainingArguments.__init__() got an unexpected keyword argument 'finetune_mode'
```

通常说明运行的还是旧代码或旧镜像：

```bash
docker compose exec finetuning grep -n "Chronos2Pipeline.fit" /app/timeSeries/predictor_server/finetune.py
docker compose restart finetuning
```

### 输出目录没有文件

检查三个位置：

```bash
docker compose exec finetuning ls -la /data/huggingface/finetuned
ls -la "${MODEL_DIR}/finetuned"
docker compose logs --tail=200 finetuning
```

请求中的 `outputDir` 必须填写容器路径 `/data/huggingface/...`，不能填写只有宿主机才能识别的路径。

### SSE 前端一次性收到全部日志

常见原因是客户端、网关或反向代理缓冲。确认：

- curl 使用 `-N`。
- 前端逐块读取 `response.body`。
- Nginx 对该路由关闭 `proxy_buffering`。
- 网关的空闲超时大于训练时间。

### CUDA 显存不足

可依次尝试：

- 减小 `batchSize`。
- 使用 `finetuneMode: "lora"`。
- 减小 `contextLength`。
- 为请求指定空闲 GPU，例如 `device: "cuda:1"`。
- 避免在同一块 GPU 同时运行多个训练任务。

## 14. 测试

运行与微调相关的测试：

```bash
pytest -q tests/test_finetune.py tests/test_training_stream.py
```

检查 Compose 配置是否有效：

```bash
docker compose config
```

检查容器实际挂载：

```bash
docker compose exec finetuning ls -la /app/timeSeries
docker compose exec finetuning ls -la /data/huggingface
```

## 15. API 快速索引

| 方法 | 路径 | 返回方式 | 用途 |
| --- | --- | --- | --- |
| GET | `/health` | JSON | 健康检查 |
| POST | `/time/seriesFinetune` | JSON | 等待训练完成后返回结果及全部日志 |
| POST | `/time/seriesFinetune/stream` | SSE | 实时返回状态、训练进度及最终结果 |

启动后还可以访问 FastAPI 自动文档：

```text
http://localhost:19155/docs
```
