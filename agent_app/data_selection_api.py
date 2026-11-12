"""Prepare shared files or online tables for the existing upload/task pipeline."""
import csv
import os
import tempfile
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pymysql
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict, model_validator
from starlette.background import BackgroundTask

from . import public_datasets_api as public
from .config.online_sources import ONLINE_SOURCES
from .utils import online_data_sources as online
from .utils.helpers import validate_existing_file_name

router = APIRouter(prefix='/api/data-selection', tags=['data-selection'])
MAX_BYTES = 100 * 1024 * 1024
ONLINE_ROW_LIMIT = 5_000


class PreviewExportRequest(BaseModel):
    """Import the exact displayed snapshot rather than rerun a changing query."""
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)
    source_id: str = Field(min_length=1, max_length=100)
    table_name: str = Field(min_length=1, max_length=255)
    display_name: str = Field(default='', max_length=255)
    columns: list[str] = Field(min_length=1, max_length=1000)
    selected_columns: list[str] = Field(min_length=1, max_length=1000)
    rows: list[list[str | int | float | bool | None]] = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def validate_snapshot(self):
        if len(set(self.columns)) != len(self.columns) or any(not col or len(col) > 255 for col in self.columns):
            raise ValueError('无效或重复的字段名称')
        if len(set(self.selected_columns)) != len(self.selected_columns) or not set(self.selected_columns).issubset(self.columns):
            raise ValueError('导出字段必须来自当前表格且不能重复')
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError('数据行与字段数量不一致')
        return self


@router.post('/export')
def export_preview_to_private(request: PreviewExportRequest, x_user_id: str = Header(alias='X-User-Id')):
    if request.source_id not in ONLINE_SOURCES:
        raise HTTPException(400, '无效的在线数据源')
    # Identity is supplied by SessionAuthMiddleware, never by the request body.
    user_id = re.sub(r'_+', '_', re.sub(r'[^A-Za-z0-9_.\-]', '_', x_user_id.strip())).strip('._')[:96].rstrip('._')
    if not user_id:
        raise HTTPException(401, '会话已失效，请重新登录')
    if not user_id.startswith('user_'):
        user_id = 'user_' + user_id
    uploads = Path('uploads')
    root = (uploads if uploads.exists() else Path(__file__).with_name('uploads')).resolve()
    user_dir = root / user_id
    if user_dir.resolve() != user_dir:
        raise HTTPException(403, '无法访问私有数据目录')
    user_dir.mkdir(parents=True, exist_ok=True)
    title = re.sub(r'[^\w.\-]', '_', request.display_name or request.table_name).strip('._')[:80] or '在线数据'
    name = f'在线导出_{title}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex}.csv'
    destination = user_dir / name
    fd, temporary = tempfile.mkstemp(dir=user_dir, suffix='.tmp', prefix='.export-')
    os.close(fd)
    pending = Path(temporary)
    selected = set(request.selected_columns)
    indexes = [i for i, column in enumerate(request.columns) if column in selected]
    try:
        with pending.open('w', encoding='utf-8-sig', newline='') as output:
            writer = csv.writer(output)
            writer.writerow([request.columns[i] for i in indexes])
            for row in request.rows:
                writer.writerow([row[i] for i in indexes])
                if output.tell() > MAX_BYTES:
                    raise HTTPException(413, '导出数据大小不能超过 100MB')
        os.replace(pending, destination)
    finally:
        pending.unlink(missing_ok=True)
    stat = destination.stat()
    return {'success': True, 'row_count': len(request.rows), 'column_count': len(indexes), 'dataset': {
        'name': name, 'file_name': name, 'extension': 'csv', 'size_bytes': stat.st_size,
        'modified_at': datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(), 'session_id': None,
    }}


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
