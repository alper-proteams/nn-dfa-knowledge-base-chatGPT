import pytest
from backend.utils import (
    build_request_debug_summary,
    format_as_ndjson,
    get_retry_reason,
    parse_multi_columns,
    response_contains_citations,
    response_contains_fallback,
    summarize_citations_for_debug,
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


def test_get_retry_reason_reports_missing_citations():
    messages = [{"role": "assistant", "content": "No citations here."}]
    assert get_retry_reason(messages, "fallback phrase") == "missing_citations"


def test_get_retry_reason_reports_combined_reason():
    messages = [
        {"role": "assistant", "content": "The requested information is not available in the retrieved data. Please try another query or topic."}
    ]
    assert get_retry_reason(messages, "the requested information is not available in the retrieved data.") == "missing_citations+fallback_phrase"


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


def test_extract_assistant_content_and_citations_handles_model_extra_context():
    class DummyMessage:
        def __init__(self):
            self.content = "Answer text"
            self.model_extra = {"context": {"citations": [{"id": 4}]}}

    class DummyChoice:
        def __init__(self):
            self.message = DummyMessage()

    class DummyChatCompletion:
        def __init__(self):
            self.choices = [DummyChoice()]

    result = extract_assistant_content_and_citations(DummyChatCompletion())
    assert result["assistant_text"] == "Answer text"
    assert result["citations"] == [{"id": 4}]
    assert result["context_details"]["context_source"] == "model_extra"


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


def test_accumulate_stream_response_collects_model_extra_context():
    class DummyDelta:
        def __init__(self, content=None, model_extra=None):
            self.content = content
            self.model_extra = model_extra or {}
            self.tool_calls = None

    class DummyChoice:
        def __init__(self, delta):
            self.delta = delta

    class DummyChunk:
        def __init__(self, delta):
            self.choices = [DummyChoice(delta)]

    acc = StreamResponseAccumulator()
    acc = accumulate_stream_response(
        acc,
        DummyChunk(DummyDelta(content="world!", model_extra={"context": {"citations": [{"id": 5}]}})),
    )

    assert acc.assistant_text == "world!"
    assert acc.citations == [{"id": 5}]
    assert acc.context_sources == ["model_extra"]
    assert acc.model_extra_keys == ["context"]


def test_build_request_debug_summary_redacts_by_shape():
    request_body = {
        "conversation_id": "conv-1",
        "messages": [{"role": "user", "content": "What is FPG?"}],
    }
    model_args = {
        "model": "gpt-4.1",
        "stream": True,
        "extra_body": {
            "data_sources": [
                {
                    "type": "azure_search",
                    "parameters": {
                        "index_name": "index-v1",
                        "query_type": "semantic",
                        "include_contexts": ["citations", "intent"],
                        "fields_mapping": {"title_field": "title", "filepath_field": "title"},
                        "authentication": {"key": "secret"},
                    },
                }
            ]
        },
    }

    summary = build_request_debug_summary(request_body, model_args)

    assert summary["conversation_id"] == "conv-1"
    assert summary["query_preview"] == "What is FPG?"
    assert summary["fields_mapping"] == {"title_field": "title", "filepath_field": "title"}
    assert "authentication" not in summary
    assert "secret" not in str(summary)


def test_summarize_citations_for_debug_excludes_full_content():
    citations = [
        {
            "title": "WB710",
            "filepath": "WB710",
            "url": "123",
            "id": "abc",
            "chunk_id": "0",
            "content": "Very long secret content",
            "metadata": "{\"foo\": \"bar\"}",
        }
    ]

    summary = summarize_citations_for_debug(citations)

    assert summary == [
        {
            "title": "WB710",
            "filepath": "WB710",
            "url": "123",
            "id": "abc",
            "chunk_id": "0",
            "content_length": 24,
            "metadata_length": 14,
        }
    ]
