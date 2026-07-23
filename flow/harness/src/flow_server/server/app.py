"""The daemon: a FastAPI app that owns runs and a durable event log.

Design notes that fall straight out of the durable-log model:
  - POST /run returns immediately and the run proceeds as a background task; no pinned
    workers, and a dropped client never abandons a run. `?wait=true` instead blocks and
    returns the run's terminal summary (a Flow-like synchronous response over the same
    endpoint) for callers that want request/response ergonomics.
  - GET /stream?since=N replays the durable log from the cursor, then attaches to the live
    feed — so "catch up after a disconnect" and "watch live" are one code path.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from flow_server import agent
from flow_server.session.store import Session, SessionConfig, SessionStore


class RunRequest(BaseModel):
	message: str


class ResumeRequest(BaseModel):
	answers: dict[str, str]  # pending tool_call_id -> "Approve" | "Deny" | free text


def create_app(store: SessionStore) -> FastAPI:
	app = FastAPI(title="flow_server", version="0.1.0")

	def _get(sid: str) -> Session:
		try:
			return store.get(sid)
		except KeyError:
			raise HTTPException(status_code=404, detail="session not found") from None

	@app.get("/healthz")
	async def healthz():
		return {"ok": True}

	@app.post("/sessions")
	async def create_session(config: SessionConfig):
		try:
			session = store.create(config)
		except ValueError as e:
			raise HTTPException(status_code=400, detail=str(e)) from None
		return {"session_id": session.id, "config": session.config.redacted()}

	@app.get("/sessions/{sid}")
	async def get_session(sid: str):
		session = _get(sid)
		return {
			"session_id": session.id,
			"running": session.is_running,
			"latest_seq": session.log.latest_seq,
			"config": session.config.redacted(),
		}

	@app.post("/sessions/{sid}/run")
	async def run(sid: str, req: RunRequest, wait: bool = False):
		session = _get(sid)
		if session.is_running:
			session.steer(req.message)
			return {"status": "steered"}
		return await _launch(session, agent.run(session, req.message), wait)

	@app.post("/sessions/{sid}/resume")
	async def resume(sid: str, req: ResumeRequest, wait: bool = False):
		session = _get(sid)
		if session.is_running:
			raise HTTPException(status_code=409, detail="run is not paused")
		return await _launch(session, agent.resume(session, req.answers), wait)

	@app.post("/sessions/{sid}/abort")
	async def abort(sid: str):
		session = _get(sid)
		session.abort.set()
		return {"status": "aborting" if session.is_running else "idle"}

	@app.get("/sessions/{sid}/entries")
	async def entries(sid: str, since: int = 0):
		session = _get(sid)
		return {
			"entries": session.log.read_since(since),
			"latest_seq": session.log.latest_seq,
			"running": session.is_running,
		}

	@app.get("/sessions/{sid}/stream")
	async def stream(sid: str, since: int = 0):
		session = _get(sid)
		return StreamingResponse(
			_stream_events(session, since),
			media_type="text/event-stream",
			headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
		)

	return app


async def _launch(session: Session, coro, wait: bool) -> dict:
	"""Fire-and-forget by default; with `wait`, run to completion and return a summary."""
	from_seq = session.log.latest_seq
	if wait:
		await coro
		return _summary(session, from_seq)
	session.run_task = asyncio.create_task(coro)
	return {"status": "started"}


def _summary(session: Session, from_seq: int) -> dict:
	"""Distil this turn's durable entries into a Flow-like result: reason, final text,
	usage totals, and any pending approval calls."""
	text, reason, pending = "", "done", []
	input_tokens = output_tokens = 0
	for row in session.log.read_since(from_seq):
		t = row["type"]
		if t == "assistant_message":
			text = row.get("text") or text
		elif t == "usage":
			input_tokens += row.get("input_tokens", 0)
			output_tokens += row.get("output_tokens", 0)
		elif t == "approval_required":
			pending = row.get("calls", [])
		elif t == "run_ended":
			reason = row.get("reason", "done")
	return {
		"reason": reason,
		"output": text,
		"usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
		"pending": pending,
	}


async def _stream_events(session: Session, since: int) -> AsyncIterator[bytes]:
	q = session.subscribe()
	max_seq = since
	try:
		for row in session.log.read_since(since):  # replay history from the cursor
			max_seq = max(max_seq, row.get("seq", max_seq))
			yield _sse(row)
		if not session.is_running:
			return
		while True:  # then attach to the live feed
			try:
				ev = await asyncio.wait_for(q.get(), timeout=0.5)
			except TimeoutError:
				if not session.is_running:
					break
				continue
			data = ev.model_dump()
			seq = data.get("seq")
			if seq is not None:
				if seq <= max_seq:  # already replayed
					continue
				max_seq = seq
			yield _sse(data)
			if ev.type == "run_ended":
				break
	finally:
		session.unsubscribe(q)


def _sse(data: dict) -> bytes:
	return f"data: {json.dumps(data)}\n\n".encode()
