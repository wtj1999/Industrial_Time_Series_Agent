# 生产 BI 独立适配服务

`bi_app` 与本地 `agent_app`/`OrchestratorAgent` 独立。原有四类生产 BI 继续转发远程服务；新增 NG 问数直接读取金寨三期工厂数据库。

- 本地接口：`POST /api/bi/query`
- 健康检查：`GET /health`
- 远程地址：通过 `BI_REMOTE_QUERY_URL` 配置，默认使用项目约定地址
- 超时配置：`BI_CONNECT_TIMEOUT_SECONDS`、`BI_REQUEST_TIMEOUT_SECONDS`

## 四领域查询结果分析

制造、品质、成本、设备入口会在远程查询成功后生成领域分析，在查询结果表下展示总结、数据观察、分优先级的建议及验证方式。NG 智能体保留原有流程。

| 领域 | 分析重点 | 建议方向 |
| --- | --- | --- |
| 制造 | 投入产出计划差异、工时劳产率、损耗、批次流转 | 排产、齐套供料、节拍协同、人员调配与后续达成验证 |
| 品质 | 订单 A 品/非 A 品、预警处理与问题状态 | 重点订单复检、工艺一致性、响应及验证关闭；不把已处理等同已关闭 |
| 成本 | 工段用电、能耗费用、物料及库存、制费结构 | 空转能耗、用能安排、损耗和库存优化；不虚构预算、单价或节省金额 |
| 设备 | OEE 分项、停机/待料/堵料、故障及 MTBF/MTTR | 区分故障维修与供料/节拍组织，按检查结果维修并试机验证 |

前端每次请求传递可选 `domain`（`manufacturing/quality/cost/equipment`），筛选恢复时用 `analysis_query` 保留原问题。两个字段只在本地适配层消费，不转发远程 BI。旧调用若未传领域，仅在返回的数据表属于已知领域映射时启用分析，不从模糊用户问题猜测领域。确认阶段不分析；成功后结合原问题、已确认筛选和本次返回数据分析。

四个入口的确认卡片支持全部不勾选直接点击「不限定筛选并继续」。提交时为每个待确认字段传递已选列表，未选字段传 `[]`，明确表示已确认且不限制该字段，避免空对象被远程工作流当作尚未确认；日期范围等固定查询上下文继续沿用当前线程。部分选择时也保留其他待确认字段的空列表。已提交、失效或请求中的卡片不能重复提交。更新前端时需同时同步 `FieldConfirmationCard.tsx` 与新增的 `confirmation.ts`。

模型复用 `BI_NG_LLM_*` 配置，单次最多45秒、无自动重试。先扫描全部返回行计算每个数值指标的极值和重点对象；数值指标最多12个、字段最多24个、样例最多8行，文本限长。ID、凭据字段、布尔值和非有限数值不作为指标。百分数字符串保留百分数量纲；混合百分数与原始数值的列不做排名。不直接累加汇总与明细、比率、单价、MTBF/MTTR，不编造阈值、分母、单位、币种、同比环比或因果。界面说明分析基于本次返回数据，不宣称覆盖数据库全量。

空数据或无可分析数值时跳过模型；模型故障/超时返回 `analysis.status=unavailable`，原始查询仍然成功，表格不丢失。成功分析按用户、领域、原问题、筛选和完整返回数据指纹缓存24小时；默认最多保留512条，存储在 `bi_app/.state/bi_analysis.sqlite3`，可通过 `BI_ANALYSIS_CACHE_PATH` 修改。失败结果不缓存；缓存读写故障不影响查询或分析。

同步 `bi_app/analysis.py`、`bi_app/api.py`、`bi_app/schemas.py` 和前端改动到服务器后重新加载 BI 服务与前端；无新增 Python/npm 依赖。Vite BI 代理等待时间增加为240秒，覆盖远程查询及分析；使用构建后的 Nginx 部署时也需同步 `docker/nginx.conf` 并按现有部署方式加载。已有确认卡建议重新发起查询以携带领域与原问题。

验证：`python -m pytest bi_app/test_analysis.py bi_app/test_api.py bi_app/test_auth.py bi_app/ng/test_analysis.py bi_app/ng/test_ng.py -q`；前端执行 `npm run test:bi-analysis`、`npm run test:ng-chart` 和 `npm run build`。测试替换远程查询、数据库及模型调用，不代表生产模型已完成实际数据验收。

## BI 账户校验与服务器更新

BI 和 NG 接口要求前端传递 `Authorization: Bearer ...`，BI 向主后端的 `/api/auth/me` 校验会话，并从验证结果推导用户身份。外部传入的 `X-User-Id` 不作为身份凭证。

账户服务地址由 `AUTH_SERVICE_URL` 配置。未设置或为空时，Docker 容器默认使用 `http://backend:8000`，普通本机进程默认使用 `http://127.0.0.1:8000`。可以显式指定其他部署地址。Docker Compose 中 `bi-backend` 会等待 `backend` 健康后启动。地址不经过宿主机 HTTP 代理。

旧 BI 容器可能没有加载新增的 `AUTH_SERVICE_URL`，此前会回退到容器自己的 `127.0.0.1:8000`，从而在 NG 查询前就报「账户服务暂时不可用」。仅重新创建主 `backend` 容器不会刷新 `bi-backend` 的环境。

将更新后的 `bi_app/auth.py`、`bi_app/diagnose_auth.py` 和 `docker-compose.yml` 同步到服务器，在项目目录执行：

```bash
# 使用现有镜像，不重新构建或替换手动安装的依赖。
sudo docker compose up -d --no-deps --force-recreate --no-build --pull never bi-backend
sudo docker compose exec -T bi-backend python -m bi_app.diagnose_auth
```

诊断输出应指向 `http://backend:8000/api/auth/me`，并返回 HTTP 401：这是未提供 token 的诊断请求被正常拒绝，证明账户路由可达，不表示真实登录已失效。此命令不会创建账户、读取业务数据库或执行 NG 分析。

之后重新运行「统计近七日的NG类型和数量」。若仍失败，查看：

```bash
sudo docker compose logs --since=10m --tail=100 bi-backend
sudo docker compose ps backend bi-backend
```

日志会记录账户校验地址、异常类型及上游 HTTP 状态，不记录 token。`AUTH_SERVICE_UNREACHABLE` 表示连接/超时异常，`AUTH_SERVICE_INVALID_RESPONSE` 表示地址/接口版本或响应结构不匹配，其他上游错误返回 `AUTH_SERVICE_UNAVAILABLE`。真实会话被拒绝时仍返回 401，不能通过伪造用户 ID 或跳过认证继续查询。

请求支持普通问题 `{query, thread_id}` 和确认恢复 `{query: "", thread_id, resume}` 两种形式。

## 本地 NG 类型统计

前端入口：“我的智能体 → 生产域 → 不良品类型分析智能体”。卡片不展示示例，进入查询页可点击推荐问题。

1. 输入自然语言，如“统计近七日的NG类型和数量”。LLM 首先提取日期、分组维度和六个白名单筛选字段的**用户原话**，这些原话不会作为统计 SQL 的筛选值。
2. 根据问题确定 `shift_date` 起止日期（包含边界，北京时间；近七日包含今天），后续确认及查询沿用这一范围；`qualification_ratio_type` 始终为0。未指定日期默认近七日，单次默认最多366天。
3. 查询该时间范围内的实际租户、产线、班次、工单、工序、设备选项。对于明确提到的条件，再将真实数据库候选提供给 LLM 匹配简称、别名和模糊描述。模型仅返回候选编号，后端根据编号还原并校验实际值。例如“314线”可匹配“金寨三期314Ah”；“氦气检测”若可能对应一次/二次氦检，会提示用户确认，不擅自预选。无明确条件时跳过第二次 LLM 调用。
4. LangGraph `interrupt` 返回筛选卡片，展示识别出的统计分组、原话、真实候选及“已匹配/需确认/未匹配”。仅可靠匹配预选，歧义和未匹配不自动加限制；用户可以修改、清空或搜索其他实际值。不勾选即不限制，同字段取并集、不同字段取交集。提交时再次校验每个选中值存在于当前日期范围内，再使用 `Command(resume=...)` 恢复 SELECT 模板，按 `ng_type` 及额外分组维度做 `SUM(ng_count)`。确认阶段不再解析时间或匹配筛选值。
5. 对 `dim.dim_qual_defect_ni` 的 `defect_code` 去重后映射 `defect_name` 及 `technics_process_name`，防止重复字典记录放大数量。结果表包含“NG类型、NG编码、工序名称、NG数量”，其中“工序名称”来自字典视图；同编码有多个工序名称时去重后合并展示，未映射工序显示“—”。按工序分组时，额外的“工序”列仍来自明细视图。未匹配编码显示“未映射（编码）”，空编码显示“未分类NG”；中文名称相同但编码不同的项仍分别保留。
6. 返回中文类型柱状图、总量及分页明细表。单个图表始终按NG编码展示绿色单系列柱形。不指定额外维度时显示原NG类型分布；指定维度时，在图上方一排可横向滚动的小选择框中列出实际组合（例如“2026-10-10 · 设备A”），默认选中首个组合。点击组合即展示该组合内按NG类型汇总的分布及对应总量；点击“全部组合”则跨组合按NG编码汇总。日期组合按日期升序，其他组合按NG总量降序。每个图表按NG数量降序，默认显示前20种NG，可展开全部；不合并NG类型。下方明细始终保留全部NG编码及分组字段。

7. 聚合后进入 LangGraph `analyze` 节点，复用 `BI_NG_LLM_*` 模型配置生成结构化分析，随成功响应的 `analysis` 返回并展示在明细表下方，包含总结、数据观察、分优先级的设备检查/保养/维修建议及检修后验证方式。建议针对具体不良关联的设备机构或部件，按检查结果建议清洁、校准、紧固或更换磨损件，不把数据核对作为主要改善措施，也不把故障假设当成已确认根因。后端先基于全部返回行计算NG类型排行/占比、分组边际总量、组合排行及按天总量（仅在按天分组时提供）。分析摘要最多保留20种NG、每维度10项和10个组合（含组合内部前三种NG），总量、占比仍按完整结果计算。模型输入使用中文业务标签和不良名称，不提供NG编码、当前日期变量和省略数量元数据；未映射名称使用“未命名不良类型”，明细表仍保留实际编码。提示词要求仅展示中文不良名称，不输出内部字段、摘要截取说明、泛化免责声明或分析边界段落，兼容响应字段 `limitations` 固定为空。NG构成占比不能用于推断合格率、不良率。没有数据/合计不大于0时不调用分析模型；模型异常或超时（最多45秒、无自动重试）时保留查询结果并显示分析暂不可用。分析结果也保存在checkpoint中，重复提交不会重复调用LLM；提示词调整对新查询生效。

支持的额外分组维度：日期 `shift_date`（按天）、设备 `device_name`、工序 `technics_process_name`、产线 `technics_line_name`、班次 `shift`、工单 `produce_order_code`、租户 `tenant_id`。可组合多个维度，`ng_type` 始终保留；未指定则只按NG类型汇总。分组标识只从白名单组装，LLM不生成SQL。按周、月、小时分组尚未支持，按最近一周或本月限定查询范围仍支持。

例如：

- “切卷工序的每台设备的不良”：工序匹配为筛选条件，按设备 × NG类型统计。
- “切卷工序的每天的不良”：工序匹配为筛选条件，按日期 × NG类型统计。
- “近七日切卷工序每天每台设备的不良”：按日期 × 设备 × NG类型统计。

日期仅输出存在数据记录的分组，不额外补齐零记录日期。分组维度为空的记录保留为独立分组。

这里的“一次合格”指固定统计口径；当前指标是 **NG数量**，不计算合格率百分比。

接口：

- `POST /api/bi/ng/query`：首次 `{query, thread_id}`；返回 `need_confirm` 和 `confirm.confirmation_id`。
- 同一接口恢复：`{query:"", thread_id, confirmation_id, resume:{technics_line_name:["产线名称"]}}`。`resume:{}` 表示所有筛选维度不限制，但保留首次识别的分组。日期、分组、统计口径和未知字段不能通过 resume 修改。
- `POST /api/bi/ng/options`：`{thread_id, confirmation_id, field, search:"", offset:0}`；返回 `values/has_more/next_offset`。选项查询使用断点内冻结的日期。
- 工作区隔离键由 Bearer 会话验证结果生成，BI 内部再通过 `X-User-Id` 传给 NG 工作流；它不是数据库 `tenant_id` 的权限控制。租户在本功能中是用户可选的业务筛选。

配置：将 [ng.env.example](ng.env.example) 的设置填入 `bi_app/.env`。数据库密码只从 `BI_NG_DB_PASSWORD` 读取；LLM 的 `BI_NG_LLM_*` 可独立配置，也兼容环境中的 `MODEL_NAME/BASE_URL/API_KEY`，不读取 `agent_app` 代码或密钥文件。

内网模型连接默认不使用宿主机 HTTP 代理；若部署环境需要代理，可设置 `BI_NG_LLM_TRUST_ENV=true`。

高基数字段匹配会读取界面首屏之外的真实选项，默认每个被提到的字段最多扫描5000项（`BI_NG_MATCH_SCAN_LIMIT`），按名称近似召回每个描述最多60项（`BI_NG_MATCH_CANDIDATE_LIMIT`）供 LLM 判断。扫描不完整时只提示候选，不自动预选；可在前端搜索实际名称继续选择。模型返回不存在的候选编号、遗漏或重复决策时，相关描述会标为未匹配。

```sh
python -m pip install -r bi_app/requirements.txt
python -m uvicorn bi_app.api:app --host 0.0.0.0 --port 8010 --workers 1
python -m pytest bi_app/test_api.py bi_app/ng/test_ng.py bi_app/ng/test_analysis.py -q
# Frontend chart totals, grouping, date ordering and category identity:
cd frontend
npm run test:ng-chart
```

SQLite checkpoint 默认保存在 `bi_app/.state/ng_checkpoints.sqlite3`，已忽略版本控制。服务重启后，同一用户和线程携带确认ID可继续恢复；前端刷新仍按现有页面行为开启新会话。使用单 worker 运行（同线程请求由进程内锁串行化），多实例部署需换用共享锁和服务端持久化 checkpoint。Docker 的现有 `./bi_app:/app/bi_app` 挂载会保留 checkpoint；修改依赖后需重建 `bi-backend` 镜像。

过期或旧确认卡返回 409/410。重复提交同一筛选返回缓存结果；数据库暂时失败后可用原确认及相同筛选重试，不重复解析。全部数据库操作均为 SELECT，连接和查询分别设置超时。

实现参考：[LangGraph interrupt/resume](https://docs.langchain.com/oss/python/langgraph/interrupts)、[PyMySQL 参数绑定](https://pymysql.readthedocs.io/en/latest/modules/cursors.html)。



## 工厂租户参数

`POST /api/bi/query` 支持字符串字段 `tenant_id`，首次查询与确认恢复请求均应携带。适配层校验为 1–64 位数字字符串后透传至远端 BI 接口，分析缓存也包含租户标识。为兼容旧客户端，未提供该字段时保持原有透传行为。

生产域下，金寨二期的制造/品质/成本/设备 BI 入口使用 `11200001`，芜湖一期的同名四个入口使用 `14100001`。租户来自目录配置，不依赖用户在问题中指定。进入不同目录或应用会重新创建 BI 页面和对话，后续确认沿用该工厂租户。

首次请求示例：`{"query":"统计最近30天设备运行时间","thread_id":"factory-thread","domain":"equipment","tenant_id":"14100001"}`。确认请求示例：`{"query":"","thread_id":"factory-thread","resume":{"device_type":[]},"domain":"equipment","tenant_id":"14100001"}`。

部署需同步前端目录配置、BI 页面与类型，以及 `bi_app/schemas.py`、`bi_app/analysis.py`，重新构建前端并重启 BI 服务。远端 BI 服务也需支持 `tenant_id` 并按该租户过滤数据。
