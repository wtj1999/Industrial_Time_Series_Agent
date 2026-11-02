import logging
import threading

from fastapi import APIRouter, Header, HTTPException

from .config import get_ng_settings
from .errors import NgError
from .schemas import NgOptionsRequest, NgQueryRequest
from .workflow import NgWorkflow

router = APIRouter(prefix="/api/bi/ng", tags=["NG问数"])
logger = logging.getLogger(__name__)
_service: NgWorkflow | None = None
_service_lock = threading.Lock()


def get_ng_service() -> NgWorkflow:
    global _service
    with _service_lock:
        if _service is None:
            _service = NgWorkflow(get_ng_settings())
        return _service


def close_ng_service():
    global _service
    with _service_lock:
        if _service is not None:
            _service.close()
            _service = None


def _invoke(action):
    try:
        return action()
    except NgError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        # Do not emit DB messages, connection strings, request data, or LLM credentials.
        logger.error("NG workflow failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=500, detail="NG问数暂时无法完成，请稍后重试") from exc


@router.post("/query")
def query_ng(request: NgQueryRequest, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    # FastAPI runs synchronous endpoints in its worker pool, keeping DB/LLM calls off the event loop.
    return _invoke(lambda: get_ng_service().query(request, x_user_id))


@router.post("/options")
def ng_options(request: NgOptionsRequest, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    return _invoke(lambda: get_ng_service().options(request, x_user_id))
