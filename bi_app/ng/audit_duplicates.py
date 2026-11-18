"""Read-only, full-history product-code uniqueness audit of parameter wide tables."""

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .catalog import NgCatalog, identifier, write_json
from .config import NG_FACTORIES, get_ng_factory_settings
from .deep_repository import NgDeepRepository
from .repository import NgRepository


def statistics_sql(table: str) -> str:
    # Two levels distinguish genuine within-tenant repeats from cross-tenant code reuse.
    return f"""WITH per_tenant AS (
    SELECT tenant_id, product_code, COUNT(1) AS n
    FROM dwd.{identifier(table)}
    GROUP BY tenant_id, product_code
), per_product AS (
    SELECT product_code, SUM(n) AS row_count, COUNT(1) AS tenant_keys,
           SUM(CASE WHEN n > 1 THEN 1 ELSE 0 END) AS repeated_tenant_keys,
           SUM(CASE WHEN n > 1 THEN n ELSE 0 END) AS repeated_tenant_rows,
           MAX(n) AS max_rows_in_tenant
    FROM per_tenant GROUP BY product_code
)
SELECT COALESCE(SUM(row_count), 0) AS total_rows,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN row_count ELSE 0 END), 0) AS valid_code_rows,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN 1 ELSE 0 END), 0) AS distinct_product_codes,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN tenant_keys ELSE 0 END), 0) AS distinct_tenant_product_keys,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' AND row_count > 1 THEN 1 ELSE 0 END), 0) AS repeated_product_codes,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' AND tenant_keys > 1 THEN 1 ELSE 0 END), 0) AS cross_tenant_product_codes,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN repeated_tenant_keys ELSE 0 END), 0) AS repeated_tenant_product_keys,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN repeated_tenant_rows ELSE 0 END), 0) AS repeated_tenant_rows,
       COALESCE(SUM(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN row_count - tenant_keys ELSE 0 END), 0) AS excess_rows_within_tenant,
       COALESCE(MAX(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN row_count ELSE 0 END), 0) AS max_rows_per_product,
       COALESCE(MAX(CASE WHEN product_code IS NOT NULL AND TRIM(product_code) <> '' THEN max_rows_in_tenant ELSE 0 END), 0) AS max_rows_per_tenant_product
FROM per_product"""


def audit_table(reader, table: dict) -> dict:
    started = time.perf_counter()
    name = table["table_name"]
    try:
        rows, seconds = reader._read(statistics_sql(name), [])
        stats = {key: int(value or 0) for key, value in rows[0].items()}
        stats["invalid_code_rows"] = stats["total_rows"] - stats["valid_code_rows"]
        result = {"status": "success", "table_name": name, "table_comment": table["table_comment"],
                  "process_codes": [process["code"] for process in table["technics_processes"]],
                  **stats, "query_seconds": seconds}
    except Exception as exc:
        result = {"status": "failed", "table_name": name, "table_comment": table["table_comment"],
                  "error_type": type(exc).__name__, "error": str(exc), "query_seconds": round(time.perf_counter() - started, 3)}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def detail_table(reader, table: dict, *, sample_size: int = 3) -> dict:
    """Inspect a few repeated keys; samples do not replace the full-history counts."""
    name = table["table_name"]
    rows, _ = reader._read("""SELECT column_name FROM information_schema.columns
WHERE table_schema='dwd' AND table_name=%s ORDER BY ordinal_position""", [name])
    columns = {row["column_name"] for row in rows}
    samples, _ = reader._read(f"""SELECT tenant_id, product_code, COUNT(1) AS n
FROM dwd.{identifier(name)} WHERE product_code IS NOT NULL AND TRIM(product_code) <> ''
GROUP BY tenant_id, product_code HAVING COUNT(1) > 1
ORDER BY n DESC, tenant_id, product_code LIMIT %s""", [sample_size])
    details = []
    variation_columns = [column for column in ["produce_id", "product_in_code", "device_code", "start_time", "end_time", "shift_date", "technics_step_code", "technics_step_name",
                         "technics_process_code", "technics_line_name", "device_name", "product_quality", "ng_type"] if column in columns]
    for sample in samples:
        projections = ["COUNT(1) AS n"]
        for column in variation_columns:
            projections.append(f"COUNT(DISTINCT {identifier(column)}) AS {identifier(column + '_distinct')}")
        for column in ("start_time", "end_time", "shift_date"):
            if column in columns:
                projections.extend([f"MIN({identifier(column)}) AS {identifier(column + '_min')}", f"MAX({identifier(column)}) AS {identifier(column + '_max')}"])
        stats, _ = reader._read(f"SELECT {','.join(projections)} FROM dwd.{identifier(name)} WHERE tenant_id <=> %s AND product_code=%s", [sample["tenant_id"], sample["product_code"]])
        details.append({"tenant_id": sample["tenant_id"], "product_code": sample["product_code"], **stats[0]})
    ddl_rows, _ = reader._read(f"SHOW CREATE TABLE dwd.{identifier(name)}", [])
    ddl = next((str(value) for row in ddl_rows for key, value in row.items() if "create" in key.lower()), "")
    key_lines = [line.strip() for line in ddl.splitlines() if re.match(r"\s*(PRIMARY|DUPLICATE|UNIQUE|AGGREGATE)\s+KEY", line, re.I)]
    return {"table_name": name, "table_comment": table["table_comment"], "key_definitions": key_lines, "samples": details}


def markdown_report(report: dict) -> str:
    succeeded = [row for row in report["tables"] if row["status"] == "success"]
    repeated = sorted([row for row in succeeded if row["repeated_tenant_product_keys"]], key=lambda row: -row["excess_rows_within_tenant"])
    unique = [row for row in succeeded if not row["repeated_tenant_product_keys"]]
    lines = ["# 参数宽表 product_code 唯一性核查", "", f"工厂：{report['factory_id']}；生成时间：{report['generated_at']}。", "",
             f"范围：{len(report['tables'])} 张参数表的全历史记录，不限定日期、产线、工序编码或产品集合，不抽样。排除 NULL/空产品码后分别检查 product_code 和 (tenant_id, product_code)。", "",
             f"成功 {len(succeeded)} 张；同一租户内有重复 {len(repeated)} 张；同一租户内未见重复 {len(unique)} 张；失败 {len(report['tables']) - len(succeeded)} 张。", "",
             "重复键数指同一租户内记录数大于 1 的产品数；多出行数为每个租户/产品保留一行后多出的记录数。", "",
             "| 表中文描述 | 表名 | 总记录数 | 同租户重复产品数 | 多出行数 | 单产品最多记录数 | 跨租户同码数 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in [*repeated, *unique]:
        lines.append(f"| {row['table_comment']} | `{row['table_name']}` | {row['total_rows']:,} | {row['repeated_tenant_product_keys']:,} | {row['excess_rows_within_tenant']:,} | {row['max_rows_per_tenant_product']:,} | {row['cross_tenant_product_codes']:,} |")
    failed = [row for row in report["tables"] if row["status"] != "success"]
    if failed:
        lines.extend(["", "## 未完成查询", ""] + [f"- {row['table_name']}：{row['error']}" for row in failed])
    lines.extend(["", "## 重复记录抽查", "", "以下样本仅解释重复记录形态，不代表所有重复均由相同原因导致。", ""])
    for detail in report.get("details", []):
        lines.extend([f"### {detail['table_comment']}（{detail['table_name']}）", "", f"DDL 键定义：`{' / '.join(detail['key_definitions']) or '未提取到'}`", ""])
        for sample in detail["samples"]:
            variations = "；".join(f"{key.removesuffix('_distinct')}不同值数={value}" for key, value in sample.items() if key.endswith("_distinct"))
            lines.append(f"- 租户 `{sample['tenant_id']}`，产品 `{sample['product_code']}`：{sample['n']:,} 行。{variations}。时间范围：{sample.get('end_time_min')} 至 {sample.get('end_time_max')}。")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--factory", choices=list(NG_FACTORIES), default="jinzhai-phase-3")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--read-timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    settings = get_ng_factory_settings(args.factory).model_copy(update={"db_read_timeout": args.read_timeout})
    repository = NgRepository(settings)
    reader = NgDeepRepository(repository)
    catalog = NgCatalog(repository, args.factory).load()
    tables = catalog["tables"]
    report = {"factory_id": args.factory, "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "scope": "full_history_all_lines_all_tenants", "tables": [], "details": []}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(audit_table, reader, table) for table in tables]
        for future in as_completed(futures):
            report["tables"].append(future.result())
            write_json(args.output, report)
    report["tables"].sort(key=lambda row: row["table_name"])
    if args.details:
        duplicated = {row["table_name"] for row in report["tables"] if row["status"] == "success" and row["repeated_tenant_product_keys"] > 0}
        for table in tables:
            if table["table_name"] in duplicated:
                try:
                    report["details"].append(detail_table(reader, table))
                    print(json.dumps({"detail_complete": table["table_name"]}, ensure_ascii=False), flush=True)
                except Exception as exc:
                    report.setdefault("detail_errors", []).append({"table_name": table["table_name"], "error": str(exc)})
                write_json(args.output, report)
    write_json(args.output, report)
    args.output.with_suffix(".md").write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps({"report": str(args.output), "completed": len(report["tables"])}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
