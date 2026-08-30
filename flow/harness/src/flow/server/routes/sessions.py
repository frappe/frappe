"""Session routes: lifecycle, attachments, the run verbs, entries, and the SSE stream.

Two ergonomics from one durable log:
  - POST run/resume return immediately and the run proceeds as a background task, so a
    dropped client never abandons a run. `?wait=true` instead drains the run and returns
    its terminal summary (a Flow-like synchronous response) over the same endpoint.
  - GET /stream?since=N replays the durable log from the cursor, then stays on the live
    feed — catching up after a disconnect and watching live are one code path.
    `follow=true` keeps the connection open across run boundaries, with keepalive
    comments while the session idles.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from flow.events import AssistantMessage, ReasoningEffort, parse_event
from flow.model.catalog import model_supports_images
from flow.model.discovery import context_window_for
from flow.path_policy import absolute_path, canonical_path, is_path_allowed
from flow.server.utils import sse
from flow.server.utils.workspace import read_text_file
from flow.session.attachments import MAX_ATTACHMENTS_PER_MESSAGE, MAX_SOURCE_BYTES
from flow.session.config import SessionConfig
from flow.session.file_changes import file_change_results, reconstruct_original
from flow.session.log import SessionLogError
from flow.session.session import RunHandle, Session
from flow.session.skills import SkillCatalog
from flow.session.store import SessionStore
from flow.session.transcript import active_path


class RunRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	message: str = ""
	attachments: list[str] = Field(default_factory=list, max_length=MAX_ATTACHMENTS_PER_MESSAGE)


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


class CompactRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	instructions: str | None = None


class ConfigPatchRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	auto_approve: bool | None = None
	title: str | None = Field(default=None, min_length=1, max_length=200)


class AttachmentCleanupRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	attachments: list[str] = Field(min_length=1, max_length=MAX_ATTACHMENTS_PER_MESSAGE * 2)


def create_sessions_router(store: SessionStore, *, system_append: str | None = None) -> APIRouter:
	router = APIRouter()

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

	@router.get("/sessions")
	async def list_sessions():
		infos = await asyncio.to_thread(store.list)  # per-session file reads
		return {"sessions": [asdict(info) for info in infos]}

	def skill_catalog_payload(skill_catalog: SkillCatalog) -> dict:
		return {
			"skills": [
				{"name": skill.name, "description": skill.description} for skill in skill_catalog.skills
			],
			"diagnostics": [{"message": diagnostic.message} for diagnostic in skill_catalog.diagnostics],
		}

	@router.post("/skills")
	async def preview_skills(config: SessionConfig):
		"""Return the catalog a lazy client would get without creating a session."""
		try:
			skill_catalog = await store.preview_skill_catalog(config)
		except ValueError as e:
			raise HTTPException(status_code=400, detail=str(e)) from None
		return skill_catalog_payload(skill_catalog)

	@router.post("/sessions")
	async def create_session(config: SessionConfig):
		if system_append:
			joined = "\n\n".join(p for p in (config.system_append, system_append) if p)
			config = config.model_copy(update={"system_append": joined})
		try:
			session = await store.create_async(config)
		except ValueError as e:
			raise HTTPException(status_code=400, detail=str(e)) from None
		return {"session_id": session.id, "config": session.config.redacted()}

	@router.get("/sessions/{sid}")
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
			# both block: a file read, and litellm's import on the first call
			"title": await asyncio.to_thread(store.title, sid),
			"context_tokens": session.transcript.context_tokens,
			"context_window": await asyncio.to_thread(context_window_for, session.model),
			"supports_images": await asyncio.to_thread(model_supports_images, session.model),
		}

	@router.get("/sessions/{sid}/skills")
	async def session_skills(sid: str):
		session = _get(sid)
		return skill_catalog_payload(session.skill_catalog)

	@router.get("/sessions/{sid}/extensions")
	async def session_extensions(sid: str):
		"""Loaded server extensions, their tools, and non-fatal diagnostics."""
		_get(sid)
		return store.extension_runtime.info()

	@router.post("/extensions/reload")
	async def reload_extensions():
		"""Re-import all extensions; returns the fresh info payload."""
		await asyncio.to_thread(store.reload_extensions)  # imports run arbitrary setup code
		return store.extension_runtime.info()

	@router.delete("/sessions/{sid}")
	async def delete_session(sid: str):
		try:
			store.delete(sid)
		except KeyError:
			raise HTTPException(status_code=404, detail="session not found") from None
		return {"status": "deleted"}

	@router.post("/sessions/{sid}/attachments")
	async def upload_attachments(sid: str, files: Annotated[list[UploadFile], File()]):
		session = _get(sid)
		if not files or len(files) > MAX_ATTACHMENTS_PER_MESSAGE:
			raise HTTPException(
				status_code=400,
				detail=f"upload between 1 and {MAX_ATTACHMENTS_PER_MESSAGE} files",
			)
		assert session.attachment_store is not None
		stored = []
		try:
			for upload in files:
				data = await upload.read(MAX_SOURCE_BYTES + 1)
				stored.append(
					await asyncio.to_thread(
						session.attachment_store.add_bytes,
						upload.filename or "attachment",
						data,
					)
				)
		except Exception:
			for item in stored:
				session.attachment_store.remove(item.id)
			raise
		return {"attachments": [item.model_dump(exclude_none=True) for item in stored]}

	@router.get("/sessions/{sid}/attachments/{attachment_id}")
	async def read_attachment(sid: str, attachment_id: str):
		"""Return a session-owned image for composer previews and other local clients."""
		session = _get(sid)
		assert session.attachment_store is not None
		metadata = await asyncio.to_thread(session.attachment_store.get, attachment_id)
		data = await asyncio.to_thread(session.attachment_store.read, attachment_id)
		return Response(
			content=data,
			media_type=metadata.mime_type,
			headers={"Cache-Control": "private, max-age=31536000, immutable"},
		)

	@router.delete("/sessions/{sid}/attachments")
	async def cleanup_attachments(sid: str, req: AttachmentCleanupRequest):
		session = _get(sid)
		assert session.attachment_store is not None
		removed = session.attachment_store.remove_unclaimed(req.attachments)
		return {"removed": removed}

	@router.post("/sessions/{sid}/run")
	async def run(sid: str, req: RunRequest, wait: bool = False):
		session = _get(sid)
		handle = await session.run(req.message, attachment_ids=req.attachments)
		if handle.status == "steered":
			return {"status": "steered"}
		return await _finish(session, handle, wait)

	@router.post("/sessions/{sid}/resume")
	async def resume(sid: str, req: ResumeRequest, wait: bool = False):
		session = _get(sid)
		handle = await session.resume(req.answers, approval_seq=req.approval_seq)
		return await _finish(session, handle, wait)

	@router.post("/sessions/{sid}/abort")
	async def abort(sid: str):
		session = _get(sid)
		if session.abort():
			return {"status": "aborting"}
		return {"status": session.state}

	@router.post("/sessions/{sid}/rewind")
	async def rewind(sid: str, req: RewindRequest):
		session = _get(sid)
		await session.rewind(req.target_seq)
		return {"status": "rewound"}

	@router.patch("/sessions/{sid}/config")
	async def patch_config(sid: str, req: ConfigPatchRequest):
		# safe mid-run: the loop reads config at each tool gate
		session = _get(sid)
		if req.auto_approve is not None:
			previous = session.config.auto_approve
			session.set_auto_approve(req.auto_approve)
			try:
				store.save_meta(session)
			except OSError:
				# memory and disk must agree, or the flag resurfaces after restart
				session.set_auto_approve(previous)
				raise HTTPException(status_code=500, detail="failed to persist config") from None
		if req.title is not None:
			title = req.title.strip()
			if not title:
				raise HTTPException(status_code=400, detail="title cannot be empty")
			previous_title = session.config.title
			session.config.title = title
			try:
				store.save_meta(session)
			except OSError:
				session.config.title = previous_title
				raise HTTPException(status_code=500, detail="failed to persist config") from None
		return {"config": session.config.redacted()}

	@router.post("/sessions/{sid}/model")
	async def set_model(sid: str, req: SetModelRequest):
		session = _get(sid)
		await session.set_model(
			req.model, credential_id=req.credential_id, reasoning_effort=req.reasoning_effort
		)
		context_window, supports_images = await asyncio.gather(
			asyncio.to_thread(context_window_for, session.model),
			asyncio.to_thread(model_supports_images, session.model),
		)
		return {
			"model": session.model,
			"credential_id": session.credential_id,
			"reasoning_effort": session.reasoning_effort,
			"context_window": context_window,
			"supports_images": supports_images,
		}

	@router.post("/sessions/{sid}/compact")
	async def compact(sid: str, req: CompactRequest | None = None, wait: bool = False):
		session = _get(sid)
		handle = await session.compact(req.instructions if req else None)
		return await _finish(session, handle, wait)

	@router.post("/sessions/{sid}/cancel_pending")
	async def cancel_pending(sid: str):
		session = _get(sid)
		if await session.cancel_pending():
			return {"status": "cancelled"}
		return {"status": session.state}

	@router.get("/sessions/{sid}/entries")
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

	@router.get("/sessions/{sid}/file/diff")
	async def file_diff(sid: str, path: str):
		"""Both sides of the session's changes to one file, for the diff viewer.
		`original` is reconstructed by reverse-applying the recorded edit diffs;
		a write marks the file as created, so its original is empty."""
		session = _get(sid)
		full_path = absolute_path(path, base=session.config.cwd)
		if session.allowed_roots and not is_path_allowed(canonical_path(full_path), session.allowed_roots):
			raise HTTPException(status_code=403, detail="path is outside the allowed roots")

		def compute() -> dict:
			# the log scan and the string-heavy reconstruction stay off the event loop
			results = file_change_results(active_path(session.log.read_since(0)), full_path)
			if not results:
				raise HTTPException(status_code=404, detail="the session has not changed this file")
			modified = read_text_file(full_path, strip_bom=True)
			return {
				"path": full_path,
				"original": reconstruct_original(modified, results),
				"modified": modified,
			}

		return await asyncio.to_thread(compute)

	@router.get("/sessions/{sid}/stream")
	async def stream(sid: str, since: int = 0, follow: bool = False):
		session = _get(sid)
		body = sse.sse_follow_stream(session, since) if follow else sse.sse_stream(session, since)
		return StreamingResponse(
			body,
			media_type="text/event-stream",
			headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
		)

	return router


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
	input_tokens = output_tokens = cache_read_tokens = cache_write_tokens = 0
	for row in session.log.read_since(from_seq):
		t = row["type"]
		if t == "assistant_message":
			message = parse_event(row)
			assert isinstance(message, AssistantMessage)
			text = message.text or text
		elif t == "usage":
			input_tokens += row.get("input_tokens", 0)
			output_tokens += row.get("output_tokens", 0)
			cache_read_tokens += row.get("cache_read_tokens", 0)
			cache_write_tokens += row.get("cache_write_tokens", 0)
		elif t == "approval_required":
			pending = row.get("calls", [])
			approval_seq = row.get("seq")
		elif t == "run_ended":
			reason = row.get("reason", "done")
	return {
		"reason": reason,
		"output": text,
		"usage": {
			"input_tokens": input_tokens,
			"output_tokens": output_tokens,
			"cache_read_tokens": cache_read_tokens,
			"cache_write_tokens": cache_write_tokens,
		},
		"pending": pending,
		"approval_seq": approval_seq,
	}
