"""Read-only metadata and bounded table previews for configured online sources."""

from __future__ import annotations

from typing import Any

import pymysql

from config.online_sources import ONLINE_SOURCES, OnlineSource
from utils.dataset_table_preview import to_preview_cell


PREVIEW_ROWS = 50


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
        if table_name in timestamped_tables
    ]


def preview_online_table(source: OnlineSource, table_name: str) -> dict[str, Any]:
    """Validate metadata before interpolating a quoted identifier into SQL."""
    with _connect(source) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'",
                (source.database, table_name),
            )
            if cursor.fetchone() is None:
                raise OnlineTableNotFound(table_name)
            cursor.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s AND column_name = 'insert_time'",
                (source.database, table_name),
            )
            if cursor.fetchone() is None:
                raise MissingInsertTime(table_name)

            cursor.execute(
                f"SELECT * FROM {_quoted(source.database)}.{_quoted(table_name)} "
                f"ORDER BY {_quoted('insert_time')} DESC LIMIT {PREVIEW_ROWS + 1}"
            )
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()

    return {
        "file_name": table_name,
        "columns": columns,
        "rows": [[to_preview_cell(value) for value in row] for row in rows[:PREVIEW_ROWS]],
        "preview_rows": min(len(rows), PREVIEW_ROWS),
        "has_more": len(rows) > PREVIEW_ROWS,
        "total_rows": None,
    }
