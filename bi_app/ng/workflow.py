"""Parse -> discover -> match -> interrupt -> parameterized aggregate -> analyze."""

import hashlib
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .config import NgSettings
from .analysis import NgResultAnalyzer
from .errors import NgError
from .parser import NgIntentParser
from .repository import NgRepository
from .schemas import FILTER_LABELS, GROUP_LABELS, NgFilters, NgOptionsRequest, NgParameters, NgQueryRequest

logger = logging.getLogger(__name__)


class NgState(TypedDict, total=False):
    query: str
    thread_id: str
    confirmation_id: str
    expires_at: float
    parameters: dict[str, Any]
    filter_mentions: dict[str, list[str]]
    fields: list[dict]
    confirm: dict[str, Any]
    selected: dict[str, list[str]]
    result: dict[str, Any]


class NgWorkflow:
    def __init__(self, settings: NgSettings, *, parser=None, repository=None, analyzer=None, checkpointer=None):
        self.settings = settings
        self.parser = parser or NgIntentParser(settings)
        self.repository = repository or NgRepository(settings)
        self.analyzer = analyzer or NgResultAnalyzer(settings)
        self._connection = None
        if checkpointer is None:
            settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(settings.checkpoint_path), check_same_thread=False)
            # SqliteSaver initializes its schema and WAL mode on first use.
            checkpointer = SqliteSaver(self._connection)
        self.checkpointer = checkpointer
        self._guard = threading.Lock()
        self._locks: dict[str, tuple[threading.Lock, int]] = {}
        builder = StateGraph(NgState)
        builder.add_node("parse", self._parse)
        builder.add_node("discover", self._discover)
        builder.add_node("match_filters", self._match_filters)
        builder.add_node("confirm", self._confirm)
        builder.add_node("aggregate", self._aggregate)
        builder.add_node("analyze", self._analyze)
        builder.add_edge(START, "parse")
        builder.add_edge("parse", "discover")
        builder.add_edge("discover", "match_filters")
        builder.add_edge("match_filters", "confirm")
        builder.add_edge("confirm", "aggregate")
        builder.add_edge("aggregate", "analyze")
        builder.add_edge("analyze", END)
        self.graph = builder.compile(checkpointer=checkpointer)

    def close(self):
        if hasattr(self.parser, "close"):
            self.parser.close()
        if hasattr(self.analyzer, "close"):
            self.analyzer.close()
        if self._connection is not None:
            self._connection.close()

    @contextmanager
    def _thread_lock(self, key: str):
        # Serialize one user's thread; unrelated threads can query concurrently.
        with self._guard:
            lock, count = self._locks.get(key, (threading.Lock(), 0))
            self._locks[key] = (lock, count + 1)
        try:
            with lock:
                yield
        finally:
            with self._guard:
                _, count = self._locks[key]
                if count == 1:
                    del self._locks[key]
                else:
                    self._locks[key] = (lock, count - 1)

    @staticmethod
    def _config(thread_id: str, user_id: str) -> dict:
        key = hashlib.sha256(f"{user_id}\0{thread_id}".encode()).hexdigest()
        return {"configurable": {"thread_id": f"ng:{key}"}}

    def _parse(self, state: NgState) -> dict:
        parameters = self.parser.parse(state["query"])
        # Raw mentions stay separate from executable parameters until database grounding.
        return {"parameters": parameters.model_copy(update={"filters": NgFilters()}).model_dump(mode="json"),
                "filter_mentions": parameters.filters.nonempty()}

    def _discover(self, state: NgState) -> dict:
        parameters = NgParameters.model_validate(state["parameters"])
        fields = self.repository.discover(parameters)
        return {"fields": fields}

    def _match_filters(self, state: NgState) -> dict:
        parameters = NgParameters.model_validate(state["parameters"])
        mentions = NgFilters.model_validate(state["filter_mentions"])
        fields = [dict(field) for field in state["fields"]]
        grounded, matches = NgFilters(), []
        if mentions.nonempty():
            options = {field["cls"]: {"values": field["values"], "truncated": False} for field in fields}
            paginated = [field["cls"] for field in fields if field.get("has_more") and field["cls"] in mentions.nonempty()]
            if paginated:
                options.update(self.repository.matching_values(parameters, paginated))
            grounded, matches = self.parser.match_filters(state["query"], mentions, options)
            # Defense in depth: even a faulty matcher must not preselect invented values.
            for name, values in grounded.nonempty().items():
                if not set(values).issubset(options[name]["values"]):
                    raise NgError("筛选匹配包含数据库候选以外的值，请重新提问", 422)
        selected = grounded.nonempty()
        for field in fields:
            field["selected_values"] = selected.get(field["cls"], [])
            # Surface recalled matches even when they occur beyond the UI's first page.
            recalled = [value for match in matches if match["field"] == field["cls"] for value in match["values"]]
            field["values"] = list(dict.fromkeys([*recalled, *field["values"]]))
        period = f"{parameters.start_date} 至 {parameters.end_date}"
        grouping_text = " × ".join([*[GROUP_LABELS[field] for field in parameters.group_by], "NG类型"])
        return {"parameters": parameters.model_copy(update={"filters": grounded}).model_dump(mode="json"), "confirm": {
            "type": "field_confirm",
            "confirmation_id": state["confirmation_id"],
            "thread_id": state["thread_id"],
            "selected_table": "dwd.dwd_qual_defect_detail_pim",
            "rewritten_query": f"{period}，一次合格口径，按{grouping_text}统计NG数量",
            "message": f"根据问题确定的日期为 {period}，统计口径为一次合格（qualification_ratio_type=0）。"
                       "可勾选筛选值；同一字段多选取并集，不同字段取交集。未勾选的字段不限制。",
            "locked_conditions": [f"班次日期：{period}", "一次合格口径", f"统计分组：{grouping_text}"],
            "group_by": [{"field": field, "label": GROUP_LABELS[field]} for field in parameters.group_by],
            "need_confirm": fields,
            "filter_matches": matches,
        }}

    def _confirm(self, state: NgState) -> dict:
        # No LLM/DB calls before this interrupt: resuming does not rediscover options or dates.
        answer = interrupt(state["confirm"])
        return {"selected": NgFilters.model_validate(answer["filters"]).nonempty()}

    def _aggregate(self, state: NgState) -> dict:
        parameters = NgParameters.model_validate(state["parameters"])
        filters = NgFilters.model_validate(state["selected"])
        rows, sql_template = self.repository.aggregate(parameters, filters)
        period = {"start_date": str(parameters.start_date), "end_date": str(parameters.end_date)}
        selected_text = "；".join(f"{FILTER_LABELS[key]}：{'、'.join(values)}" for key, values in filters.nonempty().items())
        grouping_text = " × ".join([*[GROUP_LABELS[field] for field in parameters.group_by], "NG类型"])
        description = f"{parameters.start_date} 至 {parameters.end_date}，一次合格口径下按{grouping_text}汇总不良数量"
        return {"result": {
            "status": "success", "type": "success", "thread_id": state["thread_id"],
            "rewritten_query": description + (f"；{selected_text}" if selected_text else "；全部筛选维度"),
            "table": "dwd.dwd_qual_defect_detail_pim",
            "row_count": len(rows),
            "data": [{**{GROUP_LABELS[field]: row["dimensions"].get(field) for field in parameters.group_by},
                      "NG类型": row["ng_name"], "NG编码": row["ng_type"],
                      "工序名称": row.get("ng_process_name"), "NG数量": row["ng_count"]} for row in rows],
            "sql": sql_template,
            "chart": {"type": "ng_bar", "rows": rows, "period": period,
                      "group_by": [{"field": field, "label": GROUP_LABELS[field]} for field in parameters.group_by],
                      "total_ng_count": sum(row["ng_count"] for row in rows)},
        }}

    def _analyze(self, state: NgState) -> dict:
        # The aggregate is already checkpointed; advice cannot invalidate a valid query.
        try:
            analysis = self.analyzer.analyze(
                state["query"], NgParameters.model_validate(state["parameters"]),
                NgFilters.model_validate(state["selected"]), state["result"]["chart"]["rows"],
            )
        except Exception as exc:
            logger.warning("NG result analysis unavailable (%s)", type(exc).__name__)
            analysis = {"status": "unavailable", "message": "分析服务暂时不可用，查询数据已保留；可稍后重新查询以生成分析。"}
        return {"result": {**state["result"], "analysis": analysis}}

    def _snapshot(self, config: dict, confirmation_id: str):
        snapshot = self.graph.get_state(config)
        state = snapshot.values
        if not state or state.get("confirmation_id") != confirmation_id:
            raise NgError("该筛选卡片已失效，请使用最新的筛选卡片或重新提问", 409)
        if state.get("expires_at", 0) < time.time():
            raise NgError("筛选确认已过期，请重新提问", 410)
        return snapshot

    def query(self, request: NgQueryRequest, user_id: str) -> dict:
        config = self._config(request.thread_id, user_id)
        with self._thread_lock(config["configurable"]["thread_id"]):
            if request.resume is None:
                # An independent question replaces the pending run on this chat thread.
                self.checkpointer.delete_thread(config["configurable"]["thread_id"])
                result = self.graph.invoke({
                    "query": request.query, "thread_id": request.thread_id,
                    "confirmation_id": str(uuid4()),
                    "expires_at": time.time() + self.settings.confirmation_ttl_seconds,
                }, config)
            else:
                snapshot = self._snapshot(config, request.confirmation_id or "")
                selected = NgFilters.model_validate(request.resume).nonempty()
                if snapshot.next == ("confirm",):
                    self.repository.validate_filters(NgParameters.model_validate(snapshot.values["parameters"]), NgFilters.model_validate(selected))
                    # A bare {} is interpreted by LangGraph as an empty interrupt-ID map.
                    # Keep the resume envelope nonempty even when all checkboxes are clear.
                    result = self.graph.invoke(Command(resume={"filters": selected}), config)
                elif snapshot.values.get("selected") == selected:
                    # DB failures can be retried without re-consuming an interrupt.
                    if snapshot.next in {("aggregate",), ("analyze",)}:
                        result = self.graph.invoke(None, config)
                    elif not snapshot.next and snapshot.values.get("result"):
                        return snapshot.values["result"]
                    else:
                        raise NgError("当前查询无法恢复，请重新提问", 409)
                else:
                    raise NgError("该筛选卡片已经提交，请重新提问以更改筛选条件", 409)
            if result.get("__interrupt__"):
                return {"status": "need_confirm", "type": "field_confirm",
                        "thread_id": request.thread_id, "confirm": result["__interrupt__"][0].value}
            return result["result"]

    def options(self, request: NgOptionsRequest, user_id: str) -> dict:
        config = self._config(request.thread_id, user_id)
        with self._thread_lock(config["configurable"]["thread_id"]):
            snapshot = self._snapshot(config, request.confirmation_id)
            if snapshot.next != ("confirm",):
                raise NgError("筛选已提交，请重新提问以选择其他筛选条件", 409)
            parameters = NgParameters.model_validate(snapshot.values["parameters"])
            return self.repository.options(parameters, request.field, request.search, request.offset)
