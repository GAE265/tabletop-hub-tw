import json
import logging
import sys
import traceback
from contextvars import ContextVar, Token
from logging import LogRecord
from typing import Any

_request_context: ContextVar[tuple[str, str] | None] = ContextVar(
    "request_logging_context", default=None
)


def set_request_context(method: str, path: str) -> Token[tuple[str, str] | None]:
    return _request_context.set((method, path))


def reset_request_context(token: Token[tuple[str, str] | None]) -> None:
    _request_context.reset(token)


class JsonLogFormatter(logging.Formatter):
    """輸出 Cloud Run 可辨識的單行 JSON。"""

    def format(self, record: LogRecord) -> str:
        access_fields = None
        message = record.getMessage()
        if record.name == "uvicorn.access" and len(record.args) == 5:
            _, method, full_path, http_version, status_code = record.args
            path = str(full_path).split("?", 1)[0]
            message = f'"{method} {path} HTTP/{http_version}" {status_code}'
            access_fields = (method, path, http_version, status_code)

        payload: dict[str, Any] = {
            "severity": _severity(record.levelname),
            "message": message,
        }
        if record.name:
            payload["logger"] = record.name

        exception = _exception_from_record(record)
        if exception is not None:
            payload["exception_type"] = type(exception).__name__
            payload["stacktrace"] = "".join(traceback.format_exception(*record.exc_info))

        if hasattr(record, "method"):
            payload["method"] = record.method
        if hasattr(record, "path"):
            payload["path"] = record.path
        if not hasattr(record, "method") or not hasattr(record, "path"):
            request = _request_context.get()
            if request is not None:
                payload.setdefault("method", request[0])
                payload.setdefault("path", request[1])
        if hasattr(record, "context"):
            payload["context"] = record.context
        elif access_fields is not None:
            method, path, http_version, status_code = access_fields
            payload["method"] = method
            payload["path"] = path
            payload["context"] = {"http_version": http_version, "status_code": status_code}

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


class _HandledExceptionFilter(logging.Filter):
    """阻止 Uvicorn 再輸出已由 HTTP exception handler 記錄的例外。"""

    def filter(self, record: LogRecord) -> bool:
        exception = _exception_from_record(record)
        return not bool(getattr(exception, "_app_error_logged", False))


def _exception_from_record(record: LogRecord) -> BaseException | None:
    if not record.exc_info:
        return None
    if isinstance(record.exc_info, tuple):
        return record.exc_info[1]
    if isinstance(record.exc_info, BaseException):
        return record.exc_info
    return sys.exc_info()[1]


def _severity(levelname: str) -> str:
    return {"WARN": "WARNING", "FATAL": "CRITICAL"}.get(levelname, levelname)


def mark_exception_logged(exception: BaseException) -> None:
    """標記 HTTP handler 已記錄的例外，供 Uvicorn 避免第二筆相同 traceback。"""
    try:
        exception._app_error_logged = True  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        pass


def configure_logging() -> None:
    """將應用、Uvicorn 與會往 root 傳遞的標準 logger 設為 JSON 輸出。"""
    current_factory = logging.getLogRecordFactory()
    if not getattr(current_factory, "_request_context_factory", False):

        def contextual_factory(*args: Any, **kwargs: Any) -> LogRecord:
            record = current_factory(*args, **kwargs)
            request = _request_context.get()
            if request is not None:
                record.method, record.path = request
            return record

        contextual_factory._request_context_factory = True  # type: ignore[attr-defined]
        logging.setLogRecordFactory(contextual_factory)

    def make_handler(*, deduplicate_handled_errors: bool = False) -> logging.Handler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonLogFormatter())
        if deduplicate_handled_errors:
            handler.addFilter(_HandledExceptionFilter())
        return handler

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [make_handler()]

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = [make_handler(deduplicate_handled_errors=name == "uvicorn.error")]
        logger.propagate = False
        logger.setLevel(logging.INFO)
