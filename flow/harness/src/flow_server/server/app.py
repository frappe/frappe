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
import secrets
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from flow_server import agent
from flow_server.events import AssistantMessage, parse_event
from flow_server.session.log import SessionLogError
from flow_server.session.store import (
	Session,
	SessionConfig,
	SessionState,
	SessionStore,
	pending_approval,
)


class RunRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	message: str
	# A turn may switch the model or select another stored credential. Provider secrets
	# and endpoints are resolved inside flow_server and are never run inputs.
	model: str | None = None
	credential_id: str | None = None


class ResumeRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	approval_seq: int
	answers: dict[str, str]  # pending tool_call_id -> "Approve" | "Deny" | free text


def create_app(store: SessionStore, *, auth_token: str | None = None) -> FastAPI:
	app = FastAPI(title="flow_server", version="0.1.0")

	if auth_token:

		@app.middleware("http")
		async def authenticate(request: Request, call_next):
			if request.url.path == "/healthz":
				return await call_next(request)
			scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
			if scheme.lower() != "bearer" or not secrets.compare_digest(supplied, auth_token):
				return JSONResponse({"detail": "unauthorized"}, status_code=401)
			return await call_next(request)

	def _get(sid: str) -> Session:
		try:
			return store.get(sid)
		except KeyError:
			raise HTTPException(status_code=404, detail="session not found") from None
		except SessionLogError as e:
			# the request is well formed; the stored log is not. Report where, but never
			# the on-disk path.
			raise HTTPException(
				status_code=500,
				detail={
					"error": "session_log_corrupt",
					"session_id": sid,
					"line": e.line,
					"offset": e.offset,
					"reason": e.reason,
				},
			) from None

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
			"state": session.state,
			"running": session.is_running,
			"latest_seq": session.log.latest_seq,
			"config": session.config.redacted(),
		}

	@app.post("/sessions/{sid}/run")
	async def run(sid: str, req: RunRequest, wait: bool = False):
		session = _get(sid)
		async with session.operation_lock:
			if session.state is SessionState.PAUSED:
				raise HTTPException(
					status_code=409,
					detail="run is paused for approval; resolve it with /resume",
				)
			_apply_overrides(store, session, req)
			if session.state is SessionState.RUNNING:
				if not session.steer(req.message):
					raise HTTPException(status_code=409, detail="run is aborting")
				return {"status": "steered"}
			from_seq = session.log.latest_seq
			task = session._start_operation(agent.run(session, req.message))
		return await _launch(session, task, from_seq, wait)

	@app.post("/sessions/{sid}/resume")
	async def resume(sid: str, req: ResumeRequest, wait: bool = False):
		session = _get(sid)
		async with session.operation_lock:
			if session.state is not SessionState.PAUSED:
				raise HTTPException(status_code=409, detail="run is not paused")
			approval = pending_approval(session.log)
			try:
				agent.validate_resume(approval, req.approval_seq, req.answers)
			except agent.ResumeError as e:
				raise HTTPException(status_code=409, detail=str(e)) from None
			from_seq = session.log.latest_seq
			task = session._start_operation(
				agent.resume(
					session,
					req.answers,
					approval_seq=req.approval_seq,
				)
			)
		return await _launch(session, task, from_seq, wait)

	@app.post("/sessions/{sid}/abort")
	async def abort(sid: str):
		session = _get(sid)
		async with session.operation_lock:
			if not session.is_running:
				return {"status": session.state}
			session.request_abort()
			return {"status": "aborting"}

	@app.get("/sessions/{sid}/entries")
	async def entries(sid: str, since: int = 0):
		session = _get(sid)
		return {
			"entries": session.log.read_since(since),
			"latest_seq": session.log.latest_seq,
			"state": session.state,
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


def _apply_overrides(store: SessionStore, session: Session, req: RunRequest) -> None:
	"""Apply a per-run model/credential override to the session and persist it, so switching
	model on a turn sticks for later turns (like Flow keeps a session's chosen model). Takes
	effect on the next turn; a model can't be swapped mid-generation."""
	changed = False
	for field in ("model", "credential_id"):
		value = getattr(req, field)
		if value is not None and value != getattr(session.config, field):
			setattr(session.config, field, value)
			changed = True
	if changed:
		store.save_meta(session)


async def _launch(
	session: Session,
	task: asyncio.Task[None],
	from_seq: int,
	wait: bool,
) -> dict:
	"""Return immediately or wait on the already-registered session operation."""
	if wait:
		await task
		return _summary(session, from_seq)
	return {"status": "started"}


def _summary(session: Session, from_seq: int) -> dict:
	"""Distil this turn's durable entries into a Flow-like result: reason, final text,
	usage totals, and any pending approval calls."""
	text, reason, pending = "", "done", []
	approval_seq = None
	input_tokens = output_tokens = 0
	for row in session.log.read_since(from_seq):
		t = row["type"]
		if t == "assistant_message":
			message = parse_event(row)
			assert isinstance(message, AssistantMessage)
			text = message.text or text
		elif t == "usage":
			input_tokens += row.get("input_tokens", 0)
			output_tokens += row.get("output_tokens", 0)
		elif t == "approval_required":
			pending = row.get("calls", [])
			approval_seq = row.get("seq")
		elif t == "run_ended":
			reason = row.get("reason", "done")
	return {
		"reason": reason,
		"output": text,
		"usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
		"pending": pending,
		"approval_seq": approval_seq,
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
			data = ev.model_dump(exclude_none=True)
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
