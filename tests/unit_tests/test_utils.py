import pytest
from backend.utils import (
    format_as_ndjson,
    parse_multi_columns,
    response_contains_citations,
    response_contains_fallback,
    should_retry_response,
    extract_assistant_content_and_citations,
    StreamResponseAccumulator,
    accumulate_stream_response
)


@pytest.mark.asyncio
async def test_format_as_ndjson():
    async def dummy_generator():
        yield {"message": "test message\n"}

    async for event in format_as_ndjson(dummy_generator()):
        assert event == '{"message": "test message\\n"}\n'


@pytest.mark.asyncio
async def test_format_as_ndjson_exception():
    async def dummy_generator():
        raise Exception("test exception")
        yield {"message": "test message\n"}
    
    async for event in format_as_ndjson(dummy_generator()):
        assert event == '{"error": "test exception"}'

def test_parse_multi_columns():
    test_pipes = "col1|col2|col3"
    test_commas = "col1,col2,col3"
    test_single = "col1"
    assert parse_multi_columns(test_pipes) == ["col1", "col2", "col3"]
    assert parse_multi_columns(test_commas) == ["col1", "col2", "col3"]
    assert parse_multi_columns(test_single) == ["col1"]


def test_response_contains_citations_in_tool_message():
    messages = [
        {"role": "tool", "content": '{"citations": [{"id": 1}]}'},
        {"role": "assistant", "content": "Here is your answer."}
    ]
    assert response_contains_citations(messages) is True


def test_response_contains_citations_in_context():
    messages = [
        {"role": "assistant", "content": "Here is your answer.", "context": {"citations": [{"id": 1}]}}
    ]
    assert response_contains_citations(messages) is True


def test_response_contains_fallback_phrase_detects_variations():
    messages = [{"role": "assistant", "content": "  The requested information is not available   in the retrieved data.  "}]
    assert response_contains_fallback(messages, "the requested information is not available in the retrieved data.") is True


def test_should_retry_without_citations():
    messages = [{"role": "assistant", "content": "No citations here."}]
    assert should_retry_response(messages, "fallback phrase") is True


def test_should_retry_on_fallback_even_with_citations():
    messages = [
        {"role": "tool", "content": '{"citations": [{"id": 1}]}'},
        {"role": "assistant", "content": "The requested information is not available in the retrieved data. Please try another query or topic."}
    ]
    assert should_retry_response(messages, "the requested information is not available in the retrieved data.") is True


def test_should_not_retry_when_citations_and_no_fallback():
    messages = [
        {"role": "tool", "content": '{"citations": [{"id": 1}]}'},
        {"role": "assistant", "content": "Valid answer"}
    ]
    assert should_retry_response(messages, "the requested information is not available in the retrieved data.") is False


def test_extract_assistant_content_and_citations_handles_context():
    class DummyMessage:
        def __init__(self):
            self.content = "Answer text"
            self.context = {"citations": [{"id": 2}]}

    class DummyChoice:
        def __init__(self):
            self.message = DummyMessage()

    class DummyChatCompletion:
        def __init__(self):
            self.choices = [DummyChoice()]

    result = extract_assistant_content_and_citations(DummyChatCompletion())
    assert result["assistant_text"] == "Answer text"
    assert result["citations"] == [{"id": 2}]


def test_accumulate_stream_response_collects_text_and_citations():
    class DummyDelta:
        def __init__(self, content=None, context=None):
            self.content = content
            self.context = context
            self.tool_calls = None

    class DummyChoice:
        def __init__(self, delta):
            self.delta = delta

    class DummyChunk:
        def __init__(self, delta):
            self.choices = [DummyChoice(delta)]

    acc = StreamResponseAccumulator()
    acc = accumulate_stream_response(acc, DummyChunk(DummyDelta(content="Hello ")))
    acc = accumulate_stream_response(acc, DummyChunk(DummyDelta(content="world!", context={"citations": [{"id": 3}]})))

    assert acc.assistant_text == "Hello world!"
    assert acc.citations == [{"id": 3}]
