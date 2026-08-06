#!/usr/bin/env python3
"""Minimal local Hermes Runs server for isolated browser acceptance."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


app = FastAPI(title="ChatRaw acceptance Hermes")
_runs: dict[str, asyncio.Event] = {}


class ApprovalRequest(BaseModel):
    choice: str
    resolve_all: bool = False


@app.get("/v1/acceptance/runs")
async def acceptance_runs() -> dict[str, list[str]]:
    return {"run_ids": list(_runs)}


@app.post("/v1/runs")
async def create_run() -> dict[str, str]:
    run_id = f"acceptance-{uuid.uuid4()}"
    _runs[run_id] = asyncio.Event()
    return {"run_id": run_id}


@app.get("/v1/runs/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    approval = _runs.get(run_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def stream():
        yield 'event: tool.started\ndata: {"tool_name":"acceptance.check","message":"Checking the isolated browser flow"}\n\n'
        yield 'event: approval.request\ndata: {"approval":{"command":"acceptance.check","description":"Allow this isolated acceptance action","pattern_keys":["acceptance:check"]}}\n\n'
        try:
            await asyncio.wait_for(approval.wait(), timeout=600)
        except TimeoutError:
            yield 'event: run.failed\ndata: {"error":"approval timed out"}\n\n'
        else:
            yield 'event: approval.responded\ndata: {"choice":"once","resolved":1}\n\n'
            yield 'event: message.delta\ndata: {"delta":"Hermes approval completed."}\n\n'
            yield 'event: run.completed\ndata: {}\n\n'
        finally:
            _runs.pop(run_id, None)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/v1/runs/{run_id}/approval")
async def approve_run(run_id: str, body: ApprovalRequest) -> dict[str, str]:
    approval = _runs.get(run_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="run not found")
    if body.choice not in {"once", "session", "deny"}:
        raise HTTPException(status_code=400, detail="invalid choice")
    approval.set()
    return {"status": "running", "choice": body.choice}


@app.post("/v1/runs/{run_id}/stop")
async def stop_run(run_id: str) -> dict[str, str]:
    approval = _runs.pop(run_id, None)
    if approval is not None:
        approval.set()
    return {"status": "stopped"}
