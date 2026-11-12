import logging
import threading

from fastapi import APIRouter, Header, HTTPException

from .config import DEFAULT_NG_FACTORY, NG_FACTORIES, get_ng_factory_settings
from .errors import NgError
from .schemas import NgOptionsRequest, NgQueryRequest
from .workflow import NgWorkflow

router = APIRouter(prefix="/api/bi/ng", tags=["NG问数"])
logger = logging.getLogger(__name__)
_services: dict[str, NgWorkflow] = {}
_service_lock = threading.Lock()


def get_ng_service(factory_id: str = DEFAULT_NG_FACTORY) -> NgWorkflow:
    if factory_id not in NG_FACTORIES:
        raise HTTPException(status_code=422, detail='不支持的NG工厂')
    with _service_lock:
        if factory_id not in _services:
            _services[factory_id] = NgWorkflow(get_ng_factory_settings(factory_id))
        return _services[factory_id]


def close_ng_service():
    with _service_lock:
        for service in _services.values():
            service.close()
        _services.clear()


def _invoke(action):
    try:
        return action()
    except NgError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        # Do not emit DB messages, connection strings, request data, or LLM credentials.
        logger.error("NG workflow failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="NG问数暂时无法完成，请稍后重试") from exc


@router.post("/query")
def query_ng(request: NgQueryRequest, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    # FastAPI runs synchronous endpoints in its worker pool, keeping DB/LLM calls off the event loop.
    return _invoke(lambda: get_ng_service(request.factory_id).query(request, x_user_id))


@router.post("/options")
def ng_options(request: NgOptionsRequest, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    return _invoke(lambda: get_ng_service(request.factory_id).options(request, x_user_id))
