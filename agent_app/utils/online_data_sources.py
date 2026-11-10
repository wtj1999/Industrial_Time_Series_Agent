"""Read-only metadata and bounded table previews for configured online sources."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from math import isfinite
import re
from typing import Any

import pymysql

from config.online_sources import ONLINE_SOURCES, OnlineSource
from utils.dataset_table_preview import to_preview_cell


# Hide backup/test/maintenance tables by their physical name, not their comment.
EXCLUDED_TABLE_NAME_RE = re.compile(
    r"(?i).*_(bak|backup|test|tmp|temp|old|copy|clone|draft|scratch|demo|sample|example|spare|deprecated|obsolete|disabled|archive|archived|trace|debug|check|chk|verify|verification|fix|fixed)([_-]?\d+)?$"
)

PREVIEW_ROWS = 50
METRIC_SAMPLE_ROWS = 100
FACTORY_TIMEZONE = timezone(timedelta(hours=8))
MAX_PREVIEW_ROWS = 500
OPTION_LIMIT = 100
STRING_TYPES = {'char', 'varchar', 'string', 'text', 'tinytext', 'mediumtext', 'longtext'}
NUMERIC_TYPES = {'tinyint', 'smallint', 'mediumint', 'int', 'integer', 'bigint', 'largeint', 'float', 'double', 'real', 'decimal', 'numeric'}
TIME_TYPES = {'date', 'datetime', 'timestamp', 'datetimev2', 'datev2'}


class InvalidOnlineQuery(ValueError):
    """Invalid column, filter, or query bound supplied by the client."""


def _metadata(cursor, source: OnlineSource, table_name: str):
    cursor.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'",
        (source.database, table_name),
    )
    if cursor.fetchone() is None:
        raise OnlineTableNotFound(table_name)
    cursor.execute(
        "SELECT column_name, data_type, column_comment FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (source.database, table_name),
    )
    columns = [
        {'name': name, 'data_type': kind.lower(), 'comment': comment or '',
         'filterable': kind.lower() in STRING_TYPES,
         'chartable': kind.lower() in NUMERIC_TYPES,
         'temporal': kind.lower() in TIME_TYPES}
        for name, kind, comment in cursor.fetchall()
    ]
    if not any(column['name'] == 'insert_time' for column in columns):
        raise MissingInsertTime(table_name)
    return columns


def _where(columns, filters: dict[str, str | None] | None):
    if filters is None:
        filters = {}
    if not isinstance(filters, dict) or len(filters) > 32:
        raise InvalidOnlineQuery('筛选条件必须是对象，最多支持 32 列')
    allowed = {column['name'] for column in columns if column['filterable']}
    clauses, values = [], []
    for column, value in filters.items():
        if column not in allowed or (value is not None and not isinstance(value, str)):
            raise InvalidOnlineQuery('只能按字符类型列筛选，筛选值必须是字符串或 null')
        if value is not None and len(value) > 4096:
            raise InvalidOnlineQuery('筛选值过长')
        if value is None:
            clauses.append(f'{_quoted(column)} IS NULL')
        else:
            clauses.append(f'{_quoted(column)} = %s')
            values.append(value)
    return clauses, values


class OnlineTableNotFound(Exception):
    """The requested table is not part of the configured database."""


class MissingInsertTime(Exception):
    """The table cannot be ordered by insert_time."""


def _connect(source: OnlineSource):
    return pymysql.connect(
        host=source.host,
        port=source.port,
        user=source.user,
        password=source.password,
        database=source.database,
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=15,
        write_timeout=5,
        autocommit=True,
    )


def _quoted(identifier: str) -> str:
    return "`" + identifier.replace("`", "``") + "`"


def list_online_sources() -> list[dict[str, str]]:
    """Return public source metadata, never credentials."""
    return [
        {"id": source_id, "name": source.name, "description": source.description, "database": source.database}
        for source_id, source in ONLINE_SOURCES.items()
    ]


def list_online_tables(source: OnlineSource) -> list[dict[str, Any]]:
    with _connect(source) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name, table_comment FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name",
                (source.database,),
            )
            tables = cursor.fetchall()
            cursor.execute(
                "SELECT DISTINCT table_name FROM information_schema.columns "
                "WHERE table_schema = %s AND column_name = 'insert_time'",
                (source.database,),
            )
            timestamped_tables = {row[0] for row in cursor.fetchall()}

    return [
        {
            "name": comment.strip() if comment and comment.strip().upper() != "OLAP" else table_name,
            "table_name": table_name,
        }
        for table_name, comment in tables
        if table_name in timestamped_tables and not EXCLUDED_TABLE_NAME_RE.search(table_name)
    ]


def preview_online_table(source: OnlineSource, table_name: str, filters: dict[str, str | None] | None = None, limit: int = PREVIEW_ROWS) -> dict[str, Any]:
    """Validate metadata before interpolating a quoted identifier into SQL."""
    if not isinstance(limit, int) or not 1 <= limit <= MAX_PREVIEW_ROWS:
        raise InvalidOnlineQuery('记录数必须在 1 到 500 之间')
    with _connect(source) as connection:
        with connection.cursor() as cursor:
            metadata = _metadata(cursor, source, table_name)
            clauses, values = _where(metadata, filters)
            where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
            cursor.execute(
                f"SELECT * FROM {_quoted(source.database)}.{_quoted(table_name)} "
                f"{where} ORDER BY {_quoted('insert_time')} DESC LIMIT %s",
                (*values, limit + 1),
            )
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()

    return {
        "file_name": table_name,
        "columns": columns,
        "column_metadata": metadata,
        "rows": [[to_preview_cell(value) for value in row] for row in rows[:limit]],
        "preview_rows": min(len(rows), limit),
        "has_more": len(rows) > limit,
        "total_rows": None,
    }


def _missing_metric_cell(value: Any) -> bool:
    # Zero, False and literal strings such as 'NULL' are real stored values.
    return (value is None or isinstance(value, str) and not value.strip()
            or isinstance(value, float) and not isfinite(value)
            or isinstance(value, Decimal) and not value.is_finite())


def _metric_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
        except ValueError:
            return None
    else:
        return None
    # Factory timestamps without an offset use China Standard Time, never host-local time.
    return parsed.replace(tzinfo=FACTORY_TIMEZONE) if parsed.tzinfo is None else parsed.astimezone(FACTORY_TIMEZONE)


def summarize_online_sample(columns: list[str], rows: list[tuple], *, numeric_columns: list[str] | None = None,
                            now: datetime | None = None) -> dict[str, Any]:
    """Duplicate rate is the share of numeric columns constant across the sample."""
    checked_at = now or datetime.now(FACTORY_TIMEZONE)
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=FACTORY_TIMEZONE)
    sample_rows = len(rows)
    total_cells = sample_rows * len(columns)
    missing_cells = sum(_missing_metric_cell(value) for row in rows for value in row)
    # Classify by database schema, never by whether varchar values look like numbers.
    numeric_names = set(numeric_columns or [])
    numeric_indexes = [index for index, name in enumerate(columns) if name in numeric_names]
    constant_numeric_columns = sum(
        all(not _missing_metric_cell(row[index]) and row[index] == rows[0][index] for row in rows)
        for index in numeric_indexes
    ) if sample_rows else 0
    time_index = columns.index('insert_time')
    latest = max((value for row in rows if (value := _metric_time(row[time_index])) is not None), default=None)
    return {
        'sample_limit': METRIC_SAMPLE_ROWS, 'sample_rows': sample_rows,
        'column_count': len(columns), 'total_cells': total_cells, 'missing_cells': missing_cells,
        'completeness_rate': round((total_cells - missing_cells) / total_cells * 100, 2) if total_cells else None,
        'numeric_column_count': len(numeric_indexes),
        'constant_numeric_column_count': constant_numeric_columns,
        'duplicate_rate': round(constant_numeric_columns / len(numeric_indexes) * 100, 2) if sample_rows and numeric_indexes else None,
        'latest_insert_time': latest.isoformat() if latest else None,
        'freshness_seconds': (checked_at - latest).total_seconds() if latest else None,
        'checked_at': checked_at.isoformat(),
    }


def online_table_metrics(source: OnlineSource, table_name: str) -> dict[str, Any]:
    """Only SELECT the latest 100 rows; never count or return the full table."""
    with _connect(source) as connection:
        with connection.cursor() as cursor:
            metadata = _metadata(cursor, source, table_name)
            cursor.execute(
                f'SELECT * FROM {_quoted(source.database)}.{_quoted(table_name)} '
                f'ORDER BY {_quoted("insert_time")} DESC LIMIT %s', (METRIC_SAMPLE_ROWS,),
            )
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
    return summarize_online_sample(columns, rows,
                                   numeric_columns=[column['name'] for column in metadata if column['data_type'] in NUMERIC_TYPES])


def online_column_options(source: OnlineSource, table_name: str, column: str,
                          filters: dict[str, str | None] | None = None, search: str = '',
                          limit: int = PREVIEW_ROWS) -> dict[str, Any]:
    """Search distinct values within the latest preview-sized matching records."""
    if not isinstance(limit, int) or not 1 <= limit <= MAX_PREVIEW_ROWS:
        raise InvalidOnlineQuery('记录数必须在 1 到 500 之间')
    if len(search) > 200:
        raise InvalidOnlineQuery('搜索词最多 200 字符')
    with _connect(source) as connection:
        with connection.cursor() as cursor:
            metadata = _metadata(cursor, source, table_name)
            if column not in {item['name'] for item in metadata if item['filterable']}:
                raise InvalidOnlineQuery('该列不支持下拉筛选')
            clauses, values = _where(metadata, filters)
            where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
            search_where = ''
            params = [*values, limit]
            if search:
                # LOCATE performs literal substring search (no LIKE wildcard ambiguity).
                # Apply search after selecting recent rows; never reach older records.
                search_where = f' WHERE LOCATE(%s, {_quoted(column)}) > 0'
                params.append(search)
            cursor.execute(
                f'SELECT DISTINCT {_quoted(column)} FROM ('
                f'SELECT {_quoted(column)} FROM {_quoted(source.database)}.{_quoted(table_name)}'
                f'{where} ORDER BY {_quoted("insert_time")} DESC LIMIT %s) AS recent_records'
                f'{search_where} ORDER BY {_quoted(column)} LIMIT %s', (*params, OPTION_LIMIT + 1),
            )
            rows = cursor.fetchall()
    return {'values': [None if row[0] is None else str(row[0]) for row in rows[:OPTION_LIMIT]],
            'has_more': len(rows) > OPTION_LIMIT}
