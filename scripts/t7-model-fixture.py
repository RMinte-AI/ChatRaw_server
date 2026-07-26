#!/usr/bin/env python3
"""Deterministic OpenAI-compatible model fixture for Agent T7 acceptance."""

from __future__ import annotations

import argparse
import json
import re
import signal
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _text_content(value) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return ""
    return "\n".join(
        item.get("text", "")
        for item in value
        if isinstance(item, dict) and isinstance(item.get("text"), str)
    )


class ModelHandler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload) -> None:
        raw = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self._json(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json(400, {"error": "invalid_json"})
            return
        messages = payload.get("messages")
        tools = payload.get("tools", [])
        if not isinstance(messages, list) or not isinstance(tools, list):
            self._json(400, {"error": "invalid_request"})
            return
        transcript = "\n".join(
            _text_content(item.get("content"))
            for item in messages
            if isinstance(item, dict)
        )
        last_user = next(
            (
                _text_content(item.get("content"))
                for item in reversed(messages)
                if isinstance(item, dict) and item.get("role") == "user"
            ),
            "",
        )
        tool_names = {
            item.get("function", {}).get("name")
            for item in tools
            if isinstance(item, dict)
            and isinstance(item.get("function"), dict)
        }
        has_tool_result = any(
            isinstance(item, dict) and item.get("role") == "tool"
            for item in messages
        )
        plate_match = re.search(r"苏A\d{5}", transcript)
        plate = plate_match.group(0) if plate_match else "苏A12345"
        if (
            "docx_create" in tool_names
            and "T7_CREATE_DOCX_ARTIFACT" in last_user
            and not has_tool_result
        ):
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": {
                            "name": "docx_create",
                            "arguments": json.dumps(
                                {
                                    "markdown": (
                                        "# T7 报告\n\n"
                                        "Office artifact chain."
                                    ),
                                    "output_filename": "t7-report.docx",
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    }
                ],
            }
            finish_reason = "tool_calls"
        elif (
            "query_exit_transaction" in tool_names
            and "出口流水" in last_user
            and not has_tool_result
        ):
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call_{uuid.uuid4().hex}",
                        "type": "function",
                        "function": {
                            "name": "query_exit_transaction",
                            "arguments": json.dumps(
                                {
                                    "start_time": "2026-07-02 00:00:00",
                                    "end_time": "2026-07-03 00:00:00",
                                    "plate_number": plate,
                                    "plate_color": "蓝牌",
                                    "page_number": 1,
                                    "page_size": 20,
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        },
                    }
                ],
            }
            finish_reason = "tool_calls"
        elif "总金额" in last_user and "12.5" in transcript:
            message = {
                "role": "assistant",
                "content": "上一轮两条流水总金额为 30.5 元。",
            }
            finish_reason = "stop"
        elif (
            has_tool_result
            and "T7_CREATE_DOCX_ARTIFACT" in transcript
        ):
            message = {
                "role": "assistant",
                "content": "T7 DOCX artifact created.",
            }
            finish_reason = "stop"
        elif has_tool_result:
            message = {
                "role": "assistant",
                "content": (
                    f"{plate} 查询成功：第一条金额 12.5 元，"
                    "第二条金额 18.0 元。"
                ),
            }
            finish_reason = "stop"
        else:
            message = {
                "role": "assistant",
                "content": "T7 deterministic model response.",
            }
            finish_reason = "stop"
        response_payload = {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model", "t7-model"),
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 32,
                "completion_tokens": 16,
                "total_tokens": 48,
            },
        }
        if payload.get("stream") is True and isinstance(
            message.get("content"), str
        ):
            chunks = [
                {
                    "id": response_payload["id"],
                    "object": "chat.completion.chunk",
                    "created": response_payload["created"],
                    "model": response_payload["model"],
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": message["content"]},
                            "finish_reason": None,
                        }
                    ],
                },
                {
                    "id": response_payload["id"],
                    "object": "chat.completion.chunk",
                    "created": response_payload["created"],
                    "model": response_payload["model"],
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                },
            ]
            body = "".join(
                f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                for chunk in chunks
            ) + "data: [DONE]\n\n"
            raw = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self._json(
            200,
            response_payload,
        )

    def log_message(self, _format, *_args):
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    arguments = parser.parse_args()
    server = ThreadingHTTPServer(
        (arguments.host, arguments.port),
        ModelHandler,
    )

    def stop(_signum, _frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
