"""The daemon's HTTP boundary: thin handlers over the Session verbs.

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
import contextlib
import json
import os
import re
import secrets
import subprocess
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from flow import config as server_config
from flow.events import AssistantMessage, ReasoningEffort, parse_event
from flow.model.auth import AuthError
from flow.model.catalog import model_supports_images
from flow.model.discovery import available_models, context_window_for
from flow.path_policy import absolute_path, canonical_path, is_path_allowed
from flow.server.fspick import PickerUnavailable, pick_folder
from flow.server.provider_auth import (
	OAuthCoordinator,
	create_custom_provider,
	provider_catalog,
	require_provider,
	update_custom_provider,
)
from flow.session.attachments import (
	MAX_ATTACHMENTS_PER_MESSAGE,
	MAX_SOURCE_BYTES,
	AttachmentError,
)
from flow.session.config import SessionConfig
from flow.session.log import SessionLogError
from flow.session.session import (
	ResumeError,
	RewindError,
	RunHandle,
	Session,
	SessionConflict,
)
from flow.session.skills import SkillCatalog, SkillError
from flow.session.store import SessionStore
from flow.session.transcript import active_path
from flow.tools.builtins.common import to_lf

# viewer payload cap; anything bigger is not a file to render in a chat UI
MAX_FILE_VIEW_BYTES = 2 * 1024 * 1024

# file-name search: skip dependency/VCS trees, cap results, and bound the walk
# itself so a huge un-pruned tree cannot pin a thread per keystroke
SEARCH_SKIP_DIRS = {"node_modules", "__pycache__", "venv", "dist", "build", "target"}
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_SCAN = 20_000


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


class ApiKeyRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	key: str = Field(min_length=1)


class CustomProviderRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	name: str = Field(min_length=1, max_length=60)
	base_url: str = Field(min_length=1, max_length=300)
	models: list[str] = Field(min_length=1, max_length=50)
	api_key: str | None = None


class AttachmentCleanupRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	attachments: list[str] = Field(min_length=1, max_length=MAX_ATTACHMENTS_PER_MESSAGE * 2)


class OAuthCompleteRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	callback_url: str = Field(min_length=1)


class WriteFileRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	path: str = Field(min_length=1)
	content: str


def create_app(
	store: SessionStore,
	*,
	auth_token: str | None = None,
	cors_origins: list[str] | None = None,
	webui_dir: str | None = None,
	system_append: str | None = None,
) -> FastAPI:
	"""`system_append` is text the operator adds to every session's system prompt
	(`flow web --append-system-prompt`); it lands after whatever the client sends."""
	# docs off: those routes would be reachable without a bearer beside the web UI
	app = FastAPI(title="flow server", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
	oauth = OAuthCoordinator(store.credentials)

	origins = cors_origins if cors_origins is not None else server_config.CORS_ORIGINS
	if origins:
		app.add_middleware(
			CORSMiddleware,
			allow_origins=origins,
			allow_methods=["*"],
			allow_headers=["Authorization", "Content-Type"],
		)

	@app.exception_handler(SessionConflict)
	@app.exception_handler(ResumeError)
	@app.exception_handler(RewindError)
	async def state_conflict(request: Request, error: Exception):
		"""A session verb refused by the session's current state answers 409."""
		return JSONResponse({"detail": str(error)}, status_code=409)

	@app.exception_handler(AttachmentError)
	@app.exception_handler(SkillError)
	async def input_error(request: Request, error: Exception):
		return JSONResponse({"detail": str(error)}, status_code=400)

	@app.exception_handler(AuthError)
	async def auth_error(request: Request, error: AuthError):
		"""Provider setup problems are client errors, never 500s."""
		return JSONResponse({"detail": str(error)}, status_code=400)

	if auth_token:
		api_prefixes = ("/sessions", "/models", "/providers", "/fs")

		@app.middleware("http")
		async def authenticate(request: Request, call_next):
			if request.url.path == "/healthz":
				return await call_next(request)
			if request.method == "OPTIONS":
				return await call_next(request)  # preflights carry no Authorization
			# the static shell must load before the page can send a bearer
			if (
				webui_dir
				and request.method in ("GET", "HEAD")
				and not request.url.path.startswith(api_prefixes)
			):
				return await call_next(request)
			scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
			if scheme.lower() != "bearer" or not secrets.compare_digest(
				supplied.encode(), auth_token.encode()
			):
				return JSONResponse({"detail": "unauthorized"}, status_code=401)
			return await call_next(request)
	else:
		# Tokenless mode trusts the local machine, so browsers are the threat:
		# DNS rebinding forges a loopback Host, cross-site requests a foreign Origin.
		allowed_origins = set(origins or [])
		loopback_hosts = ("127.0.0.1", "localhost", "::1")

		@app.middleware("http")
		async def guard_browser_boundaries(request: Request, call_next):
			server = request.scope.get("server")
			if server is None or server[1] is None:
				return await call_next(request)  # unix socket
			if server[0] in loopback_hosts and request.url.hostname not in loopback_hosts:
				return JSONResponse({"detail": "invalid host header"}, status_code=400)
			origin = request.headers.get("origin")
			if origin and origin not in allowed_origins:
				if urlsplit(origin).hostname not in loopback_hosts:
					return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
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
		catalog = await available_models(store.credentials)
		return {"models": [asdict(model) for model in catalog.models], "errors": catalog.errors}

	@app.get("/providers")
	async def providers():
		return {"providers": provider_catalog(store.credentials)}

	@app.post("/providers/custom")
	async def save_custom_provider(req: CustomProviderRequest):
		"""Register an OpenAI-compatible endpoint (Ollama, LM Studio, a gateway)."""
		name, base_url, models, api_key = _normalized_custom_provider_request(req)
		row = create_custom_provider(
			store.credentials,
			name=name,
			base_url=base_url,
			models=models,
			api_key=api_key,
		)
		return {"provider": row}

	@app.put("/providers/custom/{provider_id}")
	async def edit_custom_provider(provider_id: str, req: CustomProviderRequest):
		"""Rewrite a stored endpoint in place; a blank api_key keeps the saved one."""
		name, base_url, models, api_key = _normalized_custom_provider_request(req)
		row = update_custom_provider(
			store.credentials,
			provider_id,
			name=name,
			base_url=base_url,
			models=models,
			api_key=api_key,
		)
		if row is None:
			raise HTTPException(status_code=404, detail="no such custom endpoint")
		return {"provider": row}

	@app.post("/providers/{provider_id}/api-key")
	async def save_provider_api_key(provider_id: str, req: ApiKeyRequest):
		provider = require_provider(provider_id)
		if "api_key" not in provider.auth_methods:
			raise AuthError(f"{provider.display_name} does not take an API key")
		store.credentials.set_api_key(provider_id, req.key)
		return {"status": "saved"}

	@app.delete("/providers/{provider_id}")
	async def remove_provider_credential(provider_id: str):
		# custom endpoints have no ProviderSpec; a stored credential proves the id
		if store.credentials.get(provider_id) is None:
			require_provider(provider_id)  # unknown id → 400, known-but-unset → 404
			raise HTTPException(status_code=404, detail="no stored credential")
		store.credentials.delete(provider_id)
		return {"status": "removed"}

	@app.post("/providers/{provider_id}/oauth/start")
	async def start_provider_oauth(provider_id: str):
		return await oauth.start(provider_id)

	@app.get("/providers/{provider_id}/oauth/status")
	async def provider_oauth_status(provider_id: str):
		require_provider(provider_id)
		return oauth.status(provider_id)

	@app.post("/providers/{provider_id}/oauth/complete")
	async def complete_provider_oauth(provider_id: str, req: OAuthCompleteRequest):
		return await oauth.complete(provider_id, req.callback_url)

	# POST, not GET: a GET could be fired by a hostile page's <img src=…>.
	# One at a time — each pick pins a thread until the user answers.
	pick_lock = asyncio.Lock()

	@app.post("/fs/pick")
	async def fs_pick():
		async with pick_lock:
			try:
				path = await asyncio.to_thread(pick_folder)
			except PickerUnavailable as e:
				raise HTTPException(status_code=501, detail=str(e)) from None
		return {"path": path}

	@app.get("/sessions")
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

	@app.post("/skills")
	async def preview_skills(config: SessionConfig):
		"""Return the catalog a lazy client would get without creating a session."""
		try:
			skill_catalog = await store.preview_skill_catalog(config)
		except ValueError as e:
			raise HTTPException(status_code=400, detail=str(e)) from None
		return skill_catalog_payload(skill_catalog)

	@app.post("/sessions")
	async def create_session(config: SessionConfig):
		if system_append:
			joined = "\n\n".join(p for p in (config.system_append, system_append) if p)
			config = config.model_copy(update={"system_append": joined})
		try:
			session = await store.create_async(config)
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
			# both block: a file read, and litellm's import on the first call
			"title": await asyncio.to_thread(store.title, sid),
			"context_tokens": session.transcript.context_tokens,
			"context_window": await asyncio.to_thread(context_window_for, session.model),
			"supports_images": await asyncio.to_thread(model_supports_images, session.model),
		}

	@app.get("/sessions/{sid}/skills")
	async def session_skills(sid: str):
		session = _get(sid)
		return skill_catalog_payload(session.skill_catalog)

	@app.get("/sessions/{sid}/extensions")
	async def session_extensions(sid: str):
		"""Loaded server extensions, their tools, and non-fatal diagnostics."""
		_get(sid)
		return store.extension_runtime.info()

	@app.post("/extensions/reload")
	async def reload_extensions():
		"""Re-import all extensions; returns the fresh info payload."""
		await asyncio.to_thread(store.reload_extensions)  # imports run arbitrary setup code
		return store.extension_runtime.info()

	@app.delete("/sessions/{sid}")
	async def delete_session(sid: str):
		try:
			store.delete(sid)
		except KeyError:
			raise HTTPException(status_code=404, detail="session not found") from None
		return {"status": "deleted"}

	@app.post("/sessions/{sid}/attachments")
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

	@app.get("/sessions/{sid}/attachments/{attachment_id}")
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

	@app.delete("/sessions/{sid}/attachments")
	async def cleanup_attachments(sid: str, req: AttachmentCleanupRequest):
		session = _get(sid)
		assert session.attachment_store is not None
		removed = session.attachment_store.remove_unclaimed(req.attachments)
		return {"removed": removed}

	@app.post("/sessions/{sid}/run")
	async def run(sid: str, req: RunRequest, wait: bool = False):
		session = _get(sid)
		handle = await session.run(req.message, attachment_ids=req.attachments)
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

	@app.patch("/sessions/{sid}/config")
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

	@app.post("/sessions/{sid}/model")
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

	@app.post("/sessions/{sid}/compact")
	async def compact(sid: str, req: CompactRequest | None = None, wait: bool = False):
		session = _get(sid)
		handle = await session.compact(req.instructions if req else None)
		return await _finish(session, handle, wait)

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

	@app.get("/sessions/{sid}/file/diff")
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
			results = _file_change_results(active_path(session.log.read_since(0)), full_path)
			if not results:
				raise HTTPException(status_code=404, detail="the session has not changed this file")
			modified = _read_text_file(full_path, strip_bom=True)
			return {
				"path": full_path,
				"original": _reconstruct_original(modified, results),
				"modified": modified,
			}

		return await asyncio.to_thread(compute)

	# explorer reads are cwd-keyed so they work before the first message
	# creates a session; diffs and saves stay on the session routes.
	@app.get("/fs/files")
	async def list_files(cwd: str, path: str = ""):
		full_path = _resolve_allowed_path(cwd, path or ".")
		return {"path": full_path, "entries": await asyncio.to_thread(_list_directory, full_path)}

	@app.get("/fs/files/search")
	async def search_files(cwd: str, query: str):
		root = _resolve_allowed_path(cwd, ".")
		if not os.path.isdir(root):
			raise HTTPException(status_code=404, detail="directory not found")
		needle = query.strip().lower()
		if not needle:
			return {"path": root, "matches": [], "truncated": False}
		matches, truncated = await asyncio.to_thread(_search_tree, root, needle)
		return {"path": root, "matches": matches, "truncated": truncated}

	@app.get("/fs/file")
	async def read_file(cwd: str, path: str):
		full_path = _resolve_allowed_path(cwd, path)
		return {"path": full_path, "content": await asyncio.to_thread(_read_text_file, full_path)}

	def _resolve_allowed_path(cwd: str, path: str) -> str:
		if not os.path.isabs(cwd):
			raise HTTPException(status_code=400, detail="cwd must be an absolute path")
		full_path = absolute_path(path, base=cwd)
		if store.allowed_roots and not is_path_allowed(canonical_path(full_path), store.allowed_roots):
			raise HTTPException(status_code=403, detail="path is outside the allowed roots")
		return full_path

	@app.get("/fs/git/changes")
	async def git_changes(cwd: str):
		"""The repository's uncommitted files with added/removed line counts."""
		root = _resolve_allowed_path(cwd, ".")
		if not os.path.isdir(root):
			raise HTTPException(status_code=404, detail="directory not found")
		return await asyncio.to_thread(_git_changes, root, store.allowed_roots)

	@app.get("/fs/git/file/diff")
	async def git_file_diff(cwd: str, path: str):
		"""Both sides of one file's uncommitted changes: HEAD and the working tree."""
		base = _resolve_allowed_path(cwd, ".")
		full_path = _resolve_allowed_path(cwd, path)

		def compute() -> dict:
			top = _git_output(base, "rev-parse", "--show-toplevel")
			if top is None:
				raise HTTPException(status_code=400, detail="not a git repository")
			root = top.decode("utf-8", "replace").strip()
			rel = os.path.relpath(canonical_path(full_path), root)
			if rel.startswith(".."):
				raise HTTPException(status_code=400, detail="file is outside the repository")
			original = _git_head_text(root, rel.replace(os.sep, "/"))
			modified = _read_text_file(full_path) if os.path.isfile(full_path) else ""
			return {"path": full_path, "original": original, "modified": modified}

		return await asyncio.to_thread(compute)

	@app.put("/sessions/{sid}/file")
	async def write_file(sid: str, req: WriteFileRequest):
		"""Save the file viewer's edits. Same fence as reading; parent directories
		are created like the write tool does."""
		session = _get(sid)
		full_path = absolute_path(req.path, base=session.config.cwd)
		if session.allowed_roots and not is_path_allowed(canonical_path(full_path), session.allowed_roots):
			raise HTTPException(status_code=403, detail="path is outside the allowed roots")
		if len(req.content.encode()) > MAX_FILE_VIEW_BYTES:
			raise HTTPException(status_code=413, detail="file too large to save")

		def save() -> None:
			try:
				os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
				with open(full_path, "w", encoding="utf-8", newline="") as f:
					f.write(req.content)
			except PermissionError:
				raise HTTPException(status_code=403, detail="file is not writable") from None
			except IsADirectoryError:
				raise HTTPException(status_code=400, detail="path is a directory") from None

		await asyncio.to_thread(save)
		return {"path": full_path}

	@app.get("/sessions/{sid}/stream")
	async def stream(sid: str, since: int = 0, follow: bool = False):
		session = _get(sid)
		body = _sse_follow_stream(session, since) if follow else _sse_stream(session, since)
		return StreamingResponse(
			body,
			media_type="text/event-stream",
			headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
		)

	if webui_dir:
		# registered last, so every API route above wins; "/" serves index.html
		app.mount("/", StaticFiles(directory=webui_dir, html=True), name="webui")

	return app


def _normalized_custom_provider_request(
	req: CustomProviderRequest,
) -> tuple[str, str, tuple[str, ...], str | None]:
	base_url = req.base_url.strip().rstrip("/")
	parsed = urlsplit(base_url)
	if parsed.scheme not in ("http", "https") or not parsed.netloc:
		raise HTTPException(status_code=422, detail="Base URL must be an absolute http(s) URL")
	if parsed.username or parsed.password:
		raise HTTPException(status_code=422, detail="Base URL must not contain credentials")
	models = tuple(dict.fromkeys(m.strip() for m in req.models if m.strip()))
	if not models:
		raise HTTPException(status_code=422, detail="Add at least one model id")
	# the prefix is what routes a model back to this endpoint later
	if any("/" not in m for m in models):
		raise HTTPException(
			status_code=422,
			detail="Model ids need a provider prefix, for example ollama/llama3.2",
		)
	name = req.name.strip()
	if not name:
		raise HTTPException(status_code=422, detail="Name must not be empty")
	return name, base_url, models, (req.api_key or "").strip() or None


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


# follow-mode keepalive cadence; a module global so tests can shrink it
KEEPALIVE_SECONDS = 15.0


async def _sse_follow_stream(session: Session, since: int) -> AsyncIterator[bytes]:
	"""Follow mode: never close at a run boundary. The subscription stays attached
	between runs and an SSE comment goes out whenever the feed is quiet, so proxies
	and dead-peer detection keep working while the session idles."""
	since = min(since, session.log.latest_seq)
	events = session.events(since)
	pending = asyncio.ensure_future(anext(events))
	try:
		while True:
			done, _ = await asyncio.wait({pending}, timeout=KEEPALIVE_SECONDS)
			if not done:
				yield b": keepalive\n\n"
				continue
			try:
				event = pending.result()
			except StopAsyncIteration:
				return
			yield _sse(event.model_dump(exclude_none=True))
			pending = asyncio.ensure_future(anext(events))
	finally:
		pending.cancel()
		with contextlib.suppress(asyncio.CancelledError):
			await pending
		await events.aclose()


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


_HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _read_text_file(full_path: str, *, strip_bom: bool = False) -> str:
	"""Workspace file bytes as text, with the viewer's caps mapped to HTTP errors."""
	if not os.path.isfile(full_path):
		raise HTTPException(status_code=404, detail="file not found")
	if os.path.getsize(full_path) > MAX_FILE_VIEW_BYTES:
		raise HTTPException(status_code=413, detail="file too large to display")
	try:
		with open(full_path, "rb") as f:
			data = f.read()
	except PermissionError:
		raise HTTPException(status_code=403, detail="file is not readable") from None
	try:
		text = data.decode("utf-8")
	except UnicodeDecodeError:
		raise HTTPException(status_code=415, detail="not a text file") from None
	# BOM-stripped callers diff line one cleanly (the edit tool records BOM-less diffs)
	return text.removeprefix("\ufeff") if strip_bom else text


def _list_directory(full_path: str) -> list[dict]:
	"""One directory level for the file explorer, errors mapped to HTTP."""
	try:
		with os.scandir(full_path) as it:
			entries = [{"name": e.name, "type": "dir" if e.is_dir() else "file"} for e in it]
	except FileNotFoundError:
		raise HTTPException(status_code=404, detail="directory not found") from None
	except NotADirectoryError:
		raise HTTPException(status_code=400, detail="not a directory") from None
	except PermissionError:
		raise HTTPException(status_code=403, detail="directory is not readable") from None
	entries.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))
	return entries


def _search_tree(root: str, needle: str) -> tuple[list[str], bool]:
	"""File-name matches under root; hidden and dependency directories are pruned."""
	matches: list[str] = []
	scanned = 0
	for dirpath, dirnames, filenames in os.walk(root):
		# directories count too, so file-sparse deep trees still hit the cap
		scanned += 1
		if scanned >= MAX_SEARCH_SCAN:
			return matches, True
		dirnames[:] = sorted(
			(d for d in dirnames if not d.startswith(".") and d not in SEARCH_SKIP_DIRS),
			key=str.lower,
		)
		for name in sorted(filenames, key=str.lower):
			scanned += 1
			if needle in name.lower():
				matches.append(os.path.relpath(os.path.join(dirpath, name), root))
				if len(matches) >= MAX_SEARCH_RESULTS:
					return matches, True
			if scanned >= MAX_SEARCH_SCAN:
				return matches, True
	return matches, False


def _git_changes(cwd: str, allowed_roots: tuple[str, ...]) -> dict:
	"""Working-tree changes vs HEAD (staged, unstaged, and untracked), whole repo.
	`root` is None outside a repository; files outside the allowed roots are dropped."""
	top = _git_output(cwd, "rev-parse", "--show-toplevel")
	if top is None:
		return {"root": None, "files": []}
	root = top.decode("utf-8", "replace").strip()
	counts: dict[str, tuple[int, int]] = {}
	# no HEAD yet (fresh repo): every file counts like an untracked one below
	if _git_output(root, "rev-parse", "--verify", "--quiet", "HEAD") is not None:
		numstat = _git_output(root, "diff", "--numstat", "--no-renames", "-z", "HEAD") or b""
		for record in numstat.decode("utf-8", "replace").split("\0"):
			fields = record.split("\t")
			if len(fields) != 3:
				continue
			added, removed, rel = fields
			counts[rel] = (
				int(added) if added.isdigit() else 0,  # "-" marks a binary file
				int(removed) if removed.isdigit() else 0,
			)
	status = _git_output(root, "status", "--porcelain", "--no-renames", "--untracked-files=all", "-z") or b""
	files = []
	seen: set[str] = set()
	for record in status.decode("utf-8", "replace").split("\0"):
		if len(record) < 4:
			continue
		rel = record[3:]
		# an index/worktree split (e.g. `git rm --cached`) lists one path twice
		if rel in seen:
			continue
		seen.add(rel)
		full_path = os.path.join(root, rel)
		if allowed_roots and not is_path_allowed(canonical_path(full_path), allowed_roots):
			continue
		added, removed = counts[rel] if rel in counts else (_count_lines(full_path), 0)
		files.append({"path": full_path, "added": added, "removed": removed})
	files.sort(key=lambda f: f["path"])
	return {"root": root, "files": files}


def _git_head_text(root: str, rel: str) -> str:
	"""The file's HEAD content; empty when git has no blob for it (untracked, new repo)."""
	blob = _git_output(root, "show", f"HEAD:{rel}")
	if blob is None:
		return ""
	if len(blob) > MAX_FILE_VIEW_BYTES:
		raise HTTPException(status_code=413, detail="file too large to display")
	try:
		return blob.decode("utf-8")
	except UnicodeDecodeError:
		raise HTTPException(status_code=415, detail="not a text file") from None


def _count_lines(full_path: str) -> int:
	"""Line count of an untracked text file, 0 for anything unreadable/binary/huge."""
	try:
		if os.path.getsize(full_path) > MAX_FILE_VIEW_BYTES:
			return 0
		with open(full_path, "rb") as f:
			data = f.read()
	except OSError:
		return 0
	if b"\0" in data:
		return 0
	return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def _git_output(cwd: str, *args: str) -> bytes | None:
	try:
		completed = subprocess.run(["git", "-C", cwd, *args], capture_output=True)
	except OSError:
		return None
	return completed.stdout if completed.returncode == 0 else None


def _file_change_results(rows: list[dict], full_path: str) -> list[dict]:
	"""Successful edit/write results for one file, in log order."""
	results = []
	for row in rows:
		if row.get("type") != "tool_result" or row.get("name") not in ("edit", "write"):
			continue
		if row.get("is_error") or (row.get("details") or {}).get("path") != full_path:
			continue
		content = row.get("content") or ""
		if content.startswith("{"):  # an approval decision marker, not a real result
			with contextlib.suppress(ValueError):
				if json.loads(content).get("status") in ("denied", "cancelled", "redirect"):
					continue
		results.append(row)
	return results


def _reconstruct_original(modified: str, results: list[dict]) -> str:
	"""The file as it was before the session's changes, by reverse-applying the
	recorded edit diffs newest-first. A write marks the file as created by the
	session, so its original is empty."""
	text = to_lf(modified)
	for result in reversed(results):
		if result.get("name") == "write":
			return ""
		diff = (result.get("details") or {}).get("diff") or ""
		if diff:
			text = _reverse_unified_diff(diff, text)
	return text


def _reverse_unified_diff(diff: str, text: str) -> str:
	"""Undo one recorded unified diff (LF, keepends) against `text`, best-effort:
	hunks whose after-side no longer matches (the file changed since) are left
	as they are, so the caller still gets a usable original for the rest."""
	lines = text.splitlines(keepends=True)
	out: list[str] = []
	pos = 0
	dl = diff.splitlines(keepends=True)
	i = 0
	while i < len(dl) and not dl[i].startswith("@@"):
		i += 1
	while i < len(dl):
		m = _HUNK_RE.match(dl[i])
		if not m:
			break  # malformed: keep the rest of the file untouched
		new_len = int(m.group(2)) if m.group(2) is not None else 1
		new_start = int(m.group(1)) - (1 if new_len else 0)
		i += 1
		before: list[str] = []
		after: list[str] = []
		while i < len(dl) and not dl[i].startswith("@@"):
			tag, body = dl[i][:1], dl[i][1:]
			if tag == " ":
				before.append(body)
				after.append(body)
			elif tag == "-":
				before.append(body)
			elif tag == "+":
				after.append(body)
			i += 1
		if new_start < pos or new_start + new_len > len(lines):
			continue  # out of bounds for the current file: skip the hunk
		region = lines[new_start : new_start + new_len]
		out.extend(lines[pos:new_start])
		out.extend(before if region == after else region)
		pos = new_start + new_len
	out.extend(lines[pos:])
	return "".join(out)
