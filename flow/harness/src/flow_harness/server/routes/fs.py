"""cwd-keyed filesystem routes: the folder picker, the explorer, and git views.
These work before the first message creates a session; diffs and saves that
belong to a session stay on the session routes."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from flow_harness.path_policy import canonical_path
from flow_harness.server.policy import ServerPolicy, gate
from flow_harness.server.utils.fspick import PickerUnavailable, pick_folder
from flow_harness.server.utils.git import git_branch, git_changes, git_head_text, git_output
from flow_harness.server.utils.workspace import (
	MAX_FILE_VIEW_BYTES,
	list_directory,
	read_text_file,
	resolve_allowed_path,
	save_text_file,
	search_tree,
)
from flow_harness.session.store import SessionStore


class FsWriteFileRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	cwd: str = Field(min_length=1)
	path: str = Field(min_length=1)
	content: str


def create_fs_router(
	resolve_store: Callable[[Request], SessionStore], *, policy: ServerPolicy | None = None
) -> APIRouter:
	"""`resolve_store` picks the store a request acts on — the authenticated site's
	partition in multi-tenant mode, else the daemon's root store."""
	policy = policy or ServerPolicy()
	router = APIRouter(dependencies=gate(policy.fs_api))

	# POST, not GET: a GET could be fired by a hostile page's <img src=…>.
	# One at a time — each pick pins a thread until the user answers.
	pick_lock = asyncio.Lock()

	@router.post("/fs/pick")
	async def fs_pick():
		async with pick_lock:
			try:
				path = await asyncio.to_thread(pick_folder)
			except PickerUnavailable as e:
				raise HTTPException(status_code=501, detail=str(e)) from None
		return {"path": path}

	def _resolve_allowed_path(store: SessionStore, cwd: str, path: str) -> str:
		if not os.path.isabs(cwd):
			raise HTTPException(status_code=400, detail="cwd must be an absolute path")
		return resolve_allowed_path(cwd, path, store.allowed_roots)

	@router.get("/fs/files")
	async def list_files(request: Request, cwd: str, path: str = ""):
		full_path = _resolve_allowed_path(resolve_store(request), cwd, path or ".")
		return {"path": full_path, "entries": await asyncio.to_thread(list_directory, full_path)}

	@router.get("/fs/files/search")
	async def search_files(request: Request, cwd: str, query: str):
		root = _resolve_allowed_path(resolve_store(request), cwd, ".")
		if not os.path.isdir(root):
			raise HTTPException(status_code=404, detail="directory not found")
		needle = query.strip().lower()
		if not needle:
			return {"path": root, "matches": [], "truncated": False}
		matches, truncated = await asyncio.to_thread(search_tree, root, needle)
		return {"path": root, "matches": matches, "truncated": truncated}

	@router.get("/fs/file")
	async def read_file(request: Request, cwd: str, path: str):
		full_path = _resolve_allowed_path(resolve_store(request), cwd, path)
		return {"path": full_path, "content": await asyncio.to_thread(read_text_file, full_path)}

	@router.put("/fs/file")
	async def write_fs_file(request: Request, req: FsWriteFileRequest):
		"""The cwd-keyed twin of the session save, so edits work before a session exists."""
		full_path = _resolve_allowed_path(resolve_store(request), req.cwd, req.path)
		if len(req.content.encode()) > MAX_FILE_VIEW_BYTES:
			raise HTTPException(status_code=413, detail="file too large to save")
		await asyncio.to_thread(save_text_file, full_path, req.content)
		return {"path": full_path}

	@router.get("/fs/git/changes")
	async def fs_git_changes(request: Request, cwd: str):
		"""The repository's uncommitted files with added/removed line counts."""
		store = resolve_store(request)
		root = _resolve_allowed_path(store, cwd, ".")
		if not os.path.isdir(root):
			raise HTTPException(status_code=404, detail="directory not found")
		return await asyncio.to_thread(git_changes, root, store.allowed_roots)

	@router.get("/fs/git/branch")
	async def fs_git_branch(request: Request, cwd: str):
		"""The branch checked out in the folder, and whether it is a linked worktree."""
		root = _resolve_allowed_path(resolve_store(request), cwd, ".")
		if not os.path.isdir(root):
			raise HTTPException(status_code=404, detail="directory not found")
		return await asyncio.to_thread(git_branch, root)

	@router.get("/fs/git/file/diff")
	async def git_file_diff(request: Request, cwd: str, path: str):
		"""Both sides of one file's uncommitted changes: HEAD and the working tree."""
		store = resolve_store(request)
		base = _resolve_allowed_path(store, cwd, ".")
		full_path = _resolve_allowed_path(store, cwd, path)

		def compute() -> dict:
			top = git_output(base, "rev-parse", "--show-toplevel")
			if top is None:
				raise HTTPException(status_code=400, detail="not a git repository")
			root = top.decode("utf-8", "replace").strip()
			rel = os.path.relpath(canonical_path(full_path), root)
			if rel.startswith(".."):
				raise HTTPException(status_code=400, detail="file is outside the repository")
			original = git_head_text(root, rel.replace(os.sep, "/"))
			modified = read_text_file(full_path) if os.path.isfile(full_path) else ""
			return {"path": full_path, "original": original, "modified": modified}

		return await asyncio.to_thread(compute)

	return router
