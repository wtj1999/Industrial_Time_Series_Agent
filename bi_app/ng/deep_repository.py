"""Bound target/trace queries, temporal product joins, and NG/OK box statistics."""

import bisect
import json
import math
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pymysql

from .catalog import identifier
from .errors import NgError
from .genealogy import resolve_genealogy, stamp
from .record_selection import order_sql, rule_description, rule_filter, selection_config
from .schemas import FILTER_LABELS, NgFilters, NgParameters
from .visualization import SHARED_MATERIAL_PROCESSES, interval_bubbles, parameter_record_stats


def numeric(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def box_stats(values: list[float], total: int) -> dict:
    ordered = sorted(values)
    count = len(ordered)
    result = {"count": count, "missing_count": total - count}
    if not count:
        return {**result, **dict.fromkeys(["min", "q1", "median", "q3", "max", "mean", "whisker_low", "whisker_high"]), "outlier_count": 0, "outliers": []}

    def percentile(p):
        position = (count - 1) * p
        low, high = math.floor(position), math.ceil(position)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    q1, median, q3 = percentile(.25), percentile(.5), percentile(.75)
    fence_low, fence_high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    low_index, high_index = bisect.bisect_left(ordered, fence_low), bisect.bisect_right(ordered, fence_high)
    outliers = ordered[:low_index] + ordered[high_index:]
    # Retain the complete distribution in statistics; only plotted outlier dots are capped.
    plotted = outliers if len(outliers) <= 80 else [outliers[round(i * (len(outliers) - 1) / 79)] for i in range(80)]
    return {**result, "min": ordered[0], "q1": q1, "median": median, "q3": q3, "max": ordered[-1],
            "mean": math.fsum(value / count for value in ordered), "whisker_low": ordered[low_index],
            "whisker_high": ordered[high_index - 1], "outlier_count": len(outliers), "outliers": plotted}


def classify(row: dict, ng_code: str) -> str:
    raw = str(row.get("ng_type") or "").strip()
    tokens = set(re.findall(r"[\w-]+", raw))
    if ng_code in tokens:
        return "NG"
    if raw.upper() in {"", "OK"} and numeric(row.get("product_quality")) == 1:
        return "OK"
    return "excluded"


def trace_codes(row: dict) -> list[str]:
    """Use explicit material genealogy, never barcode substring/format guesses."""
    raw = str(row.get("product_in_code") or "").strip()
    try:
        parsed = json.loads(raw) if raw.startswith("[") else None
    except ValueError:
        parsed = None
    inputs = parsed if isinstance(parsed, list) else re.split(r"[,，;；|]", raw)
    codes = list(dict.fromkeys(str(value).strip() for value in [row.get("product_code"), *inputs] if value is not None and str(value).strip()))
    if len(codes) > 100:
        raise NgError("产品投入编码过多，请核对追溯数据", 422)
    return codes


def feature_query(process: dict, columns: list[str], tenant: str, lookups: list[tuple[str, datetime]], limit: int, *, exact_cutoffs: bool = False) -> tuple[str, list]:
    """Return one policy-selected event per code/cutoff, entirely inside the DB."""
    clock, _ = selection_config(process)
    codes = sorted({code for code, _ in lookups})
    selected = ", ".join(identifier(column) for column in columns)
    qualified = ", ".join(f"p.{identifier(column)}" for column in columns)
    clauses, rule_values = rule_filter(process)
    where = ["`tenant_id` = %s", "`technics_process_code` = %s",
             f"`product_code` IN ({','.join(['%s'] * len(codes))})", f"{identifier(clock)} <= CAST(%s AS DATETIME)", *clauses]
    values = [tenant, process["code"], *codes, max(cutoff for _, cutoff in lookups), *rule_values]
    if not exact_cutoffs:
        sql = f"""SELECT {selected}, `_source_row_count` FROM (
    SELECT {selected},
           COUNT(1) OVER (PARTITION BY `tenant_id`, `product_code`) AS `_source_row_count`,
           ROW_NUMBER() OVER (PARTITION BY `tenant_id`, `product_code` ORDER BY {order_sql(process, columns)}) AS `_trace_rank`
    FROM dwd.{identifier(process['table'])} WHERE {' AND '.join(where)}
) AS ranked WHERE `_trace_rank` = 1 LIMIT %s"""
        return sql, [*values, limit + 1]
    requests = []
    for code, cutoff in lookups:
        requests.append("SELECT %s AS lookup_code, CAST(%s AS DATETIME) AS lookup_time")
        values.extend([code, cutoff])
    partition = "p.`tenant_id`, p.`product_code`, requested.lookup_time"
    sql = f"""SELECT {selected}, `_source_row_count` FROM (
    SELECT {qualified},
           COUNT(1) OVER (PARTITION BY {partition}) AS `_source_row_count`,
           ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {order_sql(process, columns, 'p')}) AS `_trace_rank`
    FROM (
        SELECT {selected} FROM dwd.{identifier(process['table'])}
        WHERE {' AND '.join(where)}
    ) AS p
    INNER JOIN ({' UNION ALL '.join(requests)}) AS requested
      ON p.`product_code` = requested.lookup_code
     AND p.{identifier(clock)} <= requested.lookup_time
) AS ranked
WHERE `_trace_rank` = 1 LIMIT %s"""
    return sql, [*values, limit + 1]


class NgDeepRepository:
    def __init__(self, repository, settings=None):
        self.repository = repository
        self.settings = settings or repository.settings

    def _read(self, sql, values):
        started = time.perf_counter()
        for attempt in range(2):
            try:
                with self.repository.connection() as connection, connection.cursor() as cursor:
                    cursor.execute(sql, values)
                    rows = list(cursor.fetchall())
                break
            except NgError as exc:
                cause = exc.__cause__
                if attempt or not isinstance(cause, pymysql.OperationalError) or cause.args[0] not in {2003, 2006, 2013}:
                    raise
                # One fresh connection for a transient read failure; never retry invalid SQL.
                time.sleep(.25)
        return rows, round(time.perf_counter() - started, 4)

    def defect_processes(self, ng_code: str) -> set[str]:
        rows, _ = self._read("SELECT DISTINCT technics_process_code FROM dim.dim_qual_defect_ni WHERE defect_code = %s", [ng_code])
        return {str(row["technics_process_code"]) for row in rows}

    def targets(self, context: dict, target: dict) -> tuple[list[dict], dict]:
        parameters = NgParameters.model_validate(context["parameters"])
        filters = NgFilters.model_validate(context["filters"])
        process = target["process"]
        clock, rule = selection_config(process)
        date_field = process.get("date_filter_field")
        columns = set(process["columns"])
        if date_field != "shift_date" or date_field not in columns:
            raise NgError("目标宽表缺少已验证的shift_date字段，无法按班次日期筛选，请刷新字段字典", 422)
        required = {"tenant_id", "product_code", clock, "ng_type", "product_quality", target["column"]}
        if not required.issubset(columns):
            raise NgError("目标宽表缺少追溯或质量字段，请刷新字段字典", 422)
        clauses = [f"{identifier(date_field)} >= %s", f"{identifier(date_field)} <= %s", "`technics_process_code` = %s"]
        values = [parameters.start_date.isoformat(), parameters.end_date.isoformat(), process["code"]]
        # Original selections and the clicked row's dimensions are intersected.
        for name, selected in filters.nonempty().items():
            if name not in columns:
                raise NgError(f"目标宽表缺少筛选维度：{FILTER_LABELS[name]}", 422)
            clauses.append(f"{identifier(name)} IN ({','.join(['%s'] * len(selected))})")
            values.extend(selected)
        for name, value in context["row"].get("dimensions", {}).items():
            if name not in {"shift_date", *FILTER_LABELS} or name not in columns:
                raise NgError("结果行包含无效的分组维度", 422)
            if value is None:
                clauses.append(f"{identifier(name)} IS NULL")
            else:
                clauses.append(f"{identifier(name)} = %s")
                values.append(value)
        rule_clauses, rule_values = rule_filter(process)
        clauses.extend(rule_clauses)
        values.extend(rule_values)
        selected = sorted(required | (columns & {"produce_id", "product_in_code", "technics_step_code", "technics_line_name"}))
        projections = ','.join(identifier(col) for col in selected)
        sql = f"""SELECT {projections}, `_source_row_count` FROM (
    SELECT {projections},
           COUNT(1) OVER (PARTITION BY `tenant_id`, `product_code`) AS `_source_row_count`,
           ROW_NUMBER() OVER (PARTITION BY `tenant_id`, `product_code` ORDER BY {order_sql(process, selected)}) AS `_trace_rank`
    FROM dwd.{identifier(process['table'])} WHERE {' AND '.join(clauses)}
) AS ranked WHERE `_trace_rank` = 1 LIMIT %s"""
        rows, seconds = self._read(sql, [*values, self.settings.deep_max_rows + 1])
        if len(rows) > self.settings.deep_max_rows:
            raise NgError(f"目标产品结果超过{self.settings.deep_max_rows}条，请缩小日期或筛选范围；未使用截断样本分析", 422)
        latest, no_key, source_rows = {}, 0, 0
        for row in rows:
            raw_count = int(row.get("_source_row_count") or 1)
            source_rows += raw_count
            if row.get("tenant_id") is None or not str(row.get("product_code") or "").strip():
                no_key += raw_count
                continue
            key = (str(row["tenant_id"]), str(row["product_code"]))
            step = int(str(row.get(rule.get("step_field"), "-1")).strip()) if rule["mode"] == "last_numeric_step_latest" else -1
            order = (step, stamp(row.get(clock)), str(row.get("produce_id") or ""), json_tie(row))
            if key not in latest or order > latest[key][0]:
                latest[key] = (order, row)
        products = []
        for key, (_, row) in latest.items():
            products.append({**row, "_key": key, "_anchor": stamp(row.get(clock)),
                             "_group": classify(row, context["row"]["ng_type"]), "_trace_codes": trace_codes(row)})
        return products, {"table": process["table"], "seconds": seconds, "rows": len(rows),
                          "source_rows": source_rows, "product_count": len(products), "duplicate_rows": source_rows - no_key - len(products),
                          "invalid_product_rows": no_key, "date_filter_field": date_field, "sort_time_field": clock, "record_selection": rule}

    def features(self, products: list[dict], features: list[dict], *, workers: int | None = None, progress=None) -> tuple[dict, list[dict], float]:
        by_table = defaultdict(list)
        for field in features:
            by_table[(field["process"]["table"], field["process"]["code"])].append(field)
        tasks = []
        for (table, code), fields in by_table.items():
            by_tenant = defaultdict(set)
            for row in products:
                if row["_group"] != "excluded" and row["_anchor"] != datetime.min:
                    codes = (row["_feature_codes"].get((table, code), []) if "_feature_codes" in row
                             else row.get("_trace_codes", [row["_key"][1]]))
                    by_tenant[row["_key"][0]].update((value, row["_anchor"]) for value in codes)
            process = fields[0]["process"]
            clock, _ = selection_config(process)
            columns = sorted({"tenant_id", "product_code", clock, *(field["column"] for field in fields)} | (set(process["columns"]) & {"produce_id", "technics_step_code"}))
            for tenant, lookups in by_tenant.items():
                lookups = sorted(lookups)
                for offset in range(0, len(lookups), self.settings.deep_product_batch_size):
                    batch = lookups[offset:offset + self.settings.deep_product_batch_size]
                    sql, values = feature_query(process, columns, tenant, batch, self.settings.deep_max_rows)
                    tasks.append((process, columns, sql, values, tenant, batch))

        if progress:
            progress.emit("features", f"正在读取{len(by_table)}个上游工序，共{len(tasks)}个参数批次，{workers or self.settings.deep_query_workers}路并发", total=len(tasks))

        def run(task):
            process, columns, sql, values, tenant, batch = task
            def read_batch(query, parameters, requested, strategy):
                if progress:
                    progress.check()
                rows, seconds = self._read(query, parameters)
                if len(rows) > self.settings.deep_max_rows:
                    raise NgError(f"上游工序“{process['name']}”选择后的结果超过{self.settings.deep_max_rows}条，请缩小查询范围", 422)
                timing = {"table": process["table"], "process_code": process["code"], "seconds": seconds, "rows": len(rows),
                    "eligible_source_rows": sum(int(row.get("_source_row_count") or 1) for row in rows),
                    "product_batch_size": len({code for code, _ in requested}), "lookup_count": len(requested),
                    "query_strategy": strategy, "sort_time_field": process["sort_time_field"], "record_selection": process["record_selection"]}
                if progress:
                    progress.emit("features", f"{process['name']} · 查询{len(requested)}个请求，返回{len(rows)}条记录，耗时{seconds:.2f}秒", rows=len(rows), process_code=process["code"])
                return rows, timing
            rows, timing = read_batch(sql, values, batch, "batch_latest")
            timings = [timing]
            clock = process["sort_time_field"]
            latest_by_code = {str(row["product_code"]): stamp(row.get(clock)) for row in rows}
            # A candidate already within its own cutoff is necessarily the correct
            # maximum under that cutoff. Only future candidates need an exact query.
            unresolved = [(code, cutoff) for code, cutoff in batch if code in latest_by_code and latest_by_code[code] > cutoff]
            cutoffs_by_code = defaultdict(list)
            for code, cutoff in batch:
                cutoffs_by_code[code].append(cutoff)
            selected_rows = [row for row in rows if any(stamp(row.get(clock)) <= cutoff for cutoff in cutoffs_by_code[str(row["product_code"])])]
            if unresolved:
                exact_sql, exact_values = feature_query(process, columns, tenant, unresolved, self.settings.deep_max_rows, exact_cutoffs=True)
                exact_rows, exact_timing = read_batch(exact_sql, exact_values, unresolved, "exact_cutoff")
                selected_rows.extend(exact_rows)
                timings.append(exact_timing)
            return process, columns, selected_rows, timings

        started = time.perf_counter()
        indices, timings, counts, seen = defaultdict(lambda: defaultdict(list)), [], defaultdict(int), defaultdict(set)
        clocks = {}
        with ThreadPoolExecutor(max_workers=workers or self.settings.deep_query_workers) as pool:
            futures = {pool.submit(run, task): index for index, task in enumerate(tasks)}
            try:
                for future in as_completed(futures):
                    process, columns, rows, query_timings = future.result()
                    table_code = (process["table"], process["code"])
                    clocks[table_code] = process["sort_time_field"]
                    timings.extend(((futures[future], index), timing) for index, timing in enumerate(query_timings))
                    for row in rows:
                        record = {column: row.get(column) for column in columns}
                        fingerprint = json_tie(record)
                        if fingerprint in seen[table_code]:
                            continue
                        seen[table_code].add(fingerprint)
                        counts[table_code] += 1
                        if counts[table_code] > self.settings.deep_max_rows:
                            raise NgError(f"上游工序“{process['name']}”选择后的总记录超过{self.settings.deep_max_rows}条，请缩小查询范围", 422)
                        key = (str(row["tenant_id"]), str(row["product_code"]))
                        if record.get(process["sort_time_field"]):
                            indices[table_code][key].append(record)
            except Exception:
                for future in futures:
                    future.cancel()
                raise
        merged = {}
        # Select one actual upstream event, never average incompatible rework records.
        for table_code, groups in indices.items():
            for key, rows in groups.items():
                rows.sort(key=lambda row: (stamp(row.get(clocks[table_code])), str(row.get("produce_id") or ""), json_tie(row)))
                ends = [stamp(row.get(clocks[table_code])) for row in rows]
                merged[(table_code, key)] = (ends, rows)
        return merged, [timing for _, timing in sorted(timings)], round(time.perf_counter() - started, 4)

    def analyze(self, context: dict, target: dict, features: list[dict], *, catalog: dict | None = None, progress=None) -> dict:
        started = time.perf_counter()
        if progress:
            progress.emit("target", f"正在读取目标工序：{target['process']['name']}，按shift_date筛选、按end_time选取记录")
        products, target_timing = self.targets(context, target)
        if progress:
            progress.emit("target", f"目标取数完成 · {len(products)}个产品，耗时{target_timing['seconds']:.2f}秒", rows=len(products))
        trace = resolve_genealogy(self, products, target, features, catalog, progress=progress)
        merged, timings, feature_seconds = self.features(products, features, progress=progress)
        counts = {name: sum(row["_group"] == name for row in products) for name in ("NG", "OK", "excluded")}
        boxes = []
        for field_index, field in enumerate(features, 1):
            if progress:
                progress.emit("statistics", f"正在统计特征 {field_index}/{len(features)}：{field['process']['name']} / {field['name']}", current=field_index, total=len(features))
            observations = []
            grouped, matched = {"NG": [], "OK": []}, {"NG": 0, "OK": 0}
            strategies = {group: {"direct_products": 0, "input_code_products": 0, "ads_products": 0,
                                   "ambiguous_products": 0, "expected_samples": 0, "valid_products": 0,
                                   "complete_products": 0, "partial_products": 0, "trace_missing_products": 0,
                                   "multi_code_products": 0} for group in ("NG", "OK")}
            table_code = (field["process"]["table"], field["process"]["code"])
            for product in products:
                group = product["_group"]
                if group == "excluded":
                    continue
                events, strategy = self.trace_events(merged, table_code, product)
                if strategy:
                    strategies[group][strategy] += 1
                metrics = strategies[group]
                metrics["expected_samples"] += len(events)
                if sum(item["expected_samples"] for item in strategies.values()) > self.settings.deep_max_rows:
                    raise NgError(f"特征“{field['name']}”关联样本超过{self.settings.deep_max_rows}条，请缩小查询范围；未截断绘图样本", 422)
                metrics["multi_code_products"] += int(len(events) > 1)
                metrics["trace_missing_products"] += int(not events)
                if any(row is not None for row in events):
                    matched[group] += 1
                valid = 0
                for upstream in events:
                    value = numeric(upstream.get(field["column"])) if upstream is not None else None
                    if value is not None:
                        grouped[group].append(value)
                        record = (str(upstream["tenant_id"]), str(upstream["product_code"]),
                                  stamp(upstream.get(field["process"]["sort_time_field"])),
                                  str(upstream.get("produce_id") or ""), value)
                        observations.append((value, product["_key"], group, record))
                        valid += 1
                metrics["valid_products"] += int(valid > 0)
                metrics["complete_products"] += int(bool(events) and valid == len(events))
                metrics["partial_products"] += int(0 < valid < len(events))
            record_stats = parameter_record_stats(observations)
            boxes.append({"field_id": field["id"], "name": field["name"], "process_name": field["process"]["name"],
                          "process_code": field["process"]["code"],
                          "analysis_type": "shared_material" if field["process"]["code"] in SHARED_MATERIAL_PROCESSES else "individual",
                          "bubble": interval_bubbles(observations),
                          "sample_unit": "target_material_association",
                          "groups": {group: {**box_stats(grouped[group], strategies[group]["expected_samples"]),
                                             "target_products": counts[group], "missing_products": counts[group] - strategies[group]["valid_products"],
                                             "matched_products": matched[group], **strategies[group], **record_stats[group]} for group in ("NG", "OK")}})
        warnings = (["当前条件缺少NG或OK样本，请调整范围后对比。"] if not counts["NG"] or not counts["OK"] else [])
        low_coverage = [box["name"] for box in boxes if any(counts[group] and box["groups"][group]["valid_products"] / counts[group] < .5 for group in ("NG", "OK"))]
        if low_coverage:
            warnings.append("部分特征有效数值覆盖率不足50%，请结合每组有效样本数判断，并核对跨工序产品编码是否一致。")
        if any(box["groups"][group]["ambiguous_products"] for box in boxes for group in ("NG", "OK")):
            warnings.append("部分产品的投入编码对应多个上游产品，无法唯一确认，已按缺失处理。")
        if trace["unknown_route_products"]:
            warnings.append(f"{trace['unknown_route_products']}个产品缺少可唯一确定的工艺路线或有效时间，其上游特征未关联，未混用314Ah与588Ah追溯表。")
        if trace["enabled"] and any(box["groups"][group]["trace_missing_products"] for box in boxes for group in ("NG", "OK")):
            warnings.append("部分电芯在目标时点没有可用的追溯关系或工序映射；已计入缺失电芯数，未知上游码数量未按2个或4个补造。")
        result = {"status": "success", "ng_type": context["row"]["ng_type"], "ng_name": context["row"]["ng_name"],
                "period": {key: context["parameters"][key] for key in ("start_date", "end_date")},
                "filters": context["filters"], "row_dimensions": context["row"].get("dimensions", {}),
                "target": {"id": target["id"], "name": target["name"], "process_name": target["process"]["name"],
                           "date_filter_field": target["process"]["date_filter_field"], "sort_time_field": target["process"]["sort_time_field"], "record_selection": target["process"]["record_selection"],
                           "groups": {group: box_stats([value for row in products if row["_group"] == group and (value := numeric(row.get(target["column"]))) is not None], counts[group]) for group in ("NG", "OK")}},
                "counts": counts, "boxes": boxes,
                "timing": {"total_seconds": round(time.perf_counter() - started, 4), "target_query": target_timing,
                           "feature_wall_seconds": feature_seconds, "feature_queries": timings, "workers": self.settings.deep_query_workers,
                           "trace_wall_seconds": trace["seconds"], "trace_queries": trace["queries"]},
                "rules": ["按租户和产品编码关联；目标时间范围内同一产品按工序规则保留一条记录。",
                          "目标宽表按shift_date班次日期筛选，起止日期均包含；最新记录排序与上游追溯时点仍采用字典中经DDL确认的分区时间字段。",
                          *dict.fromkeys(rule_description(field["process"]) for field in [target, *features]),
                          ("按目标租户和产线确定314Ah或588Ah路线，再按字典关联ADS，保留所选追溯批次全部物料行；同一目标产品、同一上游码只计一次。"
                           if trace["enabled"] else "优先使用product_code直接关联；换码时仅使用目标记录product_in_code中的显式投入编码，且要求唯一匹配。"),
                          "ADS在一次氦检生成：电芯码目标使用目标时点以内的追溯批次；更早工序的物料码目标使用最新已知编码关系，其上游参数仍严格不晚于目标时点。",
                          "NG/OK产品数按目标产品计数；箱线图n为目标产品与上游码关联后的有效参数数，关联到的多个卷绕码全部绘图，不求平均。同一物料用于多个目标产品时按各目标产品关联计数，这些样本不是相互独立的观测。",
                          "摘要中的参数条数与中位数按当前字段有效的上游实际记录统计：各NG/OK组内按租户、上游码、记录时间和记录标识去重；同一记录可分别属于NG和OK组。覆盖目标产品码仍按具有有效参数的目标产品去重计数。",
                          "参数缺失数按已知上游码统计；缺失电芯数为没有任何有效参数的目标电芯，部分缺失电芯另计；追溯缺失时不猜测上游码数量。",
                          "气泡图按当前特征的有效值划分最多10个等宽区间，左闭右开且最后区间包含右端点；气泡纵轴为区间内去重NG产品数/(NG+OK去重产品数)，面积为区间覆盖产品数。",
                          "同一产品的多个上游码落入同一区间时只计一次；落入不同区间时分别计入，各区间产品数不能直接相加作为总产品数。空区间不绘制气泡，也不视作NG占比为0。",
                          "正负极合浆、涂布、辊压只显示区间气泡图；其他工序可切换气泡图与箱线图。箱线图统计包含全部有效值，隐藏离群散点。",
                          "NG为当前缺陷；OK为缺陷字段为空或OK且产品质量为合格的记录；其他缺陷和未知质量排除。",
                          "上游不沿用目标日期、班次或设备限制；在目标记录的分区时间之前，按各工序规则在数据库内选取一条记录。",
                          "缺失值不填零；箱体为25%至75%分位数，须为1.5倍IQR范围内实际值；统计使用全部取回记录。"],
                "warnings": warnings}
        if progress:
            progress.emit("completed", f"取数与分析完成 · NG {counts['NG']}，OK {counts['OK']}，总耗时{result['timing']['total_seconds']:.2f}秒")
        return result

    @staticmethod
    def trace_events(merged, table_code, product):
        if "_feature_codes" not in product:
            event, strategy = NgDeepRepository.trace_event(merged, table_code, product)
            return [event], strategy
        events = []
        for code in product["_feature_codes"].get(table_code, []):
            ends, rows = merged.get((table_code, (product["_key"][0], code)), ([], []))
            index = bisect.bisect_right(ends, product["_anchor"]) - 1
            events.append(rows[index] if index >= 0 else None)
        return events, product.get("_feature_strategy", {}).get(table_code) if events else None

    @staticmethod
    def trace_event(merged, table_code, product):
        if product["_anchor"] == datetime.min:
            return None, None
        candidates = []
        for code in product.get("_trace_codes", [product["_key"][1]]):
            key = (product["_key"][0], code)
            ends, rows = merged.get((table_code, key), ([], []))
            index = bisect.bisect_right(ends, product["_anchor"]) - 1
            if index >= 0:
                if code == product["_key"][1]:
                    return rows[index], "direct_products"
                candidates.append(rows[index])
        if len(candidates) == 1:
            return candidates[0], "input_code_products"
        return None, "ambiguous_products" if candidates else None


def json_tie(row):
    # A deterministic tie breaker for tables without a unique event ID.
    return tuple(str(row[key]) for key in sorted(row))
