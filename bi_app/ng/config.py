import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

BI_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NG_FACTORY = 'jinzhai-phase-3'


class NgFactoryConfig(BaseModel):
    name: str
    db_host: str
    db_port: int = Field(default=19030, ge=1, le=65535)
    db_user: str = 'gdmo'
    db_password: SecretStr = SecretStr('')


# Add factories here; credentials never go to the browser. Each entry also accepts
# BI_NG_<FACTORY_ID_WITH_UNDERSCORES>_DB_HOST/PORT/USER/PASSWORD overrides.
NG_FACTORIES: dict[str, NgFactoryConfig] = {
    'jinzhai-phase-2': NgFactoryConfig(name='金寨二期', db_host='10.36.94.9', db_password=SecretStr('gdmo@123!!')),
    'jinzhai-phase-3': NgFactoryConfig(name='金寨三期', db_host='10.52.94.75'),
    'wuhu-phase-1': NgFactoryConfig(name='芜湖一期', db_host='10.53.195.56', db_password=SecretStr('Y@3R!o!@qwq')),
}


class NgSettings(BaseModel):
    db_host: str = "10.52.94.75"
    db_port: int = Field(default=19030, ge=1, le=65535)
    db_user: str = "gdmo"
    db_password: SecretStr = SecretStr("")
    db_connect_timeout: int = Field(default=5, gt=0)
    db_read_timeout: int = Field(default=60, gt=0)
    llm_model: str = "DeepSeek-V4.1-Flash"
    llm_base_url: str = "http://10.2.131.172:3627/v1"
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
    default = NG_FACTORIES[DEFAULT_NG_FACTORY]
    return NgSettings(
        db_host=os.getenv("BI_NG_DB_HOST", default.db_host),
        db_port=int(os.getenv("BI_NG_DB_PORT", str(default.db_port))),
        db_user=os.getenv("BI_NG_DB_USER", default.db_user),
        db_password=SecretStr(os.getenv("BI_NG_DB_PASSWORD", default.db_password.get_secret_value())),
        db_connect_timeout=int(os.getenv("BI_NG_DB_CONNECT_TIMEOUT", "5")),
        db_read_timeout=int(os.getenv("BI_NG_DB_READ_TIMEOUT", "60")),
        llm_model=os.getenv("BI_NG_LLM_MODEL", os.getenv("MODEL_NAME", "DeepSeek-V4.1-Flash")),
        llm_base_url=os.getenv("BI_NG_LLM_BASE_URL", os.getenv("BASE_URL", "http://10.2.131.172:3627/v1")),
        llm_api_key=SecretStr(os.getenv("BI_NG_LLM_API_KEY", os.getenv("API_KEY", "EMPTY"))),
        llm_timeout=int(os.getenv("BI_NG_LLM_TIMEOUT", "60")),
        llm_trust_env=os.getenv("BI_NG_LLM_TRUST_ENV", "false").lower() in {"true", "1", "yes"},
        checkpoint_path=Path(os.getenv("BI_NG_CHECKPOINT_PATH", str(BI_ROOT / ".state" / "ng_checkpoints.sqlite3"))),
        max_date_days=int(os.getenv("BI_NG_MAX_DATE_DAYS", "366")),
        confirmation_ttl_seconds=int(os.getenv("BI_NG_CONFIRMATION_TTL_SECONDS", "86400")),
        match_scan_limit=int(os.getenv("BI_NG_MATCH_SCAN_LIMIT", "5000")),
        match_candidate_limit=int(os.getenv("BI_NG_MATCH_CANDIDATE_LIMIT", "60")),
    )


def get_ng_factory_settings(factory_id: str = DEFAULT_NG_FACTORY) -> NgSettings:
    if factory_id not in NG_FACTORIES:
        raise ValueError('不支持的NG工厂')
    base = get_ng_settings()
    factory = NG_FACTORIES[factory_id]
    # Preserve legacy BI_NG_DB_* and checkpoints for existing phase-3 sessions.
    defaults = base if factory_id == DEFAULT_NG_FACTORY else factory
    prefix = f'BI_NG_{factory_id.upper().replace("-", "_")}_DB_'
    path = base.checkpoint_path
    if factory_id != DEFAULT_NG_FACTORY:
        path = path.with_name(f'{path.stem}.{factory_id}{path.suffix}')
    return NgSettings.model_validate({
        **base.model_dump(),
        'db_host': os.getenv(prefix + 'HOST', defaults.db_host),
        'db_port': int(os.getenv(prefix + 'PORT', str(defaults.db_port))),
        'db_user': os.getenv(prefix + 'USER', defaults.db_user),
        'db_password': SecretStr(os.getenv(prefix + 'PASSWORD', defaults.db_password.get_secret_value())),
        'checkpoint_path': path,
    })
