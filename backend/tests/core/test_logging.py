import json
import logging
import sys

import pytest
from fastapi.testclient import TestClient

from app.core.logging import JsonLogFormatter


def test_formatter_emits_one_line_json_with_severity_and_message() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord("sample", logging.INFO, "", 0, "ready %s", ("now",), None)

    output = formatter.format(record)

    assert "\n" not in output
    assert json.loads(output) == {
        "severity": "INFO",
        "message": "ready now",
        "logger": "sample",
    }


def test_formatter_preserves_exception_chain_in_one_json_record() -> None:
    formatter = JsonLogFormatter()
    try:
        try:
            raise ValueError("inner failure")
        except ValueError as exc:
            raise RuntimeError("outer failure") from exc
    except RuntimeError:
        record = logging.LogRecord("sample", logging.ERROR, "", 0, "request failed", (), None)
        record.exc_info = sys.exc_info()

    payload = json.loads(formatter.format(record))

    assert payload["severity"] == "ERROR"
    assert payload["exception_type"] == "RuntimeError"
    assert "ValueError: inner failure" in payload["stacktrace"]
    assert "The above exception was the direct cause" in payload["stacktrace"]
    assert payload["stacktrace"].count("Traceback (most recent call last):") == 2
    assert "\n" in payload["stacktrace"]


def test_formatter_includes_context_when_present() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord("sample", logging.WARNING, "", 0, "slow", (), None)
    record.context = {"elapsed_ms": 123}

    payload = json.loads(formatter.format(record))

    assert payload["severity"] == "WARNING"
    assert payload["context"] == {"elapsed_ms": 123}


def test_unhandled_request_log_contains_http_fields_and_json(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger="app.core.errors")

    response = client.get("/_probe/boom")

    assert response.status_code == 500
    records = [record for record in caplog.records if record.name == "app.core.errors"]
    assert len(records) == 1
    assert records[0].method == "GET"
    assert records[0].path == "/_probe/boom"
    payload = json.loads(JsonLogFormatter().format(records[0]))
    assert payload["severity"] == "ERROR"
    assert payload["exception_type"] == "RuntimeError"
    assert "super-secret-internal-detail" in payload["stacktrace"]
    assert "\n" not in JsonLogFormatter().format(records[0])


def test_formatter_handles_warning_and_error_severity() -> None:
    formatter = JsonLogFormatter()
    warning = logging.LogRecord("sample", logging.WARNING, "", 0, "warn", (), None)
    error = logging.LogRecord("sample", logging.ERROR, "", 0, "error", (), None)

    assert json.loads(formatter.format(warning))["severity"] == "WARNING"
    assert json.loads(formatter.format(error))["severity"] == "ERROR"


def test_uvicorn_uses_json_handler_and_deduplicates_handled_exceptions() -> None:
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_access = logging.getLogger("uvicorn.access")

    assert uvicorn_error.handlers
    assert uvicorn_access.handlers
    assert isinstance(uvicorn_error.handlers[0].formatter, JsonLogFormatter)
    assert isinstance(uvicorn_access.handlers[0].formatter, JsonLogFormatter)
    exception = RuntimeError("already logged")
    exception._app_error_logged = True
    record = logging.LogRecord("uvicorn.error", logging.ERROR, "", 0, "failure", (), None)
    record.exc_info = (RuntimeError, exception, None)

    assert not uvicorn_error.handlers[0].filter(record)


def test_uvicorn_access_log_does_not_emit_query_parameters() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/api/games?token=secret", "1.1", 200),
        None,
    )

    output = JsonLogFormatter().format(record)
    payload = json.loads(output)

    assert "secret" not in output
    assert payload["path"] == "/api/games"
    assert payload["method"] == "GET"
    assert payload["context"]["status_code"] == 200


def test_request_logs_include_method_and_path(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR, logger="app.dev.router")

    response = client.post("/api/v1/dev/error-logs/9")

    assert response.status_code == 500
    record = next(record for record in caplog.records if record.name == "app.dev.router")
    assert record.method == "POST"
    assert record.path == "/api/v1/dev/error-logs/9"
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["method"] == "POST"
    assert payload["path"] == "/api/v1/dev/error-logs/9"
