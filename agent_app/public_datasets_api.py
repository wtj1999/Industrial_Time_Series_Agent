"""Read-only shared offline datasets, separate from per-user uploads."""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .utils.dataset_table_preview import read_dataset_table_preview
from .utils.helpers import validate_existing_file_name

router = APIRouter(prefix="/api/public-datasets", tags=["public-datasets"])
PUBLIC_DATASETS_DIR = Path(__file__).with_name("public_datasets")
SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".parquet"}
logger = logging.getLogger(__name__)


@router.get("")
def list_public_datasets():
    root = PUBLIC_DATASETS_DIR.resolve()
    entries = []
    if root.is_dir():
        for path in root.iterdir():
            if path.name.startswith('.') or path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_SUFFIXES or path.resolve().parent != root:
                continue
            stat = path.stat()
            entries.append({
                "name": path.name, "file_name": path.name,
                "extension": path.suffix.lower().lstrip('.'), "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "session_id": None,
            })
    entries.sort(key=lambda entry: (entry['modified_at'], entry['file_name']), reverse=True)
    return {"datasets": entries, "total": len(entries)}


@router.get("/{file_name}/preview")
async def preview_public_dataset(file_name: str):
    valid, message = validate_existing_file_name(file_name)
    if not valid or file_name.startswith('.'):
        raise HTTPException(status_code=400, detail=message or "无效的文件名")
    if Path(file_name).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail="不支持的文件格式")
    root = PUBLIC_DATASETS_DIR.resolve()
    candidate = root / file_name
    path = candidate.resolve()
    if candidate.is_symlink() or path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="公共文件不存在")
    try:
        return await asyncio.to_thread(read_dataset_table_preview, path)
    except Exception as exc:
        logger.warning("Public dataset preview failed: %s", type(exc).__name__)
        raise HTTPException(status_code=422, detail="无法读取文件内容，请检查文件格式") from exc
