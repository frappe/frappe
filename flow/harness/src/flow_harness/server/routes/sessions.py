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
import os
from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from flow_harness.agent.client_tools import deliver_result, is_waiting
from flow_harness.events import AssistantMessage, ReasoningEffort, parse_event
from flow_harness.model.catalog import model_supports_images
from flow_harness.model.discovery import context_window_for
from flow_harness.server.policy import ServerPolicy, gate
from flow_harness.server.utils import sse
from flow_harness.server.utils.workspace import (
	read_file_bytes,
	read_file_head,
	read_text_file,
	resolve_allowed_path,
)
from flow_harness.session.attachments import MAX_ATTACHMENTS_PER_MESSAGE, MAX_SOURCE_BYTES, SNIFF_BYTES
from flow_harness.session.config import SessionConfig
from flow_harness.session.file_changes import file_change_results, reconstruct_original
from flow_harness.session.log import SessionLogError
from flow_harness.session.session import RunHandle, Session
from flow_harness.session.skills import SkillCatalog
from flow_harness.session.store import SessionStore
from flow_harness.session.transcript import active_path


class RunRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	message: str = ""
	attachments: list[str] = Field(default_factory=list, max_length=MAX_ATTACHMENTS_PER_MESSAGE)


class SetModelRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	# api_key/api_base/model_params are accepted only when the policy allows inline credentials
	model: str = Field(min_length=1)
	credential_id: str | None = None
	reasoning_effort: ReasoningEffort | None = None
	api_key: str | None = None
	api_base: str | None = None
	model_params: dict[str, Any] | None = None


class ResumeRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	approval_seq: int
	answers: dict[str, str]  # pending tool_call_id -> "Approve" | "Deny" | free text


class ToolResultRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	token: str
	content: str = ""
	is_error: bool = False


class ToolWaitingRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	token: str


class RewindRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	target_seq: int


class CompactRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	instructions: str | None = None


class ConfigPatchRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	auto_approve: bool | None = None
	tools: list[str] | None = None
	client_tools: list[dict] | None = None
	confirm_tools: list[str] | None = None
	title: str | None = Field(default=None, min_length=1, max_length=200)


class AttachmentCleanupRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	attachments: list[str] = Field(min_length=1, max_length=MAX_ATTACHMENTS_PER_MESSAGE * 2)


class AttachFilesRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	paths: list[str] = Field(min_length=1, max_length=MAX_ATTACHMENTS_PER_MESSAGE)


def create_sessions_router(
	resolve_store: Callable[[Request], SessionStore],
	*,
	system_append: str | None = None,
	policy: ServerPolicy | None = None,
) -> APIRouter:
	"""`resolve_store` picks the store a request acts on — the authenticated site's
	partition in multi-tenant mode, else the daemon's root store."""
	policy = policy or ServerPolicy()
	router = APIRouter()

	def _refuse_inline_credentials(
		api_key: str | None, api_base: str | None, model_params: dict | None = None
	) -> None:
		# model params can carry a key or endpoint of their own
		if (api_key or api_base or model_params) and not policy.inline_credentials:
			raise HTTPException(
				status_code=400, detail="inline model credentials and params are disabled by server policy"
			)

	def _get(store: SessionStore, sid: str) -> Session:
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
	async def list_sessions(request: Request):
		infos = await asyncio.to_thread(resolve_store(request).list)  # per-session file reads
		return {"sessions": [asdict(info) for info in infos]}

	def skill_catalog_payload(skill_catalog: SkillCatalog) -> dict:
		return {
			"skills": [
				{"name": skill.name, "description": skill.description} for skill in skill_catalog.skills
			],
			"diagnostics": [{"message": diagnostic.message} for diagnostic in skill_catalog.diagnostics],
		}

	@router.post("/skills", dependencies=gate(policy.skills_api))
	async def preview_skills(request: Request, config: SessionConfig):
		"""Return the catalog a lazy client would get without creating a session."""
		try:
			skill_catalog = await resolve_store(request).preview_skill_catalog(config)
		except ValueError as e:
			raise HTTPException(status_code=400, detail=str(e)) from None
		return skill_catalog_payload(skill_catalog)

	@router.post("/sessions")
	async def create_session(request: Request, config: SessionConfig):
		_refuse_inline_credentials(config.api_key, config.api_base, config.model_params)
		for agent in config.subagents:
			_refuse_inline_credentials(agent.api_key, agent.api_base, agent.model_params)
		if system_append:
			joined = "\n\n".join(p for p in (config.system_append, system_append) if p)
			config = config.model_copy(update={"system_append": joined})
		try:
			session = await resolve_store(request).create_async(config)
		except ValueError as e:
			raise HTTPException(status_code=400, detail=str(e)) from None
		return {"session_id": session.id, "config": session.config.redacted()}

	@router.get("/sessions/{sid}")
	async def get_session(request: Request, sid: str):
		store = resolve_store(request)
		session = _get(store, sid)
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

	@router.get("/sessions/{sid}/skills", dependencies=gate(policy.skills_api))
	async def session_skills(request: Request, sid: str):
		"""The skills this session can invoke now, including ones added after it started."""
		store = resolve_store(request)
		return skill_catalog_payload(await store.invocable_skills(_get(store, sid)))

	@router.get("/sessions/{sid}/extensions", dependencies=gate(policy.extensions))
	async def session_extensions(request: Request, sid: str):
		"""Loaded server extensions, their tools, and non-fatal diagnostics."""
		store = resolve_store(request)
		_get(store, sid)
		return store.extension_runtime.info()

	@router.post("/extensions/reload", dependencies=gate(policy.extensions))
	async def reload_extensions(request: Request):
		"""Re-import all extensions; returns the fresh info payload."""
		store = resolve_store(request)
		await asyncio.to_thread(store.reload_extensions)  # imports run arbitrary setup code
		return store.extension_runtime.info()

	@router.delete("/sessions/{sid}")
	async def delete_session(request: Request, sid: str):
		try:
			resolve_store(request).delete(sid)
		except KeyError:
			raise HTTPException(status_code=404, detail="session not found") from None
		return {"status": "deleted"}

	@router.post("/sessions/{sid}/attachments")
	async def upload_attachments(request: Request, sid: str, files: Annotated[list[UploadFile], File()]):
		session = _get(resolve_store(request), sid)
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

	@router.post("/sessions/{sid}/attachments/files", dependencies=gate(policy.fs_api))
	async def attach_files(request: Request, sid: str, req: AttachFilesRequest):
		"""Read project files by path and store them as attachments (@-mentions):
		images and small text inline, anything else by its path."""
		session = _get(resolve_store(request), sid)
		assert session.attachment_store is not None
		tools = session.server_tools or {}
		stored = []
		try:
			for path in req.paths:
				full_path = resolve_allowed_path(session.config.cwd, path, session.allowed_roots)
				# named by its cwd-relative path, so the model can address the file
				name = os.path.relpath(full_path, session.config.cwd)
				if os.path.isfile(full_path) and (size := os.path.getsize(full_path)) > MAX_SOURCE_BYTES:
					# too big to read in; tools open it where it lies
					head = await asyncio.to_thread(read_file_head, full_path, SNIFF_BYTES)
					stored.append(
						session.attachment_store.add_reference(name, head, size, full_path, tools=tools)
					)
					continue
				data = await asyncio.to_thread(read_file_bytes, full_path, MAX_SOURCE_BYTES, purpose="attach")
				stored.append(
					await asyncio.to_thread(
						session.attachment_store.add_file, name, data, tools=tools, path=full_path
					)
				)
		except Exception:
			for item in stored:
				session.attachment_store.remove(item.id)
			raise
		return {"attachments": [item.model_dump(exclude_none=True) for item in stored]}

	@router.get("/sessions/{sid}/attachments/{attachment_id}")
	async def read_attachment(request: Request, sid: str, attachment_id: str):
		"""Return a session-owned image for composer previews and other local clients."""
		session = _get(resolve_store(request), sid)
		assert session.attachment_store is not None
		metadata = await asyncio.to_thread(session.attachment_store.get, attachment_id)
		data = await asyncio.to_thread(session.attachment_store.read, attachment_id)
		return Response(
			content=data,
			media_type=metadata.mime_type,
			headers={"Cache-Control": "private, max-age=31536000, immutable"},
		)

	@router.delete("/sessions/{sid}/attachments")
	async def cleanup_attachments(request: Request, sid: str, req: AttachmentCleanupRequest):
		session = _get(resolve_store(request), sid)
		assert session.attachment_store is not None
		removed = session.attachment_store.remove_unclaimed(req.attachments)
		return {"removed": removed}

	@router.post("/sessions/{sid}/run")
	async def run(request: Request, sid: str, req: RunRequest, wait: bool = False):
		session = _get(resolve_store(request), sid)
		handle = await session.run(req.message, attachment_ids=req.attachments)
		return await _finish(session, handle, wait)

	@router.post("/sessions/{sid}/resume")
	async def resume(request: Request, sid: str, req: ResumeRequest, wait: bool = False):
		session = _get(resolve_store(request), sid)
		handle = await session.resume(req.answers, approval_seq=req.approval_seq)
		return await _finish(session, handle, wait)

	@router.post("/sessions/{sid}/abort")
	async def abort(request: Request, sid: str):
		session = _get(resolve_store(request), sid)
		if session.abort():
			return {"status": "aborting"}
		return {"status": session.state}

	@router.post("/sessions/{sid}/rewind")
	async def rewind(request: Request, sid: str, req: RewindRequest):
		session = _get(resolve_store(request), sid)
		await session.rewind(req.target_seq)
		return {"status": "rewound"}

	@router.patch("/sessions/{sid}/config")
	async def patch_config(request: Request, sid: str, req: ConfigPatchRequest):
		# Confirmation changes apply at the next tool gate; tools apply to later runs.
		store = resolve_store(request)
		session = _get(store, sid)
		if (req.client_tools is None) != (req.confirm_tools is None):
			raise HTTPException(
				status_code=400, detail="client_tools and confirm_tools must be patched together"
			)
		changes: dict[str, object] = {}
		server_tools = None
		if req.tools is not None:
			candidate = session.config.model_copy(update={"tools": req.tools})
			server_tools = store.resolve_tools(candidate)
			changes["tools"] = req.tools
		if req.client_tools is not None:
			changes["client_tools"] = req.client_tools
			changes["confirm_tools"] = req.confirm_tools or []
		if req.auto_approve is not None:
			changes["auto_approve"] = req.auto_approve
		if req.title is not None:
			changes["title"] = req.title.strip()
			if not changes["title"]:
				raise HTTPException(status_code=400, detail="title cannot be empty")
		if not changes:
			return {"config": session.config.redacted()}
		previous = {field: getattr(session.config, field) for field in changes}
		previous_server_tools = session.server_tools
		for field, value in changes.items():
			setattr(session.config, field, value)
		if server_tools is not None:
			session.server_tools = server_tools
		try:
			store.save_meta(session)
		except OSError:
			for field, value in previous.items():
				setattr(session.config, field, value)
			session.server_tools = previous_server_tools
			raise HTTPException(status_code=500, detail="failed to persist config") from None
		return {"config": session.config.redacted()}

	@router.post("/sessions/{sid}/model")
	async def set_model(request: Request, sid: str, req: SetModelRequest):
		_refuse_inline_credentials(req.api_key, req.api_base, req.model_params)
		store = resolve_store(request)
		session = _get(store, sid)
		model_before = (session.model, session.credential_id, session.reasoning_effort)
		await session.set_model(
			req.model, credential_id=req.credential_id, reasoning_effort=req.reasoning_effort
		)
		if {"api_key", "api_base", "model_params"} & req.model_fields_set:
			# replaced as a unit, so no endpoint or params outlive the key they came with
			config = session.config
			previous = (config.api_key, config.api_base, config.model_params)
			config.api_key = req.api_key
			config.api_base = req.api_base
			config.model_params = req.model_params or {}
			try:
				store.save_meta(session)
			except OSError:
				config.api_key, config.api_base, config.model_params = previous
				# the model change is already durable — undo it, or the 500 lies
				model, credential_id, effort = model_before
				await session.set_model(model, credential_id=credential_id, reasoning_effort=effort)
				raise HTTPException(status_code=500, detail="failed to persist config") from None
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
	async def compact(request: Request, sid: str, req: CompactRequest | None = None, wait: bool = False):
		session = _get(resolve_store(request), sid)
		handle = await session.compact(req.instructions if req else None)
		return await _finish(session, handle, wait)

	@router.post("/sessions/{sid}/cancel_pending")
	async def cancel_pending(request: Request, sid: str):
		session = _get(resolve_store(request), sid)
		if await session.cancel_pending():
			return {"status": "cancelled"}
		return {"status": session.state}

	@router.post("/sessions/{sid}/tool_result")
	async def tool_result(request: Request, sid: str, req: ToolResultRequest):
		if not resolve_store(request).exists(sid):
			raise HTTPException(status_code=404, detail="session not found")
		result = {"content": req.content, "is_error": req.is_error}
		return {"delivered": deliver_result(sid, req.token, result)}

	@router.post("/sessions/{sid}/tool_waiting")
	async def tool_waiting(request: Request, sid: str, req: ToolWaitingRequest):
		if not resolve_store(request).exists(sid):
			raise HTTPException(status_code=404, detail="session not found")
		return {"waiting": is_waiting(sid, req.token)}

	@router.get("/sessions/{sid}/entries")
	async def entries(request: Request, sid: str, since: int = 0, path: Literal["active", "all"] = "active"):
		session = _get(resolve_store(request), sid)
		if path == "active" and since:
			raise HTTPException(
				status_code=422,
				detail="the active view is a snapshot; catch up over /stream or path=all",
			)
		snapshot = session.event_snapshot(since)
		if path == "active":
			snapshot["entries"] = active_path(snapshot["entries"])
		return snapshot

	@router.get("/sessions/{sid}/file/diff", dependencies=gate(policy.fs_api))
	async def file_diff(request: Request, sid: str, path: str):
		"""Both sides of the session's changes to one file, for the diff viewer.
		`original` is reconstructed by reverse-applying the recorded edit diffs;
		a write marks the file as created, so its original is empty."""
		session = _get(resolve_store(request), sid)
		full_path = resolve_allowed_path(session.config.cwd, path, session.allowed_roots)

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
	async def stream(request: Request, sid: str, since: int = 0, follow: bool = False):
		store = resolve_store(request)
		session = _get(store, sid)
		body = (
			sse.sse_follow_stream(session, since, store.closing) if follow else sse.sse_stream(session, since)
		)
		return StreamingResponse(
			body,
			media_type="text/event-stream",
			headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
		)

	return router


async def _finish(session: Session, handle: RunHandle, wait: bool) -> dict:
	"""The handle's status; with `?wait=true`, a started run is drained and summarized."""
	if wait and handle.task is not None:
		await handle.task
		return _summary(session, handle.from_seq)
	return {"status": handle.status}


def _summary(session: Session, from_seq: int) -> dict:
	"""Distil this turn's durable entries into a Flow-like result: reason, final text,
	usage totals, and any pending approval calls."""
	text, reason, pending = "", "done", []
	approval_seq = None
	input_tokens = output_tokens = cache_read_tokens = cache_write_tokens = 0
	for row in session.log.read_since(from_seq):
		t = row["type"]
		if row.get("subagent_id") and t != "usage":
			continue  # a sub-agent's rows: only its usage counts toward the turn
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
