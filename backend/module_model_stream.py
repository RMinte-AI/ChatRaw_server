"""Bounded OpenAI-compatible SSE parsing for module model capabilities."""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any


MAX_MODEL_STREAM_EVENT_BYTES = 256 * 1024
MAX_MODEL_STREAM_TOOL_DELTA_BYTES = 2 * 1024 * 1024
MAX_MODEL_STREAM_TOTAL_BYTES = 16 * 1024 * 1024
MAX_MODEL_STREAM_CHOICES = 16
MAX_MODEL_STREAM_TOOL_CALLS = 128
MAX_MODEL_STREAM_USAGE_TOKENS = 1_000_000_000
MAX_MODEL_STREAM_TIMESTAMP = (1 << 63) - 1
STANDARD_FINISH_REASONS = {
    "stop",
    "length",
    "tool_calls",
    "content_filter",
    "function_call",
}


class ModuleModelStreamError(RuntimeError):
    def __init__(self, code: str, public_message: str):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def _invalid_stream() -> ModuleModelStreamError:
    return ModuleModelStreamError(
        "invalid_model_stream",
        "Model returned an invalid stream",
    )


def _reject_json_constant(_value: str) -> None:
    raise ValueError


def _bounded_string(value: Any, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value.encode("utf-8")) > maximum:
        raise _invalid_stream()
    return value


def _sanitize_tool_function(
    function: Any,
) -> tuple[dict[str, str], bool, int]:
    if not isinstance(function, dict):
        raise _invalid_stream()
    safe: dict[str, str] = {}
    has_generation_delta = False
    encoded_bytes = 0
    for field in ("name", "arguments"):
        if field not in function:
            continue
        value = _bounded_string(
            function[field],
            maximum=MAX_MODEL_STREAM_TOOL_DELTA_BYTES,
        )
        safe[field] = value
        encoded_bytes += len(value.encode("utf-8"))
        if field == "arguments" and value:
            has_generation_delta = True
    return safe, has_generation_delta, encoded_bytes


def _sanitize_tool_call(
    tool_call: Any,
) -> tuple[dict[str, Any], bool, int]:
    if not isinstance(tool_call, dict):
        raise _invalid_stream()
    tool_index = tool_call.get("index")
    if (
        not isinstance(tool_index, int)
        or isinstance(tool_index, bool)
        or not 0 <= tool_index < MAX_MODEL_STREAM_TOOL_CALLS
    ):
        raise _invalid_stream()
    safe: dict[str, Any] = {"index": tool_index}
    if "id" in tool_call:
        safe["id"] = _bounded_string(tool_call["id"], maximum=512)
    if "type" in tool_call:
        tool_type = _bounded_string(tool_call["type"], maximum=32)
        if tool_type != "function":
            raise _invalid_stream()
        safe["type"] = tool_type
    if "function" not in tool_call:
        return safe, False, 0
    function, has_progress, encoded_bytes = _sanitize_tool_function(
        tool_call["function"]
    )
    safe["function"] = function
    return safe, has_progress, encoded_bytes


def _sanitize_delta(
    delta: Any,
) -> tuple[dict[str, Any], bool, int]:
    if not isinstance(delta, dict):
        raise _invalid_stream()
    safe: dict[str, Any] = {}
    has_generation_delta = False
    tool_delta_bytes = 0
    if "role" in delta:
        role = _bounded_string(delta["role"], maximum=32)
        if role != "assistant":
            raise _invalid_stream()
        safe["role"] = role
    if "content" in delta:
        content = delta["content"]
        if content is not None and not isinstance(content, str):
            raise _invalid_stream()
        safe["content"] = content
        has_generation_delta = bool(content)
    if "tool_calls" not in delta:
        return safe, has_generation_delta, tool_delta_bytes

    tool_calls = delta["tool_calls"]
    if (
        not isinstance(tool_calls, list)
        or len(tool_calls) > MAX_MODEL_STREAM_TOOL_CALLS
    ):
        raise _invalid_stream()
    safe_tool_calls = []
    for tool_call in tool_calls:
        safe_call, call_progress, call_bytes = _sanitize_tool_call(tool_call)
        safe_tool_calls.append(safe_call)
        has_generation_delta = has_generation_delta or call_progress
        tool_delta_bytes += call_bytes
    safe["tool_calls"] = safe_tool_calls
    return safe, has_generation_delta, tool_delta_bytes


def _sanitize_choice(
    choice: Any,
) -> tuple[dict[str, Any], bool, int]:
    if not isinstance(choice, dict):
        raise _invalid_stream()
    index = choice.get("index")
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or not 0 <= index < MAX_MODEL_STREAM_CHOICES
    ):
        raise _invalid_stream()
    finish_reason = choice.get("finish_reason")
    if finish_reason is not None:
        finish_reason = _bounded_string(finish_reason, maximum=128)
        if finish_reason not in STANDARD_FINISH_REASONS:
            raise _invalid_stream()
    safe_delta, has_progress, tool_bytes = _sanitize_delta(
        choice.get("delta")
    )
    return (
        {
            "index": index,
            "delta": safe_delta,
            "finish_reason": finish_reason,
        },
        has_progress,
        tool_bytes,
    )


def _sanitize_usage(usage: Any) -> dict[str, int]:
    if not isinstance(usage, dict):
        raise _invalid_stream()
    safe: dict[str, int] = {}
    for field in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    ):
        if field not in usage:
            continue
        value = usage[field]
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= MAX_MODEL_STREAM_USAGE_TOKENS
        ):
            raise _invalid_stream()
        safe[field] = value
    return safe


def sanitize_openai_stream_chunk(
    payload: Any,
) -> tuple[dict[str, Any], bool, int]:
    """Return a safe OpenAI chunk, real-progress flag, and tool delta bytes."""
    if not isinstance(payload, dict):
        raise _invalid_stream()
    chunk_id = _bounded_string(payload.get("id"), maximum=512)
    if payload.get("object") != "chat.completion.chunk":
        raise _invalid_stream()
    created = payload.get("created")
    if (
        not isinstance(created, int)
        or isinstance(created, bool)
        or not 0 <= created <= MAX_MODEL_STREAM_TIMESTAMP
    ):
        raise _invalid_stream()
    model = _bounded_string(payload.get("model"), maximum=512)
    choices = payload.get("choices")
    if (
        not isinstance(choices, list)
        or len(choices) > MAX_MODEL_STREAM_CHOICES
    ):
        raise _invalid_stream()

    safe_choices = []
    has_generation_delta = False
    tool_delta_bytes = 0
    for choice in choices:
        safe_choice, choice_progress, choice_bytes = _sanitize_choice(choice)
        safe_choices.append(safe_choice)
        has_generation_delta = has_generation_delta or choice_progress
        tool_delta_bytes += choice_bytes

    safe: dict[str, Any] = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": safe_choices,
    }
    if payload.get("usage") is not None:
        safe["usage"] = _sanitize_usage(payload["usage"])
    return safe, has_generation_delta, tool_delta_bytes


def encode_openai_stream_error(
    code: str,
    message: str,
) -> bytes:
    payload = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    return (
        "data: "
        + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n\n"
    ).encode("utf-8")


def _extract_sse_data(
    lines: list[bytes],
) -> tuple[bytes, bool, bool]:
    data_lines: list[bytes] = []
    heartbeat = False
    for line in lines:
        if line.startswith(b":"):
            heartbeat = True
            continue
        if line == b"data" or line.startswith(b"data:"):
            value = line[5:] if line.startswith(b"data:") else b""
            if value.startswith(b" "):
                value = value[1:]
            data_lines.append(value)
            continue
        if line.startswith((b"event:", b"id:", b"retry:")):
            continue
        raise _invalid_stream()
    return b"\n".join(data_lines), bool(data_lines), heartbeat


def _sanitize_sse_event(
    lines: list[bytes],
) -> tuple[bytes | None, bool, int]:
    raw_data, has_data, heartbeat = _extract_sse_data(lines)
    if not has_data:
        return (b": heartbeat\n\n" if heartbeat else None), False, 0
    if not raw_data:
        return b": heartbeat\n\n", False, 0
    if raw_data == b"[DONE]":
        return b"data: [DONE]\n\n", True, 0
    try:
        payload = json.loads(
            raw_data.decode("utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ):
        raise _invalid_stream() from None
    safe, _has_progress, tool_bytes = sanitize_openai_stream_chunk(payload)
    encoded = json.dumps(
        safe,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return b"data: " + encoded + b"\n\n", False, tool_bytes


def _validated_stream_chunk(
    chunk: Any,
    total_bytes: int,
) -> tuple[bytes, int]:
    if not isinstance(chunk, (bytes, bytearray)):
        raise _invalid_stream()
    total_bytes += len(chunk)
    if total_bytes > MAX_MODEL_STREAM_TOTAL_BYTES:
        raise ModuleModelStreamError(
            "model_stream_limit_exceeded",
            "Model stream exceeds the size limit",
        )
    return bytes(chunk), total_bytes


async def iter_sanitized_openai_sse(
    source: AsyncIterable[bytes],
) -> AsyncIterator[bytes]:
    """Parse upstream SSE and emit only bounded, normalized OpenAI events."""
    buffer = b""
    event_lines: list[bytes] = []
    event_bytes = 0
    total_bytes = 0
    cumulative_tool_delta_bytes = 0

    async for chunk in source:
        validated_chunk, total_bytes = _validated_stream_chunk(
            chunk,
            total_bytes,
        )
        buffer += validated_chunk
        while b"\n" in buffer:
            raw_line, buffer = buffer.split(b"\n", 1)
            line = raw_line[:-1] if raw_line.endswith(b"\r") else raw_line
            if line:
                event_bytes += len(raw_line) + 1
                if event_bytes > MAX_MODEL_STREAM_EVENT_BYTES:
                    raise ModuleModelStreamError(
                        "model_stream_limit_exceeded",
                        "Model stream event exceeds the size limit",
                    )
                event_lines.append(line)
                continue
            if event_lines:
                encoded, done, tool_bytes = _sanitize_sse_event(
                    event_lines
                )
                cumulative_tool_delta_bytes += tool_bytes
                if (
                    cumulative_tool_delta_bytes
                    > MAX_MODEL_STREAM_TOOL_DELTA_BYTES
                ):
                    raise ModuleModelStreamError(
                        "model_stream_limit_exceeded",
                        "Model stream exceeds the size limit",
                    )
                if encoded is not None:
                    yield encoded
                event_lines = []
                event_bytes = 0
                if done:
                    return
        if (
            len(buffer) + event_bytes
            > MAX_MODEL_STREAM_EVENT_BYTES
        ):
            raise ModuleModelStreamError(
                "model_stream_limit_exceeded",
                "Model stream event exceeds the size limit",
            )
    raise ModuleModelStreamError(
        "model_stream_incomplete",
        "Model stream ended before completion",
    )
