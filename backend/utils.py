import os
import json
import logging
import requests
import dataclasses

from typing import List, Any, Optional

DEBUG = os.environ.get("DEBUG", "false")
if DEBUG.lower() == "true":
    logging.basicConfig(level=logging.DEBUG)

AZURE_SEARCH_PERMITTED_GROUPS_COLUMN = os.environ.get(
    "AZURE_SEARCH_PERMITTED_GROUPS_COLUMN"
)


def is_citation_debug_enabled() -> bool:
    return os.environ.get("DEBUG", "false").lower() == "true"


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


async def format_as_ndjson(r):
    try:
        async for event in r:
            yield json.dumps(event, cls=JSONEncoder) + "\n"
    except Exception as error:
        logging.exception("Exception while generating response stream: %s", error)
        yield json.dumps({"error": str(error)})


def parse_multi_columns(columns: str) -> list:
    if "|" in columns:
        return columns.split("|")
    else:
        return columns.split(",")


def _normalize_text(text: Optional[str]) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.lower().split())


def _truncate_text(text: str, max_length: int = 160) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3] + "..."


def _extract_citations(payload: Any) -> list:
    if payload is None:
        return []
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return []
    if isinstance(payload, dict):
        citations = payload.get("citations")
        if isinstance(citations, list) and len(citations) > 0:
            return citations
    return []


def _merge_unique_strings(target: list, new_items: list) -> None:
    for item in new_items:
        if isinstance(item, str) and item not in target:
            target.append(item)


def _get_model_extra(obj: Any) -> dict:
    model_extra = getattr(obj, "model_extra", None)
    if isinstance(model_extra, dict):
        return model_extra
    return {}


def get_context_details(obj: Any) -> dict:
    model_extra = _get_model_extra(obj)
    model_extra_keys = sorted(str(key) for key in model_extra.keys())
    extra_context = model_extra.get("context")
    attr_context = getattr(obj, "context", None)

    context = attr_context
    context_source = None

    if extra_context is not None:
        context = extra_context
        context_source = "model_extra"
    elif attr_context is not None:
        context_source = "attribute"

    return {
        "context": context,
        "context_present": context is not None,
        "context_source": context_source,
        "model_extra_keys": model_extra_keys,
    }


def summarize_citations_for_debug(citations: list, limit: int = 3) -> list:
    summaries = []
    for citation in citations[:limit]:
        if not isinstance(citation, dict):
            summaries.append({"type": type(citation).__name__})
            continue
        content = citation.get("content")
        metadata = citation.get("metadata")
        summaries.append(
            {
                "title": citation.get("title"),
                "filepath": citation.get("filepath"),
                "url": citation.get("url"),
                "id": citation.get("id"),
                "chunk_id": citation.get("chunk_id"),
                "content_length": len(content) if isinstance(content, str) else 0,
                "metadata_length": len(metadata) if isinstance(metadata, str) else 0,
            }
        )
    return summaries


def get_citation_gap_stats(citations: list) -> dict:
    missing_title_count = 0
    missing_filepath_count = 0

    for citation in citations:
        if not isinstance(citation, dict):
            missing_title_count += 1
            missing_filepath_count += 1
            continue

        title = citation.get("title")
        filepath = citation.get("filepath")
        if not isinstance(title, str) or not title.strip():
            missing_title_count += 1
        if not isinstance(filepath, str) or not filepath.strip():
            missing_filepath_count += 1

    return {
        "citation_count": len(citations),
        "missing_title_count": missing_title_count,
        "missing_filepath_count": missing_filepath_count,
    }


def build_request_debug_summary(request_body: dict, model_args: dict) -> dict:
    request_messages = request_body.get("messages", [])
    last_user_content = None

    for message in reversed(request_messages):
        if message and message.get("role") == "user":
            last_user_content = message.get("content")
            break

    query_preview = None
    if isinstance(last_user_content, str):
        query_preview = _truncate_text(last_user_content)
    elif isinstance(last_user_content, list):
        parts = []
        for content_item in last_user_content:
            if not isinstance(content_item, dict):
                continue
            if content_item.get("type") == "text" and isinstance(content_item.get("text"), str):
                parts.append(content_item["text"])
            elif content_item.get("type") == "image_url":
                parts.append("[image]")
        query_preview = _truncate_text(" ".join(parts)) if parts else None

    datasource = ((model_args.get("extra_body") or {}).get("data_sources") or [{}])[0]
    parameters = datasource.get("parameters", {})
    history_metadata = request_body.get("history_metadata", {})

    return {
        "conversation_id": request_body.get("conversation_id") or history_metadata.get("conversation_id"),
        "query_preview": query_preview,
        "model": model_args.get("model"),
        "stream": model_args.get("stream"),
        "datasource_type": datasource.get("type"),
        "index_name": parameters.get("index_name"),
        "query_type": parameters.get("query_type"),
        "include_contexts": parameters.get("include_contexts"),
        "fields_mapping": parameters.get("fields_mapping"),
    }


def get_retry_reason(messages: Optional[List[dict]], fallback_phrase: str) -> Optional[str]:
    reasons = []

    if not response_contains_citations(messages):
        reasons.append("missing_citations")
    if response_contains_fallback(messages, fallback_phrase):
        reasons.append("fallback_phrase")

    return "+".join(reasons) if reasons else None


def citation_debug_log(
    event: str,
    *,
    trace_id: Optional[str] = None,
    attempt: Optional[int] = None,
    apim_request_id: Optional[str] = None,
    level: int = logging.DEBUG,
    **details,
) -> None:
    if not is_citation_debug_enabled():
        return

    payload = {"event": event}
    if trace_id is not None:
        payload["trace_id"] = trace_id
    if attempt is not None:
        payload["attempt"] = attempt
    if apim_request_id is not None:
        payload["apim_request_id"] = apim_request_id
    payload.update(details)

    logging.log(level, "CITATION_DEBUG %s", json.dumps(payload, cls=JSONEncoder, sort_keys=True))


def _merge_citations(target: list, new_items: list) -> None:
    for item in new_items:
        if item not in target:
            target.append(item)


def response_contains_citations(messages: Optional[List[dict]]) -> bool:
    """
    Inspect messages (tool/context) for citations.
    """
    if not messages:
        return False

    for message in messages:
        citations: list = []
        if message.get("role") == "tool":
            citations = _extract_citations(message.get("content"))
        elif "context" in message:
            citations = _extract_citations(message.get("context"))

        if citations:
            return True

    return False


def response_contains_fallback(messages: Optional[List[dict]], fallback_phrase: str) -> bool:
    """
    Detect whether the assistant reply matches the configured fallback phrase,
    using case/whitespace-insensitive comparison.
    """
    if not fallback_phrase:
        return False

    normalized_fallback = _normalize_text(fallback_phrase)
    if not normalized_fallback or not messages:
        return False

    assistant_text = ""
    for message in reversed(messages):
        if message.get("role") == "assistant" and isinstance(message.get("content"), str):
            assistant_text = message.get("content")
            break

    return normalized_fallback in _normalize_text(assistant_text)


def should_retry_response(messages: Optional[List[dict]], fallback_phrase: str) -> bool:
    """
    Decide if a response should be retried: retry when no citations are present
    or when the assistant replied with the fallback phrase.
    """
    return get_retry_reason(messages, fallback_phrase) is not None


def extract_assistant_content_and_citations(chat_completion: Any) -> dict:
    """
    Extract assistant text and citations from a non-streaming chat completion response.
    """
    assistant_text = ""
    citations: list = []
    context_details = {
        "context_present": False,
        "context_source": None,
        "model_extra_keys": [],
    }

    try:
        if (
            hasattr(chat_completion, "choices")
            and chat_completion.choices
            and hasattr(chat_completion.choices[0], "message")
        ):
            message = chat_completion.choices[0].message
            assistant_text = getattr(message, "content", "") or ""
            context_details = get_context_details(message)
            _merge_citations(citations, _extract_citations(context_details["context"]))
            if not citations:
                _merge_citations(citations, _extract_citations(getattr(message, "content", None)))
    except Exception as error:
        logging.debug("Failed to extract assistant content/citations: %s", error)

    return {
        "assistant_text": assistant_text,
        "citations": citations,
        "context_details": context_details,
    }


@dataclasses.dataclass
class StreamResponseAccumulator:
    assistant_text: str = ""
    citations: list = dataclasses.field(default_factory=list)
    chunk_count: int = 0
    context_chunk_count: int = 0
    context_sources: list = dataclasses.field(default_factory=list)
    model_extra_keys: list = dataclasses.field(default_factory=list)
    apim_request_id: Optional[str] = None


def accumulate_stream_response(accumulator: StreamResponseAccumulator, completion_chunk: Any) -> StreamResponseAccumulator:
    """
    Update an accumulator with assistant text and citations from a streaming chunk.
    """
    try:
        if hasattr(completion_chunk, "choices") and completion_chunk.choices:
            delta = completion_chunk.choices[0].delta
            if delta:
                accumulator.chunk_count += 1
                chunk_text = getattr(delta, "content", None)
                if chunk_text:
                    accumulator.assistant_text += chunk_text

                context_details = get_context_details(delta)
                if context_details["context_present"]:
                    accumulator.context_chunk_count += 1
                if context_details["context_source"]:
                    _merge_unique_strings(accumulator.context_sources, [context_details["context_source"]])
                _merge_unique_strings(accumulator.model_extra_keys, context_details["model_extra_keys"])
                _merge_citations(accumulator.citations, _extract_citations(context_details["context"]))
    except Exception as error:
        logging.debug("Failed to accumulate stream response: %s", error)

    return accumulator


def fetchUserGroups(userToken, nextLink=None):
    # Recursively fetch group membership
    if nextLink:
        endpoint = nextLink
    else:
        endpoint = "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id"

    headers = {"Authorization": "bearer " + userToken}
    try:
        r = requests.get(endpoint, headers=headers)
        if r.status_code != 200:
            logging.error(f"Error fetching user groups: {r.status_code} {r.text}")
            return []

        r = r.json()
        if "@odata.nextLink" in r:
            nextLinkData = fetchUserGroups(userToken, r["@odata.nextLink"])
            r["value"].extend(nextLinkData)

        return r["value"]
    except Exception as e:
        logging.error(f"Exception in fetchUserGroups: {e}")
        return []


def generateFilterString(userToken):
    # Get list of groups user is a member of
    userGroups = fetchUserGroups(userToken)

    # Construct filter string
    if not userGroups:
        logging.debug("No user groups found")

    group_ids = ", ".join([obj["id"] for obj in userGroups])
    return f"{AZURE_SEARCH_PERMITTED_GROUPS_COLUMN}/any(g:search.in(g, '{group_ids}'))"


def format_non_streaming_response(chatCompletion, history_metadata, apim_request_id):
    response_obj = {
        "id": chatCompletion.id,
        "model": chatCompletion.model,
        "created": chatCompletion.created,
        "object": chatCompletion.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
        "apim-request-id": apim_request_id,
    }

    if len(chatCompletion.choices) > 0:
        message = chatCompletion.choices[0].message
        if message:
            context_details = get_context_details(message)
            if context_details["context_present"]:
                response_obj["choices"][0]["messages"].append(
                    {
                        "role": "tool",
                        "content": json.dumps(context_details["context"]),
                    }
                )
            response_obj["choices"][0]["messages"].append(
                {
                    "role": "assistant",
                    "content": message.content,
                }
            )
            return response_obj

    return {}

def format_stream_response(chatCompletionChunk, history_metadata, apim_request_id):
    response_obj = {
        "id": chatCompletionChunk.id,
        "model": chatCompletionChunk.model,
        "created": chatCompletionChunk.created,
        "object": chatCompletionChunk.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
        "apim-request-id": apim_request_id,
    }

    if len(chatCompletionChunk.choices) > 0:
        delta = chatCompletionChunk.choices[0].delta
        if delta:
            context_details = get_context_details(delta)
            if context_details["context_present"]:
                messageObj = {"role": "tool", "content": json.dumps(context_details["context"])}
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            if delta.tool_calls:
                messageObj = {
                    "role": "tool",
                    "tool_calls": {
                        "id": delta.tool_calls[0].id,
                        "function": {
                            "name" : delta.tool_calls[0].function.name,
                            "arguments": delta.tool_calls[0].function.arguments
                        },
                        "type": delta.tool_calls[0].type
                    }
                }
                if context_details["context_present"]:
                    messageObj["context"] = json.dumps(context_details["context"])
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            else:
                if delta.content:
                    messageObj = {
                        "role": "assistant",
                        "content": delta.content,
                    }
                    response_obj["choices"][0]["messages"].append(messageObj)
                    return response_obj

    return {}


def format_pf_non_streaming_response(
    chatCompletion, history_metadata, response_field_name, citations_field_name, message_uuid=None
):
    if chatCompletion is None:
        logging.error(
            "chatCompletion object is None - Increase PROMPTFLOW_RESPONSE_TIMEOUT parameter"
        )
        return {
            "error": "No response received from promptflow endpoint increase PROMPTFLOW_RESPONSE_TIMEOUT parameter or check the promptflow endpoint."
        }
    if "error" in chatCompletion:
        logging.error(f"Error in promptflow response api: {chatCompletion['error']}")
        return {"error": chatCompletion["error"]}

    logging.debug(f"chatCompletion: {chatCompletion}")
    try:
        messages = []
        if response_field_name in chatCompletion:
            messages.append({
                "role": "assistant",
                "content": chatCompletion[response_field_name] 
            })
        if citations_field_name in chatCompletion:
            citation_content= {"citations": chatCompletion[citations_field_name]}
            messages.append({ 
                "role": "tool",
                "content": json.dumps(citation_content)
            })

        response_obj = {
            "id": chatCompletion["id"],
            "model": "",
            "created": "",
            "object": "",
            "history_metadata": history_metadata,
            "choices": [
                {
                    "messages": messages,
                }
            ]
        }
        return response_obj
    except Exception as e:
        logging.error(f"Exception in format_pf_non_streaming_response: {e}")
        return {}


def convert_to_pf_format(input_json, request_field_name, response_field_name):
    output_json = []
    logging.debug(f"Input json: {input_json}")
    # align the input json to the format expected by promptflow chat flow
    for message in input_json["messages"]:
        if message:
            if message["role"] == "user":
                new_obj = {
                    "inputs": {request_field_name: message["content"]},
                    "outputs": {response_field_name: ""},
                }
                output_json.append(new_obj)
            elif message["role"] == "assistant" and len(output_json) > 0:
                output_json[-1]["outputs"][response_field_name] = message["content"]
    logging.debug(f"PF formatted response: {output_json}")
    return output_json


def comma_separated_string_to_list(s: str) -> List[str]:
    '''
    Split comma-separated values into a list.
    '''
    return s.strip().replace(' ', '').split(',')
