"""Read numeric feature names and descriptions directly from DWD DDL metadata."""

import hashlib
import json
import re
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .errors import NgError
from .repository import NgRepository
from .schemas import FILTER_LABELS
from .visualization import SHARED_MATERIAL_PROCESSES

CATALOG_VERSION = 5
CATALOG_FILENAME = "numeric_field_catalog.json"
NUMERIC_TYPES = {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "largeint", "float", "real", "double", "decimal", "numeric", "decimalv2", "decimalv3"}
NON_MEASURE = re.compile(r"结果|判定|合格|条码|状态|使能|编号|序号|代码|标志|\bNG\b", re.I)
IDENTIFIER = re.compile(r"^[a-zA-Z0-9_]+$")
# These columns describe records and cohorts rather than measured process features.
CONTEXT_COLUMNS = {"id", "produce_id", "data_source", "product_count", "ok_count", "ng_count", "product_quality", "qualification_ratio_type",
                   "product_code", "product_in_code", "start_time", "end_time", "shift_date", "ng_type", "technics_process_code", "technics_step_code", "technics_step_name", *FILTER_LABELS}

# Confirmed analysis scope; matching a parameter-table name alone is insufficient.
EXCLUDED_TABLES = {"jinzhai-phase-3": {
    "dwd_qual_pos_ceramic_mixing_param_pim": "用户确认无法串连，移出分析字典",
    "dwd_qual_scrap_inter_resis_comp_param_pim": "用户确认不是工序宽表",
}}
EXCLUDED_PROCESS_CODES = {"jinzhai-phase-3": {"C1102"}}
CONFIRMED_CODE_FIELDS = {"jinzhai-phase-3": {
    "dwd_qual_high_temp_rest1_param_pim": {"314ah": "cell_code", "588ah": "cell_code"},
}}


def apply_catalog_rules(catalog: dict):
    """Keep user-confirmed scope and identities authoritative across refresh/audit."""
    factory = catalog["factory_id"]
    excluded = EXCLUDED_TABLES.get(factory, {})
    codes = EXCLUDED_PROCESS_CODES.get(factory, set())
    catalog["tables"] = [table for table in catalog["tables"] if table["table_name"] not in excluded]
    if "dimension_processes" in catalog:
        catalog["dimension_processes"] = [row for row in catalog["dimension_processes"] if str(row["technics_process_code"]) not in codes]
    if "unmapped_processes" in catalog:
        catalog["unmapped_processes"] = [row for row in catalog["unmapped_processes"] if row["code"] not in codes]
    if "warnings" in catalog:
        catalog["warnings"] = [warning for warning in catalog["warnings"] if not any(table in warning for table in excluded)]
    for table in catalog["tables"]:
        if table["table_name"] == "dwd_qual_grading_param_pim":
            table["record_selection"] = record_selection(table["table_name"])
        for route, field in CONFIRMED_CODE_FIELDS.get(factory, {}).get(table["table_name"], {}).items():
            linkage = table.setdefault("code_linkage", {"product_field": "product_code"})
            mapping = linkage.setdefault("resolved_mapping", {}).setdefault(route, {})
            mapping.update({"trace_schema": "ads", "trace_table": f"ads_trace_cell_coding_{route}_pim",
                            "tenant_field": None, "product_code_field": field, "status": "user_confirmed",
                            "selection_basis": "explicit_user_confirmation",
                            "confirmation": {"source": "user", "date": "2026-11-17",
                                             "note": "高温静置1的product_code为cell_code"}})
            mapping["candidate_fields"] = sorted(set(mapping.get("candidate_fields", [])) | {field})
    catalog.setdefault("source", {})["analysis_scope"] = "User-confirmed process table scope and code-field overrides"
    if "code_trace_policy" in catalog:
        catalog["code_trace_policy"].update({
            "plot_sample_unit": "target_material_association",
            "plot_sample_unit_applies_to": "box",
            "bubble_sample_unit": "distinct_target_products_within_interval",
            "bubble_strategy": "equal_width_max_10_intervals",
            "shared_material_process_codes": sorted(SHARED_MATERIAL_PROCESSES),
            "shared_material_charts": ["bubble"],
            "other_process_charts": ["bubble", "box"],
            "box_outlier_points": False,
            "plot_deduplication": "distinct_upstream_code_per_target_product",
            "plot_values": "all_finite_values_no_averaging",
            "product_counts": "count_target_products_once",
            "trace_time_policy": {"cell_code_target": "latest_snapshot_not_after_target",
                                  "pre_cell_material_target": "latest_known_identity_snapshot"},
            "measurement_time_policy": "not_after_individual_target_end_time",
        })


def partition_metadata(ddl: str, columns: list[dict]) -> dict:
    match = re.search(r"\bPARTITION\s+BY\s+RANGE\s*\(([^)]+)\)", ddl, re.I)
    if not match:
        return {"type": None, "columns": [], "definition": "", "sort_time_field": None}
    names = re.findall(r"`([a-zA-Z0-9_]+)`", match.group(1))
    if not names:
        names = [value.strip() for value in match.group(1).split(",") if IDENTIFIER.fullmatch(value.strip())]
    temporal = {col["column_name"] for col in columns if col["data_type"].lower().split("(", 1)[0] in {"date", "datetime", "timestamp", "datetimev2", "datev2"}}
    candidates = [name for name in names if name in temporal]
    return {"type": "RANGE", "columns": names, "definition": match.group(0),
            "sort_time_field": candidates[0] if len(candidates) == 1 else None}


def record_selection(table_name: str) -> dict:
    if table_name == "dwd_qual_grading_param_pim":
        return {"mode": "fixed_step_latest", "step_field": "technics_step_code", "step_value": "10"}
    if table_name == "dwd_qual_formation_param_pim":
        return {"mode": "last_numeric_step_latest", "step_field": "technics_step_code", "step_order": "numeric_desc"}
    return {"mode": "latest"}


def identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise NgError("参数字典包含无效的数据库标识符", 503)
    return f"`{value}`"


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def is_numeric_feature(column: dict) -> bool:
    kind = re.split(r"[\s(]", column["data_type"].lower(), maxsplit=1)[0]
    name = column["column_name"]
    comment = column.get("column_comment") or ""
    return (kind in NUMERIC_TYPES and name not in CONTEXT_COLUMNS
            and not re.search(r"(^|_)(ng|result|status|flag|id|code)($|_)", name, re.I)
            and not NON_MEASURE.search(comment))


class NgCatalog:
    def __init__(self, repository: NgRepository, factory_id: str, settings=None):
        self.repository = repository
        self.settings = settings or repository.settings
        self.factory_id = factory_id
        self.directory = self.settings.catalog_root / factory_id
        self._lock = threading.Lock()

    def load(self) -> dict:
        with self._lock:
            path = self.directory / CATALOG_FILENAME
            if not path.exists():
                return self.refresh()
            try:
                catalog = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                raise NgError("工序参数字典无法读取，请刷新字典", 503) from exc
            if catalog.get("factory_id") != self.factory_id:
                raise NgError("工序参数字典与当前工厂不匹配", 503)
            if catalog.get("version") != CATALOG_VERSION:
                return self.refresh()
            return self.runtime_catalog(catalog)

    def refresh(self) -> dict:
        # TABLE_COMMENT and COLUMN_COMMENT expose the comments from the actual DDL.
        # Field discovery has no production-date filter and never reads mes.produce_param.
        with self.repository.connection() as connection, connection.cursor() as cursor:
            cursor.execute("""SELECT table_name, table_comment
FROM information_schema.tables
WHERE table_schema = 'dwd' AND table_name LIKE 'dwd_qual_%_param_pim'
ORDER BY table_name""")
            tables = list(cursor.fetchall())
            cursor.execute("""SELECT table_name, column_name, data_type, column_comment, ordinal_position
FROM information_schema.columns
WHERE table_schema = 'dwd' AND table_name LIKE 'dwd_qual_%_param_pim'
ORDER BY table_name, ordinal_position""")
            columns = list(cursor.fetchall())
            cursor.execute("""SELECT DISTINCT technics_process_code, technics_process_name
FROM dim.dim_qual_defect_ni ORDER BY technics_process_code, technics_process_name""")
            dimensions = list(cursor.fetchall())
        return self.build(tables, columns, dimensions)

    def build(self, tables: list[dict], columns: list[dict], dimensions: list[dict], *, table_processes: list[dict] | None = None, table_ddls: dict[str, str] | None = None) -> dict:
        excluded = EXCLUDED_TABLES.get(self.factory_id, {})
        tables = [row for row in tables if row["table_name"] not in excluded]
        columns = [row for row in columns if row["table_name"] not in excluded]
        dimensions = [row for row in dimensions if str(row["technics_process_code"]) not in EXCLUDED_PROCESS_CODES.get(self.factory_id, set())]
        by_table, names = defaultdict(list), defaultdict(list)
        for row in dimensions:
            if row["technics_process_name"]:
                names[str(row["technics_process_code"])].append(row["technics_process_name"])
        for column in columns:
            by_table[column["table_name"]].append(column)
        required = {"product_code", "tenant_id", "technics_process_code", "technics_process_name", "shift_date", "ng_type", "product_quality"}
        mappable = {table for table, cols in by_table.items() if required.issubset({col["column_name"] for col in cols})}

        def probe(table):
            # Latest actual records avoid stale codes/names in historical rows.
            # This query is only for routing; DDL field discovery does not depend on rows.
            with self.repository.connection() as connection, connection.cursor() as cursor:
                cursor.execute(f"SHOW CREATE TABLE dwd.{identifier(table)}")
                ddl_row = cursor.fetchone()
                ddl = next((str(value) for key, value in ddl_row.items() if "create" in key.lower()), "")
                partition = partition_metadata(ddl, by_table[table])
                if table not in mappable or not partition["sort_time_field"]:
                    return table, (partition, [])
                clock = identifier(partition["sort_time_field"])
                cursor.execute(f"""SELECT DISTINCT technics_process_code, technics_process_name FROM (
SELECT technics_process_code, technics_process_name FROM dwd.{identifier(table)}
WHERE technics_process_code IS NOT NULL
  AND {clock} >= (SELECT DATE_SUB(MAX({clock}), INTERVAL 2 DAY) FROM dwd.{identifier(table)})
ORDER BY {clock} DESC LIMIT 200
) AS recent_processes""")
                return table, (partition, list(cursor.fetchall()))

        if table_processes is None or table_ddls is None:
            with ThreadPoolExecutor(max_workers=self.settings.deep_query_workers) as pool:
                probes = dict(pool.map(probe, sorted(table["table_name"] for table in tables)))
        else:
            saved_processes = {row["table"]: row["processes"] for row in table_processes}
            probes = {table["table_name"]: (partition_metadata(table_ddls.get(table["table_name"], ""), by_table[table["table_name"]]), saved_processes.get(table["table_name"], [])) for table in tables}
        catalog_tables, warnings, mapped_codes = [], [], set()
        for table in tables:
            table_name = table["table_name"]
            identifier(table_name)
            table_columns = by_table[table_name]
            features = [{"column_name": col["column_name"], "column_comment": col.get("column_comment") or "", "data_type": col["data_type"]}
                        for col in table_columns if is_numeric_feature(col)]
            partition, records = probes[table_name]
            rule = record_selection(table_name)
            available = {col["column_name"] for col in table_columns}
            mapped = table_name in mappable and bool(partition["sort_time_field"])
            if rule["mode"] != "latest" and rule["step_field"] not in available:
                mapped = False
                warnings.append(f"{table_name}缺少工步字段，未启用取数映射")
            if not partition["sort_time_field"]:
                warnings.append(f"{table_name}无法从DDL的RANGE分区确定唯一时间字段，未启用取数映射")
            if not mapped:
                records = []
            processes = []
            for code in sorted({str(row["technics_process_code"]) for row in records if row["technics_process_code"]}):
                if not re.fullmatch(r"C\d+", code):
                    warnings.append(f"{code}缺少可识别的工序顺序，未启用取数映射")
                    continue
                actual_names = [row["technics_process_name"] for row in records if str(row["technics_process_code"]) == code and row["technics_process_name"]]
                process_names = list(dict.fromkeys(names[code] + actual_names))
                processes.append({"code": code, "name": (process_names or [table.get("table_comment") or code])[0], "names": process_names, "order": int(code[1:])})
                if features:
                    mapped_codes.add(code)
            if not features:
                warnings.append(f"{table_name}没有可用的数值测量字段")
            if table_name not in mappable:
                warnings.append(f"{table_name}缺少追溯或NG分组字段，数值列已保存但未启用取数映射")
            elif not processes:
                warnings.append(f"{table_name}尚无可验证的工序编码，数值列已保存但未启用取数映射")
            if any(not feature["column_comment"].strip() for feature in features):
                warnings.append(f"{table_name}部分数值列缺少DDL注释，保留原列名，不编造释义")
            catalog_tables.append({"table_schema": "dwd", "table_name": table_name, "table_comment": table.get("table_comment") or "",
                                   "technics_processes": processes,
                                   "partition": {key: value for key, value in partition.items() if key != "sort_time_field"},
                                   "sort_time_field": partition["sort_time_field"], "sort_time_source": "SHOW CREATE TABLE / PARTITION BY RANGE",
                                   "date_filter_field": "shift_date" if "shift_date" in available else None,
                                   "record_selection": rule,
                                   "context_columns": [col["column_name"] for col in table_columns if col["column_name"] in CONTEXT_COLUMNS or col["column_name"] == partition["sort_time_field"]],
                                   "columns": features})
        unmapped = [{"code": code, "names": list(dict.fromkeys(names[code])), "reason": "未找到同时具备追溯、NG字段及DDL数值测量列的参数宽表"}
                    for code in sorted(names) if code not in mapped_codes]
        catalog = {"version": CATALOG_VERSION, "factory_id": self.factory_id,
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "source": {"table_descriptions": "information_schema.tables.TABLE_COMMENT", "column_descriptions": "information_schema.columns.COLUMN_COMMENT", "numeric_types": "information_schema.columns.DATA_TYPE", "sort_time_field": "SHOW CREATE TABLE / PARTITION BY RANGE", "date_filter_field": "information_schema.columns / shift_date"},
                   "order_basis": "C工序编码数字顺序；可在字典中调整order以匹配实际路线",
                   "dimension_processes": dimensions, "tables": catalog_tables,
                   "unmapped_processes": unmapped, "warnings": warnings}
        self.preserve_code_linkage(catalog)
        apply_catalog_rules(catalog)
        catalog["revision"] = hashlib.sha256(json.dumps(catalog, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        write_json(self.directory / CATALOG_FILENAME, catalog)
        return self.runtime_catalog(catalog)

    def preserve_code_linkage(self, catalog: dict):
        """A DDL refresh must not silently discard an independently audited route map."""
        path = self.directory / CATALOG_FILENAME
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if previous.get("factory_id") != self.factory_id:
            return
        old_tables = {table["table_name"]: table for table in previous.get("tables", [])}
        retained = False
        for table in catalog["tables"]:
            old = old_tables.get(table["table_name"], {})
            if not old.get("code_linkage"):
                continue
            # The observation is about these actual identity/route/time columns;
            # changes to measurement columns do not change that observation.
            scope = {"tenant_id", "product_code", "technics_line_name"}
            if (old.get("table_schema") == table["table_schema"]
                    and old.get("sort_time_field") == table["sort_time_field"]
                    and scope.intersection(old.get("context_columns", [])) == scope.intersection(table["context_columns"])):
                table["code_linkage"] = old["code_linkage"]
                retained = True
            else:
                catalog["warnings"].append(f"{table['table_name']}关联或时间字段已变化，原编码映射需重新核验")
        if retained:
            catalog["code_trace_routes"] = previous.get("code_trace_routes", {})
            if "code_trace_policy" in previous:
                catalog["code_trace_policy"] = previous["code_trace_policy"]
            if "code_trace_audit" in previous:
                catalog["code_trace_audit"] = previous["code_trace_audit"]
            catalog["source"]["code_linkage"] = previous.get("source", {}).get("code_linkage", "ADS route audit")

    @staticmethod
    def runtime_catalog(catalog: dict) -> dict:
        """Adapt the single DDL dictionary to the existing validated query interface."""
        processes = []
        for table in catalog["tables"]:
            for process in table["technics_processes"]:
                fields = [{"id": f"{process['code']}.{table['table_name']}.{col['column_name']}", "column": col["column_name"],
                           "name": col["column_comment"] or col["column_name"], "column_comment": col["column_comment"], "data_type": col["data_type"]}
                          for col in table["columns"]]
                if fields:
                    processes.append({**process, "table": table["table_name"], "table_comment": table["table_comment"],
                                      "partition": table["partition"], "sort_time_field": table["sort_time_field"], "date_filter_field": table["date_filter_field"], "record_selection": table["record_selection"],
                                      "code_linkage": table.get("code_linkage"),
                                      "columns": list(dict.fromkeys([*table["context_columns"], *(col["column_name"] for col in table["columns"])])), "fields": fields})
        return {**catalog, "processes": sorted(processes, key=lambda process: (process["order"], process["table"]))}


if __name__ == "__main__":
    import argparse
    from .config import NG_FACTORIES, get_ng_factory_settings
    parser = argparse.ArgumentParser(description="从DWD宽表DDL注释刷新NG数值字段字典（只读数据库）")
    parser.add_argument("--factory", choices=list(NG_FACTORIES), default="jinzhai-phase-3")
    args = parser.parse_args()
    catalog = NgCatalog(NgRepository(get_ng_factory_settings(args.factory)), args.factory).refresh()
    print(json.dumps({"factory": args.factory, "tables": len(catalog["tables"]), "mapped_processes": len(catalog["processes"]),
                      "numeric_fields": sum(len(table["columns"]) for table in catalog["tables"]), "warnings": catalog["warnings"]}, ensure_ascii=False))
