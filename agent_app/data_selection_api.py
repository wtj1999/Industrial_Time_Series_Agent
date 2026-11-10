"""Prepare shared files or online tables for the existing upload/task pipeline."""
import csv
import os
import tempfile
from pathlib import Path
from typing import Literal

import pymysql
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from . import public_datasets_api as public
from .config.online_sources import ONLINE_SOURCES
from .utils import online_data_sources as online
from .utils.helpers import validate_existing_file_name

router = APIRouter(prefix='/api/data-selection', tags=['data-selection'])
MAX_BYTES = 100 * 1024 * 1024
ONLINE_ROW_LIMIT = 5_000


class SelectionRequest(BaseModel):
    kind: Literal['public', 'online']
    file_name: str = Field(default='', max_length=255)
    source_id: str = Field(default='', max_length=100)
    table_name: str = Field(default='', max_length=255)


def export_online_table(source, table_name: str, path: Path):
    """Select the latest 5,000 inserted records, then export chronologically."""
    with online._connect(source) as connection:
        try:
            with connection.cursor() as cursor:
                online._metadata(cursor, source, table_name)
            with connection.cursor(pymysql.cursors.SSCursor) as cursor:
                cursor.execute(
                    f'SELECT * FROM (SELECT * FROM {online._quoted(source.database)}.{online._quoted(table_name)} '
                    f'ORDER BY {online._quoted("insert_time")} DESC LIMIT %s) AS recent_records '
                    f'ORDER BY {online._quoted("insert_time")} ASC',
                    (ONLINE_ROW_LIMIT,),
                )
                with path.open('w', encoding='utf-8-sig', newline='') as output:
                    writer = csv.writer(output)
                    writer.writerow([col[0] for col in cursor.description])
                    while rows := cursor.fetchmany(1000):
                        writer.writerows(rows)
                        if output.tell() > MAX_BYTES:
                            connection.close()
                            raise HTTPException(413, '表数据超过 100MB，请选择较小的数据表或上传筛选后的数据文件')
        except Exception:
            connection.close()
            raise


@router.post('')
def prepare_selection(request: SelectionRequest):
    if request.kind == 'public':
        valid, _ = validate_existing_file_name(request.file_name)
        root = public.PUBLIC_DATASETS_DIR.resolve()
        candidate = root / request.file_name
        path = candidate.resolve()
        if not valid or request.file_name.startswith('.') or candidate.is_symlink() or path.parent != root or not path.is_file():
            raise HTTPException(404, '公共文件不存在')
        if path.suffix.lower() not in public.SUPPORTED_SUFFIXES:
            raise HTTPException(400, '不支持的文件格式')
        if path.stat().st_size > MAX_BYTES:
            raise HTTPException(413, '文件大小不能超过 100MB')
        return FileResponse(path, filename=path.name)
    source = ONLINE_SOURCES.get(request.source_id)
    if source is None or not request.table_name:
        raise HTTPException(400, '请选择有效的基地和数据表')
    fd, name = tempfile.mkstemp(suffix='.csv', prefix='agent-selection-')
    os.close(fd)
    path = Path(name)
    try:
        export_online_table(source, request.table_name, path)
    except Exception as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, (online.OnlineTableNotFound, online.MissingInsertTime)):
            raise HTTPException(400, '该数据表不可用，请重新选择') from exc
        raise HTTPException(503, '读取在线数据失败，请稍后重试') from exc
    return FileResponse(path, filename='online.csv', background=BackgroundTask(path.unlink, missing_ok=True))
