import json
import logging
import pytest

import app as app_module
from backend.utils import StreamResponseAccumulator


@pytest.mark.asyncio
async def test_conversation_stream_retries_and_only_final_response_sent(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    attempts = {"count": 0}

    async def fake_stream_request(request_body, request_headers):
        attempts["count"] += 1
        if attempts["count"] == 1:
            buffer = [
                {"id": "1", "choices": [{"messages": [{"role": "assistant", "content": "Try 1"}]}]}
            ]
            accumulator = StreamResponseAccumulator(assistant_text="Try 1", citations=[])
        else:
            buffer = [
                {"id": "2", "choices": [{"messages": [{"role": "assistant", "content": "Try 2"}]}]}
            ]
            accumulator = StreamResponseAccumulator(assistant_text="Try 2", citations=[{"id": 1}])
        return buffer, accumulator

    monkeypatch.setattr(app_module, "stream_chat_request", fake_stream_request)
    app_module.app_settings.base_settings.retry_max_attempts = 2
    app_module.app_settings.azure_openai.stream = True
    app = app_module.app

    async with app.test_client() as client:
        resp = await client.post(
            "/conversation",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers={"Content-Type": "application/json"},
        )
        body = await resp.get_data(as_text=True)

    # Only the final attempt's buffered events should be returned
    lines = [line for line in body.split("\n") if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["choices"][0]["messages"][0]["content"] == "Try 2"

    # Retry was triggered
    assert attempts["count"] == 2
    assert any("Retrying streaming chat request" in rec.message for rec in caplog.records)
