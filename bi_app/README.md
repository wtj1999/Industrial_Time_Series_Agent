# 生产 BI 独立适配服务

`bi_app` 与本地 `agent_app`/`OrchestratorAgent` 完全分离，仅负责把前端生产 BI 请求转发至远程服务，并校验稳定响应信封。

- 本地接口：`POST /api/bi/query`
- 健康检查：`GET /health`
- 远程地址：通过 `BI_REMOTE_QUERY_URL` 配置，默认使用项目约定地址
- 超时配置：`BI_CONNECT_TIMEOUT_SECONDS`、`BI_REQUEST_TIMEOUT_SECONDS`

请求支持普通问题 `{query, thread_id}` 和确认恢复 `{query: "", thread_id, resume}` 两种形式。

