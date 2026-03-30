import copy
import json
import pytest

import app as app_module
from backend.utils import StreamResponseAccumulator


def _response_with_messages(messages):
    return {"choices": [{"messages": messages}]}


@pytest.mark.asyncio
async def test_complete_chat_request_with_retry_success_first_attempt(monkeypatch):
    attempts = {"count": 0}

    async def fake_attempt(request_body, request_headers):
        attempts["count"] += 1
        return _response_with_messages([
            {"role": "tool", "content": json.dumps({"citations": [{"id": 1}]})},
            {"role": "assistant", "content": "Answer"}
        ])

    monkeypatch.setattr(app_module, "_complete_chat_request_attempt", fake_attempt)
    app_module.app_settings.base_settings.retry_max_attempts = 3

    result = await app_module.complete_chat_request_with_retry({}, {})

    assert attempts["count"] == 1
    assert result["choices"][0]["messages"][-1]["content"] == "Answer"


@pytest.mark.asyncio
async def test_complete_chat_request_with_retry_success_third_attempt(monkeypatch):
    attempts = {"count": 0}

    async def fake_attempt(request_body, request_headers):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return _response_with_messages([
                {"role": "assistant", "content": "No data"}
            ])
        return _response_with_messages([
            {"role": "tool", "content": json.dumps({"citations": [{"id": 2}]})},
            {"role": "assistant", "content": "Final"}
        ])

    monkeypatch.setattr(app_module, "_complete_chat_request_attempt", fake_attempt)
    app_module.app_settings.base_settings.retry_max_attempts = 3

    result = await app_module.complete_chat_request_with_retry({}, {})

    assert attempts["count"] == 3
    assert result["choices"][0]["messages"][-1]["content"] == "Final"


@pytest.mark.asyncio
async def test_complete_chat_request_with_retry_failure_after_max(monkeypatch):
    attempts = {"count": 0}

    async def fake_attempt(request_body, request_headers):
        attempts["count"] += 1
        return _response_with_messages([
            {"role": "assistant", "content": "No citations yet"}
        ])

    monkeypatch.setattr(app_module, "_complete_chat_request_attempt", fake_attempt)
    app_module.app_settings.base_settings.retry_max_attempts = 2

    result = await app_module.complete_chat_request_with_retry({}, {})

    assert attempts["count"] == 2
    assert result["choices"][0]["messages"][-1]["content"] == "No citations yet"


@pytest.mark.asyncio
async def test_stream_chat_request_with_retry_success_after_retry(monkeypatch):
    attempts = {"count": 0}

    async def fake_stream_request(request_body, request_headers):
        attempts["count"] += 1
        if attempts["count"] == 1:
            buffer = [
                {"id": "1", "choices": [{"messages": [{"role": "assistant", "content": "Try 1"}]}]}
            ]
            accumulator = StreamResponseAccumulator(assistant_text="Try 1", citations=[], apim_request_id="req-1")
        else:
            buffer = [
                {"id": "2", "choices": [{"messages": [{"role": "assistant", "content": "Try 2"}]}]}
            ]
            accumulator = StreamResponseAccumulator(assistant_text="Try 2", citations=[{"id": 3}], apim_request_id="req-2")
        return buffer, accumulator

    monkeypatch.setattr(app_module, "stream_chat_request", fake_stream_request)
    app_module.app_settings.base_settings.retry_max_attempts = 2

    generator = await app_module.stream_chat_request_with_retry({}, {})
    events = [event async for event in generator]

    assert attempts["count"] == 2
    assert len(events) == 1
    assert events[0]["choices"][0]["messages"][0]["content"] == "Try 2"


@pytest.mark.asyncio
async def test_stream_chat_request_with_retry_failure_after_max(monkeypatch):
    attempts = {"count": 0}

    async def fake_stream_request(request_body, request_headers):
        attempts["count"] += 1
        buffer = [
            {"id": "1", "choices": [{"messages": [{"role": "assistant", "content": "No cite"}]}]}
        ]
        accumulator = StreamResponseAccumulator(assistant_text="No cite", citations=[], apim_request_id="req-1")
        return buffer, accumulator

    monkeypatch.setattr(app_module, "stream_chat_request", fake_stream_request)
    app_module.app_settings.base_settings.retry_max_attempts = 2

    generator = await app_module.stream_chat_request_with_retry({}, {})
    events = [event async for event in generator]

    assert attempts["count"] == 2
    assert len(events) == 1
    assert events[0]["choices"][0]["messages"][0]["content"] == "No cite"
