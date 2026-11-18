"""Request-local progress callbacks and cooperative cancellation for read queries."""

import threading
import time
import asyncio
import json
import logging

from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from .errors import NgError

logger = logging.getLogger(__name__)


class AnalysisCancelled(Exception):
    pass


class DeepProgress:
    def __init__(self, publish, cancelled=None):
        self.publish = publish
        self.cancelled = cancelled or threading.Event()
        self.started = time.perf_counter()
        self.lock = threading.Lock()
        self.sequence = 0

    def check(self):
        if self.cancelled.is_set():
            raise AnalysisCancelled()

    def emit(self, stage, message, **details):
        self.check()
        with self.lock:
            self.sequence += 1
            self.publish({"stage": stage, "message": message, "sequence": self.sequence,
                          "elapsed_seconds": round(time.perf_counter() - self.started, 2), **details})


async def analysis_event_stream(action):
    """Bound the transport backlog; keep terminal events and cancel new SQL work."""
    queue = asyncio.Queue(maxsize=128)
    loop = asyncio.get_running_loop()
    stopped = threading.Event()

    def enqueue(event):
        if stopped.is_set():
            return
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(event)

    def publish(event):
        if not stopped.is_set():
            loop.call_soon_threadsafe(enqueue, event)

    progress = DeepProgress(lambda data: publish({"type": "progress", "data": data}), stopped)

    async def execute():
        try:
            def run():
                progress.emit("preparing", "分析字段已确认，开始读取数据")
                return action(progress)
            result = await run_in_threadpool(run)
            publish({"type": "result", "data": result})
        except AnalysisCancelled:
            publish({"type": "error", "message": "分析已停止", "status_code": 499})
        except Exception as exc:
            status = exc.status_code if isinstance(exc, NgError) else 500
            message = str(exc) if isinstance(exc, NgError) else "深度分析暂时无法完成，请稍后重试"
            if not isinstance(exc, NgError):
                logger.error("NG deep stream failed (%s)", type(exc).__name__)
            if not stopped.is_set():
                try:
                    progress.emit("failed", message)
                except AnalysisCancelled:
                    pass
            publish({"type": "error", "message": message, "status_code": status})

    worker = asyncio.create_task(execute())
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=5)
            except asyncio.TimeoutError:
                event = {"type": "heartbeat", "elapsed_seconds": round(time.perf_counter() - progress.started, 2)}
            yield json.dumps(jsonable_encoder(event), ensure_ascii=False, allow_nan=False) + "\n"
            if event["type"] in {"result", "error"}:
                break
    finally:
        stopped.set()
        if not worker.done():
            worker.cancel()
        worker.add_done_callback(lambda task: None if task.cancelled() else task.exception())
