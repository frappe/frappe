"""The daemon's HTTP boundary: thin handlers over the Session verbs.

Two ergonomics from one durable log:
  - POST run/resume return immediately and the run proceeds as a background task, so a
    dropped client never abandons a run. `?wait=true` instead drains the run and returns
    its terminal summary (a Flow-like synchronous response) over the same endpoint.
  - GET /stream?since=N replays the durable log from the cursor, then stays on the live
    feed — catching up after a disconnect and watching live are one code path.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from flow.events import AssistantMessage, ReasoningEffort, parse_event
from flow.model.catalog import list_models
from flow.session.config import SessionConfig
from flow.session.log import SessionLogError
from flow.session.session import (
	ResumeError,
	RewindError,
	RunHandle,
	Session,
	SessionConflict,
)
from flow.session.store import SessionStore
from flow.session.transcript import active_path


class RunRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	message: str


class SetModelRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	# Names only: provider secrets and endpoints are resolved inside flow.
	model: str = Field(min_length=1)
	credential_id: str | None = None
	reasoning_effort: ReasoningEffort | None = None


class ResumeRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	approval_seq: int
	answers: dict[str, str]  # pending tool_call_id -> "Approve" | "Deny" | free text


class RewindRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	target_seq: int


def create_app(store: SessionStore, *, auth_token: str | None = None) -> FastAPI:
	app = FastAPI(title="flow server", version="0.1.0")

	@app.exception_handler(SessionConflict)
	@app.exception_handler(ResumeError)
	@app.exception_handler(RewindError)
	async def state_conflict(request: Request, error: Exception):
		"""A session verb refused by the session's current state answers 409."""
		return JSONResponse({"detail": str(error)}, status_code=409)

	if auth_token:

		@app.middleware("http")
		async def authenticate(request: Request, call_next):
			if request.url.path == "/healthz":
				return await call_next(request)
			scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
			if scheme.lower() != "bearer" or not secrets.compare_digest(
				supplied.encode(), auth_token.encode()
			):
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

	@app.get("/models")
	async def models():
		return {"models": [asdict(model) for model in list_models(store.credentials)]}

	@app.get("/sessions")
	async def list_sessions():
		return {"sessions": [asdict(info) for info in store.list()]}

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
			"model": session.model,
			"credential_id": session.credential_id,
			"reasoning_effort": session.reasoning_effort,
			"config": session.config.redacted(),
		}

	@app.post("/sessions/{sid}/run")
	async def run(sid: str, req: RunRequest, wait: bool = False):
		session = _get(sid)
		handle = await session.run(req.message)
		if handle.status == "steered":
			return {"status": "steered"}
		return await _finish(session, handle, wait)

	@app.post("/sessions/{sid}/resume")
	async def resume(sid: str, req: ResumeRequest, wait: bool = False):
		session = _get(sid)
		handle = await session.resume(req.answers, approval_seq=req.approval_seq)
		return await _finish(session, handle, wait)

	@app.post("/sessions/{sid}/abort")
	async def abort(sid: str):
		session = _get(sid)
		if session.abort():
			return {"status": "aborting"}
		return {"status": session.state}

	@app.post("/sessions/{sid}/rewind")
	async def rewind(sid: str, req: RewindRequest):
		session = _get(sid)
		await session.rewind(req.target_seq)
		return {"status": "rewound"}

	@app.post("/sessions/{sid}/model")
	async def set_model(sid: str, req: SetModelRequest):
		session = _get(sid)
		await session.set_model(
			req.model, credential_id=req.credential_id, reasoning_effort=req.reasoning_effort
		)
		return {
			"model": session.model,
			"credential_id": session.credential_id,
			"reasoning_effort": session.reasoning_effort,
		}

	@app.post("/sessions/{sid}/cancel_pending")
	async def cancel_pending(sid: str):
		session = _get(sid)
		if await session.cancel_pending():
			return {"status": "cancelled"}
		return {"status": session.state}

	@app.get("/sessions/{sid}/entries")
	async def entries(sid: str, since: int = 0, path: Literal["active", "all"] = "active"):
		session = _get(sid)
		if path == "all":  # the raw log, including branches a rewind abandoned
			rows = session.log.read_since(since)
		else:
			if since:  # a rewind can retract rows before the cursor, so no cursor here
				raise HTTPException(
					status_code=422,
					detail="the active view is a snapshot; catch up over /stream or path=all",
				)
			rows = active_path(session.log.read_since(0))
		return {
			"entries": rows,
			"latest_seq": session.log.latest_seq,
			"state": session.state,
			"running": session.is_running,
		}

	@app.get("/sessions/{sid}/stream")
	async def stream(sid: str, since: int = 0):
		session = _get(sid)
		return StreamingResponse(
			_sse_stream(session, since),
			media_type="text/event-stream",
			headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
		)

	return app


async def _finish(session: Session, handle: RunHandle, wait: bool) -> dict:
	"""Fire-and-forget by default; `?wait=true` drains the run and returns its summary."""
	if not wait:
		return {"status": "started"}
	assert handle.task is not None  # a "started" handle always carries its task
	await handle.task
	return _summary(session, handle.from_seq)


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


async def _sse_stream(session: Session, since: int) -> AsyncIterator[bytes]:
	"""Serve `session.events` as SSE, closing where a reconnecting client expects: when
	the watched run ends, or once a session with no active run is fully replayed."""
	since = min(since, session.log.latest_seq)  # a future cursor would suppress live events
	boundary = session.log.latest_seq  # replay ends here: no await before events() attaches
	if not session.is_running and boundary <= since:
		return
	async for event in session.events(since):
		yield _sse(event.model_dump(exclude_none=True))
		if event.type == "run_ended" and event.seq is not None and event.seq >= boundary:
			return  # the live run (or the final historical one) is over
		if event.seq == boundary and not session.is_running:
			return  # replay is done and no live run follows


def _sse(data: dict) -> bytes:
	return f"data: {json.dumps(data)}\n\n".encode()
