import logging
import threading
import time

from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.responses import StreamingResponse

from .config import DEFAULT_NG_FACTORY, NG_FACTORIES, get_ng_factory_settings
from .errors import NgError
from .schemas import NgOptionsRequest, NgQueryRequest
from .deep_schemas import DeepAnalyzeRequest, DeepRecommendRequest, ValidationListRequest, ValidationRecordRequest, QualityAuditRequest
from .deep_progress import analysis_event_stream
from .workflow import NgWorkflow
from ..session_store import get_bi_sessions, scope
from ..sessions import failed_operation
from .deep_progress import AnalysisCancelled

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
def query_ng(request: NgQueryRequest, response: Response, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    # FastAPI runs synchronous endpoints in its worker pool, keeping DB/LLM calls off the event loop.
    history = get_bi_sessions()
    operation = history.begin(x_user_id, request.thread_id, scope('ng-defect-analysis', factory_id=request.factory_id),
                              query=request.query, confirmation=request.confirmation_id, selection=request.resume)
    response.headers['X-BI-Session-ID'] = operation['session_id']
    try:
        result = _invoke(lambda: get_ng_service(request.factory_id).query(request, x_user_id))
        history.finish(operation, result)
        return result
    except Exception as exc:
        failed_operation(history, operation, exc)
        raise


@router.post("/options")
def ng_options(request: NgOptionsRequest, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    return _invoke(lambda: get_ng_service(request.factory_id).options(request, x_user_id))


@router.post("/deep/recommend")
def recommend_ng_fields(request: DeepRecommendRequest, response: Response, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    history = get_bi_sessions()
    operation = history.begin(x_user_id, request.thread_id, scope('ng-defect-analysis', factory_id=request.factory_id),
                              query=request.display_message or '针对当前NG类型进行深度分析', kind='deep_recommend')
    response.headers['X-BI-Session-ID'] = operation['session_id']
    try:
        result = _invoke(lambda: get_ng_service(request.factory_id).deep.recommend(request, x_user_id))
        history.finish(operation, result)
        return result
    except Exception as exc:
        failed_operation(history, operation, exc, '深度分析未完成')
        raise


@router.post("/deep/analyze")
def analyze_ng_fields(request: DeepAnalyzeRequest, response: Response, x_user_id: str = Header(default="anonymous", max_length=200)) -> dict:
    history, operation = _begin_deep_history(request, x_user_id)
    response.headers['X-BI-Session-ID'] = operation['session_id']
    try:
        result = _invoke(lambda: get_ng_service(request.factory_id).deep.analyze(request, x_user_id))
        history.finish(operation, result)
        return result
    except Exception as exc:
        failed_operation(history, operation, exc, '深度分析未完成')
        raise


def _begin_deep_history(request, user):
    history = get_bi_sessions()
    operation = history.begin(user, request.thread_id, scope('ng-defect-analysis', factory_id=request.factory_id), kind='deep_analyze',
                              confirmation=request.plan_id, selection={'target_id': request.target_id, 'feature_ids': request.feature_ids})
    return history, operation


@router.post("/deep/analyze/stream")
def stream_ng_analysis(request: DeepAnalyzeRequest, x_user_id: str = Header(default="anonymous", max_length=200)):
    history, operation = _begin_deep_history(request, x_user_id)
    try:
        service = _invoke(lambda: get_ng_service(request.factory_id).deep)
        prepared = _invoke(lambda: service.prepare_analysis(request, x_user_id))
    except Exception as exc:
        failed_operation(history, operation, exc, '深度分析未完成')
        raise
    def run(progress):
        publish = progress.publish
        last_save = [0.0]
        def save_progress(event):
            publish(event)
            if time.monotonic()-last_save[0] >= 1 or event['stage'] in {'completed', 'failed'}:
                history.update_progress(operation, event)
                last_save[0] = time.monotonic()
        progress.publish = save_progress
        try:
            result = service.run_prepared(prepared, progress)
            history.finish(operation, result)
            return result
        except Exception as exc:
            history.fail(operation, '分析已停止' if isinstance(exc, AnalysisCancelled) else str(exc) if isinstance(exc, NgError) else '深度分析暂时无法完成，请稍后重试', cancelled=isinstance(exc, AnalysisCancelled))
            raise
    return StreamingResponse(analysis_event_stream(run),
                             media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", 'X-BI-Session-ID': operation['session_id']})


@router.post("/deep/validation/list")
def list_ng_validations(request: ValidationListRequest, x_user_id: str = Header(default="anonymous", max_length=200)):
    return _invoke(lambda: {"records": get_ng_service(request.factory_id).deep.validations.list(request.analysis_id,x_user_id,request.thread_id)})


@router.post("/deep/validation/record")
def record_ng_validation(request: ValidationRecordRequest, x_user_id: str = Header(default="anonymous", max_length=200)):
    return _invoke(lambda: get_ng_service(request.factory_id).deep.validations.append(request,x_user_id))


@router.post("/deep/quality/audit")
def ng_quality_audit(request: QualityAuditRequest, x_user_id: str = Header(default="anonymous", max_length=200)):
    return _invoke(lambda: get_ng_service(request.factory_id).deep.validations.quality_audit(request,x_user_id))
