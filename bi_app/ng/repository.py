"""Only fixed SELECT templates and bound values can reach the factory database."""

from contextlib import contextmanager
from typing import Any

import pymysql

from .config import NgSettings
from .errors import NgError
from .schemas import FILTER_LABELS, GROUP_LABELS, NgFilters, NgParameters

FACT_TABLE = "`dwd`.`dwd_qual_defect_detail_pim`"
DIM_TABLE = "`dim`.`dim_qual_defect_ni`"


def build_where(parameters: NgParameters, filters: NgFilters | None = None) -> tuple[str, list[Any]]:
    clauses = ["`qualification_ratio_type` = %s", "`shift_date` >= %s", "`shift_date` <= %s"]
    values: list[Any] = [0, parameters.start_date.isoformat(), parameters.end_date.isoformat()]
    for field, selected in (filters or NgFilters()).nonempty().items():
        # Field names come exclusively from NgFilters, never from model/user SQL.
        if field not in FILTER_LABELS:
            raise NgError("不支持的筛选字段")
        clauses.append(f"`{field}` IN ({', '.join(['%s'] * len(selected))})")
        values.extend(selected)
    return " AND ".join(clauses), values


def build_aggregate_sql(parameters: NgParameters, filters: NgFilters) -> tuple[str, list[Any]]:
    where, values = build_where(parameters, filters)
    # Identifiers can only come from this closed registry; the model supplies enum values.
    if any(field not in GROUP_LABELS for field in parameters.group_by):
        raise NgError("不支持的分组维度")
    dimension_columns = [f"`{field}`" for field in parameters.group_by]
    group_columns = ", ".join(["`ng_type`", *dimension_columns])
    selected_dimensions = "".join(f"       facts.{column},\n" for column in dimension_columns)
    ordered_fields = (["shift_date"] if "shift_date" in parameters.group_by else []) + [field for field in parameters.group_by if field != "shift_date"]
    ordered_dimensions = "".join(f"facts.`{field}` ASC, " for field in ordered_fields)
    # Aggregate facts BEFORE joining. Duplicate dictionary rows cannot multiply ng_count.
    sql = f"""SELECT facts.ng_type,
       names.defect_name,
       names.ng_process_name,
{selected_dimensions}       facts.ng_count
FROM (
    SELECT {group_columns}, SUM(COALESCE(`ng_count`, 0)) AS ng_count
    FROM {FACT_TABLE}
    WHERE {where}
    GROUP BY {group_columns}
) AS facts
LEFT JOIN (
    SELECT `defect_code`, MAX(NULLIF(`defect_name`, '')) AS defect_name,
           GROUP_CONCAT(DISTINCT NULLIF(`technics_process_name`, '')) AS ng_process_name
    FROM {DIM_TABLE}
    GROUP BY `defect_code`
) AS names ON facts.ng_type = names.defect_code
ORDER BY {ordered_dimensions}facts.ng_count DESC, facts.ng_type ASC"""
    return sql, values


class NgRepository:
    def __init__(self, settings: NgSettings):
        self.settings = settings

    @contextmanager
    def connection(self):
        password = self.settings.db_password.get_secret_value()
        if not password:
            raise NgError("尚未配置 BI_NG_DB_PASSWORD", 503)
        connection = None
        try:
            connection = pymysql.connect(
                host=self.settings.db_host, port=self.settings.db_port,
                user=self.settings.db_user, password=password, database="dwd",
                charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=self.settings.db_connect_timeout,
                read_timeout=self.settings.db_read_timeout, write_timeout=10,
                autocommit=True,
            )
            yield connection
        except pymysql.MySQLError as exc:
            raise NgError("金寨三期数据库查询失败，请检查网络、视图权限或稍后重试", 503) from exc
        finally:
            if connection is not None:
                connection.close()

    def _options(self, connection, parameters: NgParameters, field: str, search: str = "", offset: int = 0) -> dict:
        if field not in FILTER_LABELS:
            raise NgError("不支持的筛选字段")
        where, values = build_where(parameters)
        # INSTR treats % and _ literally and works on the factory's MySQL-compatible engine.
        if search:
            where += f" AND INSTR(CAST(`{field}` AS CHAR), %s) > 0"
            values.append(search)
        size = self.settings.option_page_size
        sql = f"""SELECT DISTINCT CAST(`{field}` AS CHAR) AS value
FROM {FACT_TABLE}
WHERE {where} AND `{field}` IS NOT NULL AND CAST(`{field}` AS CHAR) <> ''
ORDER BY value ASC LIMIT %s OFFSET %s"""
        with connection.cursor() as cursor:
            cursor.execute(sql, [*values, size + 1, offset])
            rows = cursor.fetchall()
        return {
            "values": [str(row["value"]) for row in rows[:size]],
            "has_more": len(rows) > size,
            "next_offset": offset + min(len(rows), size),
        }

    def discover(self, parameters: NgParameters) -> list[dict]:
        with self.connection() as connection:
            return [
                {"cls": field, "cls_name": label,
                 **self._options(connection, parameters, field),
                 "selected_values": []}
                for field, label in FILTER_LABELS.items()
            ]

    def options(self, parameters: NgParameters, field: str, search: str, offset: int) -> dict:
        with self.connection() as connection:
            return self._options(connection, parameters, field, search, offset)

    def matching_values(self, parameters: NgParameters, fields: list[str]) -> dict[str, dict]:
        """Read more than the UI's first page before matching high-cardinality fields."""
        where, values = build_where(parameters)
        result = {}
        with self.connection() as connection, connection.cursor() as cursor:
            for field in fields:
                if field not in FILTER_LABELS:
                    raise NgError("不支持的筛选字段")
                sql = f"""SELECT DISTINCT CAST(`{field}` AS CHAR) AS value
FROM {FACT_TABLE}
WHERE {where} AND `{field}` IS NOT NULL AND CAST(`{field}` AS CHAR) <> ''
ORDER BY value ASC LIMIT %s"""
                cursor.execute(sql, [*values, self.settings.match_scan_limit + 1])
                rows = cursor.fetchall()
                result[field] = {
                    "values": [str(row["value"]) for row in rows[:self.settings.match_scan_limit]],
                    "truncated": len(rows) > self.settings.match_scan_limit,
                }
        return result

    def validate_filters(self, parameters: NgParameters, filters: NgFilters) -> None:
        """Validate resumed selections as well as model output against actual dated data."""
        if not filters.nonempty():
            return
        where, values = build_where(parameters)
        with self.connection() as connection, connection.cursor() as cursor:
            for field, selected in filters.nonempty().items():
                sql = f"""SELECT DISTINCT CAST(`{field}` AS CHAR) AS value
FROM {FACT_TABLE}
WHERE {where} AND CAST(`{field}` AS CHAR) IN ({', '.join(['%s'] * len(selected))})"""
                cursor.execute(sql, [*values, *selected])
                actual = {str(row["value"]) for row in cursor.fetchall()}
                if not set(selected).issubset(actual):
                    raise NgError(f"{FILTER_LABELS[field]}包含当前时间范围内不存在的值，请搜索实际选项后重新勾选", 422)

    def aggregate(self, parameters: NgParameters, filters: NgFilters) -> tuple[list[dict], str]:
        sql, values = build_aggregate_sql(parameters, filters)
        with self.connection() as connection, connection.cursor() as cursor:
            cursor.execute(sql, values)
            records = cursor.fetchall()
        rows = []
        for record in records:
            code = record["ng_type"]
            name = record["defect_name"]
            rows.append({
                "ng_type": str(code) if code is not None else "",
                "ng_name": str(name) if name else (f"未映射（{code}）" if code else "未分类NG"),
                "ng_process_name": str(record["ng_process_name"]) if record.get("ng_process_name") else None,
                "ng_count": float(record["ng_count"] or 0),
                **({"dimensions": {
                    field: str(record[field]) if record[field] is not None else None
                    for field in parameters.group_by
                }} if parameters.group_by else {}),
            })
        return rows, sql
