import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

BI_ROOT = Path(__file__).resolve().parents[1]


class NgSettings(BaseModel):
    db_host: str = "10.52.94.75"
    db_port: int = Field(default=19030, ge=1, le=65535)
    db_user: str = "gdmo"
    db_password: SecretStr = SecretStr("")
    db_connect_timeout: int = Field(default=5, gt=0)
    db_read_timeout: int = Field(default=60, gt=0)
    llm_model: str = "DeepSeek-V4-Flash"
    llm_base_url: str = "http://10.2.131.184:3304/v1"
    llm_api_key: SecretStr = SecretStr("EMPTY")
    llm_timeout: int = Field(default=60, gt=0)
    llm_trust_env: bool = False
    checkpoint_path: Path = BI_ROOT / ".state" / "ng_checkpoints.sqlite3"
    max_date_days: int = Field(default=366, ge=7)
    confirmation_ttl_seconds: int = Field(default=86400, gt=0)
    option_page_size: int = Field(default=100, ge=1, le=500)
    match_scan_limit: int = Field(default=5000, ge=100, le=20000)
    match_candidate_limit: int = Field(default=60, ge=10, le=200)


@lru_cache
def get_ng_settings() -> NgSettings:
    # Read only this service's environment file. Container/host variables take priority.
    load_dotenv(BI_ROOT / ".env", override=False)
    return NgSettings(
        db_host=os.getenv("BI_NG_DB_HOST", "10.52.94.75"),
        db_port=int(os.getenv("BI_NG_DB_PORT", "19030")),
        db_user=os.getenv("BI_NG_DB_USER", "gdmo"),
        db_password=SecretStr(os.getenv("BI_NG_DB_PASSWORD", "")),
        db_connect_timeout=int(os.getenv("BI_NG_DB_CONNECT_TIMEOUT", "5")),
        db_read_timeout=int(os.getenv("BI_NG_DB_READ_TIMEOUT", "60")),
        llm_model=os.getenv("BI_NG_LLM_MODEL", os.getenv("MODEL_NAME", "DeepSeek-V4-Flash")),
        llm_base_url=os.getenv("BI_NG_LLM_BASE_URL", os.getenv("BASE_URL", "http://10.2.131.184:3304/v1")),
        llm_api_key=SecretStr(os.getenv("BI_NG_LLM_API_KEY", os.getenv("API_KEY", "EMPTY"))),
        llm_timeout=int(os.getenv("BI_NG_LLM_TIMEOUT", "60")),
        llm_trust_env=os.getenv("BI_NG_LLM_TRUST_ENV", "false").lower() in {"true", "1", "yes"},
        checkpoint_path=Path(os.getenv("BI_NG_CHECKPOINT_PATH", str(BI_ROOT / ".state" / "ng_checkpoints.sqlite3"))),
        max_date_days=int(os.getenv("BI_NG_MAX_DATE_DAYS", "366")),
        confirmation_ttl_seconds=int(os.getenv("BI_NG_CONFIRMATION_TTL_SECONDS", "86400")),
        match_scan_limit=int(os.getenv("BI_NG_MATCH_SCAN_LIMIT", "5000")),
        match_candidate_limit=int(os.getenv("BI_NG_MATCH_CANDIDATE_LIMIT", "60")),
    )
