"""Audit recent product codes against route-specific ADS genealogy (read-only SQL)."""

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .catalog import CATALOG_FILENAME, apply_catalog_rules, identifier, write_json
from .config import NG_FACTORIES, get_ng_factory_settings
from .deep_repository import NgDeepRepository
from .repository import NgRepository


TRACE_TABLES = {
    "314ah": "ads_trace_cell_coding_314ah_pim",
    "588ah": "ads_trace_cell_coding_588ah_pim",
}
NON_MATERIAL_CODES = {"tenant_code", "device_code", "produce_order_code", "work_order_code",
                      "technics_line_code", "technics_process_code", "technics_step_code",
                      "factory_code", "workshop_code", "org_code", "station_code"}


def trace_fields(columns):
    """Inspect other material-code columns too; never infer a match from their names."""
    available = {row["column_name"] for row in columns}
    if "cell_code" not in available:
        raise ValueError("追溯表缺少cell_code，停止核验")
    return [row["column_name"] for row in columns
            if row["column_name"].endswith("_code")
            and row["column_name"] not in NON_MATERIAL_CODES
            and row["data_type"].lower().split("(")[0] in {"char", "varchar", "string", "text"}]


def sample_query(table, sample_size, lookback_days):
    columns = set(table["context_columns"])
    if not {"tenant_id", "product_code"}.issubset(columns) or not table.get("sort_time_field"):
        raise ValueError("宽表缺少租户、产品码或已验证的排序时间")
    clock = identifier(table["sort_time_field"])
    name = f"{identifier(table['table_schema'])}.{identifier(table['table_name'])}"
    line = "`technics_line_name`" if "technics_line_name" in columns else "CAST(NULL AS CHAR)"
    # Sample distinct codes separately for every tenant/line; a high-volume route
    # must not hide another route. Sparse tables use their own latest timestamp.
    sql = f"""WITH recent AS (
    SELECT tenant_id, {line} AS line_name, product_code, MAX({clock}) AS recent_end_time
    FROM {name}
    WHERE {clock} >= (SELECT DATE_SUB(MAX({clock}), INTERVAL %s DAY) FROM {name})
      AND tenant_id IS NOT NULL AND product_code IS NOT NULL AND TRIM(product_code) <> ''
    GROUP BY tenant_id, {line}, product_code
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY tenant_id, line_name ORDER BY recent_end_time DESC, product_code
    ) AS sample_rank FROM recent
)
SELECT tenant_id, line_name, product_code, recent_end_time
FROM ranked WHERE sample_rank <= %s ORDER BY tenant_id, line_name, sample_rank"""
    return sql, [lookback_days, sample_size]


def match_query(route, fields, tenant, codes):
    """Aggregate in the DB so an upstream roll linked to many cells stays bounded."""
    table = f"`ads`.{identifier(route['table_name'])}"
    marks = ",".join(["%s"] * len(codes))
    queries, values = [], []
    for field in fields:
        col = identifier(field)
        tenant_clause = " AND `tenant_id` = %s" if route["tenant_field"] else ""
        queries.append(f"""SELECT %s AS trace_field, {col} AS matched_code,
       COUNT(1) AS trace_rows, COUNT(DISTINCT `cell_code`) AS cell_count
FROM {table} WHERE {col} IN ({marks}){tenant_clause} GROUP BY {col}""")
        values.extend([field, *codes])
        if route["tenant_field"]:
            values.append(tenant)
    return " UNION ALL ".join(queries), values


def code_format(value):
    # Preserve separators/spacing but keep actual production IDs out of the catalog.
    return re.sub(r"[a-z]", "a", re.sub(r"[A-Z]", "A", re.sub(r"\d", "9", value)))


def infer_linkage(samples, matches, routes, *, minimum_matches=3):
    """Only exact, route-exclusive empirical matches can propose a join field."""
    keys = {(str(row["tenant_id"]), str(row["product_code"])) for row in samples}
    hits = defaultdict(lambda: defaultdict(set))
    multiplicities = defaultdict(list)
    for route, rows in matches.items():
        for row in rows:
            key = (str(row["tenant_id"]), str(row["matched_code"]))
            if key in keys:
                hits[key][route].add(row["trace_field"])
                multiplicities[(route, row["trace_field"])].append(int(row["cell_count"]))
    cross_route = {key for key, values in hits.items() if len(values) > 1}
    route_results = {}
    for route_id, route in routes.items():
        exclusive = {key: values[route_id] for key, values in hits.items()
                     if route_id in values and key not in cross_route}
        fields = set().union(*exclusive.values()) if exclusive else set()
        ambiguous = sum(len(value) > 1 for value in exclusive.values())
        if not exclusive:
            status = "no_match"
        elif ambiguous:
            status = "ambiguous_fields"
        elif len(fields) > 1:
            status = "mixed_code_fields"
        elif len(exclusive) < minimum_matches:
            status = "insufficient_samples"
        else:
            status = "verified_on_sample"
        counts = {field: sum(field in values for values in exclusive.values()) for field in sorted(fields)}
        route_results[route_id] = {
            "trace_schema": "ads", "trace_table": route["table_name"],
            "tenant_field": route["tenant_field"], "status": status,
            "product_code_field": next(iter(fields)) if status == "verified_on_sample" else None,
            "observed_product_code_fields": sorted(fields),
            "matched_sample_codes": len(exclusive), "ambiguous_field_codes": ambiguous,
            "field_match_counts": counts,
            "max_cells_per_sample_code": {field: max(multiplicities[(route_id, field)], default=0) for field in sorted(fields)},
        }
    by_line = defaultdict(set)
    for row in samples:
        by_line[(str(row["tenant_id"]), row["line_name"])].add((str(row["tenant_id"]), str(row["product_code"])))
    line_evidence = []
    for (tenant, line), line_keys in sorted(by_line.items(), key=lambda item: str(item[0])):
        counts = {route: sum(key in hits and set(hits[key]) == {route} for key in line_keys) for route in routes}
        observed_routes = [route for route, count in counts.items() if count]
        line_evidence.append({"tenant_id": tenant, "technics_line_name": line,
                              "sample_codes": len(line_keys), "route_match_counts": counts,
                              "observed_routes": observed_routes,
                              "unmatched_codes": sum(key not in hits for key in line_keys)})
    return {"product_field": "product_code", "comparison": "exact_value_no_substring_or_format_inference",
            "sample_codes": len(keys), "unmatched_sample_codes": sum(key not in hits for key in keys),
            "cross_route_ambiguous_codes": len(cross_route),
            "sample_formats": dict(Counter(code_format(code) for _, code in keys)),
            "routes": route_results, "line_evidence": line_evidence}


def inspect_routes(reader):
    rows, _ = reader._read("""SELECT table_name, column_name, data_type, column_comment
FROM information_schema.columns WHERE table_schema=%s AND table_name IN (%s,%s)
ORDER BY table_name, ordinal_position""", ["ads", *TRACE_TABLES.values()])
    comments, _ = reader._read("""SELECT table_name, table_comment FROM information_schema.tables
WHERE table_schema=%s AND table_name IN (%s,%s)""", ["ads", *TRACE_TABLES.values()])
    routes = {}
    for route_id, name in TRACE_TABLES.items():
        columns = [row for row in rows if row["table_name"] == name]
        fields = trace_fields(columns)
        routes[route_id] = {"table_schema": "ads", "table_name": name,
                            "table_comment": next((row["table_comment"] for row in comments if row["table_name"] == name), ""),
                            "tenant_field": "tenant_id" if any(row["column_name"] == "tenant_id" for row in columns) else None,
                            "code_fields": fields,
                            "columns": [{key: row[key] for key in ("column_name", "data_type", "column_comment")} for row in columns]}
    return routes


def recent_trace_codes(reader, routes, sample_size, lookback_days):
    """Backcheck completed cells: the newest upstream products may not reach ADS yet."""
    indices, summaries = {}, {}
    for route_id, route in routes.items():
        name = f"`ads`.{identifier(route['table_name'])}"
        fields = ",".join(f"t.{identifier(field)}" for field in route["code_fields"])
        sql = f"""WITH cells AS (
    SELECT cell_code, CAST(end_time AS DATE) AS trace_date, MAX(end_time) AS trace_time
    FROM {name}
    WHERE end_time >= (SELECT DATE_SUB(MAX(end_time), INTERVAL %s DAY) FROM {name})
    GROUP BY cell_code, CAST(end_time AS DATE)
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY trace_date ORDER BY trace_time DESC, cell_code) AS sample_rank
    FROM cells
)
SELECT {fields}, t.end_time FROM {name} AS t INNER JOIN ranked AS r
  ON t.cell_code = r.cell_code AND t.end_time = r.trace_time
WHERE r.sample_rank <= %s LIMIT 100001"""
        rows, seconds = reader._read(sql, [lookback_days, sample_size])
        if len(rows) > 100000:
            raise ValueError("追溯样本超过100000行，未使用截断数据核验")
        index = defaultdict(lambda: defaultdict(set))
        by_cell = defaultdict(lambda: defaultdict(set))
        for row in rows:
            for field in route["code_fields"]:
                code = row.get(field)
                if code is not None and str(code).strip():
                    index[str(code)][field].add(str(row["cell_code"]))
                    by_cell[str(row["cell_code"])][field].add(str(code))
        indices[route_id] = index
        summaries[route_id] = {"sample_cells_per_day_limit": sample_size, "lookback_days": lookback_days,
                               "sample_cell_codes": len({row["cell_code"] for row in rows}), "sample_rows": len(rows),
                               "query_seconds": seconds,
                               "distinct_codes_per_cell": {
                                   field: {"min": min((len(values.get(field, set())) for values in by_cell.values()), default=0),
                                           "max": max((len(values.get(field, set())) for values in by_cell.values()), default=0)}
                                   for field in route["code_fields"]},
                               "latest_trace_time": max((str(row["end_time"]) for row in rows), default=None)}
    return indices, summaries


def backcheck_table(reader, table, routes, indices):
    codes = sorted({code for index in indices.values() for code in index})
    if not codes:
        return infer_linkage([], {}, routes)
    name = f"{identifier(table['table_schema'])}.{identifier(table['table_name'])}"
    clock = identifier(table["sort_time_field"])
    line = "`technics_line_name`" if "technics_line_name" in table["context_columns"] else "CAST(NULL AS CHAR)"
    samples, seconds = [], 0.0
    # Query all history by an explicit code set; older material must remain eligible.
    for offset in range(0, len(codes), reader.settings.deep_product_batch_size):
        batch = codes[offset:offset + reader.settings.deep_product_batch_size]
        sql = f"""SELECT tenant_id, {line} AS line_name, product_code, MAX({clock}) AS recent_end_time
FROM {name} WHERE product_code IN ({','.join(['%s'] * len(batch))}) AND tenant_id IS NOT NULL
GROUP BY tenant_id, {line}, product_code"""
        rows, duration = reader._read(sql, batch)
        samples.extend(rows)
        seconds += duration
    matches = defaultdict(list)
    for tenant, code in {(str(row["tenant_id"]), str(row["product_code"])) for row in samples}:
        for route_id, index in indices.items():
            for field, cells in index.get(code, {}).items():
                matches[route_id].append({"tenant_id": tenant, "matched_code": code, "trace_field": field,
                                          "cell_count": len(cells)})
    result = infer_linkage(samples, matches, routes)
    for route_id, index in indices.items():
        evidence = result["routes"][route_id]
        requested = Counter(field for fields in index.values() for field in fields)
        evidence["field_requested_codes"] = dict(requested)
        evidence["field_match_precision"] = {
            field: evidence["field_match_counts"].get(field, 0) / count for field, count in requested.items()}
    result["query_seconds"] = round(seconds, 4)
    return result


def resolve_mapping(recent, backcheck):
    """Disambiguate shared stage values by coverage and precision of the backcheck."""
    result = {}
    for route_id in TRACE_TABLES:
        direct, reverse = recent["routes"][route_id], backcheck["routes"][route_id]
        fields = sorted(set(direct["observed_product_code_fields"]) | set(reverse["observed_product_code_fields"]))
        verified = {entry["product_code_field"] for entry in (direct, reverse) if entry["product_code_field"]}
        scores = {field: (count, reverse.get("field_match_precision", {}).get(field, 0))
                  for field, count in reverse["field_match_counts"].items()}
        best = [field for field, score in scores.items() if score == max(scores.values())] if scores else []
        selected = None
        basis = None
        if len(fields) == 1:
            selected = fields[0]
            basis = "single_observed_field"
        elif len(best) == 1 and scores[best[0]][1] > 0:
            selected = best[0]
            basis = "completed_cell_field_coverage_then_precision"
        if selected and (not verified or verified == {selected}):
            evidence_count = max(direct["field_match_counts"].get(selected, 0), reverse["field_match_counts"].get(selected, 0))
            status, field = ("verified_on_sample" if evidence_count >= 3 else "limited_samples"), selected
        elif fields:
            status, field = "needs_review", None
        else:
            status, field = "no_match", None
        result[route_id] = {"trace_schema": direct["trace_schema"], "trace_table": direct["trace_table"],
                            "tenant_field": direct["tenant_field"], "status": status,
                            "product_code_field": field, "candidate_fields": fields,
                            "selection_basis": basis if field else None,
                            "backcheck_field_scores": {field: {"matched_codes": score[0], "match_precision": score[1]}
                                                       for field, score in scores.items()},
                            "recent_matched_codes": direct["matched_sample_codes"],
                            "backcheck_matched_codes": reverse["matched_sample_codes"],
                            "tenant_scope_note": "追溯表无tenant_id；后续宽表读取仍须限制目标租户" if not direct["tenant_field"] else "按tenant_id核验"}
    return result


def audit_table(reader, table, routes, sample_size, lookback_days):
    sql, values = sample_query(table, sample_size, lookback_days)
    samples, sample_seconds = reader._read(sql, values)
    matches, query_seconds = defaultdict(list), sample_seconds
    by_tenant = defaultdict(set)
    for row in samples:
        by_tenant[str(row["tenant_id"])].add(str(row["product_code"]))
    for tenant, codes in sorted(by_tenant.items()):
        for route_id, route in routes.items():
            sql, values = match_query(route, route["code_fields"], tenant, sorted(codes))
            rows, seconds = reader._read(sql, values)
            query_seconds += seconds
            matches[route_id].extend({**row, "tenant_id": tenant} for row in rows)
    linkage = infer_linkage(samples, matches, routes)
    linkage.update({"audited_at": datetime.now(timezone.utc).isoformat(),
                    "sampling": {"per_tenant_line_limit": sample_size, "lookback_days_from_table_latest": lookback_days,
                                 "time_field": table["sort_time_field"],
                                 "latest_sample_time": max((str(row["recent_end_time"]) for row in samples), default=None)},
                    "query_seconds": round(query_seconds, 4)})
    return {"table_name": table["table_name"], "table_comment": table["table_comment"], "status": "success",
            "code_linkage": linkage}


def apply_to_catalog(path, original, report):
    if any(row["status"] != "success" for row in report["tables"]):
        raise ValueError("部分表查询失败，未修改numeric_field_catalog.json")
    # Do not clobber a concurrent DDL refresh or another audit.
    current = json.loads(path.read_text(encoding="utf-8"))
    if current != original:
        raise ValueError("核验期间字段字典已变化，请重新运行；本次未覆盖字典")
    updates = {row["table_name"]: row["code_linkage"] for row in report["tables"]}
    if set(updates) != {row["table_name"] for row in current["tables"]}:
        raise ValueError("核验表清单与字典不一致，未修改字典")
    for table in current["tables"]:
        table["code_linkage"] = updates[table["table_name"]]
    current["code_trace_routes"] = report["trace_routes"]
    current["code_trace_audit"] = {"audited_at": report.get("generated_at"), "trace_sampling": report.get("trace_sampling", {}),
                                   "report": f"product_code_linkage_{datetime.now().date().isoformat()}.json"}
    current["code_trace_policy"] = {
        "route_selection": "exact_tenant_and_target_line_binding; unresolved_routes_must_not_be_combined",
        "line_bindings": route_line_bindings(report["tables"]),
        "join_path": ["target.product_code = route_trace[target_table.code_linkage.resolved_mapping[route].product_code_field]",
                      "route_trace[feature_table.code_linkage.resolved_mapping[route].product_code_field] = feature.product_code"],
        "feature_tenant_scope": "always_restrict_to_target_tenant",
        "multiple_material_codes": "preserve_all; never_silently_select_first_or_average",
        "unresolved_fields": "do_not_infer_from_barcode_length_or_prefix",
    }
    current["source"]["code_linkage"] = "Recent DWD product_code exact matches against separate ADS route tables"
    apply_catalog_rules(current)
    current.pop("revision", None)
    current["revision"] = hashlib.sha256(json.dumps(current, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    write_json(path, current)


def route_line_bindings(tables):
    # Bind using observed cell-code stages. Material-production lines may serve
    # several battery routes and must not define the target route by themselves.
    observed = defaultdict(set)
    for table in tables:
        if table["status"] != "success":
            continue
        link = table["code_linkage"]
        for line in link.get("line_evidence", []):
            for route in line["observed_routes"]:
                if link["routes"][route]["product_code_field"] == "cell_code":
                    observed[(line["tenant_id"], line["technics_line_name"])].add(route)
    return [{"tenant_id": tenant, "technics_line_name": line,
             "route": next(iter(routes)) if len(routes) == 1 else None,
             "observed_routes": sorted(routes)}
            for (tenant, line), routes in sorted(observed.items(), key=lambda item: str(item[0])) if line]


def markdown_report(report):
    lines = ["# 工序产品编码与工艺路线核验", "", f"核验时间：{report['generated_at']}", "",
             "每个租户、产线分别抽取最近的不同product_code；以各表自身最新时间为基准。",
             "314Ah、588Ah分别精确匹配，不用编码长度、前缀或工序名称推断；未匹配不代表全表不存在关联。", "",
             "匹配数记为“近期工序编码匹配数+已生成追溯的近期电芯反查匹配数”，两者可能重叠，不能相加为独立样本数。",
             "共有字段先比较反查覆盖的工序编码数；覆盖数相同时比较该字段候选编码在工序表中的命中率，仍相同则保留待核验。", "",
             "314Ah追溯表实际没有tab_pre_weld_code；588Ah有此字段。两张追溯表都没有tenant_id，宽表查询仍须限制目标租户。", ""]
    for route, sample in report.get("trace_sampling", {}).items():
        winding = sample.get("distinct_codes_per_cell", {}).get("winding_slit_code", {})
        lines.append(f"- {route}：反查{sample['sample_cell_codes']}个电芯、{sample['sample_rows']}行追溯；每电芯卷绕码数{winding.get('min', '?')}至{winding.get('max', '?')}。")
    lines += ["", "| 工序宽表 | 近期样本编码 | 314Ah字段 / 状态 / 匹配数 | 588Ah字段 / 状态 / 匹配数 | 近期未匹配 / 跨路线歧义 |",
             "|---|---:|---|---|---:|"]
    labels = {"verified_on_sample": "样本已验证", "limited_samples": "支持样本较少", "no_match": "未匹配",
              "needs_review": "待核验", "ambiguous_fields": "字段重叠", "mixed_code_fields": "混合编码",
              "insufficient_samples": "支持样本较少"}
    for table in report["tables"]:
        if table["status"] != "success":
            lines.append(f"| {table['table_name']} | 查询失败 | {table['error']} | | |")
            continue
        link = table["code_linkage"]
        cells = []
        for route in TRACE_TABLES:
            match = link.get("resolved_mapping", link["routes"])[route]
            fields = match.get('candidate_fields', match.get('observed_product_code_fields', []))
            counts = f"{match['recent_matched_codes']}+{match['backcheck_matched_codes']}" if 'recent_matched_codes' in match else str(match['matched_sample_codes'])
            cells.append(f"{match['product_code_field'] or ','.join(fields) or '—'} / {labels.get(match['status'], match['status'])} / {counts}")
        lines.append(f"| {table['table_comment']} `{table['table_name']}` | {link['sample_codes']} | {cells[0]} | {cells[1]} | {link['unmatched_sample_codes']} / {link['cross_route_ambiguous_codes']} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="核验各工序product_code与两条ADS追溯路线（只读数据库）")
    parser.add_argument("--factory", choices=list(NG_FACTORIES), default="jinzhai-phase-3")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--write-catalog", action="store_true")
    args = parser.parse_args()
    if not 3 <= args.sample_size <= 1000 or not 1 <= args.lookback_days <= 90:
        parser.error("sample-size须为3至1000，lookback-days须为1至90")
    settings = get_ng_factory_settings(args.factory)
    reader = NgDeepRepository(NgRepository(settings))
    directory = settings.catalog_root / args.factory
    path = directory / CATALOG_FILENAME
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if catalog["factory_id"] != args.factory:
        raise ValueError("字典与当前工厂不匹配")
    # Missing schema/connectivity aborts before touching the existing dictionary.
    routes = inspect_routes(reader)
    print(json.dumps({"trace_routes": routes}, ensure_ascii=False), flush=True)
    indices, trace_sampling = recent_trace_codes(reader, routes, args.sample_size, args.lookback_days)

    def inspect(table):
        result = audit_table(reader, table, routes, args.sample_size, args.lookback_days)
        backcheck = backcheck_table(reader, table, routes, indices)
        result["code_linkage"]["completed_cell_backcheck"] = backcheck
        result["code_linkage"]["resolved_mapping"] = resolve_mapping(result["code_linkage"], backcheck)
        return result

    results = []
    with ThreadPoolExecutor(max_workers=settings.deep_query_workers) as pool:
        tasks = {pool.submit(inspect, table): table for table in catalog["tables"]}
        for task in as_completed(tasks):
            table = tasks[task]
            try:
                result = task.result()
            except Exception as exc:
                result = {"table_name": table["table_name"], "status": "failed", "error": str(exc)}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False, default=str), flush=True)
    report = {"factory_id": args.factory, "generated_at": datetime.now(timezone.utc).isoformat(),
              "catalog_revision_before_audit": catalog["revision"], "trace_routes": routes, "trace_sampling": trace_sampling,
              "tables": sorted(results, key=lambda row: row["table_name"])}
    stem = f"product_code_linkage_{datetime.now().date().isoformat()}"
    write_json(directory / f"{stem}.json", report)
    (directory / f"{stem}.md").write_text(markdown_report(report), encoding="utf-8")
    if args.write_catalog:
        apply_to_catalog(path, catalog, report)
        print("numeric_field_catalog.json已更新", flush=True)
    elif any(row["status"] != "success" for row in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
