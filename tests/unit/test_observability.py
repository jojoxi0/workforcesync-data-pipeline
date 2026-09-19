import json
import logging

import httpx
import pytest

from workforcesync.logging import JsonFormatter


def test_structured_log_context():
    record = logging.LogRecord("workforcesync", logging.INFO, "", 0, "pipeline_started", (), None)
    record.context = {"run_id": "abc", "entity": "person", "rows": 3}
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["run_id"] == "abc"
    assert parsed["rows"] == 3
    assert parsed["level"] == "INFO"


def test_prefect_errors_are_sanitized():
    from orchestration.flows import TransientStageError, safe_invoke

    def fail():
        raise httpx.ConnectError("secret-password-in-url")

    with pytest.raises(TransientStageError) as raised:
        safe_invoke(fail)
    assert "secret" not in str(raised.value)


@pytest.mark.parametrize("status,retry", [(503, True), (429, True), (400, False), (401, False)])
def test_retry_policy(status, retry):
    from orchestration.flows import TransientStageError, retry_transient, safe_invoke

    def fail():
        response = httpx.Response(status, request=httpx.Request("GET", "http://source"))
        response.raise_for_status()

    class State:
        def result(self):
            return safe_invoke(fail)

    assert retry_transient(None, None, State()) is retry
    if retry:
        with pytest.raises(TransientStageError):
            safe_invoke(fail)
