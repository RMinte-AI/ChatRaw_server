import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from aiohttp import web
from openai import AsyncOpenAI

from backend import main
from backend.module_model_stream import (
    MAX_MODEL_STREAM_EVENT_BYTES,
    MAX_MODEL_STREAM_JSON_DEPTH,
    ModuleModelStreamError,
    iter_sanitized_openai_sse,
    sanitize_openai_stream_chunk,
)


def _chunk(
    delta,
    *,
    finish_reason=None,
    extra=None,
):
    payload = {
        "id": "chatcmpl-safe",
        "object": "chat.completion.chunk",
        "created": 1785000000,
        "model": "safe-model",
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    if extra:
        payload.update(extra)
    return payload


def _event(payload):
    return (
        "data: "
        + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n\n"
    ).encode("utf-8")


async def _source(*chunks):
    for chunk in chunks:
        yield chunk


class ModuleModelStreamTests(unittest.IsolatedAsyncioTestCase):
    async def _collect(self, *chunks):
        return [
            item
            async for item in iter_sanitized_openai_sse(
                _source(*chunks)
            )
        ]

    async def test_text_private_fields_heartbeat_and_empty_are_distinct(self):
        private = {
            "reasoning_content": "PRIVATE_REASONING_SENTINEL",
            "thinking": "PRIVATE_THINKING_SENTINEL",
        }
        output = await self._collect(
            b": vendor-heartbeat\n\n",
            b"data:\n\n",
            _event(_chunk({}, extra={"vendor_trace": "PRIVATE_TRACE"})),
            _event(_chunk({"content": "real"}, extra=private)),
            b"data: [DONE]\n\n",
        )
        self.assertEqual(output[0], b": heartbeat\n\n")
        self.assertEqual(output[1], b": heartbeat\n\n")
        empty = json.loads(output[2][6:-2])
        real = json.loads(output[3][6:-2])
        self.assertEqual(empty["choices"][0]["delta"], {})
        self.assertEqual(
            real["choices"][0]["delta"],
            {"content": "real"},
        )
        rendered = b"".join(output).decode("utf-8")
        self.assertNotIn("PRIVATE_REASONING_SENTINEL", rendered)
        self.assertNotIn("PRIVATE_THINKING_SENTINEL", rendered)
        self.assertNotIn("PRIVATE_TRACE", rendered)
        self.assertEqual(output[-1], b"data: [DONE]\n\n")

        _, empty_progress, _ = sanitize_openai_stream_chunk(
            _chunk({})
        )
        _, text_progress, _ = sanitize_openai_stream_chunk(
            _chunk({"content": "real"})
        )
        self.assertFalse(empty_progress)
        self.assertTrue(text_progress)
        _, tool_name_progress, _ = sanitize_openai_stream_chunk(
            _chunk(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"name": "clock"},
                        }
                    ]
                }
            )
        )
        _, tool_arguments_progress, _ = sanitize_openai_stream_chunk(
            _chunk(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"arguments": "{}"},
                        }
                    ]
                }
            )
        )
        self.assertFalse(tool_name_progress)
        self.assertTrue(tool_arguments_progress)

    async def test_fragmented_tool_name_and_arguments_reassemble(self):
        chunks = [
            _chunk(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "query_",
                                "arguments": '{"plate":"',
                            },
                        }
                    ]
                }
            ),
            _chunk(
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {
                                "name": "exit",
                                "arguments": '苏A12345"}',
                            },
                        }
                    ]
                }
            ),
            _chunk({}, finish_reason="tool_calls"),
            {
                "id": "chatcmpl-safe",
                "object": "chat.completion.chunk",
                "created": 1785000000,
                "model": "safe-model",
                "choices": [],
                "usage": {
                    "prompt_tokens": 8,
                    "completion_tokens": 4,
                    "total_tokens": 12,
                    "vendor_cached_tokens": 99,
                },
            },
        ]
        output = await self._collect(
            *[_event(item) for item in chunks],
            b"data: [DONE]\n\n",
        )
        name = ""
        arguments = ""
        finish_reason = None
        usage = None
        for event in output:
            if not event.startswith(b"data: {"):
                continue
            payload = json.loads(event[6:-2])
            if payload.get("usage") is not None:
                usage = payload["usage"]
            if payload["choices"]:
                finish_reason = (
                    payload["choices"][0]["finish_reason"]
                    or finish_reason
                )
            if not payload["choices"]:
                continue
            for tool_call in payload["choices"][0]["delta"].get(
                "tool_calls",
                [],
            ):
                function = tool_call.get("function", {})
                name += function.get("name", "")
                arguments += function.get("arguments", "")
        self.assertEqual(name, "query_exit")
        self.assertEqual(
            json.loads(arguments),
            {"plate": "苏A12345"},
        )
        self.assertEqual(finish_reason, "tool_calls")
        self.assertEqual(
            usage,
            {
                "prompt_tokens": 8,
                "completion_tokens": 4,
                "total_tokens": 12,
            },
        )

    async def test_openai_client_reassembles_sanitized_tool_deltas(self):
        output = await self._collect(
            b": upstream-heartbeat\n\n",
            _event(
                _chunk(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "query_",
                                    "arguments": '{"plate":"',
                                },
                            }
                        ]
                    }
                )
            ),
            _event(
                _chunk(
                    {
                        "tool_calls": [
                            {
                                "index": 0,
                                "function": {
                                    "name": "exit",
                                    "arguments": '苏A12345"}',
                                },
                            }
                        ]
                    },
                    finish_reason="tool_calls",
                    extra={
                        "usage": {
                            "prompt_tokens": 8,
                            "completion_tokens": 4,
                            "total_tokens": 12,
                        }
                    },
                )
            ),
            b"data: [DONE]\n\n",
        )
        body = b"".join(output)

        def handler(request):
            request_body = json.loads(request.content)
            self.assertTrue(request_body["stream"])
            self.assertEqual(
                request_body["stream_options"],
                {"include_usage": True},
            )
            return httpx.Response(
                200,
                content=body,
                headers={"Content-Type": "text/event-stream"},
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as http_client:
            client = AsyncOpenAI(
                api_key="module-capability-token",
                base_url=(
                    "http://server.test/api/module-capabilities/v1/openai"
                ),
                http_client=http_client,
            )
            stream = await client.chat.completions.create(
                model="agent-runtime",
                messages=[{"role": "user", "content": "safe"}],
                stream=True,
                stream_options={"include_usage": True},
            )
            name = ""
            arguments = ""
            usage = None
            async for chunk in stream:
                if chunk.usage is not None:
                    usage = chunk.usage
                for tool_call in (
                    chunk.choices[0].delta.tool_calls or []
                    if chunk.choices
                    else []
                ):
                    if tool_call.function is not None:
                        name += tool_call.function.name or ""
                        arguments += tool_call.function.arguments or ""
            await client.close()

        self.assertEqual(name, "query_exit")
        self.assertEqual(
            json.loads(arguments),
            {"plate": "苏A12345"},
        )
        self.assertIsNotNone(usage)
        self.assertEqual(usage.total_tokens, 12)

    async def test_slow_heartbeat_and_empty_chunks_do_not_end_stream(self):
        waiting_without_token = asyncio.Event()
        release_next_chunk = asyncio.Event()

        async def delayed_source():
            yield b": heartbeat\n\n"
            waiting_without_token.set()
            await release_next_chunk.wait()
            yield _event(_chunk({}))
            yield _event(_chunk({"content": "still-running"}))
            yield b"data: [DONE]\n\n"

        async def collect():
            return [
                item
                async for item in iter_sanitized_openai_sse(
                    delayed_source()
                )
            ]

        task = asyncio.create_task(collect())
        await asyncio.wait_for(waiting_without_token.wait(), timeout=1)
        await asyncio.sleep(0.05)
        self.assertFalse(task.done())
        release_next_chunk.set()
        output = await asyncio.wait_for(task, timeout=1)
        self.assertIn(b"still-running", b"".join(output))
        self.assertEqual(output[-1], b"data: [DONE]\n\n")

    async def test_malformed_and_oversized_events_fail_closed(self):
        with self.assertRaises(ModuleModelStreamError) as malformed:
            await self._collect(
                b"data: {not-json}\n\n",
            )
        self.assertEqual(
            malformed.exception.code,
            "invalid_model_stream",
        )

        oversized = (
            b"data: "
            + b"x" * MAX_MODEL_STREAM_EVENT_BYTES
            + b"\n\n"
        )
        with self.assertRaises(ModuleModelStreamError) as too_large:
            await self._collect(oversized)
        self.assertEqual(
            too_large.exception.code,
            "model_stream_limit_exceeded",
        )

        with patch(
            "backend.module_model_stream."
            "MAX_MODEL_STREAM_TOOL_DELTA_BYTES",
            5,
        ):
            with self.assertRaises(ModuleModelStreamError) as tool_limit:
                await self._collect(
                    _event(
                        _chunk(
                            {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": "abc"
                                        },
                                    }
                                ]
                            }
                        )
                    ),
                    _event(
                        _chunk(
                            {
                                "tool_calls": [
                                    {
                                        "index": 0,
                                        "function": {
                                            "arguments": "def"
                                        },
                                    }
                                ]
                            }
                        )
                    ),
                )
        self.assertEqual(
            tool_limit.exception.code,
            "model_stream_limit_exceeded",
        )

        with patch(
            "backend.module_model_stream."
            "MAX_MODEL_STREAM_TOTAL_BYTES",
            8,
        ):
            with self.assertRaises(ModuleModelStreamError) as total_limit:
                await self._collect(b": heartbeat\n\n")
        self.assertEqual(
            total_limit.exception.code,
            "model_stream_limit_exceeded",
        )

    async def test_decoder_resource_abuse_and_private_finish_reason_fail_closed(
        self,
    ):
        prefix = (
            b'{"id":"chatcmpl-safe",'
            b'"object":"chat.completion.chunk",'
            b'"created":1785000000,'
            b'"model":"safe-model",'
            b'"choices":[],'
            b'"vendor":'
        )
        hostile_values = [
            b"9" * 5000,
            b"[" * 100_000 + b"0" + b"]" * 100_000,
            b"NaN",
        ]
        for value in hostile_values:
            with self.subTest(value_size=len(value)):
                with self.assertRaises(ModuleModelStreamError) as rejected:
                    await self._collect(
                        b"data: " + prefix + value + b"}\n\n"
                    )
                self.assertEqual(
                    rejected.exception.code,
                    "invalid_model_stream",
                )

        with self.assertRaises(ModuleModelStreamError):
            sanitize_openai_stream_chunk(
                _chunk({}, finish_reason="PRIVATE_VENDOR_FINISH")
            )
        with self.assertRaises(ModuleModelStreamError):
            sanitize_openai_stream_chunk(
                {
                    **_chunk({}),
                    "choices": [
                        {
                            "index": 16,
                            "delta": {},
                            "finish_reason": None,
                        }
                    ],
                }
            )

    async def test_small_unknown_vendor_metadata_is_filtered_but_bounded(self):
        output = await self._collect(
            _event(_chunk({}, extra={"vendor": {"items": [["safe"]]}})),
            b"data: [DONE]\n\n",
        )
        self.assertNotIn("vendor", b"".join(output).decode("utf-8"))

        nested: object = "too-deep"
        for _ in range(MAX_MODEL_STREAM_JSON_DEPTH + 1):
            nested = [nested]
        with self.assertRaises(ModuleModelStreamError) as rejected:
            await self._collect(
                _event(_chunk({}, extra={"vendor": nested})),
                b"data: [DONE]\n\n",
            )
        self.assertEqual(rejected.exception.code, "invalid_model_stream")

    async def test_eof_without_done_is_incomplete(self):
        with self.assertRaises(ModuleModelStreamError) as incomplete:
            await self._collect(_event(_chunk({"content": "partial"})))
        self.assertEqual(
            incomplete.exception.code,
            "model_stream_incomplete",
        )


class ModuleModelStreamTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.disconnected = asyncio.Event()
        self.preheader_started = asyncio.Event()
        self.preheader_disconnected = asyncio.Event()
        self.received_payload = None

        async def stream(request):
            self.received_payload = await request.json()
            response = web.StreamResponse(
                status=200,
                headers={"Content-Type": "text/event-stream"},
            )
            await response.prepare(request)
            await response.write(
                _event(_chunk({"content": "network-delta"}))
            )
            try:
                while True:
                    await asyncio.sleep(0.01)
                    await response.write(b": heartbeat\n\n")
            except (ConnectionResetError, RuntimeError):
                self.disconnected.set()
            return response

        async def fail(_request):
            return web.json_response(
                {"error": "PRIVATE_UPSTREAM_ERROR"},
                status=503,
            )

        async def delay_headers(request):
            await request.json()
            self.preheader_started.set()
            try:
                while (
                    request.transport is not None
                    and not request.transport.is_closing()
                ):
                    await asyncio.sleep(0.01)
            finally:
                self.preheader_disconnected.set()
            return web.Response(status=499)

        app = web.Application()
        app.router.add_post("/chat/completions", stream)
        app.router.add_post("/fail/chat/completions", fail)
        app.router.add_post("/delay/chat/completions", delay_headers)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        sockets = self.site._server.sockets
        self.port = sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await main.close_http_session()
        await self.runner.cleanup()

    @staticmethod
    def _settings():
        return SimpleNamespace(
            chat_settings=SimpleNamespace(top_p=0.9)
        )

    def _config(self, suffix=""):
        return SimpleNamespace(
            api_url=f"http://127.0.0.1:{self.port}{suffix}",
            model_id="fixture-model",
            max_output=4096,
            api_key="PRIVATE_API_KEY_SENTINEL",
            capability=SimpleNamespace(tools=True),
        )

    async def test_real_aiohttp_stream_close_reaches_upstream(self):
        request = {
            "profile": "agent-runtime",
            "messages": [
                {
                    "role": "user",
                    "content": "PRIVATE_PROMPT_SENTINEL",
                }
            ],
            "max_tokens": 128,
            "timeout_seconds": 900,
            "stream_options": {"include_usage": True},
        }
        with patch.object(
            main.db,
            "get_model_by_type",
            return_value=self._config(),
        ), patch.object(
            main.db,
            "get_settings",
            return_value=self._settings(),
        ):
            response = await main._open_module_host_model_chat_stream(
                request
            )
            first = await anext(response.content.iter_any())
            self.assertIn(b"network-delta", first)
            response.close()
            await asyncio.wait_for(
                self.disconnected.wait(),
                timeout=1,
            )
        self.assertTrue(response.closed)
        self.assertTrue(self.received_payload["stream"])
        self.assertEqual(
            self.received_payload["stream_options"],
            {"include_usage": True},
        )
        self.assertEqual(self.received_payload["max_tokens"], 128)
        self.assertEqual(
            self.received_payload["messages"],
            request["messages"],
        )

    async def test_real_upstream_failure_stays_pre_header_error(self):
        request = {
            "profile": "agent-runtime",
            "messages": [{"role": "user", "content": "safe"}],
            "timeout_seconds": 900,
        }
        with patch.object(
            main.db,
            "get_model_by_type",
            return_value=self._config("/fail"),
        ), patch.object(
            main.db,
            "get_settings",
            return_value=self._settings(),
        ):
            with self.assertRaises(main.ModuleTaskError) as failed:
                await main._open_module_host_model_chat_stream(request)
        self.assertEqual(failed.exception.code, "model_request_failed")
        self.assertEqual(failed.exception.status_code, 502)

    async def test_disconnect_before_headers_cancels_real_upstream(self):
        request = {
            "profile": "agent-runtime",
            "messages": [{"role": "user", "content": "safe"}],
            "timeout_seconds": 900,
            "stream_options": {"include_usage": True},
        }

        class DownstreamRequest:
            async def receive(inner_self):
                await self.preheader_started.wait()
                return {"type": "http.disconnect"}

        with patch.object(
            main.db,
            "get_model_by_type",
            return_value=self._config("/delay"),
        ), patch.object(
            main.db,
            "get_settings",
            return_value=self._settings(),
        ):
            response = (
                await main._open_module_host_model_chat_stream_for_request(
                    DownstreamRequest(),
                    request,
                )
            )
            self.assertIsNone(response)
            await asyncio.wait_for(
                self.preheader_disconnected.wait(),
                timeout=1,
            )
