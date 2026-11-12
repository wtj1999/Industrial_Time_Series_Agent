# 前端对接文档

后端地址 `http://<主机>:8767`，前端只需对接两个接口。本文分四块：**怎么发起、人机交互怎么对接、结果怎么对接、空结果怎么返回**。

文内所有 JSON 都是后端真实响应。

---

## 一、怎么发起

```
POST /api/query
Content-Type: application/json
```

### 1.1 请求字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | string | 二选一 | 新提问，如 `"滁州L600涂布参数"` |
| `confirm` | object | 二选一 | 回传用户的勾选，见第二节 |
| `session_id` | string | **是** | 会话标识。同一个会话每一轮都要传同一个值，自己生成 UUID 即可 |

> `query` 和 `confirm` 只能传一个，同时传会返回 `error`。
> 其余字段（如 `tenant_id`、`thread_id`、`resume`）**都不需要传**，后端不认。

发起一次提问：

```json
{ "query": "滁州L600涂布参数", "session_id": "sess-abc-123" }
```

业务错误也返回 **HTTP 200**，靠响应里的 `status` 判断。

### 1.2 响应结构总览

响应只有三种，先看 `status` 和 `content_type` 分支：

| `status` | `content_type` | 含义 | 前端动作 |
| --- | --- | --- | --- |
| `need_confirm` | `options` | 需要用户勾选 | 渲染候选项，回传 `confirm` |
| `success` | `table` | 查询完成（含空结果） | 渲染表格 |
| `error` | `text` | 出错 | 显示 `message` |

公共字段：`session_id`（会话标识）、`message`（提示语）、`status`、`content_type`、`type`（阶段名，仅调试用，**不要用它做分支**）。

---

## 二、人机交互怎么对接

### 2.1 断点响应（真实响应，候选项已截断）

下面是「金寨三期正极涂布参数」勾选 2 条工艺路线后返回的**工序层**断点。
注意：只预选了「正极涂布」，「负极涂布」保持未勾选；`preselect` 里两个 id
分别属于两条不同工艺路线（同名工序）。

```json
{
  "session_id": "d1",
  "message": "已勾选 2 项，已汇总 82 个候选项，请继续勾选：",
  "content_type": "options",
  "status": "need_confirm",
  "type": "select_process_multi",
  "confirm": {
    "selection_mode": "multiple",
    "options": [
      { "id": "2048949299794657281", "label": "正极涂布", "detail": "金寨三期 / 金寨三期314Ah", "selected": true },
      { "id": "2048950831294431234", "label": "正极涂布", "detail": "金寨三期 / 金寨三期588AH", "selected": true },
      { "id": "2048949332464091137", "label": "负极涂布", "detail": "金寨三期 / 金寨三期314Ah", "selected": false }
    ],
    "preselect": ["2048949299794657281", "2048950831294431234"],
    "page_size": 10,
    "total_count": 82,
    "shown_count": 82,
    "session_id": "d1",
    "reply_with": {
      "field": "confirm",
      "payload": { "option_ids": ["2048949299794657281", "2048950831294431234"] },
      "payload_template": { "option_ids": ["<options[].id>"] },
      "preselect": ["2048949299794657281", "2048950831294431234"],
      "session_id": "d1"
    }
  }
}
```

### 2.2 字段说明

| 字段 | 说明 |
| --- | --- |
| `message` | 提示语，直接显示给用户 |
| `confirm.selection_mode` | 恒为 `"multiple"`，用**复选框**渲染 |
| `confirm.options[].id` | 选项 id，回传时用。**当字符串处理**（19 位数字，JS `Number` 会丢精度） |
| `confirm.options[].label` | 显示名 |
| `confirm.options[].detail` | 副标题：`基地 / 工艺路线`（参数层再加 `/ 工序`）。多基地多路线汇总时靠它区分同名项 |
| `confirm.options[].selected` | **是否预选**。`true` 表示后端已理解到这一项，前端应把复选框**预先勾上** |
| `confirm.preselect` | 预选项 id 数组（字符串），等价于筛 `options[].selected === true` |
| `confirm.reply_with.payload` | **已替前端填好的 `option_ids`**（就是预选项 id）。懒人做法：直接把这份 `payload` 当 `confirm` 回传，等于「确认预选」，不必自己渲染勾选状态 |
| `confirm.reply_with.payload_template` | 字段结构占位说明（`option_ids` 应为选项 id 字符串数组） |
| `confirm.total_count` | **真实**候选总数（不因展示上限而变） |
| `confirm.shown_count` | 本次下发的候选条数，等于 `options.length` |
| `confirm.page_size` | 每页条数，固定 10 |

### 2.3 什么时候会出现

后端无法唯一确定时会返回断点，可能连续出现多次，逐层收敛：**基地 → 工艺路线 → 工序 → 参数**。

如果用户问题已经说清（如「金寨三期588AH的正极涂布速度上限」），后端会跳过若干层直接给结果。

**已理解的层会被预选**：例如问「滁州L600正极涂布参数」，路线选定后返回的工序候选里，
`正极涂布` 的 `selected` 就是 `true`。前端把它勾上，用户点一次确认即可，不用再翻找。

预选规则：

| 层 | 何时预选 |
| --- | --- |
| 工艺路线 | 用户给了规格号（如 L600）时，命中的路线预选；或该路线下有用户问的工序（且不是所有路线都有） |
| 工序 | 模型理解出的工序名匹配到的候选；**精确同名优先**，且不会把「正极涂布」与「负极涂布」互相勾上 |
| 参数 | 不做预选（参数通常要用户自己挑） |

> 后端用 `config/process_catalog.json` 里的真实工序名校正意图：用户说「正极涂布」时只预选正极，不会连负极一起勾。

> 预选只是**默认勾选**，不是替用户决定：最终仍以用户回传的 `option_ids` 为准。
> 如果某个推断会勾上全部候选（比如 7 条路线全含「正极涂布」），后端**不预选**，避免误导。
>
> **前端实现二选一**：① 读 `options[].selected` / `preselect` 把复选框勾上，用户确认后回传勾选的 id；
> ② 直接把 `reply_with.payload` 原样作为 `confirm` 回传（等于确认预选）。两种都可能拿到空数组
> （无预选时），空数组语义见 2.5「一个都不勾 = 全选当前层」，请注意区分。

### 2.4 无符合条件参数的工序：照常显示，勾选后说明

参数表里有些参数**最小值、最大值都为空，标准范围也是空或 `/`**（简称「三无」），这类参数没有任何可展示的数值，SQL 层直接不返回。
但**工序本身照常显示在候选里**，后端不会在展示前逐个预查参数（那样几十个工序会拖慢响应）。
所以某道工序可能一条参数都查不到，用户勾选后才按结果分三种：

| 情况 | 后端行为 |
| --- | --- |
| 勾中的工序全都有参数 | 正常进入参数勾选 / 结果 |
| 部分勾中的工序无参数 | `message` 写明「工序『…』没有符合条件…的参数，已跳过；以下为其余工序的参数」，**其余工序的参数照常显示** |
| 勾中的工序**全部**无参数 | 返回 `success` + `empty: true` 的空表格，`message` 说明「本次查询无数据，已返回空表格」，**不要求重新勾选** |

> 所以 `message` 一定要展示给用户，它解释了「为什么这次没数据 / 少了一些参数」。
> 进入参数勾选层后，每个参数候选项的 `detail` 是「`基地 / 工艺路线 / 工序`」，多路线汇总时同名参数也能区分来源。

### 2.5 回传规则

用**同一个 `session_id`** 回传勾选的 id（这里回传 2.1 的两个预选项）：

```json
{
  "session_id": "d1",
  "confirm": { "option_ids": ["2048949299794657281", "2048950831294431234"] }
}
```

| 情况 | 传法 |
| --- | --- |
| 勾选 1 项 | `{"option_ids": ["id1"]}` |
| 勾选多项 | `{"option_ids": ["id1", "id2"]}` |
| **一个都不勾** | `{"option_ids": []}` —— 表示**全选当前层**（参数层即该工序全部参数） |

### 2.6 前端循环写法

响应可能是断点，也可能是结果，所以写成循环：

```js
async function ask(query) {
  let res = await post({ query, session_id: sessionId });
  while (res.status === "need_confirm") {
    const cf = res.confirm;
    // 预选 id：优先 preselect，其次 options[].selected，其次 reply_with.payload
    const initial = cf.preselect.length
      ? cf.preselect
      : (cf.options.filter(o => o.selected).map(o => o.id));
    // 把复选框按 initial 预勾上，用户可增删；返回选中项的 id 字符串数组
    const ids = await showOptions(cf.options, initial);
    // 懒人做法：若用户点"确认预选"，可跳过 showOptions，
    // 直接回传 cf.reply_with.payload（即 { option_ids: [...预选id] }）
    res = await post({ session_id: sessionId, confirm: { option_ids: ids } });
  }
  return res;   // success 或 error
}
```

---

## 三、结果怎么对接

### 3.1 结果响应（真实响应）

```json
{
  "session_id": "d1",
  "message": "已按你勾选的 1 个参数查询，结果如下",
  "content_type": "table",
  "status": "success",
  "type": "success",
  "empty": false,
  "row_count": 1,
  "total_count": 1,
  "page_size": 10,
  "tenant_id": "2100001",
  "columns": {
    "detail": "基地",
    "label": "工艺路线",
    "process": "工序",
    "param_code": "参数编码",
    "param_name": "参数名称",
    "stand_value": "标准范围",
    "min_value": "最小值",
    "max_value": "最大值",
    "create_time": "创建时间",
    "update_time": "更新时间",
    "version": "版本",
    "is_self_check": "是否自检",
    "check_num": "检验值个数"
  },
  "data": [
    {
      "detail": "滁州一期",
      "label": "L600工艺路线",
      "process": "正极涂布",
      "param_code": "RG-ZJTB001",
      "param_name": "单面面密度",
      "stand_value": "/",
      "min_value": "206.5",
      "max_value": "210.5",
      "create_time": "2024-09-18 15:22:31",
      "update_time": "2026-01-27 14:37:57",
      "version": 1,
      "is_self_check": null,
      "check_num": null
    }
  ]
}
```

### 3.2 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 固定 `"success"` |
| `content_type` | string | 固定 `"table"` |
| `empty` | boolean | 是否空结果，见第四节 |
| `row_count` | number | 本次返回行数 |
| `total_count` | number | 总行数（与 `row_count` 相同） |
| `page_size` | number | 每页条数，固定 10。**分页在前端做，翻页不再请求后端** |
| `data` | array | 数据行，**一次性全量下发** |
| `columns` | object | 英文字段 → 中文表头，渲染表头时用它 |
| `tenant_id` | string \| null | 租户标识，由后端从 `pro_route` 表查出。跨租户查询时为 `A、B` 形式，无数据时为 `null` |
| `message` | string | 提示语 |

### 3.3 data 每行字段

**来源列**（说明这条数据从哪儿查出来）：

| 字段 | 中文表头 | 说明 |
| --- | --- | --- |
| `detail` | 基地 | 该行属于哪个基地 |
| `label` | 工艺路线 | 该行属于哪条工艺路线 |
| `process` | 工序 | 该行属于哪道工序 |

**参数数据**（用 `columns` 里的中文名做表头）：

| 字段 | 中文表头 | 类型 |
| --- | --- | --- |
| `param_code` | 参数编码 | string |
| `param_name` | 参数名称 | string |
| `stand_value` | 标准范围 | string（如 `"100-150"`、`"/"`） |
| `min_value` | 最小值 | number 或 string 或 null（DECIMAL 去尾零后可能是字符串，如 `"206.5"`） |
| `max_value` | 最大值 | number 或 string 或 null（同上） |
| `create_time` | 创建时间 | string |
| `update_time` | 更新时间 | string |
| `version` | 版本 | number |
| `is_self_check` | 是否自检 | number \| null |
| `check_num` | 检验值个数 | number \| null |

### 3.4 渲染要点

- **表头用 `columns`**，不要自己维护映射；`columns` 的 key 顺序即展示顺序。
- **不要写死列**：用户问「最大值」时值列会前置，列数会变。
- **`tenant_id` 只在响应顶层**，`data` 每行没有该字段。
- **分页本地做**：`data` 已是全部数据，翻页只切数组。
- **数值已格式化**：`70.000000000` 已变成 `70`。
- **`null` 显示成空**：部分参数没有最小值/最大值。

---

## 四、空结果怎么返回

**空结果不是错误**：`status` 仍是 `"success"`，`content_type` 仍是 `"table"`，只是没有数据行。

### 4.1 空结果响应（真实响应）

```json
{
  "session_id": "4525019c-48e4-4170-8ec8-2474c47f5933",
  "message": "已勾选 3 项。工序「配对、OCV5、DCR」没有符合条件（最小值/最大值/标准范围均为空）的参数，本次查询无数据，已返回空表格",
  "content_type": "table",
  "status": "success",
  "type": "success",
  "empty": true,
  "row_count": 0,
  "total_count": 0,
  "page_size": 10,
  "tenant_id": null,
  "columns": {
    "param_code": "参数编码",
    "param_name": "参数名称",
    "stand_value": "标准范围",
    "min_value": "最小值",
    "max_value": "最大值",
    "create_time": "创建时间",
    "update_time": "更新时间",
    "version": "版本",
    "is_self_check": "是否自检",
    "check_num": "检验值个数"
  },
  "data": []
}
```

### 4.2 判断方式：看 `empty`

| 字段 | 有数据 | 空结果 |
| --- | --- | --- |
| `status` | `"success"` | `"success"`（一样） |
| `content_type` | `"table"` | `"table"`（一样） |
| `empty` | `false` | **`true`** ← 用它判断 |
| `row_count` | N | `0` |
| `data` | `[{...}]` | `[]` |
| `columns` | 有 | **仍然返回** |
| `tenant_id` | 值 | `null` |

### 4.3 前端处理

```js
if (res.status === "success") {
  if (res.empty) {
    renderEmptyTable(res.columns);   // 用 columns 画空表头 + 显示「暂无数据」
  } else {
    renderTable(res.columns, res.data);
  }
}
```

> 空结果时 `columns` 依然返回，可以渲染带表头的空表格，而不是只弹一句提示。

---

## 五、出错时

`status = "error"`，`content_type = "text"`，直接显示 `message`。

```json
{
  "session_id": "doc-d",
  "message": "query / confirm 只能传其中一个（当前传了：query、confirm）",
  "content_type": "text",
  "status": "error",
  "type": "error"
}
```

| message 片段 | 原因 |
| --- | --- |
| `只能传其中一个` | `query` 和 `confirm` 同时传了 |
| `必须提供 query` | 两个都没传 |
| `会话不存在或已失效` | `session_id` 不对，或后端重启过 |
| `该候选项无效或已过期` | 回传的 option id 不在当前候选列表里 |
| `当前会话不在等待选择` | 会话已结束，又回传了 `confirm` |

---

## 六、健康检查

```
GET /health
```

```json
{
  "status": "ok",
  "version": "0.3.0",
  "prompts": ["intent_extract"],
  "bases": ["金寨三期", "金寨二期", "芜湖一期", "..."]
}
```

`bases` 是基地名列表（含产线别名），可用于输入框下拉提示。

---

## 七、注意事项

1. **`session_id` 每轮都要传同一个**，否则会话上下文丢失。
2. **ID 当字符串处理**：选项 id 是 19 位数字串，原样传递。
3. **分页在前端做**，`data` 已是全量。
4. **空结果不是错误**，判 `empty`。
5. **数值已规范化**，直接显示即可。
6. **不要传 `tenant_id` / `thread_id` / `resume`**，后端不认这三个字段。
7. **`message` 总要展示**：哪些工序无符合条件的参数、为什么这次是空表格，都只写在这里。
8. **`selected` 只用于初始勾选**，别用它判断"已经确定"，最终以用户回传为准。
9. **候选是全量下发的**（最多 200 条），别再向后端要"下一页候选"。
10. 后端为单副本部署，不要做多实例负载均衡。
