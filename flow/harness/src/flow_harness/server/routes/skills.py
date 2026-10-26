"""Skill file management for the settings UI: list, read, write, and delete the
`<name>/SKILL.md` files under the global and project skill roots. Off with the
`skills_api` policy switch."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from flow_harness.path_policy import absolute_path, canonical_path, is_path_allowed
from flow_harness.server.policy import ServerPolicy, gate
from flow_harness.server.utils.workspace import read_text_file, save_text_file
from flow_harness.session.skills import (
	MAX_SKILL_BYTES,
	SkillError,
	list_skill_files,
	load_skill,
	valid_skill_name,
	validate_skill_text,
)
from flow_harness.session.store import SessionStore


class SkillWriteRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	cwd: str | None = None
	path: str = Field(min_length=1)
	content: str


def create_skills_router(
	resolve_store: Callable[[Request], SessionStore], *, policy: ServerPolicy | None = None
) -> APIRouter:
	policy = policy or ServerPolicy()
	router = APIRouter(dependencies=gate(policy.skills_api))

	@router.get("/skills")
	async def list_skills(request: Request, cwd: str | None = None):
		roots = resolve_store(request).skill_roots(cwd)

		def inventory() -> dict:
			rows, truncated = [], []
			for scope, root in roots.items():
				paths, cut = list_skill_files(root)
				if cut:
					truncated.append(scope)
				for path in paths:
					row = {
						"scope": scope,
						"path": path,
						"name": os.path.basename(os.path.dirname(path)),
						"description": None,
						"error": None,
					}
					try:
						row["description"] = load_skill(path).description
					except SkillError as error:
						row["error"] = str(error)
					rows.append(row)
			return {"roots": roots, "skills": rows, "truncated": truncated}

		return await asyncio.to_thread(inventory)

	@router.get("/skills/file")
	async def read_skill(request: Request, path: str, cwd: str | None = None):
		full = _validate_skill_path(resolve_store(request), cwd, path)
		return {"path": full, "content": await asyncio.to_thread(read_text_file, full)}

	@router.put("/skills/file")
	async def write_skill(request: Request, req: SkillWriteRequest):
		full = _validate_skill_path(resolve_store(request), req.cwd, req.path)
		if len(req.content.encode()) > MAX_SKILL_BYTES:
			raise HTTPException(status_code=413, detail=f"skill exceeds {MAX_SKILL_BYTES // 1024} KB")
		validate_skill_text(req.content, os.path.basename(os.path.dirname(full)))  # SkillError -> 400
		await asyncio.to_thread(save_text_file, full, req.content)
		return {"path": full}

	@router.delete("/skills/file")
	async def delete_skill(request: Request, path: str, cwd: str | None = None):
		full = _validate_skill_path(resolve_store(request), cwd, path)

		def remove() -> None:
			try:
				os.remove(full)
			except FileNotFoundError:
				raise HTTPException(status_code=404, detail="skill not found") from None
			try:
				os.rmdir(os.path.dirname(full))  # only an empty skill directory goes with it
			except OSError:
				pass

		await asyncio.to_thread(remove)
		return {"status": "deleted"}

	def _validate_skill_path(store: SessionStore, cwd: str | None, path: str) -> str:
		"""`path` must address `<root>/<name>/SKILL.md` under a managed root, else 400.
		The skill directory may be a symlink, as discovery follows them; under a
		filesystem fence its target must also sit under a root or an allowed root."""
		roots = tuple(canonical_path(root) for root in store.skill_roots(cwd).values())
		full = absolute_path(path)
		directory = os.path.dirname(full)
		if (
			os.path.basename(full) != "SKILL.md"
			or not valid_skill_name(os.path.basename(directory))
			or canonical_path(os.path.dirname(directory)) not in roots
		):
			raise HTTPException(status_code=400, detail="path must be <skill root>/<name>/SKILL.md")
		if store.allowed_roots and not is_path_allowed(canonical_path(full), (*roots, *store.allowed_roots)):
			raise HTTPException(status_code=400, detail="skill path is outside allowed roots")
		return full

	return router
