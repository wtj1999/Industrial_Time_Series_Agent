"""Route-isolated ADS snapshots retaining every distinct upstream material code."""

import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

from .catalog import identifier
from .errors import NgError


def stamp(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    try:
        return datetime.fromisoformat(str(value)) if value else datetime.min
    except ValueError:
        return datetime.min


def trace_query(route, source, fields, lookups, limit, *, exact=False):
    """MAX timestamp retains all material rows of a snapshot, unlike ROW_NUMBER."""
    columns = list(dict.fromkeys([source, *fields]))
    projection = ','.join(identifier(column) for column in columns)
    codes = sorted({code for code, _ in lookups})
    where = f"{identifier(source)} IN ({','.join(['%s'] * len(codes))}) AND `end_time` <= CAST(%s AS DATETIME)"
    values = [*codes, max(cutoff for _, cutoff in lookups)]
    cutoff_projection = ""
    if exact:
        requests = []
        for code, cutoff in lookups:
            requests.append("SELECT %s AS lookup_code, CAST(%s AS DATETIME) AS lookup_time")
            values.extend([code, cutoff])
        selected = ','.join(f"p.{identifier(column)}" for column in columns)
        body = f"""SELECT {selected}, p.{identifier(source)} AS `_trace_lookup`,
           p.`end_time` AS `_trace_event`, requested.lookup_time AS `_requested_cutoff`,
           MAX(p.`end_time`) OVER (PARTITION BY p.{identifier(source)}, requested.lookup_time) AS `_trace_time`
    FROM (SELECT {projection}, `end_time` FROM ads.{identifier(route['table_name'])} WHERE {where}) AS p
    INNER JOIN ({' UNION ALL '.join(requests)}) AS requested
      ON p.{identifier(source)} = requested.lookup_code AND p.`end_time` <= requested.lookup_time"""
        cutoff_projection = ", `_requested_cutoff`"
    else:
        body = f"""SELECT {projection}, {identifier(source)} AS `_trace_lookup`, `end_time` AS `_trace_event`,
           MAX(`end_time`) OVER (PARTITION BY {identifier(source)}) AS `_trace_time`
    FROM ads.{identifier(route['table_name'])} WHERE {where}"""
    sql = f"""SELECT DISTINCT {projection}, `_trace_lookup`, `_trace_time`{cutoff_projection}
FROM ({body}) AS snapshots WHERE `_trace_event` = `_trace_time` LIMIT %s"""
    return sql, [*values, limit + 1]


def mapping_field(process, route_id, route):
    entry = (process.get("code_linkage") or {}).get("resolved_mapping", {}).get(route_id, {})
    field = entry.get("product_code_field")
    if not field:
        return None
    if (entry.get("trace_schema") != "ads" or entry.get("trace_table") != route["table_name"]
            or field not in route.get("code_fields", [])):
        raise NgError("工序编码映射与ADS路线字段不一致，请重新核验字典", 503)
    identifier(field)
    return field


def genealogy_cutoff(product, source):
    # ADS is created at first helium inspection. For an earlier material-stage
    # target its identity relationship can only become available afterwards;
    # measured feature values still use the original target cutoff in DWD.
    return product["_anchor"] if source == "cell_code" else datetime(9999, 12, 31, 23, 59, 59)


def resolve_genealogy(reader, products, target, features, catalog, progress=None):
    started = time.perf_counter()
    routes = (catalog or {}).get("code_trace_routes")
    if not routes:
        return {"enabled": False, "seconds": 0, "queries": [], "unknown_route_products": 0}
    for key, route in routes.items():
        if key not in {"314ah", "588ah"} or route.get("table_schema") != "ads" or route.get("table_name") != f"ads_trace_cell_coding_{key}_pim":
            raise NgError("ADS追溯路线配置无效，请重新核验字典", 503)
    bindings = defaultdict(set)
    for binding in catalog.get("code_trace_policy", {}).get("line_bindings", []):
        if binding.get("route") in routes:
            bindings[(str(binding["tenant_id"]), binding["technics_line_name"])].add(binding["route"])
    processes = {(field["process"]["table"], field["process"]["code"]): field["process"] for field in features}
    plans, waiting = {}, defaultdict(list)
    unknown = 0
    for product in products:
        if product["_group"] == "excluded":
            continue
        product["_feature_codes"], product["_feature_strategy"] = {}, {}
        route_ids = bindings.get((product["_key"][0], product.get("technics_line_name")), set())
        if len(route_ids) != 1 or product["_anchor"] == datetime.min:
            unknown += 1
            continue
        route_id = next(iter(route_ids))
        route = routes[route_id]
        source = mapping_field(target["process"], route_id, route)
        if not source:
            continue
        destinations = {}
        for table_code, process in processes.items():
            destination = mapping_field(process, route_id, route)
            if destination == source:
                product["_feature_codes"][table_code] = [product["_key"][1]]
                product["_feature_strategy"][table_code] = "direct_products"
            elif destination:
                destinations[table_code] = destination
        if destinations:
            key = (route_id, product["_key"][0], source)
            plans[key] = (route, destinations)
            waiting[key].append(product)

    tasks = []
    for key, group in waiting.items():
        route, destinations = plans[key]
        lookups = sorted({(p["_key"][1], genealogy_cutoff(p, key[2])) for p in group})
        for offset in range(0, len(lookups), reader.settings.deep_product_batch_size):
            tasks.append((key, route, destinations, lookups[offset:offset + reader.settings.deep_product_batch_size]))

    if progress:
        progress.emit("trace", f"正在按工艺路线追溯上游编码，共{len(tasks)}个追溯批次", total=len(tasks))

    def run(task):
        key, route, destinations, lookups = task
        timings = []
        def read(requests, exact):
            if progress:
                progress.check()
            sql, values = trace_query(route, key[2], sorted(set(destinations.values())), requests, reader.settings.deep_max_rows, exact=exact)
            rows, seconds = reader._read(sql, values)
            if len(rows) > reader.settings.deep_max_rows:
                raise NgError(f"{key[0]}追溯结果超过{reader.settings.deep_max_rows}行，请缩小查询范围；未截断关联", 422)
            timings.append({"route": key[0], "table": route["table_name"], "seconds": seconds, "rows": len(rows),
                            "lookup_count": len(requests), "query_strategy": "exact_cutoff" if exact else "batch_latest"})
            if progress:
                progress.emit("trace", f"{key[0]}追溯 · {len(requests)}个请求，返回{len(rows)}行，耗时{seconds:.2f}秒", rows=len(rows), route=key[0])
            return rows
        rows = read(lookups, False)
        by_code, exact_rows = defaultdict(list), defaultdict(list)
        for row in rows:
            by_code[str(row["_trace_lookup"])].append(row)
        unresolved = [(code, cutoff) for code, cutoff in lookups if by_code[code] and stamp(by_code[code][0]["_trace_time"]) > cutoff]
        if unresolved:
            for row in read(unresolved, True):
                exact_rows[(str(row["_trace_lookup"]), stamp(row["_requested_cutoff"]))].append(row)
        result = {}
        retained = 0
        for code, cutoff in lookups:
            candidates = by_code[code]
            if candidates and stamp(candidates[0]["_trace_time"]) > cutoff:
                candidates = exact_rows[(code, cutoff)]
            retained += len(candidates)
            result[(code, cutoff)] = {table_code: sorted({str(row[field]) for row in candidates
                                                          if row.get(field) is not None and str(row[field]).strip()})
                                      for table_code, field in destinations.items()}
        return key, result, timings, retained

    assignments, timings, counts = defaultdict(dict), [], defaultdict(int)
    with ThreadPoolExecutor(max_workers=reader.settings.deep_query_workers) as pool:
        futures = {pool.submit(run, task): index for index, task in enumerate(tasks)}
        try:
            for future in as_completed(futures):
                key, result, queries, retained = future.result()
                counts[key[0]] += retained
                if counts[key[0]] > reader.settings.deep_max_rows:
                    raise NgError(f"{key[0]}追溯关联明细超过{reader.settings.deep_max_rows}行，请缩小查询范围", 422)
                assignments[key].update(result)
                timings.extend(((futures[future], index), query) for index, query in enumerate(queries))
        except Exception:
            for future in futures:
                future.cancel()
            raise
    for key, group in waiting.items():
        for product in group:
            codes = assignments[key].get((product["_key"][1], genealogy_cutoff(product, key[2])), {})
            for table_code in plans[key][1]:
                product["_feature_codes"][table_code] = codes.get(table_code, [])
                product["_feature_strategy"][table_code] = "ads_products"
    return {"enabled": True, "seconds": round(time.perf_counter() - started, 4),
            "queries": [query for _, query in sorted(timings)], "unknown_route_products": unknown}
